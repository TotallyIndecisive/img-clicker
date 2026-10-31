# img-clicker

img-clicker is a small Linux/X11 experiment that finds a reference image on screen and can move the mouse or click it. It was built to test image-based screen detection, including targets displayed at different rotations, using the companion img-display demo. This is a demo, and detection accuracy depends on the image and screen conditions.

## Setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), Python 3.11 or newer, and use an X11 desktop session. From the project directory:

```bash
uv sync
```

Put your reference image in `targets/` (for example, `targets/tickets.png`). Target images are local and are not included in the repository. Use a clear image with sufficient detail; transparent pixels in a PNG are excluded from matching.

## Run

Start with a dry run, which reports detections without moving or clicking:

```bash
uv run python main.py targets/tickets.png --dry-run --debug
```

Use `--move-only` to move the pointer, or `--click` to click once per appearance. Stop with Ctrl+C; moving the mouse to the top-left corner triggers PyAutoGUI's failsafe. The optional `./run start`, `./run stop`, and `./run status` launcher uses `targets/tickets.png` and clicks automatically.

The default capture area is centered on monitor 1 and measures 1160 × 650 pixels. Override it with `--region-width`, `--region-height`, and `--monitor`. The rotated image must fit inside the capture area; matching assumes a fixed image scale. Use `--threshold`, `--interval`, `--duration`, `--timeout`, `--max-clicks`, or `--once` to adjust behavior. Run `uv run python main.py --help` for the full options.

For diagnostics, `--debug-save detection.png` saves the first detected frame with annotations; `--capture diagnostic.png` captures one annotated frame and exits without clicking. No screenshot is saved unless requested.

## Components

- `main.py` handles command-line options, the detection loop, and diagnostics.
- `detector.py` captures the screen region and finds rotated image matches.
- `controller.py` moves and clicks the mouse, with dry-run and move-only modes.
- `run` starts, stops, and checks a background instance.
- `tests/` checks matching, rotation, capture regions, and mouse controls using synthetic inputs.

Run the tests with `uv run python -m pytest -q`. Synthetic tests do not establish accuracy on real video or guarantee detection on every desktop. Linux/X11 is the supported test environment; Windows and macOS are not currently supported.

## License

MIT; see [LICENSE](LICENSE).
