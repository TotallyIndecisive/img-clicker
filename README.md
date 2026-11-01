# img-clicker

img-clicker is a Linux/X11 command-line tool that detects a reference image on screen and can move the pointer and click it. It supports rotated targets and monitors a centered region of the display. Detection accuracy and timing depend on the reference and the screen content.

## Install on Linux

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and use an X11 desktop session. Install img-clicker from GitHub:

```bash
uv tool install git+https://github.com/TotallyIndecisive/img-clicker.git
uv tool update-shell
```

Restart your terminal or follow the `uv tool update-shell` instructions to put uv's executable directory on `PATH`. You can then run `imgc` from any directory. To upgrade later, run `uv tool upgrade img-clicker`; to remove the tool, run `uv tool uninstall img-clicker`.

To install from a local checkout instead, run `uv tool install /path/to/img-clicker`. Use `uv tool install --editable /path/to/img-clicker` when developing locally.

## Add a target

Run:

```bash
imgc targets
```

This creates and prints the targets directory, normally:

```text
~/.local/share/img-clicker/targets/
```

If `XDG_DATA_HOME` is set to an absolute path, the directory is `$XDG_DATA_HOME/img-clicker/targets/`. Put **exactly one** PNG, JPEG, WebP, or BMP image in that folder. The original image must be no larger than **600 × 600 pixels**. `imgc start` also creates the folder if it does not exist and reports its path when an image is missing. To use an image elsewhere, pass `--image /path/to/image.png` to `imgc start` or `imgc check`.

Choose an image with visible detail. Transparent margins are trimmed, transparent pixels are excluded from matching, and the click point is chosen within an opaque part of the target. Fully transparent or visually uniform images cannot be matched reliably. For the companion img-display, use the same original image in its `images/` folder.

## Run

```bash
imgc help                 # Show commands
imgc help start           # Show detection and movement options
imgc check                # Validate the selected image
imgc start --dry-run      # Report detections without moving or clicking
imgc start                # Move and click when the target appears
```

`imgc start` runs in the foreground. Stop it with **Ctrl+C**; moving the pointer to the top-left corner triggers the PyAutoGUI failsafe. A target is acted on once per appearance and must be missed for two consecutive scans before the next action. `--move-only` moves without clicking, and `--dry-run` disables both movement and clicking.

```bash
imgc start --debug                    # Include coordinates and timing
imgc start --move-only                # Move without clicking
imgc start --image /path/to/image.png # Use a specific reference
imgc start --once                     # Stop after the first detection
```

The detection line reports the click count before the action for that detection, so the first line may show `clicks=0` even when clicking is enabled.

The previous source checkout commands remain available: `uv run python main.py --click` runs in the foreground, and `./run start`, `./run status`, and `./run stop` manage its background launcher. These legacy commands use the checkout's `targets/` folder, while `imgc` uses the user data folder described above.

## Detection and options

By default, MSS captures a centered **1160 × 650** region of monitor 1. On a 1920 × 1080 display, its top-left corner is `(380, 215)`. Detected points are converted to desktop coordinates and checked against the region before an action. Use `--region-width`, `--region-height`, and `--monitor` to change the capture area or display.

The detector searches rotated versions of the image and refines promising matches. Larger references use finer rotation steps; low-contrast grayscale references can use color during the initial search. The image must retain its original scale and its rotated visible rectangle must fit in the capture region. The companion img-display selects rotations that fit its region.

Useful options include `--threshold` (default `0.55`), `--duration` (default `0.2` seconds), `--interval`, `--timeout`, and `--max-clicks`. See all options with `imgc start --help`.

## Diagnostics

`--debug` prints the region, match confidence, coordinates, method and timing for each scan. Save the first detected frame with annotations:

```bash
imgc start --dry-run --debug-save detection.png
```

Save one diagnostic frame when the target is visible. This exits without moving or clicking:

```bash
imgc start --capture diagnostic.png
```

Screenshots are saved only when requested. Review them before sharing, as they contain screen content.

## Development

From a checkout, run `uv sync` to install project and development dependencies. Run the test suite with `uv run python -m pytest -q`. The tests cover image selection and size limits, rotation matching, capture coordinates, transparent targets and mouse controls. Mouse actions are mocked. PyAutoGUI requires an X display; on a headless machine use `xvfb-run -a uv run python -m pytest -q`.

## License

MIT; see [LICENSE](LICENSE).
