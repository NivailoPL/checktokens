"""Read document content without changing the source file."""

import codecs
import io
import os
import re
import stat
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_EXPANDED_BYTES = 100 * 1024 * 1024


@dataclass
class Extracted:
    text: str
    warnings: list[str] = field(default_factory=list)
    encoding: str | None = None


def read_file(path: Path) -> bytes:
    # O_NONBLOCK also prevents a replaced path/FIFO from hanging at open().
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("Not a regular file. Folders are not scanned.")
        if info.st_size > MAX_FILE_BYTES:
            raise ValueError("File exceeds the 50 MiB limit.")
        data = stream.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise ValueError("File exceeds the 50 MiB limit.")
        return data


def extract(path: Path) -> Extracted:
    data = read_file(path)
    suffix = path.suffix.lower()
    if suffix == ".pdf" or data.startswith(b"%PDF-"):
        return extract_pdf(data)
    if suffix == ".rtf" or data.lstrip().startswith(b"{\\rtf"):
        return extract_rtf(data)
    if suffix == ".docx" or data.startswith(b"PK\x03\x04"):
        return extract_docx(data)
    if suffix in {".doc", ".pages", ".odt", ".epub"}:
        raise ValueError("This document format is not supported yet.")
    return extract_plain(data)


def extract_plain(data: bytes) -> Extracted:
    from charset_normalizer import from_bytes

    warnings = []
    for bom, encoding in (
        (codecs.BOM_UTF32_LE, "utf-32"),
        (codecs.BOM_UTF32_BE, "utf-32"),
        (codecs.BOM_UTF16_LE, "utf-16"),
        (codecs.BOM_UTF16_BE, "utf-16"),
        (codecs.BOM_UTF8, "utf-8-sig"),
    ):
        if data.startswith(bom):
            text = data.decode(encoding)
            break
    else:
        if b"\x00" in data or data.startswith((b"\x89PNG", b"\xff\xd8", b"GIF8", b"\xd0\xcf")):
            raise ValueError("Binary data: no supported text content found.")
        try:
            text, encoding = data.decode("utf-8"), "utf-8"
        except UnicodeDecodeError:
            match = from_bytes(data).best()
            if match is None:
                raise ValueError("Could not determine the text encoding.") from None
            encoding, text = match.encoding, str(match)
            warnings.append(f"Encoding auto-detected as {encoding}; verify the source encoding.")
    if any(ord(c) < 32 and c not in "\t\n\r\f\b" for c in text):
        raise ValueError("Binary/control data: not a supported text file.")
    return Extracted(text, warnings, encoding)


def extract_rtf(data: bytes) -> Extracted:
    from striprtf.striprtf import rtf_to_text

    if not data.lstrip().startswith(b"{\\rtf"):
        raise ValueError("Invalid RTF document.")
    match = re.search(rb"\\ansicpg(\d+)", data[:4096])
    encoding = f"cp{match[1].decode()}" if match else "cp1252"
    text = rtf_to_text(data.decode(encoding), encoding=encoding, errors="strict")
    return Extracted(text)


def extract_pdf(data: bytes) -> Extracted:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted and not reader.decrypt(""):
        raise ValueError("PDF requires a password; password entry is not supported.")
    texts = [page.extract_text() or "" for page in reader.pages]
    missing = sum(not text.strip() for text in texts)
    if not texts or missing == len(texts):
        raise ValueError("No text found in PDF. OCR may be needed.")
    warnings = (
        [f"{missing} of {len(texts)} pages have no extracted text; OCR may be needed."]
        if missing
        else []
    )
    return Extracted("\n\n".join(texts), warnings)


def extract_docx(data: bytes) -> Extracted:
    from docx import Document
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    from lxml import etree

    warnings = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if sum(item.file_size for item in archive.infolist()) > MAX_EXPANDED_BYTES:
            raise ValueError("Expanded document exceeds the 100 MiB limit.")
        if "word/document.xml" not in archive.namelist():
            raise ValueError("Unsupported archive/document format; expected DOCX.")
        unsupported = {qn(f"w:{tag}") for tag in ("txbxContent", "ins", "del")}
        for name in archive.namelist():
            if name.startswith("word/") and name.endswith(".xml"):
                root = etree.fromstring(
                    archive.read(name),
                    parser=etree.XMLParser(resolve_entities=False, no_network=True),
                )
                if any(element.tag in unsupported for element in root.iter()):
                    warnings.append(
                        "Text boxes or tracked changes were detected and are not fully extracted."
                    )
                if name in {"word/footnotes.xml", "word/endnotes.xml", "word/comments.xml"}:
                    if any(element.text for element in root.iter(qn("w:t"))):
                        warnings.append("Footnotes, endnotes or comments are not included.")

    document = Document(io.BytesIO(data))

    def blocks(container):
        parts = []
        for item in container.iter_inner_content():
            if isinstance(item, Paragraph):
                parts.append(item.text)
            elif isinstance(item, Table):
                seen = set()
                for row in item.rows:
                    cells = []
                    for cell in row.cells:
                        if cell._tc not in seen:
                            seen.add(cell._tc)
                            cells.append(blocks(cell))
                    parts.append("\t".join(cells))
        return "\n".join(parts)

    parts = [blocks(document)]
    seen_parts = set()
    # Read existing header/footer relationships; do not create absent parts.
    for relation in document.part.rels.values():
        if not relation.is_external and relation.reltype.rsplit("/", 1)[-1] in {"header", "footer"}:
            part = relation.target_part
            if part.partname not in seen_parts:
                seen_parts.add(part.partname)
                from docx.blkcntnr import BlockItemContainer

                parts.append(blocks(BlockItemContainer(part.element, part)))
    return Extracted("\n\n".join(parts), list(dict.fromkeys(warnings)))
