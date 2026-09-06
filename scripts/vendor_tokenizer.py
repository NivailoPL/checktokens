"""Development-only: vendor the upstream o200k_base data and definition."""

import base64
import hashlib
import json
from pathlib import Path

import tiktoken

root = Path(__file__).resolve().parents[1] / "src/checktokens/data"
root.mkdir(parents=True, exist_ok=True)
encoding = tiktoken.get_encoding("o200k_base")
data = b"".join(
    base64.b64encode(token) + b" " + str(rank).encode() + b"\n"
    for token, rank in sorted(encoding._mergeable_ranks.items(), key=lambda item: item[1])
)
(root / "o200k_base.tiktoken").write_bytes(data)
(root / "o200k_base.json").write_text(
    json.dumps(
        {
            "name": encoding.name,
            "pat_str": encoding._pat_str,
            "special_tokens": encoding._special_tokens,
            "sha256": hashlib.sha256(data).hexdigest(),
        },
        indent=2,
    )
    + "\n"
)
print("Vendored o200k_base:", hashlib.sha256(data).hexdigest())
