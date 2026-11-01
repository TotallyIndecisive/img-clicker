"""Global command-line interface for img-clicker."""
import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path


VERSION = "1.0.0"
DEFAULT_RESOLUTION = (1160, 650)


def config_path():
    """Return the per-user configuration path following the XDG convention."""
    configured = os.environ.get("XDG_CONFIG_HOME", "")
    base = Path(configured) if configured and Path(configured).is_absolute() else Path.home() / ".config"
    return base / "img-clicker" / "config.json"


def parse_resolution(value):
    match = re.fullmatch(r"([0-9]+)[xX]([0-9]+)", value)
    if not match or int(match[1]) <= 0 or int(match[2]) <= 0:
        raise argparse.ArgumentTypeError("resolution must be WIDTHxHEIGHT with positive integers, e.g. 1920x1080")
    return int(match[1]), int(match[2])


def read_config():
    path = config_path()
    try:
        with path.open(encoding="utf-8") as file:
            config = json.load(file)
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"Invalid configuration in {path}: {exc}") from exc
    if not isinstance(config, dict):
        raise ValueError(f"Invalid configuration in {path}: expected an object")
    return config


def get_resolution(config):
    value = config.get("resolution")
    if value is None:
        return DEFAULT_RESOLUTION
    if (not isinstance(value, list) or len(value) != 2 or
            any(type(v) is not int or v <= 0 for v in value)):
        raise ValueError(f"Invalid resolution in {config_path()}: expected two positive integers")
    return tuple(value)


def save_resolution(resolution):
    path = config_path()
    config = read_config()
    config["resolution"] = list(resolution)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".config-", delete=False) as file:
            temporary = Path(file.name)
            json.dump(config, file, indent=2)
            file.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def positive_int(value):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a positive integer") from None
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def target_directory():
    """Return the XDG user data directory for reference images."""
    configured = os.environ.get("XDG_DATA_HOME", "")
    base = Path(configured) if configured and Path(configured).is_absolute() else Path.home() / ".local" / "share"
    return base / "img-clicker" / "targets"


def prepare_targets():
    directory = target_directory()
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def make_parser():
    parser = argparse.ArgumentParser(
        prog="imgc",
        description="Detect and click a reference image on an X11 desktop.",
        epilog="Set a persistent centered capture size: imgc set res 1920x1080. "
               "Run 'imgc help start' for options. Stop a running session with Ctrl+C.",
    )
    parser.add_argument("--version", action="version", version=f"img-clicker {VERSION}")
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")
    commands.add_parser("help", help="Show commands or help for a command").add_argument(
        "topic", nargs="?", choices=("start", "targets", "check", "set", "show"))
    commands.add_parser("targets", help="Create and print the user targets directory")
    show = commands.add_parser("show", help="Show the saved centered capture size")
    setting = commands.add_parser("set", help="Save a centered capture size, e.g. imgc set res 1920x1080")
    settings = setting.add_subparsers(dest="setting", required=True, metavar="SETTING")
    resolution = settings.add_parser("res", help="Set capture size as WIDTHxHEIGHT")
    resolution.add_argument("size", type=parse_resolution, metavar="WIDTHxHEIGHT",
                            help="Centered capture size in pixels, e.g. 1920x1080")
    check = commands.add_parser("check", help="Validate the selected reference image")
    check.add_argument("--image", type=Path, help="Use a specific reference image")
    start = commands.add_parser("start", help="Detect and click targets in the foreground")
    start.add_argument("--image", type=Path, help="Use a specific reference image")
    start.add_argument("--dry-run", action="store_true", help="Report matches without moving or clicking")
    start.add_argument("--move-only", action="store_true", help="Move to matches without clicking")
    start.add_argument("--debug", action="store_true", help="Print coordinates, confidence, and timing")
    start.add_argument("--once", action="store_true", help="Stop after the first detection")
    start.add_argument("--threshold", type=float, default=.55, help="Minimum confidence (default: 0.55)")
    start.add_argument("--interval", type=float, default=.01, help="Delay between scans in seconds (default: 0.01)")
    start.add_argument("--duration", type=float, default=.2, help="Pointer movement time in seconds (default: 0.2)")
    start.add_argument("--timeout", type=float, default=0, help="Stop after this many seconds (0 disables)")
    start.add_argument("--max-clicks", type=int, default=0, help="Stop after this many clicks (0 disables)")
    start.add_argument("--monitor", type=int, default=1, help="MSS monitor number (default: 1)")
    start.add_argument("--region-width", type=positive_int, help="Override saved capture width for this run")
    start.add_argument("--region-height", type=positive_int, help="Override saved capture height for this run")
    start.add_argument("--debug-save", default="", metavar="FILE", help="Save the first detected frame")
    start.add_argument("--capture", default="", metavar="FILE", help="Save one diagnostic frame and exit without clicking")
    return parser, {"start": start, "check": check, "set": setting, "show": show}


def cli():
    parser, subparsers = make_parser()
    args = parser.parse_args()
    if args.command is None or args.command == "help":
        if args.command == "help" and args.topic in subparsers:
            subparsers[args.topic].print_help()
        elif args.command == "help" and args.topic == "targets":
            print("usage: imgc targets\n\nCreate and print the user targets directory.")
        else:
            parser.print_help()
        return 0
    try:
        if args.command == "set":
            save_resolution(args.size)
            print(f"Saved centered capture size: {args.size[0]}x{args.size[1]} ({config_path()})")
            return 0
        if args.command == "show":
            width, height = get_resolution(read_config())
            print(f"Centered capture size: {width}x{height} (config: {config_path()})")
            return 0
        if args.command == "start":
            width, height = get_resolution(read_config())
            width = args.region_width if args.region_width is not None else width
            height = args.region_height if args.region_height is not None else height
        directory = prepare_targets()
        if args.command == "targets":
            print(directory)
            return 0
        # Help and directory setup work even when no X display is available.
        from main import find_target, run
        image = args.image if args.image else find_target(directory)
        if args.command == "check":
            run(path=str(image), check=True)
            return 0
        run(path=str(image), click=True, move_only=args.move_only, once=args.once,
            interval=args.interval, threshold=args.threshold, duration=args.duration,
            max_clicks=args.max_clicks, dry_run=args.dry_run, timeout=args.timeout,
            region_width=width, region_height=height, monitor=args.monitor,
            debug=args.debug, debug_save=args.debug_save, capture=args.capture)
        return 0
    except (OSError, ValueError) as exc:
        print(f"imgc: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(cli())
