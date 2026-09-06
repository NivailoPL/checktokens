"""Verify the built binary in a sandbox that denies all network access."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

binary = Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory(prefix="checktokens-smoke-") as directory:
    root = Path(directory)
    text = root / 'Żółć $test " --.md'
    text.write_text("hello world")
    env = dict(os.environ, TIKTOKEN_CACHE_DIR=str(root / "empty-cache"), PATH="/usr/bin:/bin")
    command = [
        "/usr/bin/sandbox-exec",
        "-p",
        "(version 1)(allow default)(deny network*)",
        str(binary),
        "--json",
        "--",
        str(text),
    ]
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=40)
    assert result.returncode == 0, (result.stdout, result.stderr)
    report = json.loads(result.stdout)
    assert report["total_tokens"] == 2, report
    assert report["complete"] is True
    assert not (root / "empty-cache").exists()
    print("Bundled CLI: 2 tokens; network denied; no external Python or tokenizer cache.")
