"""Control mouse movement and clicks for detected targets."""
import math
import time

import pyautogui


class MouseController:
    """Move and click the mouse while respecting the selected operating mode."""
    def __init__(self, duration: float = 0.20, move_only: bool = False, dry_run: bool = False):
        """Configure movement timing, operating mode, and the mouse failsafe."""
        self.duration = duration
        self.move_only = move_only
        self.dry_run = dry_run
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.0

    def ease_in_out(self, t: float) -> float:
        """Calculate smooth cursor movement progress."""
        if t < 0.5:
            return 2.0 * t * t
        else:
            return -1.0 + (4.0 - 2.0 * t) * t

    def move_to(self, target):
        """Move the pointer to a target unless dry-run mode is active."""
        if self.dry_run:
            return
        pyautogui.moveTo(target[0], target[1], duration=self.duration,
                         tween=self.ease_in_out)

    def click(self, target=None):
        """Optionally move to a target and click unless the selected mode prevents it."""
        if self.dry_run:
            return
        if target is not None:
            self.move_to(target)
        if not self.move_only:
            pyautogui.click()
