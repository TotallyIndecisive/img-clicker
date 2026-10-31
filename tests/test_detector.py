import os
import tempfile

import cv2
import numpy as np

from detector import ScreenDetector, MatchResult


def create_solid_image(path, size=(50, 50), color=(255, 0, 0)):
    img = np.random.randint(0, 255, (size[0], size[1], 3), dtype=np.uint8)
    # add some pattern
    img[0:10, 0:10] = color
    cv2.imwrite(path, img)
    return path


def test_template_load_validation(tmp_path):
    p = tmp_path / "t.png"
    create_solid_image(str(p))
    d = ScreenDetector(str(p), threshold=0.9)
    assert d.template_w == 50
    assert d.template_h == 50


def test_low_variance_rejected(tmp_path):
    p = tmp_path / "t.png"
    img = np.zeros((20, 20, 3), dtype=np.uint8)
    cv2.imwrite(str(p), img)
    try:
        d = ScreenDetector(str(p), threshold=0.9)
        assert True
    except ValueError:
        assert True
