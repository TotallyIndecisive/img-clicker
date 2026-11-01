"""Global command-line interface for img-clicker."""
import argparse
import os
import sys
from pathlib import Path


VERSION = "1.0.0"


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
        epilog="Run 'imgc help start' for detection options. Stop a running session with Ctrl+C.",
    )
    parser.add_argument("--version", action="version", version=f"img-clicker {VERSION}")
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")
    commands.add_parser("help", help="Show commands or help for a command").add_argument(
        "topic", nargs="?", choices=("start", "targets", "check"))
    commands.add_parser("targets", help="Create and print the user targets directory")
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
    start.add_argument("--region-width", type=int, default=1160, help="Centered capture width (default: 1160)")
    start.add_argument("--region-height", type=int, default=650, help="Centered capture height (default: 650)")
    start.add_argument("--debug-save", default="", metavar="FILE", help="Save the first detected frame")
    start.add_argument("--capture", default="", metavar="FILE", help="Save one diagnostic frame and exit without clicking")
    return parser, {"start": start, "check": check}


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
            region_width=args.region_width, region_height=args.region_height, monitor=args.monitor,
            debug=args.debug, debug_save=args.debug_save, capture=args.capture)
        return 0
    except (OSError, ValueError) as exc:
        print(f"imgc: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(cli())
