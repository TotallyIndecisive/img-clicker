#!/usr/bin/env python3
"""Run the image detection and mouse-control command-line interface."""
import time
from pathlib import Path

import cv2
import pyautogui
import typer

from controller import MouseController
from detector import ScreenDetector, in_region

TARGET_DIR = Path(__file__).resolve().parent / 'targets'
SUPPORTED_IMAGES = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}


def find_target(directory=TARGET_DIR):
    """Select the single supported image in the targets directory."""
    directory = Path(directory)
    if not directory.is_dir():
        raise ValueError(f'Target folder does not exist: {directory}')
    images = sorted(p for p in directory.iterdir()
                    if p.is_file() and p.suffix.lower() in SUPPORTED_IMAGES)
    if len(images) != 1:
        raise ValueError(f'Put exactly one PNG, JPEG, WebP or BMP image in {directory} (found {len(images)}).')
    return images[0]


def save_debug(path, screenshot, result):
    """Save a diagnostic screenshot annotated with detection details."""
    image = screenshot.copy()
    h, w = image.shape[:2]
    cv2.rectangle(image, (0, 0), (w - 1, h - 1), (0, 255, 255), 2)
    if result.bbox:
        x, y, bw, bh = result.bbox
        cv2.rectangle(image, (x, y), (x + bw, y + bh), (0, 255, 0), 2)
    if result.local_center:
        cv2.drawMarker(image, result.local_center, (0, 0, 255), cv2.MARKER_CROSS, 20, 2)
    cv2.putText(image, f'{result.method} {result.confidence:.3f} found={result.found}',
                (10, 25), cv2.FONT_HERSHEY_SIMPLEX, .6, (0, 255, 255), 2)
    if not cv2.imwrite(str(path), image):
        raise OSError(f'Could not write screenshot: {path}')


def run(path: str = '', click: bool = False, move_only: bool = False, once: bool = False,
        interval: float = 0.01, threshold: float = 0.55, duration: float = 0.2,
        max_clicks: int = 0, dry_run: bool = False, timeout: float = 0.0,
        region_width: int = 1160, region_height: int = 650, monitor: int = 1,
        debug: bool = False, debug_save: str = '', capture: str = '', check: bool = False):
    """Capture and detect targets, then perform the requested mouse action."""
    try:
        path = Path(path) if path else find_target()
        detector = ScreenDetector(str(path), threshold=threshold, region_width=region_width, region_height=region_height)
    except (ValueError, OSError) as e:
        typer.echo(f'Error loading template: {e}', err=True)
        raise typer.Exit(code=1)
    typer.echo(f'Target: {path} ({detector.template_w}×{detector.template_h} visible area)')
    if check:
        return
    controller = MouseController(duration=duration, move_only=move_only, dry_run=dry_run)
    click_count = 0
    target_visible = False
    consecutive_missing = 0
    acted_this_appearance = False
    start_time = time.monotonic()
    try:
        # Manual capture is a single diagnostic frame and can never move or click.
        if capture:
            result = detector.find(monitor)
            save_debug(capture, detector.last_screenshot, result)
            typer.echo(f'Saved diagnostic frame to {capture}; region={result.region} confidence={result.confidence:.3f}')
            return
        while True:
            if timeout > 0 and time.monotonic() - start_time >= timeout:
                typer.echo(f'Timeout reached after {timeout}s')
                break
            cycle = time.perf_counter()
            result = detector.find(monitor)
            if result.found:
                target_visible, consecutive_missing = True, 0
            elif target_visible:
                consecutive_missing += 1
                if consecutive_missing >= 2:
                    target_visible, consecutive_missing, acted_this_appearance = False, 0, False
            movement_ms = click_ms = 0.0
            valid = result.found and result.center is not None and result.region is not None and in_region(result.center, result.region)
            if valid:
                typer.echo(f'DETECTED conf={result.confidence:.3f} at {result.center} method={result.method} latency={result.latency_ms:.1f}ms clicks={click_count}')
                if not acted_this_appearance and (click or move_only):
                    if not dry_run:
                        t = time.perf_counter()
                        controller.move_to(result.center)
                        movement_ms = (time.perf_counter() - t) * 1000
                        if click and not move_only:
                            t = time.perf_counter()
                            controller.click()
                            click_ms = (time.perf_counter() - t) * 1000
                            click_count += 1
                    acted_this_appearance = True
                if debug_save:
                    save_debug(debug_save, detector.last_screenshot, result)
                    debug_save = ''  # explicitly requested: save only the first detection
            if debug:
                typer.echo(f'region={result.region} local={result.local_center} global={result.center} '
                           f'method={result.method} confidence={result.confidence:.3f} '
                           f'capture={result.capture_ms:.1f}ms detection={result.detection_ms:.1f}ms '
                           f'verification={result.verification_ms:.1f}ms movement={movement_ms:.1f}ms '
                           f'click={click_ms:.1f}ms cycle={(time.perf_counter()-cycle)*1000:.1f}ms')
            if valid and (once or (max_clicks > 0 and click_count >= max_clicks)):
                break
            if interval > 0:
                time.sleep(interval)
    except KeyboardInterrupt:
        typer.echo('\nStopped by user')
    except pyautogui.FailSafeException:
        typer.echo('\nFailsafe triggered (moved to corner)', err=True)
        raise typer.Exit(code=1)


def main(
    path: str = typer.Argument('', help='Reference image; defaults to the only image in targets/'),
    click: bool = typer.Option(False, '--click'),
    move_only: bool = typer.Option(False, '--move-only'),
    once: bool = typer.Option(False, '--once'),
    interval: float = typer.Option(0.01, '--interval'),
    threshold: float = typer.Option(0.55, '--threshold'),
    duration: float = typer.Option(0.2, '--duration'),
    max_clicks: int = typer.Option(0, '--max-clicks'),
    dry_run: bool = typer.Option(False, '--dry-run'),
    timeout: float = typer.Option(0.0, '--timeout'),
    region_width: int = typer.Option(1160, '--region-width'),
    region_height: int = typer.Option(650, '--region-height'),
    monitor: int = typer.Option(1, '--monitor'),
    debug: bool = typer.Option(False, '--debug'),
    debug_save: str = typer.Option('', '--debug-save', help='Save the first detected frame to this file'),
    capture: str = typer.Option('', '--capture', help='Save one diagnostic frame and exit without clicking'),
    check: bool = typer.Option(False, '--check', help='Validate the target and exit'),
):
    """Parse command-line options and start the detection loop."""
    run(path, click, move_only, once, interval, threshold, duration, max_clicks,
        dry_run, timeout, region_width, region_height, monitor, debug, debug_save, capture, check)


if __name__ == '__main__':
    typer.run(main)
