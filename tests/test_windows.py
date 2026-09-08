import io
import json
import os
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows interface")


@pytest.fixture(scope="module")
def app():
    from PySide6.QtGui import QFontDatabase
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(["test", "-platform", "offscreen"])
    app.setStyle("Fusion")
    for name in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf", "seguisym.ttf"):
        QFontDatabase.addApplicationFont(str(Path(os.environ["SystemRoot"]) / "Fonts" / name))
    return app


@pytest.fixture
def window(app):
    from checktokens.windows import ResultsWindow

    frame = ResultsWindow(
        ["C:/first/notes.md", "C:/second/notes.md"], start_worker=False, theme="dark"
    )
    yield frame
    frame.timer.stop()
    frame.close()
    app.processEvents()


def test_pending_and_view_switch(window):
    assert window.model.rowCount() == 2
    assert not window.copy_button.isEnabled()
    window.set_view(False)
    assert not window.table.isColumnHidden(1)
    assert not window.table.horizontalHeader().isHidden()
    window.set_view(True)
    assert window.table.isColumnHidden(1)
    assert window.table.horizontalHeader().isHidden()
    assert window.simple_button.isChecked()
    assert not window.details_toggle.isChecked()


@pytest.mark.parametrize("simple", [True, False])
@pytest.mark.parametrize("scale", [1, 1.5, 2])
def test_header_and_columns_follow_layout(window, app, simple, scale):
    # Exercise equivalent available space at multiple sizes; actual OS DPI needs manual QA.
    window.set_view(simple)
    window.resize(round(760 * scale), round(520 * scale))
    window.show()
    app.processEvents()
    width = sum(window.table.columnWidth(i) for i in range(3) if not window.table.isColumnHidden(i))
    assert abs(width - window.table.viewport().width()) <= 2
    assert window.total.geometry().right() <= window.unit.geometry().left()
    assert window.unit.geometry().right() < window.segments.geometry().left()
    assert window.simple_button.geometry().right() < window.details_toggle.geometry().left()


def test_partial_warning_and_completion(window):
    from checktokens.core import Result

    window.events.put(Result(window.paths[0], 42, warnings=["Incomplete text."]))
    window.events.put(Result(window.paths[1], error="Missing."))
    window.events.put(None)
    window.tick()
    assert window.finished
    assert window.total.text() == "42"
    assert not window.partial_badge.isHidden()
    assert window.model.index(1, 2).data() == "failed"
    window.set_view(False)
    from PySide6.QtCore import Qt

    assert "Incomplete text." in window.model.index(0, 0).data(Qt.ItemDataRole.AccessibleTextRole)
    assert window.table.rowHeight(0) > 34
    assert window.action.text() == "Close"
    assert window.copy_button.isEnabled()


def test_cancel_preserves_results(window):
    from checktokens.core import Result

    window.results = [Result(window.paths[0], 7)]
    window.on_action()
    assert window.cancel_event.is_set()
    assert window.total.text() == "7"
    window.events.put(Result(window.paths[1], error="Cancelled."))
    window.events.put(None)
    window.tick()
    assert "Cancelled" in window.status.text()


def test_long_warning_and_large_total_remain_readable(window, app):
    from checktokens.core import Result

    window.results = [
        Result(window.paths[0], 1234567890, warnings=["Long diagnostic " * 35]),
        Result(window.paths[1], 0),
    ]
    window.finished = True
    window.set_view(False)
    window.show()
    app.processEvents()
    wide = window.table.rowHeight(0)
    window.resize(560, 500)
    app.processEvents()
    narrow = window.table.rowHeight(0)
    assert narrow > wide > 34
    assert window.total.geometry().right() <= window.unit.geometry().left()
    assert window.unit.geometry().right() < window.segments.geometry().left()


def test_empty_success_distinct_from_all_failed(window):
    from checktokens.core import Result

    window.results = [Result(p, 0) for p in window.paths]
    window.finished = True
    window.set_view(False)
    assert window.badge.text() == "All 2 files counted"
    window.results = [Result(p, error="Missing") for p in window.paths]
    window.refresh()
    assert window.badge.text() == "All 2 files failed"
    assert window.total.text() == "0"


def test_theme_preserves_results_and_view(window):
    from checktokens.core import Result

    window.results = [Result(window.paths[0], 42)]
    window.set_view(False)
    window.apply_theme("light")
    assert window.theme == "light"
    assert window.total.text() == "42"
    assert not window.simple


def test_enter_closes_completed_window_but_does_not_cancel_counting(window, app):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
    window.show()
    window.activateWindow()
    app.processEvents()
    QTest.keyClick(window, Qt.Key.Key_Return)
    assert not window.cancel_event.is_set()
    assert window.isVisible()
    window.finished = True
    window.refresh()
    QTest.keyClick(window, Qt.Key.Key_Return)
    assert not window.isVisible()


def test_copy_includes_unfinished_files(window, monkeypatch):
    from types import SimpleNamespace

    from checktokens.core import Result

    copied = []
    monkeypatch.setattr(
        "checktokens.windows.QApplication",
        SimpleNamespace(clipboard=lambda: SimpleNamespace(setText=copied.append)),
    )
    window.results = [Result(window.paths[0], 42)]
    window.on_copy()
    assert "Partial total: 42" in copied[0]
    assert "Not counted yet." in copied[0]


def test_windowed_worker_uses_console_sibling(monkeypatch):
    from checktokens.runner import worker_command

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", "C:/Example/app/CheckTokens.exe")
    assert Path(worker_command("a.txt")[0]).name == "checktokens-cli.exe"
    assert worker_command("a.txt")[1:] == ["--_worker", "--", "a.txt"]


def test_selection_transport(monkeypatch):
    from checktokens.windows_entry import read_selection

    paths = ["C:/żółć & %PATH%/file.md", "C:/other/" + "long" * 5000 + ".txt"]
    payload = json.dumps(paths).encode("utf-8")
    received = []

    class Pipe(io.BytesIO):
        def read(self, size=-1):
            return super().read(min(size, 97))

        def write(self, data):
            received.append(data)
            return len(data)

    monkeypatch.setattr(
        "builtins.open", lambda *a, **kw: Pipe(len(payload).to_bytes(4, "little") + payload)
    )
    assert read_selection(r"\\.\pipe\CheckTokens-28e4a510-ebad-4b47-93c5-0a8511a4c1c8") == paths
    assert received == [b"\x01"]
    with pytest.raises(ValueError, match="channel"):
        read_selection("C:/not-a-pipe")


def test_read_preserves_windows_bytes(tmp_path):
    from checktokens.extract import read_file

    path = tmp_path / "bytes.txt"
    data = b"hello\r\nworld\x1aafter"
    path.write_bytes(data)
    assert read_file(path) == data
