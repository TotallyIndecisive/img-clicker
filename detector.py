"""Capture screen regions and locate rotated reference images."""
import math
import time
from dataclasses import dataclass
from typing import Optional

import cv2
import mss
import numpy as np


@dataclass
class MatchResult:
    """Store the detection result, coordinates, and timing information."""
    found: bool
    confidence: float = 0.0
    center: Optional[tuple] = None
    bbox: Optional[tuple] = None
    latency_ms: float = 0.0
    angle: float = 0.0
    method: str = ''
    capture_ms: float = 0.0
    detection_ms: float = 0.0
    verification_ms: float = 0.0
    region: Optional[dict] = None
    local_center: Optional[tuple] = None


def centered_region(monitor, width=1160, height=650):
    """Calculate a centered capture region within the selected monitor."""
    if width <= 0 or height <= 0 or width > monitor['width'] or height > monitor['height']:
        raise ValueError('Detection region must fit within the selected display')
    return {'left': monitor['left'] + (monitor['width'] - width) // 2,
            'top': monitor['top'] + (monitor['height'] - height) // 2,
            'width': width, 'height': height}


def local_to_global(point, region):
    """Convert capture-region coordinates to desktop coordinates."""
    return point[0] + region['left'], point[1] + region['top']


def in_region(point, region):
    """Check whether a point lies inside the capture region."""
    return (region['left'] <= point[0] < region['left'] + region['width'] and
            region['top'] <= point[1] < region['top'] + region['height'])


class RotationInvariantDetector:
    """Find a reference image in a screen capture across multiple rotations."""
    def __init__(self, template_path: str, threshold: float = 0.55, use_orb: bool = True,
                 use_multiscale: bool = True, region_width=1160, region_height=650):
        """Load and validate the reference image and prepare rotation candidates."""
        self.template_path, self.threshold = template_path, threshold
        raw = cv2.imread(template_path, cv2.IMREAD_UNCHANGED)
        if raw is None:
            raise ValueError(f'Could not load template image: {template_path}')
        if raw.ndim == 2:
            raw = cv2.cvtColor(raw, cv2.COLOR_GRAY2BGR)
        if raw.dtype == np.uint16:
            raw = (raw / 257).astype(np.uint8)
        if raw.dtype != np.uint8 or raw.shape[2] not in (3, 4):
            raise ValueError('Unsupported image format')
        original_h, original_w = raw.shape[:2]
        if max(original_h, original_w) > 600:
            raise ValueError(f'Target image is {original_w}×{original_h}; maximum size is 600×600 pixels')
        alpha = raw[:, :, 3] if raw.shape[2] == 4 else np.full(raw.shape[:2], 255, np.uint8)
        if not np.any(alpha >= 240):
            raise ValueError('Target image has no sufficiently opaque pixels')
        x, y, w, h = cv2.boundingRect((alpha > 0).astype(np.uint8))
        self.template = raw[y:y+h, x:x+w, :3]
        self.alpha = alpha[y:y+h, x:x+w]
        self.h, self.w = self.template.shape[:2]
        self.template_h, self.template_w = self.h, self.w
        if min(self.h, self.w) < 1 or max(self.h, self.w) > 4096:
            raise ValueError('Template image size out of range')
        gray = cv2.cvtColor(self.template, cv2.COLOR_BGR2GRAY)
        if np.count_nonzero(self.alpha > 200) < 16 or gray[self.alpha > 200].var() < 0.01:
            raise ValueError('Template has too low variance or insufficient opaque pixels')
        self.region_width, self.region_height = region_width, region_height
        self.use_orb, self.use_multiscale = use_orb, use_multiscale
        self.scale = 0.4
        self.coarse_color = gray[self.alpha > 200].std() < 10
        self.orb = cv2.ORB_create(nfeatures=1500)
        self.kp_t, self.des_t = self.orb.detectAndCompute(gray, self.alpha)
        self.bf = cv2.BFMatcher(cv2.NORM_HAMMING)
        # Small angular differences move large images by many pixels. Search
        # them more finely so candidates are not lost before verification.
        self.angle_step = 3 if max(self.h, self.w) >= 500 else 15
        self.rotated_templates = [(angle, *self._rotated(angle, self.scale, color=self.coarse_color))
                                  for angle in range(0, 360, self.angle_step)]

    def _rotated(self, angle, scale=1.0, color=False):
        """Rotate and scale the reference image and its transparency mask."""
        h, w = self.h, self.w
        matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, scale)
        nw = max(1, int(math.ceil((abs(matrix[0, 0]) * w + abs(matrix[0, 1]) * h))))
        nh = max(1, int(math.ceil((abs(matrix[0, 1]) * w + abs(matrix[0, 0]) * h))))
        matrix[0, 2] += (nw - w) / 2
        matrix[1, 2] += (nh - h) / 2
        image = cv2.warpAffine(self.template, matrix, (nw, nh), flags=cv2.INTER_LINEAR)
        alpha = cv2.warpAffine(self.alpha, matrix, (nw, nh), flags=cv2.INTER_LINEAR)
        mask = (alpha >= 240).astype(np.uint8) * 255
        return (image if color else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)), mask

    def _rotate_image(self, image, angle):
        """Rotate an image while expanding its bounding rectangle."""
        h, w = image.shape[:2]
        matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1)
        nw = int(math.ceil(h * abs(matrix[0, 1]) + w * abs(matrix[0, 0])))
        nh = int(math.ceil(h * abs(matrix[0, 0]) + w * abs(matrix[0, 1])))
        matrix[0, 2] += (nw - w) / 2
        matrix[1, 2] += (nh - h) / 2
        return cv2.warpAffine(image, matrix, (nw, nh))

    def capture_screenshot(self, monitor_number=1):
        """Capture the centered region of the selected monitor."""
        with mss.mss() as sct:
            if monitor_number < 0 or monitor_number >= len(sct.monitors):
                raise ValueError('Invalid monitor number')
            region = centered_region(sct.monitors[monitor_number], self.region_width, self.region_height)
            image = np.asarray(sct.grab(region))
            return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR), region

    def find_orb(self, screenshot):
        # ORB proposes a location; its inlier ratio alone is not a match confidence.
        """Propose a target location using ORB feature matches."""
        if self.des_t is None:
            return MatchResult(False, method='orb')
        gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        kp, des = self.orb.detectAndCompute(gray, None)
        if des is None:
            return MatchResult(False, method='orb')
        pairs = self.bf.knnMatch(self.des_t, des, k=2)
        good = [p[0] for p in pairs if len(p) == 2 and p[0].distance < .75 * p[1].distance]
        if len(good) < 8:
            return MatchResult(False, method='orb')
        src = np.float32([self.kp_t[m.queryIdx].pt for m in good])
        dst = np.float32([kp[m.trainIdx].pt for m in good])
        matrix, mask = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=3)
        if matrix is None or mask.sum() < 8 or not .9 <= np.hypot(matrix[0, 0], matrix[0, 1]) <= 1.1:
            return MatchResult(False, method='orb')
        center = matrix @ np.array([self.w / 2, self.h / 2, 1])
        return MatchResult(True, float(mask.mean()), tuple(np.rint(center).astype(int)), method='orb')

    @staticmethod
    def _match(screen, template, mask):
        """Measure the best masked template match within an image."""
        if template.shape[0] > screen.shape[0] or template.shape[1] > screen.shape[1]:
            return -1.0, (0, 0)
        response = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED, mask=mask)
        response = np.nan_to_num(response, nan=-1, posinf=-1, neginf=-1)
        _, value, _, loc = cv2.minMaxLoc(response)
        return value, loc

    def find_multirot(self, screenshot):
        """Search coarse rotations and verify promising matches at full resolution."""
        start = time.perf_counter()
        gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        source = screenshot[:, :, :3] if self.coarse_color and screenshot.ndim == 3 else gray
        small = cv2.resize(source, None, fx=self.scale, fy=self.scale, interpolation=cv2.INTER_AREA)
        candidates = []
        for angle, template, mask in self.rotated_templates:
            value, loc = self._match(small, template, mask)
            candidates.append((value, angle, loc, template.shape))
        candidates.sort(reverse=True, key=lambda item: item[0])
        detection_ms = (time.perf_counter() - start) * 1000
        best = MatchResult(False, method='masked-template', detection_ms=detection_ms)
        verify_start = time.perf_counter()
        # Refine a few distinct hypotheses locally, avoiding a full-resolution rotation sweep.
        selected = []
        for value, angle, loc, shape in candidates:
            center = ((loc[0] + shape[1] / 2) / self.scale, (loc[1] + shape[0] / 2) / self.scale)
            if value < max(.15, self.threshold * .45):
                break
            if any(abs(center[0] - x) < 20 and abs(center[1] - y) < 20 and
                   abs((angle - a + 180) % 360 - 180) < 25 for x, y, a in selected):
                continue
            selected.append((*center, angle))
            if len(selected) >= 4:
                break
        for cx, cy, angle in selected:
            radius = 2 if self.angle_step == 3 else 8
            for fine_angle in range(angle - radius, angle + radius + 1, 2):
                template, mask = self._rotated(fine_angle % 360)
                h, w = template.shape
                x0 = max(0, int(cx - w / 2 - 12)); y0 = max(0, int(cy - h / 2 - 12))
                x1 = min(gray.shape[1], int(cx + w / 2 + 13)); y1 = min(gray.shape[0], int(cy + h / 2 + 13))
                value, loc = self._match(gray[y0:y1, x0:x1], template, mask)
                if value > best.confidence:
                    x, y = x0 + loc[0], y0 + loc[1]
                    # The geometric center can be transparent (for example, a ring).
                    # Click the nearest opaque reference pixel instead.
                    distance = cv2.distanceTransform(mask, cv2.DIST_L2, 3)
                    # Stay away from edges so small angle and position errors do
                    # not turn an opaque reference pixel into a transparent click.
                    safe_distance = min(8.0, float(distance.max()) * .5)
                    yy, xx = np.nonzero(distance >= safe_distance)
                    nearest = np.argmin((xx - w / 2) ** 2 + (yy - h / 2) ** 2)
                    px, py = int(xx[nearest]), int(yy[nearest])
                    if screenshot.ndim == 3 and screenshot.shape[2] >= 3:
                        color_template, _ = self._rotated(fine_angle % 360, color=True)
                        ya, yb = max(0, py-2), min(h, py+3)
                        xa, xb = max(0, px-2), min(w, px+3)
                        patch_mask = mask[ya:yb, xa:xb] > 0
                        expected = color_template[ya:yb, xa:xb][patch_mask]
                        actual = screenshot[y+ya:y+yb, x+xa:x+xb, :3][patch_mask]
                        if np.mean(np.abs(expected.astype(np.float32) - actual.astype(np.float32))) > 45:
                            continue
                    best = MatchResult(value >= self.threshold, value, (x + px, y + py),
                                       (x, y, w, h), angle=fine_angle % 360,
                                       method='masked-template', detection_ms=detection_ms)
                    # A strong verified match does not need the remaining angles.
                    if best.found and best.confidence >= max(self.threshold, .92):
                        best.verification_ms = (time.perf_counter() - verify_start) * 1000
                        return best
        best.verification_ms = (time.perf_counter() - verify_start) * 1000
        return best

    def find(self, monitor_number=1):
        """Capture the screen, detect the target, and return desktop coordinates."""
        start = time.perf_counter()
        screenshot, region = self.capture_screenshot(monitor_number)
        capture_ms = (time.perf_counter() - start) * 1000
        result = self.find_multirot(screenshot) if self.use_multiscale else MatchResult(False)
        result.capture_ms = capture_ms
        result.region = region
        result.local_center = result.center
        if result.center is not None:
            result.center = local_to_global(result.center, region)
            result.found = result.found and in_region(result.center, region)
        result.latency_ms = (time.perf_counter() - start) * 1000
        self.last_screenshot = screenshot
        return result


ScreenDetector = RotationInvariantDetector
