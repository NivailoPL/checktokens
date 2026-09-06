import socket

import pytest

from checktokens.core import count_file
from checktokens.tokenizer import get_tokenizer


def test_offline_with_empty_cache(monkeypatch, tmp_path):
    def no_network(*args, **kwargs):
        raise AssertionError("Network must not be used")

    monkeypatch.setenv("TIKTOKEN_CACHE_DIR", str(tmp_path / "empty-cache"))
    monkeypatch.setattr(socket, "socket", no_network)
    get_tokenizer.cache_clear()
    assert len(get_tokenizer().encode_ordinary("hello world")) == 2
    assert not (tmp_path / "empty-cache").exists()


def test_missing_assets_do_not_download(monkeypatch, tmp_path):
    import checktokens.tokenizer as tokenizer

    monkeypatch.setattr(tokenizer, "files", lambda name: tmp_path)
    get_tokenizer.cache_clear()
    with pytest.raises(FileNotFoundError):
        get_tokenizer()
    get_tokenizer.cache_clear()


def test_size_limit_and_directory(tmp_path):
    path = tmp_path / "large.txt"
    with path.open("wb") as stream:
        stream.truncate(50 * 1024 * 1024 + 1)
    assert "50 MiB" in count_file(str(path)).error
    assert count_file(str(tmp_path)).error


def test_plain_preserves_line_endings():
    from checktokens.extract import extract_plain

    assert extract_plain(b" a\r\nb\n").text == " a\r\nb\n"
