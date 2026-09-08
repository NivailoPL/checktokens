"""Accessible Qt model and painted file rows, including inline extraction notes."""

import html

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QTextLayout, QTextOption
from PySide6.QtWidgets import QStyle, QStyledItemDelegate


def ui_font(size, bold=False):
    font = QFont("Segoe UI")
    font.setPixelSize(size)
    font.setWeight(QFont.Weight.DemiBold if bold else QFont.Weight.Normal)
    return font


def wrapped(text, width):
    layout = QTextLayout(text, ui_font(11))
    option = QTextOption()
    option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
    layout.setTextOption(option)
    layout.beginLayout()
    height = 0
    while True:
        line = layout.createLine()
        if not line.isValid():
            break
        line.setLineWidth(max(1, width))
        line.setPosition(QPointF(0, height))
        height += line.height()
    layout.endLayout()
    return layout, max(16, height) + 4


class FileModel(QAbstractTableModel):
    def __init__(self, window):
        super().__init__(window)
        self.window = window

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.window.paths)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else 3

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        w = self.window
        row, column = index.row(), index.column()
        result = w.result_at(row)
        if role == Qt.ItemDataRole.ToolTipRole:
            lines = [w.paths[row]]
            if result:
                if result.encoding:
                    lines.append(f"Encoding: {result.encoding}")
                lines.extend(m for m, _ in w.messages(result))
            return "<br>".join(html.escape(line) for line in lines)
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.AccessibleTextRole):
            if column == 0:
                text = w.names[row]
                if role == Qt.ItemDataRole.AccessibleTextRole and result:
                    text += ". " + ". ".join(m for m, _ in w.messages(result))
                return text
            if column == 1:
                total = w.report["total_tokens"]
                return f"{100 * (result.tokens or 0) / total:.1f}%" if result and total else "0%"
            if result:
                return f"{result.tokens:,}" if result.tokens is not None else "failed"
            return "counting…" if row == len(w.results) and not w.finished else "waiting"
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal:
            if role == Qt.ItemDataRole.DisplayRole:
                return ("FILE", "SHARE", "TOKENS")[section]
            if role == Qt.ItemDataRole.TextAlignmentRole:
                return Qt.AlignmentFlag.AlignRight if section == 2 else Qt.AlignmentFlag.AlignLeft
        return None


class FileDelegate(QStyledItemDelegate):
    def __init__(self, window):
        super().__init__(window.table)
        self.window = window

    def sizeHint(self, option, index):
        w = self.window
        height = 28 if w.simple else 34
        if not w.simple:
            width = w.file_column_width - 30
            height += sum(wrapped(m, width)[1] for m, _ in w.messages(w.result_at(index.row())))
        return QSize(50, round(height))

    def paint(self, painter, option, index):
        w = self.window
        c = w.colors
        row, column = index.row(), index.column()
        result = w.result_at(row)
        error = bool(result and result.error)
        warning = bool(result and result.warnings)
        color = c["red"] if error else c["orange"] if warning else c["text"]
        painter.save()
        painter.setClipRect(option.rect)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if error or warning:
            painter.fillRect(option.rect, QColor(c["error_bg"] if error else c["warning_bg"]))
        elif option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(c["selection"]))
        rect = QRectF(option.rect)
        top_height = 28 if w.simple else 34
        top = QRectF(rect.x(), rect.y(), rect.width(), top_height)
        painter.setFont(ui_font(13))
        if column == 1:
            track = QRectF(rect.x() + 5, rect.y() + 15, max(0, rect.width() - 12), 5)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(c["track"]))
            painter.drawRoundedRect(track, 2.5, 2.5)
            total = w.report["total_tokens"]
            if result and result.tokens and total:
                fill = QRectF(track)
                fill.setWidth(min(track.width(), max(3, track.width() * result.tokens / total)))
                painter.setBrush(QColor(c["accent"]))
                painter.drawRoundedRect(fill, 2.5, 2.5)
        elif column == 2:
            painter.setPen(QColor(c["red"] if error else c["text"] if result else c["secondary"]))
            painter.drawText(
                top.adjusted(0, 0, -5, 0),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                str(index.data()),
            )
        else:
            if error or warning:
                x, y = rect.x() + 8, rect.y() + top_height / 2
                painter.setPen(QPen(QColor(color), 1.4))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(QPointF(x, y), 5.5, 5.5)
                if error:
                    painter.drawLine(QPointF(x - 2, y - 2), QPointF(x + 2, y + 2))
                    painter.drawLine(QPointF(x + 2, y - 2), QPointF(x - 2, y + 2))
                else:
                    painter.drawLine(QPointF(x, y - 3), QPointF(x, y))
                    painter.drawPoint(QPointF(x, y + 2.5))
            elif not w.simple:
                w.file_icon.paint(painter, int(rect.x() + 1), int(rect.y() + 9), 14, 16)
            offset = 22 if w.simple else 26
            name_rect = top.adjusted(offset, 0, -6, 0)
            painter.setPen(QColor(c["text"] if result else c["secondary"]))
            name = painter.fontMetrics().elidedText(
                w.names[row], Qt.TextElideMode.ElideMiddle, int(name_rect.width())
            )
            painter.drawText(
                name_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name
            )
            if not w.simple:
                y = rect.y() + top_height
                for message, tone in w.messages(result):
                    layout, height = wrapped(message, max(1, rect.width() - 30))
                    painter.setPen(QColor(c[tone]))
                    layout.draw(painter, QPointF(rect.x() + 26, y))
                    y += height
        painter.restore()
