import time
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from detector import ScreenDetector, centered_region, in_region, local_to_global
from main import run


def test_region_coordinates():
    region = centered_region({'left': 0, 'top': 0, 'width': 1920, 'height': 1080})
    assert region == {'left': 380, 'top': 215, 'width': 1160, 'height': 650}
    assert local_to_global((10, 20), region) == (390, 235)
    assert in_region((380, 215), region)
    assert not in_region((1540, 865), region)
    assert not in_region((379, 215), region)
    assert centered_region({'left': -1920, 'top': 50, 'width': 1920, 'height': 1080})['left'] == -1540
    with pytest.raises(ValueError):
        centered_region({'left': 0, 'top': 0, 'width': 800, 'height': 600})


@pytest.fixture(scope='module')
def detector():
    return ScreenDetector('targets/tickets.png')


def scene(angle, seed, with_target=True):
    rng = np.random.default_rng(seed)
    base = rng.integers(0, 256, (82, 145, 3), dtype=np.uint8)
    image = cv2.resize(base, (1160, 650), interpolation=cv2.INTER_LINEAR)
    for i in range(20):
        x, y = rng.integers(0, 1160), rng.integers(0, 650)
        cv2.circle(image, (int(x), int(y)), int(rng.integers(5, 80)), tuple(int(v) for v in rng.integers(0, 255, 3)), 2)
    raw = cv2.imread('targets/tickets.png', cv2.IMREAD_UNCHANGED)
    h, w = raw.shape[:2]
    mat = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1)
    nw = int(np.ceil(abs(mat[0, 0]) * w + abs(mat[0, 1]) * h))
    nh = int(np.ceil(abs(mat[0, 1]) * w + abs(mat[0, 0]) * h))
    mat[0, 2] += (nw - w) / 2; mat[1, 2] += (nh - h) / 2
    target = cv2.warpAffine(raw, mat, (nw, nh))
    x = int(rng.integers(0, 1160 - nw)); y = int(rng.integers(0, 650 - nh))
    if with_target:
        alpha = target[:, :, 3:4].astype(np.float32) / 255
        image[y:y+nh, x:x+nw] = (target[:, :, :3] * alpha + image[y:y+nh, x:x+nw] * (1-alpha)).astype(np.uint8)
        image = cv2.imdecode(cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 65])[1], cv2.IMREAD_COLOR)
    return image, (x + nw // 2, y + nh // 2)


def test_video_scenes_rotations_and_negative(detector):
    elapsed = []
    for angle in range(0, 360, 30):
        frame, center = scene(angle + 7, angle)
        start = time.perf_counter()
        result = detector.find_multirot(frame)
        elapsed.append(time.perf_counter() - start)
        assert result.found, (angle, result.confidence)
        assert np.linalg.norm(np.array(result.center) - center) < 5
    for seed in range(4):
        frame, _ = scene(0, seed, False)
        result = detector.find_multirot(frame)
        assert not result.found, result.confidence
    print(f'\nSynthetic detection seconds median={np.median(elapsed):.3f} max={max(elapsed):.3f}')
    assert max(elapsed) < 1.8


def test_duplicate_and_boundary():
    from detector import MatchResult
    region = {'left': 380, 'top': 215, 'width': 1160, 'height': 650}
    results = [MatchResult(True, .9, (500, 300), region=region)] * 3 + [MatchResult(True, .9, (1540, 300), region=region)]
    with patch('main.ScreenDetector') as detector_cls, patch('main.MouseController') as controller_cls:
        detector_cls.return_value.find.side_effect = results + [KeyboardInterrupt()]
        run('target', click=True, interval=0)
        assert controller_cls.return_value.move_to.call_count == 1
        assert controller_cls.return_value.click.call_count == 1


def test_capture_region_and_global_conversion(detector):
    from detector import MatchResult
    region = {'left': 380, 'top': 215, 'width': 1160, 'height': 650}
    with patch.object(detector, 'capture_screenshot', return_value=(np.zeros((650, 1160, 3), np.uint8), region)), \
         patch.object(detector, 'find_multirot', return_value=MatchResult(True, .9, (0, 0))):
        result = detector.find()
        assert result.center == (380, 215)
        assert result.found
    with patch.object(detector, 'capture_screenshot', return_value=(np.zeros((650, 1160, 3), np.uint8), region)), \
         patch.object(detector, 'find_multirot', return_value=MatchResult(True, .9, (1160, 20))):
        assert not detector.find().found


def test_mss_receives_centered_region(detector):
    from unittest.mock import MagicMock
    mss_instance = MagicMock()
    mss_instance.monitors = [{}, {'left': 0, 'top': 0, 'width': 1920, 'height': 1080}]
    mss_instance.grab.return_value = np.zeros((650, 1160, 4), dtype=np.uint8)
    with patch('detector.mss.mss') as factory:
        factory.return_value.__enter__.return_value = mss_instance
        _, region = detector.capture_screenshot()
    mss_instance.grab.assert_called_once_with(region)
    assert region['left'] == 380 and region['top'] == 215


def test_manual_capture_never_moves_or_clicks(tmp_path):
    from detector import MatchResult
    with patch('main.ScreenDetector') as detector_cls, patch('main.MouseController') as controller_cls:
        det = detector_cls.return_value
        det.find.return_value = MatchResult(True, .9, (500, 300), region={'left': 380, 'top': 215, 'width': 1160, 'height': 650})
        det.last_screenshot = np.zeros((650, 1160, 3), np.uint8)
        run('target', click=True, capture=str(tmp_path / 'frame.png'))
        assert (tmp_path / 'frame.png').exists()
        controller_cls.return_value.move_to.assert_not_called()
        controller_cls.return_value.click.assert_not_called()


def test_target_close_to_region_edges(detector):
    raw = cv2.imread('targets/tickets.png', cv2.IMREAD_UNCHANGED)
    for x, y in [(0, 0), (1160-raw.shape[1], 650-raw.shape[0])]:
        frame, _ = scene(0, 100, False)
        a = raw[:, :, 3:4].astype(np.float32) / 255
        frame[y:y+raw.shape[0], x:x+raw.shape[1]] = (raw[:, :, :3] * a + frame[y:y+raw.shape[0], x:x+raw.shape[1]] * (1-a)).astype(np.uint8)
        result = detector.find_multirot(frame)
        assert result.found, result.confidence
        assert np.linalg.norm(np.array(result.center) - (x+raw.shape[1]//2, y+raw.shape[0]//2)) < 5
