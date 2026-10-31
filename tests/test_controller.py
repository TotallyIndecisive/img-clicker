from unittest.mock import patch

from controller import MouseController


def test_dry_run_no_movement():
    c = MouseController(duration=0.1, move_only=False, dry_run=True)
    with patch('pyautogui.moveTo') as m, patch('pyautogui.click') as cl:
        c.move_to((100, 100))
        c.click((200, 200))
        assert m.call_count == 0
        assert cl.call_count == 0


def test_move_only_no_click():
    c = MouseController(duration=0.1, move_only=True, dry_run=True)
    with patch('pyautogui.moveTo') as m, patch('pyautogui.click') as cl:
        c.click((50, 50))
        assert m.call_count == 0  # dry run
        assert cl.call_count == 0
