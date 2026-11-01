# img-clicker

img-clicker is a Linux/X11 tool that monitors a centered part of the screen for a reference image. It can report a match, move the pointer, or click the image once per appearance. It supports rotated targets and can be used with the companion img-display demo or other on-screen content.

Detection depends on the reference image and screen conditions. Synthetic tests do not guarantee accuracy or a particular response time on real video.

## Requirements and setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Python 3.11 or newer, and use an X11 desktop session. From the project directory:

```bash
uv sync
```

Place **exactly one** PNG, JPEG, WebP or BMP image in `targets/`. The original image must be no larger than **600 × 600 pixels**. Image files in this directory are local and are not committed to the repository. For the companion img-display, use the same image in its `images/` folder.

Use a reference with visible detail. Transparent margins are trimmed, transparent pixels are excluded from matching, and the click point is chosen within an opaque part of the target. Fully transparent and visually uniform images cannot be matched reliably.

## Run

First, validate the image and observe detections without moving the pointer:

```bash
uv run python main.py --check
uv run python main.py --dry-run --debug
```

To move the pointer and click once per appearance, stop the dry run with Ctrl+C and start:

```bash
uv run python main.py --click
```

Add `--debug` to show capture, detection, verification, movement and click timing:

```bash
uv run python main.py --click --debug
```

**Running `uv run python main.py` on its own only reports detections.** Use `--click` to move and click. Use `--move-only` to move without clicking; `--dry-run` disables both movement and clicking even if another action is selected.

The detection line reports the click count before the action for that detection, so the first line can show `clicks=0` even when clicking is enabled. A target must be missed for two consecutive scans before the application will act on its next appearance.

Stop a foreground process with Ctrl+C. Moving the mouse to the top-left corner activates the PyAutoGUI failsafe.

### Background launcher

```bash
./run start    # Validate the target, then detect and click in the background
./run status   # Show status and recent log output
./run stop     # Stop the background process
```

The launcher writes output to `/tmp/img-clicker.log`. For a target outside `targets/`, pass its path directly, for example:

```bash
uv run python main.py /path/to/image.png --click
```

## Detection and options

By default, MSS captures a centered **1160 × 650** region of monitor 1. On a 1920 × 1080 display, its top-left corner is `(380, 215)`. Detected points are converted to desktop coordinates and checked against the region before an action. Use `--region-width`, `--region-height`, and `--monitor` to change the capture area or display.

The detector searches rotated versions of the image and refines promising matches. Larger references use finer rotation steps; low-contrast grayscale references can use color during the initial search. The image must retain its original scale and its rotated visible rectangle must fit in the capture region. The companion img-display selects rotations that fit its region.

Useful options include `--threshold` (default `0.55`), `--duration` (default `0.2` seconds), `--interval`, `--timeout`, `--max-clicks`, and `--once`. See all options with:

```bash
uv run python main.py --help
```

## Diagnostics

`--debug` prints the region, match confidence, coordinates, method and timing for each scan. To save the first detected frame with annotations:

```bash
uv run python main.py --dry-run --debug-save detection.png
```

To save a single diagnostic frame when the target is visible, run the following in a separate terminal. This mode exits without moving or clicking:

```bash
uv run python main.py --capture diagnostic.png
```

Screenshots are saved only when requested. Review them before sharing, as they contain screen content.

## Tests

```bash
uv run python -m pytest -q
```

The tests cover image selection and size limits, rotation matching, capture coordinates, transparent targets and mouse controls. Mouse actions are mocked. The test suite requires access to an X display for PyAutoGUI; on a headless machine, it can be run with `xvfb-run -a uv run python -m pytest -q`.

## License

MIT; see [LICENSE](LICENSE).
