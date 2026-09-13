"""
Testar rörelsedetektering och sparning utan riktig kamera — körs på Mac.
Använder de befintliga testbilderna i inference/test-images/ istället för picamera2.
"""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from camera_trigger import LORES_SIZE, detect_motion, run

TEST_IMAGES_DIR = Path(__file__).parent.parent / "inference" / "test-images"


def load_gray(filename: str) -> np.ndarray:
    """Laddar en testbild, gråskalar och skalar till samma storlek som lores-strömmen."""
    image = Image.open(TEST_IMAGES_DIR / filename).convert("L").resize(LORES_SIZE)
    return np.array(image)


def load_full(filename: str) -> Image.Image:
    return Image.open(TEST_IMAGES_DIR / filename)


def test_detect_motion_identical_images_is_false():
    gray = load_gray("2a.jpg")
    assert detect_motion(gray, gray) is False


def test_detect_motion_large_change_is_true():
    prev = np.zeros((240, 320), dtype=np.uint8)
    curr = prev.copy()
    curr[:, :] = 255  # hela bilden ändrad — ska alltid räknas som rörelse.
    assert detect_motion(prev, curr) is True


def test_detect_motion_small_change_is_false():
    prev = np.zeros((240, 320), dtype=np.uint8)
    curr = prev.copy()
    curr[:5, :5] = 255  # << 2% av bilden — ska inte räknas som rörelse.
    assert detect_motion(prev, curr) is False


def test_detect_motion_ignores_uniform_brightness_change():
    """En jämn ljusändring (t.ex. moln) ska inte tolkas som rörelse."""
    prev = np.full((240, 320), 100, dtype=np.uint8)
    curr = np.full((240, 320), 110, dtype=np.uint8)  # +10 överallt, under pixel_threshold=25.
    assert detect_motion(prev, curr) is False


def test_first_frame_is_baseline_only(tmp_path):
    frames = [(load_gray("2a.jpg"), load_full("2a.jpg"))]
    run(frames, save_dir=tmp_path)
    assert list(tmp_path.glob("*.jpg")) == []


def test_motion_between_two_images_saves_one_capture(tmp_path):
    frames = [
        (load_gray("2a.jpg"), load_full("2a.jpg")),
        (load_gray("3a.jpg"), load_full("3a.jpg")),
    ]
    run(frames, save_dir=tmp_path)
    assert len(list(tmp_path.glob("*.jpg"))) == 1


def test_static_scene_saves_nothing(tmp_path):
    gray, full = load_gray("2a.jpg"), load_full("2a.jpg")
    frames = [(gray, full)] * 5
    run(frames, save_dir=tmp_path)
    assert list(tmp_path.glob("*.jpg")) == []


def test_cooldown_blocks_repeat_captures(tmp_path):
    a = (load_gray("2a.jpg"), load_full("2a.jpg"))
    b = (load_gray("3a.jpg"), load_full("3a.jpg"))
    frames = [a, b, a, b, a, b]  # växlar fram och tillbaka — utan cooldown blir det flera träffar.
    run(frames, save_dir=tmp_path, cooldown_frames=5)
    assert len(list(tmp_path.glob("*.jpg"))) == 1


def test_on_capture_called_with_saved_path(tmp_path):
    """on_capture ska anropas med sökvägen till den sparade bilden, inte alls vid stillhet."""
    frames = [
        (load_gray("2a.jpg"), load_full("2a.jpg")),
        (load_gray("3a.jpg"), load_full("3a.jpg")),
    ]
    captured_paths = []
    run(frames, save_dir=tmp_path, on_capture=captured_paths.append)

    assert captured_paths == list(tmp_path.glob("*.jpg"))
