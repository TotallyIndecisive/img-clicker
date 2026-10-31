import os
import tempfile

import cv2
import numpy as np

from detector import RotationInvariantDetector


def test_rotation_invariance_synthetic(tmp_path):
    # Create template
    tpath = tmp_path / "t.png"
    template = np.random.randint(0, 255, (60, 80, 3), dtype=np.uint8)
    # add strong features
    template[10:30, 10:30] = (0, 255, 0)
    template[40:50, 60:70] = (255, 0, 0)
    cv2.imwrite(str(tpath), template)
    det = RotationInvariantDetector(str(tpath), threshold=0.8)
    # Create scene with rotated target
    scene = np.random.randint(50, 200, (480, 640, 3), dtype=np.uint8)
    h, w = template.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, 45, 1.0)
    cos = np.abs(M[0, 0]); sin = np.abs(M[0, 1])
    nW = int((h * sin) + (w * cos))
    nH = int((h * cos) + (w * sin))
    M[0, 2] += (nW / 2) - center[0]
    M[1, 2] += (nH / 2) - center[1]
    rotated = cv2.warpAffine(template, M, (nW, nH))
    # Paste at random pos
    y, x = 100, 200
    scene[y:y + nH, x:x + nW] = rotated
    # Test multirot
    res = det.find_multirot(scene)
    assert res.found or res.confidence > 0.5
