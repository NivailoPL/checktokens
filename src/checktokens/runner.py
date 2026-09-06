"""Bound each file's work by a timeout and support cancellation."""

import json
import subprocess
import sys
import threading
import time

from .core import Result

TIMEOUT_SECONDS = 30


def worker_command(path: str) -> list[str]:
    prefix = (
        [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, "-m", "checktokens"]
    )
    return [*prefix, "--_worker", "--", path]


def run_file(path: str, cancel: threading.Event, timeout: float = TIMEOUT_SECONDS) -> Result:
    if cancel.is_set():
        return Result(path, error="Cancelled.")
    try:
        process = subprocess.Popen(
            worker_command(path), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
    except OSError:
        return Result(path, error="Could not start the document worker.")
    started = time.monotonic()
    try:
        while True:
            if cancel.is_set():
                return Result(path, error="Cancelled.")
            if time.monotonic() - started >= timeout:
                return Result(path, error=f"Processing exceeded the {timeout:g} second limit.")
            try:
                output, _ = process.communicate(timeout=0.1)
                if process.returncode:
                    return Result(path, error="Document worker failed.")
                return Result(**json.loads(output))
            except subprocess.TimeoutExpired:
                continue
    except (OSError, ValueError, TypeError):
        return Result(path, error="Could not read the document worker's result.")
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate()


def run_batch(paths, cancel=None):
    cancel = cancel if cancel is not None else threading.Event()
    for path in paths:
        yield run_file(path, cancel)
