# Changelog

## 0.3.0 — 2026-09-08

### Windows support

- Add a standalone Windows 10 x64 package with offline, per-user installation and uninstall, without administrator privileges or a separate Python installation.
- Add **Check Tokens** to Explorer's classic context menu. Multiple selected files open one combined report, including selections that exceed a command line's length limit.
- Add a PySide6/Qt results window inspired by the macOS design: compact **Simple** and expanded **Details**, a blue total, share bars, inline file errors and warnings, and clear partial-result status.
- Add dark and light themes, display scaling, keyboard shortcuts, clipboard copying, progress and cancellation. Retain the Windows title bar and controls.
- Bundle a separate CLI and isolated counting workers. Preserve source bytes on Windows and protect bundled tokenizer data against Git newline conversion.
- Add installer integrity checks and rollback, Windows CI, packaged CLI smoke checks and GUI regression tests.

### Documentation and packaging

- Document Windows installation, updates, uninstall, builds and verification; add UI previews generated with synthetic data.
- Include Qt/PySide6 license texts and upstream source references in the Windows distribution.
- Align package metadata, application versions, Windows manifest and macOS installer target at **0.3.0**.

### Known limits

- Windows 11 uses the classic menu under **Show more options**; the modern menu and Windows 11 acceptance testing are pending.
- The Windows package is unsigned. macOS packages remain ad hoc signed.
- Release ZIP publication is separate from pushing the source commit. The repository macOS installer requires published `v0.3.0` assets.
- Token counting and extraction semantics are unchanged; OCR and additional tokenizers are not included.

## 0.2.0

- Introduce Simple and Details views for the macOS results window.
- Package the offline application for Apple Silicon and Intel Macs.
