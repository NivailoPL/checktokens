"""Render actual Qt widgets with synthetic data; never reads user documents."""

import argparse
import os
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from checktokens.core import Result
from checktokens.windows import ResultsWindow
from checktokens.windows_table import ui_font


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("work/ui-preview"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication(["preview", "-platform", "offscreen"])
    # The offscreen plugin does not enumerate Windows system fonts automatically.
    for name in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf", "seguisym.ttf"):
        QFontDatabase.addApplicationFont(str(Path(os.environ["SystemRoot"]) / "Fonts" / name))
    app.setStyle("Fusion")
    app.setFont(ui_font(13))
    cases = {
        "complete": [Result("C:/Examples/project-notes.html", 25068)],
        "partial": [
            Result("C:/Examples/research-summary.pdf", 1094),
            Result("C:/Examples/project-notes.html", 25068),
            Result(
                "C:/Examples/unreadable-document.rtf",
                error="PermissionError: The file could not be read.",
            ),
        ],
        "warnings": [
            Result(
                "C:/Examples/notes.md",
                1234567890,
                warnings=["Encoding auto-detected as cp1250; verify the source encoding."],
            ),
            Result(
                "C:/Examples/appendix.pdf",
                1042,
                warnings=["2 of 8 pages have no extracted text; OCR may be needed."],
            ),
        ],
    }
    for theme in ("dark", "light"):
        for case, results in cases.items():
            w = ResultsWindow([r.path for r in results], start_worker=False, theme=theme)
            w.results = results
            w.finished = True
            for simple in (True, False):
                w.set_view(simple)
                w.show()
                app.processEvents()
                w.layout().activate()
                app.processEvents()
                path = args.output / f"{theme}-{case}-{'simple' if simple else 'details'}.png"
                if not w.grab().save(str(path)):
                    raise RuntimeError(f"Could not render {path}")
            w.close()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    print(f"Rendered {len(cases) * 4} real-widget previews in {args.output.resolve()}")


if __name__ == "__main__":
    main()
