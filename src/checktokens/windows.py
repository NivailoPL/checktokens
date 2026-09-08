"""Mac-inspired Windows views with Qt; counting remains in isolated workers."""

import queue
import threading

from PySide6.QtCore import QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import (
    QActionGroup,
    QColor,
    QDesktopServices,
    QFontMetrics,
    QKeySequence,
    QPalette,
    QShortcut,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStyle,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .core import Result, display_names, format_report, make_report
from .runner import run_batch
from .windows_style import PALETTES, stylesheet
from .windows_table import FileDelegate, FileModel, ui_font


def label(text="", name=""):
    widget = QLabel(text)
    widget.setObjectName(name)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    return widget


class ResultsWindow(QWidget):
    def __init__(self, paths, *, start_worker=True, theme=None):
        super().__init__()
        self.setObjectName("results")
        self.setWindowTitle("CheckTokens")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.paths = list(paths)
        self.names = display_names([Result(p) for p in paths])
        self.results = []
        self.report = make_report([])
        self.events = queue.Queue()
        self.cancel_event = threading.Event()
        self.finished = False
        self.closing = False
        self.thread = None
        self.simple = True
        self.file_column_width = 350
        self.theme = theme or str(QSettings("CheckTokens", "Appearance").value("theme", "dark"))
        if self.theme not in PALETTES:
            self.theme = "dark"
        self.file_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        self.build_window()
        self.apply_theme(self.theme)
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.tick)
        self.set_view(True)
        screen = self.screen().availableGeometry()
        self.move(screen.center() - self.rect().center())
        self.shortcuts = []
        for keys, callback in [
            ("Ctrl+1", lambda: self.set_view(True)),
            ("Ctrl+2", lambda: self.set_view(False)),
            ("Ctrl+C", self.on_copy),
            ("Escape", self.on_action),
            ("Return", lambda: self.on_action() if self.finished else None),
            ("Enter", lambda: self.on_action() if self.finished else None),
        ]:
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.activated.connect(callback)
            self.shortcuts.append(shortcut)
        if start_worker:
            self.thread = threading.Thread(target=self.work, daemon=False)
            self.thread.start()
            self.timer.start()

    def build_window(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 18)
        outer.setSpacing(0)
        header = QHBoxLayout()
        header.setSpacing(8)
        self.total = label("0")
        self.total.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.unit = label("tokens", "unit")
        self.partial_badge = label("partial", "badge")
        self.partial_badge.setFixedHeight(24)
        header.addWidget(self.total, 0, Qt.AlignmentFlag.AlignBottom)
        header.addWidget(self.unit, 0, Qt.AlignmentFlag.AlignBottom)
        header.addWidget(self.partial_badge, 0, Qt.AlignmentFlag.AlignBottom)
        header.addStretch(1)
        self.segments = QFrame()
        self.segments.setObjectName("segments")
        segment_layout = QHBoxLayout(self.segments)
        segment_layout.setContentsMargins(1, 1, 1, 1)
        segment_layout.setSpacing(1)
        self.simple_button = QPushButton("Simple")
        self.details_toggle = QPushButton("Details")
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for button in (self.simple_button, self.details_toggle):
            button.setObjectName("segment")
            button.setCheckable(True)
            button.setFixedSize(64, 23)
            self.group.addButton(button)
            segment_layout.addWidget(button)
        self.simple_button.clicked.connect(lambda: self.set_view(True))
        self.details_toggle.clicked.connect(lambda: self.set_view(False))
        header.addWidget(self.segments, 0, Qt.AlignmentFlag.AlignVCenter)
        outer.addLayout(header)
        outer.addSpacing(6)
        status_row = QHBoxLayout()
        status_row.setSpacing(12)
        self.status = label("", "status")
        self.status.setWordWrap(True)
        self.status.setMinimumWidth(0)
        status_row.addWidget(self.status, 1)
        self.details_button = QPushButton("see Details")
        self.details_button.setObjectName("link")
        self.details_button.clicked.connect(lambda: self.set_view(False))
        status_row.addWidget(self.details_button)
        self.badge = label("", "badge")
        self.badge.setFixedHeight(24)
        status_row.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignTop)
        outer.addLayout(status_row)
        outer.addSpacing(14)
        self.progress = QProgressBar()
        self.progress.setRange(0, max(1, len(self.paths)))
        self.progress.setFixedHeight(3)
        self.progress.setTextVisible(False)
        self.progress.setAccessibleName("Files processed")
        outer.addWidget(self.progress)
        self.separator = QFrame()
        self.separator.setFixedHeight(1)
        outer.addWidget(self.separator)
        self.table = QTableView()
        self.table.setAccessibleName("Per-file token counts")
        self.model = FileModel(self)
        self.table.setModel(self.model)
        self.table.setItemDelegate(FileDelegate(self))
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setMinimumSectionSize(1)
        self.table.horizontalHeader().setMinimumSectionSize(40)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionsClickable(False)
        self.table.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.table.horizontalHeader().sectionResized.connect(self.column_resized)
        self.table.doubleClicked.connect(lambda index: self.set_view(False))
        outer.addWidget(self.table, 1)
        outer.addSpacing(12)
        self.details_footer = QWidget()
        foot = QHBoxLayout(self.details_footer)
        foot.setContentsMargins(0, 0, 0, 0)
        self.explanation = label(
            "Counts extracted text, not the full cost of an AI attachment.", "note"
        )
        self.explanation.setWordWrap(True)
        foot.addWidget(self.explanation, 1)
        self.github = QPushButton(f"CheckTokens {__version__} · GitHub")
        self.github.setObjectName("github")
        self.github.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://github.com/NivailoPL/checktokens"))
        )
        foot.addWidget(self.github)
        outer.addWidget(self.details_footer)
        self.footer_space = QWidget()
        self.footer_space.setFixedHeight(18)
        outer.addWidget(self.footer_space)
        self.buttons = QHBoxLayout()
        self.buttons.setSpacing(12)
        self.note = label("ⓘ  extracted text only", "note")
        self.note.setToolTip("Right-click the background to choose Dark or Light appearance.")
        self.buttons.addWidget(self.note)
        self.buttons.addStretch(1)
        self.copy_button = QPushButton("Copy")
        self.copy_button.setMinimumWidth(76)
        self.copy_button.clicked.connect(self.on_copy)
        self.buttons.addWidget(self.copy_button)
        self.buttons.addStretch(0)
        self.action = QPushButton("Cancel")
        self.action.setObjectName("primary")
        self.action.setMinimumWidth(90)
        self.action.clicked.connect(self.on_action)
        self.buttons.addWidget(self.action)
        outer.addLayout(self.buttons)

    def apply_theme(self, theme, *, save=False):
        self.theme = theme
        self.colors = PALETTES[theme]
        self.setStyleSheet(stylesheet(self.colors))
        self.separator.setStyleSheet(f"background: {self.colors['line']};")
        palette = self.palette()
        for role, key in [
            (QPalette.ColorRole.Window, "background"),
            (QPalette.ColorRole.Base, "table"),
            (QPalette.ColorRole.Text, "text"),
            (QPalette.ColorRole.WindowText, "text"),
        ]:
            palette.setColor(role, QColor(self.colors[key]))
        self.setPalette(palette)
        if save:
            QSettings("CheckTokens", "Appearance").setValue("theme", theme)
        if hasattr(self, "timer"):
            self.refresh()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addSection("Appearance")
        group = QActionGroup(menu)
        group.setExclusive(True)
        for theme in PALETTES:
            action = menu.addAction(theme.title())
            action.setCheckable(True)
            action.setChecked(theme == self.theme)
            group.addAction(action)
            action.triggered.connect(
                lambda checked, value=theme: self.apply_theme(value, save=True)
            )
        menu.exec(event.globalPos())

    def result_at(self, row):
        return self.results[row] if row < len(self.results) else None

    def messages(self, result):
        if result is None:
            return []
        return ([(result.error, "red")] if result.error else []) + [
            (note, "orange") for note in result.warnings
        ]

    def work(self):
        emitted = 0
        try:
            for result in run_batch(self.paths, self.cancel_event):
                self.events.put(result)
                emitted += 1
        except Exception as exc:
            for path in self.paths[emitted:]:
                self.events.put(Result(path, error=f"Processing failed: {exc}"))
        finally:
            self.events.put(None)

    def tick(self):
        changed = False
        while True:
            try:
                result = self.events.get_nowait()
            except queue.Empty:
                break
            changed = True
            if result is None:
                self.finished = True
            else:
                self.results.append(result)
        if self.closing:
            if self.thread is None or not self.thread.is_alive():
                self.timer.stop()
                self.close()
            return
        if changed:
            self.refresh()
        if self.finished:
            self.timer.stop()

    def refresh(self):
        self.report = report = make_report(self.results)
        n, counted = len(self.paths), report["counted_files"]
        failed = sum(r.error is not None for r in self.results)
        warnings = sum(len(r.warnings) for r in self.results)
        cancelled, running = self.cancel_event.is_set(), not self.finished
        partial = not report["complete"] or cancelled or len(self.results) < n
        tone = "red" if failed else "orange" if warnings or cancelled else "green"
        badge = f"{failed} failed · {warnings} {'warning' if warnings == 1 else 'warnings'}"
        status = f"{counted} of {n} files counted · {badge}"
        if cancelled:
            badge = f"Cancelled · {counted} of {n} counted"
            status = "Cancelling…" if running else badge
        elif running:
            status = f"o200k_base · counting {min(len(self.results) + 1, n)} of {n}…"
        elif counted == 0:
            badge = f"All {n} {'file' if n == 1 else 'files'} failed"
            status = "No files could be counted."
        elif not partial:
            badge = f"All {n} {'file' if n == 1 else 'files'} counted"
            status = f"o200k_base · {n} {'file' if n == 1 else 'files'}, all counted"
        if not self.simple and not running and not cancelled and counted:
            status = f"o200k_base · sum of {counted} per-file counts"
            if counted < n:
                status += f", {n - counted} not counted"
        self.total.setText(f"{report['total_tokens']:,}")
        total_color = self.colors["secondary"] if running or not counted else self.colors["accent"]
        self.total.setStyleSheet(f"color: {total_color};")
        self.unit.setText(
            "tokens so far"
            if running
            else "tokens · partial"
            if not self.simple and partial and counted
            else "tokens"
        )
        self.status.setText(status)
        self.status.setStyleSheet(
            f"color: {self.colors[tone] if partial and not running else self.colors['secondary']};"
        )
        self.badge.setText(badge)
        badge_style = (
            f"color: {self.colors[tone]}; background: {self.colors[tone + '_bg']};"
            "border: none; border-radius: 11px; padding: 3px 9px; font-size: 11px;"
        )
        self.badge.setStyleSheet(badge_style)
        self.partial_badge.setStyleSheet(badge_style)
        self.partial_badge.setVisible(self.simple and partial and not running and bool(counted))
        self.badge.setVisible(not self.simple and not running)
        self.details_button.setVisible(self.simple and partial and not running)
        self.progress.setValue(len(self.results))
        self.progress.setVisible(running)
        self.separator.setVisible(self.simple and not running)
        self.copy_button.setEnabled(bool(self.results))
        self.action.setText("Close" if self.finished else "Cancel")
        self.action.setEnabled(self.finished or not cancelled)
        self.action.setDefault(self.finished)
        self.model.dataChanged.emit(self.model.index(0, 0), self.model.index(max(0, n - 1), 2))
        self.resize_rows()
        self.fit_total()
        self.table.viewport().update()

    def set_view(self, simple):
        self.simple = simple
        self.simple_button.setChecked(simple)
        self.details_toggle.setChecked(not simple)
        (self.simple_button if simple else self.details_toggle).setFocus()
        self.table.setProperty("simple", simple)
        self.table.style().unpolish(self.table)
        self.table.style().polish(self.table)
        self.table.horizontalHeader().setVisible(not simple)
        self.table.setColumnHidden(1, simple)
        self.table.setColumnWidth(1, 86)
        self.table.setColumnWidth(2, 84)
        self.note.setVisible(simple)
        self.details_footer.setVisible(not simple)
        self.footer_space.setVisible(not simple)
        self.buttons.setStretch(1, 1 if simple else 0)
        self.buttons.setStretch(3, 0 if simple else 1)
        self.copy_button.setText("Copy" if simple else "Copy results")
        self.setMinimumSize(560, 185 if simple else 380)
        self.resize(
            560 if simple else 680, 176 + 28 * min(max(len(self.paths), 1), 8) if simple else 500
        )
        self.refresh()

    def resize_rows(self, *args):
        self.table.resizeRowsToContents()

    def column_resized(self, section, old_width, new_width):
        if section == 0:
            # Qt emits sectionResized before columnWidth() exposes the new width.
            self.file_column_width = new_width
            self.resize_rows()

    def fit_total(self):
        size = 36 if self.simple else 38
        available = (
            self.width() - 40 - self.segments.sizeHint().width() - self.unit.sizeHint().width() - 32
        )
        if not self.partial_badge.isHidden():
            available -= self.partial_badge.sizeHint().width() + 8
        while (
            size > 18
            and QFontMetrics(ui_font(size, True)).horizontalAdvance(self.total.text()) > available
        ):
            size -= 1
        self.total.setStyleSheet(
            self.total.styleSheet().split("font-size:")[0]
            + f"font-size: {size}px; font-weight: 600;"
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "segments"):
            self.fit_total()

    def on_copy(self):
        if self.results:
            results = self.results + [
                Result(p, error="Not counted yet.") for p in self.paths[len(self.results) :]
            ]
            QApplication.clipboard().setText(format_report(results))

    def on_action(self):
        if self.finished:
            self.close()
        else:
            self.cancel_event.set()
            self.refresh()

    def closeEvent(self, event):
        self.cancel_event.set()
        if self.thread is not None and self.thread.is_alive():
            self.closing = True
            self.hide()
            self.timer.start()
            event.ignore()
        else:
            self.timer.stop()
            event.accept()


def show_results(paths):
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    app.setFont(ui_font(13))
    if not paths:
        paths, _ = QFileDialog.getOpenFileNames(None, "Choose files to count", "", "All files (*)")
        if not paths:
            return 0
    window = ResultsWindow(paths)
    window.show()
    try:
        return app.exec()
    finally:
        window.cancel_event.set()
        if window.thread is not None:
            window.thread.join()
