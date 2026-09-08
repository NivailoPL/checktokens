"""Windowed entry point and private, memory-only Explorer selection transport."""

import json
import re
import sys
import time


def read_selection(pipe):
    if not re.fullmatch(r"\\\\\.\\pipe\\CheckTokens-[0-9a-fA-F-]{36}", pipe):
        raise ValueError("Invalid selection channel.")
    deadline = time.monotonic() + 30
    while True:
        try:
            stream = open(pipe, "r+b", buffering=0)
            break
        except OSError:
            if time.monotonic() >= deadline:
                raise TimeoutError("Explorer did not deliver the selected files.") from None
            time.sleep(0.05)
    with stream:

        def read_exact(size):
            data = bytearray()
            while len(data) < size:
                chunk = stream.read(min(65536, size - len(data)))
                if not chunk:
                    raise ValueError("Incomplete file selection.")
                data.extend(chunk)
            return data

        length = int.from_bytes(read_exact(4), "little")
        if not 0 < length <= 16 * 1024 * 1024:
            raise ValueError("The selection is too large.")
        data = read_exact(length)
        stream.write(b"\x01")
    paths = json.loads(data)
    if not isinstance(paths, list) or not paths or not all(isinstance(p, str) and p for p in paths):
        raise ValueError("Invalid file selection.")
    return paths


def main():
    try:
        args = sys.argv[1:]
        if args[:1] == ["--_selection-pipe"]:
            if len(args) != 2:
                raise ValueError("Invalid selection arguments.")
            paths = read_selection(args[1])
        else:
            paths = args[1:] if args[:1] == ["--"] else args
        from .windows import show_results

        return show_results(paths)
    except Exception as exc:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, str(exc), "CheckTokens — could not open", 0x10)
        return 1
