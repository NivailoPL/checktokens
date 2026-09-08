"""Exercise the packaged CLI with no external Python and an empty tokenizer cache."""

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

from docx import Document
from reportlab.pdfgen.canvas import Canvas

from checktokens.core import count_file


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve()
    with tempfile.TemporaryDirectory(prefix="checktokens-smoke-") as directory:
        root = Path(directory)
        text = root / "Żółć & $test %PATH% ' --.md"
        text.write_bytes(b"hello world")
        empty = root / "empty.txt"
        empty.write_bytes(b"")
        docx = root / "document.docx"
        document = Document()
        document.add_paragraph("hello world")
        document.save(docx)
        pdf = root / "document.pdf"
        canvas = Canvas(str(pdf))
        canvas.drawString(50, 750, "hello world")
        canvas.save()
        rtf = root / "document.rtf"
        rtf.write_bytes(rb"{\rtf1\ansi hello world}")
        documents = [docx, pdf, rtf]
        env = dict(
            os.environ,
            TIKTOKEN_CACHE_DIR=str(root / "empty-cache"),
            PATH=os.environ["SystemRoot"] + "\\System32",
        )
        for files, code, total, complete in [
            ([text, empty], 0, 2, True),
            ([text, root / "missing"], 1, 2, False),
        ]:
            result = subprocess.run(
                [str(binary), "--json", "--", *map(str, files)],
                env=env,
                capture_output=True,
                timeout=60,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            assert result.returncode == code, (result.stdout, result.stderr)
            report = json.loads(result.stdout)
            assert report["total_tokens"] == total, report
            assert report["complete"] is complete, report
            assert report["files"][0]["path"] == str(text), report
        result = subprocess.run(
            [str(binary), "--json", "--", *map(str, documents)],
            env=env,
            capture_output=True,
            timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        assert result.returncode == 0, (result.stdout, result.stderr)
        report = json.loads(result.stdout)
        assert [f["tokens"] for f in report["files"]] == [
            count_file(str(p)).tokens for p in documents
        ]
        assert not (root / "empty-cache").exists()
        print(
            "Packaged CLI passed: DOCX/PDF/RTF, Unicode paths, empty file, partial report, "
            "empty cache, no external Python on PATH."
        )


if __name__ == "__main__":
    main()
