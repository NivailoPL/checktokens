"""Load a pinned tokenizer exclusively from packaged resources."""

import base64
import hashlib
import json
from functools import lru_cache
from importlib.resources import files

import tiktoken


@lru_cache(maxsize=1)
def get_tokenizer():
    resources = files("checktokens").joinpath("data")
    definition = json.loads(resources.joinpath("o200k_base.json").read_text())
    data = resources.joinpath("o200k_base.tiktoken").read_bytes()
    if hashlib.sha256(data).hexdigest() != definition["sha256"]:
        raise ValueError("Bundled tokenizer is damaged. Please reinstall CheckTokens.")
    ranks = {
        base64.b64decode(token): int(rank)
        for token, rank in (line.split() for line in data.splitlines())
    }
    return tiktoken.Encoding(
        name=definition["name"],
        pat_str=definition["pat_str"],
        mergeable_ranks=ranks,
        special_tokens=definition["special_tokens"],
    )


def count_tokens(text: str) -> int:
    return len(get_tokenizer().encode_ordinary(text))
