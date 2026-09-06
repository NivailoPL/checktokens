# CheckTokens

Count text tokens locally, straight from Finder. Select files, right-click, choose **Check Tokens**, and get individual counts and a total in one native window. macOS may group the item under **Services** when many services are available.

macOS 15+ · Apple Silicon and Intel · No account or API key · Offline after installation

## Install

Download the appropriate ZIP from [Releases](https://github.com/NivailoPL/checktokens/releases), extract it, and run its installer from Terminal:

```sh
bash /path/to/extracted/install-macos.sh
```

Alternatively, download or clone this repository, then run:

```sh
bash install-macos.sh
```

The repository installer downloads the **v0.2.0** package for your Mac and verifies its SHA-256. The extracted-package installer checks the included content manifest. Python, Homebrew and developer tools are **not** required for installation. Downloading the repository alone before the first release exists requires the developer build instructions below.

Installation is per user, without `sudo`. The app lives in `~/Library/Application Support/CheckTokens/CheckTokens.app`; the workflow lives in `~/Library/Services/Check Tokens.workflow`. You can move/delete the downloaded repository or ZIP after installation. Run the installer again to replace an existing CheckTokens installation.

The app is **ad hoc signed**, without Apple Developer ID or notarization. If macOS blocks its first launch, open the installed `CheckTokens.app` and follow [Apple's Open Anyway instructions](https://support.apple.com/en-us/102445). Do not disable Gatekeeper globally. Opening the app directly also lets you select files using a file picker.

If the action is missing, reopen the Finder menu and check **Finder → Services** with files selected. No accessibility or full-disk-access permission is needed for counting normally accessible files.

## What gets counted

The bundled **o200k_base** tokenizer counts extracted text. This is **not** a universal token count across all models or the full cost of uploading an attachment to an AI service. The total is the sum of per-file counts, not a count of concatenated files or conversation overhead.

| Input | Content |
| --- | --- |
| TXT, Markdown, code, JSON, YAML, CSV, logs | Decoded source text, including syntax and whitespace |
| HTML, XML | Source with markup, not rendered browser text |
| RTF | Text without RTF formatting commands |
| DOCX | Main paragraphs, tables (including nested tables), unique headers and footers |
| PDF | Extracted text in page order |

- Text files can have unfamiliar extensions or no extension. UTF-8 and Unicode BOMs are supported; other encodings are detected heuristically and explicitly marked for verification. No lossy decoding is used.
- DOCX text boxes, tracked changes, footnotes, endnotes and comments are not fully extracted. Their presence produces an explanatory note and marks the total partial.
- PDF extraction can change spacing or reading order. Pages without extracted text are reported; a fully textless PDF reports that OCR may be needed. This does not prove a page is a scan. OCR and password entry are not included.
- Files that fail, unsupported binary formats and directories get their own errors. Remaining files are still counted. A valid empty text file has zero tokens.
- A total is marked **partial** when any file failed or has extraction/encoding warnings.
- Limits: **50 MiB per file**, **30 seconds per file**, and **100 MiB expanded DOCX content**. Exceeding a limit fails the file rather than silently truncating it.
- Windows integration, OCR, alternate tokenizers and automatic updates are deferred.

Documents are never modified or uploaded. CheckTokens has no telemetry or document history and does not write extracted text to disk. **Copy results** copies the report to your clipboard only when clicked.

## Command line

```sh
uv run checktokens -- document.md notes.rtf
uv run checktokens --json -- document.pdf
uv run checktokens --gui -- document.md notes.rtf
```

Without `uv`, invoke the installed app's binary:

```sh
"$HOME/Library/Application Support/CheckTokens/CheckTokens.app/Contents/MacOS/checktokens" --json -- document.md
```

JSON contains `tokenizer`, `files` (path, tokens or null, error, warnings, encoding), `total_tokens`, `counted_files`, and `complete`. CLI exit codes: **0** complete, **1** partial/failed, **2** invalid arguments, **130** interrupted. GUI document errors are shown in its window and do not trigger a second Automator error dialog.

## Uninstall

```sh
bash "$HOME/Library/Application Support/CheckTokens/uninstall-macos.sh"
```

Only CheckTokens-owned files are removed. Other files in the installation directory are preserved.

## Development

Install [uv](https://docs.astral.sh/uv/), then:

```sh
uv sync --locked
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run python scripts/build_macos.py
uv run python scripts/smoke_bundle.py dist/CheckTokens.app/Contents/MacOS/checktokens
bash install-macos.sh --package dist/CheckTokens-macos-arm64.zip
```

Use `x86_64` instead of `arm64` for Intel. Build on macOS 15 for the supported minimum target. Local development on a newer macOS produces a locally verifiable build, while release packages come from the macOS 15 CI jobs. Installation tests compile a tiny fixture and therefore require Xcode Command Line Tools; end users do not need them.

Dependencies are pinned in `uv.lock`. Tokenizer data and its SHA-256 are committed. Normal builds never download tokenizer data; the explicit developer maintenance script `scripts/vendor_tokenizer.py` refreshes it from the pinned upstream library.

GitHub Actions tests, builds and runs the packaged CLI with **network access denied** for both architectures. It uploads ZIPs and SHA-256 files as workflow artifacts; publication is a separate release step. Before publishing, combine both checksum files into one `SHA256SUMS` and attach it alongside both ZIPs.

Verification: native window and packaged CLI tested locally on Apple Silicon/macOS 26.5.2. CI covers macOS 15 ARM and Intel; check the workflow result for the exact release commit. Intel Finder UI has not been manually verified.

## License

MIT. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for bundled dependencies.
