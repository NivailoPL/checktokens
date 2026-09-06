"""Portable counting and batch reporting. No platform UI dependencies."""

from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .extract import extract
from .tokenizer import count_tokens


@dataclass
class Result:
    path: str
    tokens: int | None = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    encoding: str | None = None


def count_file(path: str) -> Result:
    try:
        content = extract(Path(path))
        return Result(
            path, count_tokens(content.text), warnings=content.warnings, encoding=content.encoding
        )
    except Exception as exc:
        return Result(path, error=f"{type(exc).__name__}: {exc}")


def make_report(results: list[Result]) -> dict:
    return {
        "tokenizer": "o200k_base",
        "files": [asdict(result) for result in results],
        "total_tokens": sum(result.tokens or 0 for result in results),
        "counted_files": sum(result.tokens is not None for result in results),
        "complete": all(result.tokens is not None and not result.warnings for result in results),
    }


def display_names(results: list[Result]) -> list[str]:
    """Return unambiguous, control-character-safe names for reports and the UI."""
    output = []
    names = Counter(Path(result.path).name for result in results)
    for result in results:
        # Escape newlines/control characters in filenames to keep reports unambiguous.
        display = result.path if names[Path(result.path).name] > 1 else Path(result.path).name
        name = (
            display.encode("unicode_escape").decode()
            if any(ord(c) < 32 for c in display)
            else display
        )
        output.append(name)
    return output


def format_report(results: list[Result]) -> str:
    report = make_report(results)
    lines = ["CheckTokens", "Tokenizer: o200k_base", ""]
    for result, name in zip(results, display_names(results), strict=True):
        lines.append(
            f"{name} — {result.tokens:,} tokens"
            if result.tokens is not None
            else f"{name} — {result.error}"
        )
        lines.extend(f"  Note: {warning}" for warning in result.warnings)
    label = "Total" if report["complete"] else "Partial total"
    lines.extend(
        [
            "",
            f"{label}: {report['total_tokens']:,} tokens",
            f"Counted: {report['counted_files']} of {len(results)} files",
            "",
            "Counts extracted text, not the full cost of an AI attachment.",
        ]
    )
    return "\n".join(lines)
