import argparse
import json
import sys
from dataclasses import asdict

from . import __version__
from .core import count_file, format_report, make_report
from .runner import run_batch


def main():
    parser = argparse.ArgumentParser(description="Count text tokens locally.")
    parser.add_argument("--version", action="version", version=__version__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--json", action="store_true", help="Print a JSON report.")
    mode.add_argument("--gui", action="store_true", help="Show the macOS results window.")
    parser.add_argument("--_worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("files", nargs="*", metavar="FILE")
    args = parser.parse_args()
    if args._worker:
        if len(args.files) != 1:
            parser.error("Worker expects one file.")
        print(json.dumps(asdict(count_file(args.files[0])), ensure_ascii=True))
        return 0
    if not args.files and not args.json and getattr(sys, "frozen", False):
        args.gui = True
    if args.gui:
        if sys.platform != "darwin":
            parser.error("The graphical interface currently requires macOS.")
        from .macos import show_results

        return show_results(args.files)
    if not args.files:
        parser.error("Provide at least one file.")
    try:
        results = list(run_batch(args.files))
    except KeyboardInterrupt:
        return 130
    report = make_report(results)
    print(json.dumps(report, ensure_ascii=True, indent=2) if args.json else format_report(results))
    return 0 if report["complete"] else 1
