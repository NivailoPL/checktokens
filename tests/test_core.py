import json
import subprocess
import sys

from checktokens.core import Result, count_file, format_report, make_report


def test_plain_text_and_total(tmp_path):
    first = tmp_path / "first.md"
    second = tmp_path / "empty.txt"
    first.write_text("hello world")
    second.write_text("")
    results = [count_file(str(first)), count_file(str(second))]
    assert [r.tokens for r in results] == [2, 0]
    report = make_report(results)
    assert report["total_tokens"] == 2
    assert report["complete"] is True


def test_failure_is_not_zero(tmp_path):
    result = count_file(str(tmp_path / "missing.txt"))
    assert result.tokens is None
    assert result.error
    assert make_report([result])["complete"] is False


def test_duplicate_names_are_distinguishable():
    text = format_report([Result("/first/a.md", 2), Result("/second/a.md", 3)])
    assert "/first/a.md" in text and "/second/a.md" in text


def test_binary_not_decoded_as_text(tmp_path):
    path = tmp_path / "pretending.txt"
    path.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x01")
    assert count_file(str(path)).error


def test_utf16_and_special_token_text(tmp_path):
    path = tmp_path / "notes"
    path.write_bytes("hello world".encode("utf-16"))
    assert count_file(str(path)).tokens == 2
    path.write_text("<|endoftext|> Zażółć gęślą jaźń 🐈")
    assert count_file(str(path)).tokens > 0


def test_cli_mixed_batch(tmp_path):
    path = tmp_path / 'a $file " --.txt'
    path.write_text("hello world")
    command = [
        sys.executable,
        "-m",
        "checktokens",
        "--json",
        "--",
        str(path),
        str(tmp_path / "missing"),
    ]
    run = subprocess.run(command, capture_output=True, text=True)
    assert run.returncode == 1, run.stderr
    report = json.loads(run.stdout)
    assert report["total_tokens"] == 2
    assert report["files"][0]["path"] == str(path)
    assert report["files"][1]["tokens"] is None
