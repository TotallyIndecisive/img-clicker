from pathlib import Path

import cv2
import numpy as np
import pytest

from detector import ScreenDetector
from main import find_target


def test_target_selection(tmp_path):
    with pytest.raises(ValueError, match='found 0'):
        find_target(tmp_path)
    (tmp_path / '.gitkeep').touch()
    first = tmp_path / 'lotus.PNG'
    first.touch()
    assert find_target(tmp_path) == first
    (tmp_path / 'other.jpg').touch()
    with pytest.raises(ValueError, match='found 2'):
        find_target(tmp_path)
    with pytest.raises(ValueError, match='does not exist'):
        find_target(tmp_path / 'missing')


@pytest.mark.parametrize('shape', [(601, 100), (100, 601), (601, 601)])
def test_reject_oversize_target(tmp_path, shape):
    path = tmp_path / 'big.png'
    cv2.imwrite(str(path), np.random.default_rng(12).integers(0, 256, (*shape, 3), dtype=np.uint8))
    with pytest.raises(ValueError, match='600×600'):
        ScreenDetector(str(path))


@pytest.mark.parametrize('extension', ['png', 'jpg', 'bmp', 'webp'])
def test_common_image_formats(tmp_path, extension):
    path = tmp_path / ('image.' + extension)
    img = np.random.default_rng(10).integers(0, 255, (100, 120, 3), dtype=np.uint8)
    assert cv2.imwrite(str(path), img)
    det = ScreenDetector(str(path))
    scene = np.full((400, 600, 3), 90, np.uint8)
    scene[100:200, 150:270] = cv2.imread(str(path))
    result = det.find_multirot(scene)
    assert result.found and np.linalg.norm(np.array(result.center) - (210, 150)) <= 2


def test_600_square_and_transparent_center(tmp_path):
    path = tmp_path / 'ring.png'
    image = np.zeros((600, 600, 4), dtype=np.uint8)
    cv2.circle(image, (300, 300), 200, (30, 40, 240, 255), 60)
    cv2.circle(image, (300, 150), 20, (240, 40, 20, 255), -1)
    assert cv2.imwrite(str(path), image)
    detector = ScreenDetector(str(path))
    scene = np.full((650, 1160, 3), 55, np.uint8)
    alpha = image[:, :, 3:4] / 255
    scene[20:620, 100:700] = image[:, :, :3] * alpha + scene[20:620, 100:700] * (1 - alpha)
    result = detector.find_multirot(scene)
    assert result.found, result.confidence
    x, y = result.center
    assert image[y - 20, x - 100, 3] > 200


def test_oversize_transparent_margin_is_still_rejected(tmp_path):
    image = np.zeros((601, 100, 4), np.uint8)
    image[100:120, 10:30] = (0, 255, 0, 255)
    path = tmp_path / 'image.png'
    cv2.imwrite(str(path), image)
    with pytest.raises(ValueError, match='600×600'):
        ScreenDetector(str(path))


def test_maximum_size_textured_image_at_small_rotations(tmp_path):
    rng = np.random.default_rng(42)
    image = cv2.resize(rng.integers(0, 255, (60, 60, 3), dtype=np.uint8), (600, 600))
    path = tmp_path / 'large.png'
    cv2.imwrite(str(path), image)
    detector = ScreenDetector(str(path))
    for angle in (0, 3, 4):
        matrix = cv2.getRotationMatrix2D((300, 300), angle, 1)
        side = int(np.ceil(600 * (abs(matrix[0, 0]) + abs(matrix[0, 1]))))
        matrix[:, 2] += (side - 600) / 2
        rotated = cv2.warpAffine(image, matrix, (side, side))
        mask = cv2.warpAffine(np.full((600, 600), 255, np.uint8), matrix, (side, side))
        scene = np.full((650, 1160, 3), 80, dtype=np.uint8)
        scene[:side, :side][mask > 0] = rotated[mask > 0]
        result = detector.find_multirot(scene)
        assert result.found, (angle, result.confidence)
        assert np.linalg.norm(np.array(result.center) - (side // 2, side // 2)) < 5
