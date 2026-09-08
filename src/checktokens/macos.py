"""Native Simple and Details result views; document work stays off the UI thread."""

import math
import queue
import threading

import AppKit as A
import Foundation as F
import objc

from . import __version__, mark
from .core import Result, display_names, format_report, make_report
from .runner import run_batch


def font(size, weight=A.NSFontWeightRegular, digits=False):
    factory = (
        A.NSFont.monospacedDigitSystemFontOfSize_weight_
        if digits
        else A.NSFont.systemFontOfSize_weight_
    )
    return factory(size, weight)


def srgb(rgb, alpha=1.0):
    red, green, blue = rgb
    return A.NSColor.colorWithSRGBRed_green_blue_alpha_(red / 255, green / 255, blue / 255, alpha)


def mark_image(size):
    """The app mark, drawn rather than bundled, so it stays sharp on any display."""

    def draw(rect):
        unit = size / 100
        radius = mark.CORNER * unit
        tile = A.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            ((0, 0), (size, size)), radius, radius
        )
        A.NSGradient.alloc().initWithStartingColor_endingColor_(
            srgb(mark.TOP), srgb(mark.BOTTOM)
        ).drawInBezierPath_angle_(tile, 90)
        A.NSGraphicsContext.saveGraphicsState()
        tile.addClip()
        A.NSGradient.alloc().initWithStartingColor_endingColor_(
            srgb((255, 255, 255), mark.GLOSS_ALPHA), srgb((255, 255, 255), 0)
        ).drawInRect_angle_(((0, 0), (size, mark.GLOSS_HEIGHT * unit)), 90)
        A.NSGraphicsContext.restoreGraphicsState()
        for x, y, width, height, accent in mark.blocks(size):
            srgb(mark.ACCENT if accent else mark.PAPER).setFill()
            corner = height * unit / 2
            A.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                ((x * unit, y * unit), (width * unit, height * unit)), corner, corner
            ).fill()
        return True

    return A.NSImage.imageWithSize_flipped_drawingHandler_((size, size), True, draw)


def text_attributes(size, color, *, digits=False, align=A.NSTextAlignmentLeft, wrap=False):
    paragraph = A.NSMutableParagraphStyle.alloc().init()
    paragraph.setAlignment_(align)
    paragraph.setLineBreakMode_(
        A.NSLineBreakByWordWrapping if wrap else A.NSLineBreakByTruncatingMiddle
    )
    return {
        A.NSFontAttributeName: font(size, digits=digits),
        A.NSForegroundColorAttributeName: color,
        A.NSParagraphStyleAttributeName: paragraph,
    }


def message_height(message, width):
    rect = F.NSString.stringWithString_(message).boundingRectWithSize_options_attributes_(
        (max(1, width), 1e6),
        A.NSStringDrawingUsesLineFragmentOrigin,
        text_attributes(11, A.NSColor.labelColor(), wrap=True),
    )
    return max(18, math.ceil(rect.size.height) + 4)


class FlippedView(A.NSView):
    def isFlipped(self):
        return True


class ContentView(FlippedView):
    def drawRect_(self, rect):
        A.NSColor.windowBackgroundColor().setFill()
        A.NSRectFill(rect)


class BadgeView(FlippedView):
    def setStringValue_(self, value):
        self.text = value
        self.setAccessibilityLabel_(value)
        self.setNeedsDisplay_(True)

    def setTextColor_(self, color):
        self.color = color
        self.setNeedsDisplay_(True)

    def sizeToFit(self):
        size = F.NSString.stringWithString_(self.text).sizeWithAttributes_(
            {A.NSFontAttributeName: font(11, digits=True)}
        )
        self.setFrameSize_((size.width + 16 if self.text else 0, 22))

    def drawRect_(self, rect):
        if not self.text:
            return
        self.color.colorWithAlphaComponent_(0.10).setFill()
        A.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(self.bounds(), 10, 10).fill()
        F.NSString.stringWithString_(self.text).drawInRect_withAttributes_(
            ((8, 4), (self.bounds().size.width - 16, 16)),
            text_attributes(11, self.color, digits=True),
        )


class ResultsWindow(A.NSWindow):
    def cancelOperation_(self, sender):
        self.delegate().action_(sender)

    def performKeyEquivalent_(self, event):
        if event.modifierFlags() & A.NSEventModifierFlagCommand:
            key = event.charactersIgnoringModifiers().lower()
            if key == "c":
                self.delegate().copy_(self)
                return True
            if key in ("1", "2"):
                self.delegate().set_view(key == "1")
                return True
        return objc.super(ResultsWindow, self).performKeyEquivalent_(event)


class ShareView(FlippedView):
    def drawRect_(self, rect):
        width = max(0, self.bounds().size.width - 8)
        track = ((4, 14), (width, 5))
        A.NSColor.separatorColor().setFill()
        A.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(track, 2.5, 2.5).fill()
        if self.tokens > 0 and self.total > 0:
            A.NSColor.controlAccentColor().setFill()
            fill = ((4, 14), (min(width, max(3, round(width * self.tokens / self.total))), 5))
            A.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(fill, 2.5, 2.5).fill()


class FileRowView(A.NSTableRowView):
    def drawBackgroundInRect_(self, rect):
        if self.problem_color is not None:
            self.problem_color.colorWithAlphaComponent_(0.06).setFill()
            A.NSRectFillUsingOperation(rect, A.NSCompositingOperationSourceOver)


class FileTableSource(F.NSObject):
    @objc.python_method
    def setup(self, controller, simple):
        self.controller = controller
        self.simple = simple

    def numberOfRowsInTableView_(self, table):
        return len(self.controller.paths)

    def tableView_heightOfRow_(self, table, row):
        if self.simple:
            return 27.0
        result = self.controller.result_at(row)
        width = table.tableColumns()[0].width() - 30
        return 34.0 + sum(message_height(m, width) for m, _ in self.controller.messages(result))

    def tableView_rowViewForRow_(self, table, row):
        view = FileRowView.alloc().init()
        view.problem_color = self.controller.problem_color(self.controller.result_at(row))
        return view

    def tableView_viewForTableColumn_row_(self, table, column, row):
        c = self.controller
        result = c.result_at(row)
        width = column.width()
        height = self.tableView_heightOfRow_(table, row)
        view = FlippedView.alloc().initWithFrame_(((0, 0), (width, height)))
        view.setToolTip_(c.paths[row])
        identifier = str(column.identifier())
        if identifier == "share":
            view = ShareView.alloc().initWithFrame_(((0, 0), (width, height)))
            view.tokens = (result.tokens or 0) if result else 0
            view.total = c.report["total_tokens"]
            return view
        if identifier == "tokens":
            value = (
                f"{result.tokens:,}"
                if result and result.tokens is not None
                else (
                    "failed"
                    if result
                    else ("counting…" if row == len(c.results) and not c.finished else "waiting")
                )
            )
            color = (
                c.problem_color(result)
                if result and result.tokens is None
                else A.NSColor.labelColor()
            )
            if result is None:
                color = (
                    A.NSColor.secondaryLabelColor()
                    if row == len(c.results)
                    else A.NSColor.tertiaryLabelColor()
                )
            label = c.label(view, value, 13, color, digits=True)
            label.setAlignment_(A.NSTextAlignmentRight)
            label.setFrame_(((0, 5 if self.simple else 8), (width - 4, 19)))
            return view
        color = (
            A.NSColor.labelColor()
            if result or row == len(c.results)
            else A.NSColor.tertiaryLabelColor()
        )
        offset = 20 if self.simple else 25
        problem = c.problem_color(result)
        if problem:
            symbol = "xmark.circle" if result.error else "exclamationmark.triangle"
            icon = A.NSImageView.alloc().initWithFrame_(((1, 6 if self.simple else 9), (15, 15)))
            icon.setImage_(
                A.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
                    symbol, "Error" if result.error else "Warning"
                )
            )
            icon.setContentTintColor_(problem)
            view.addSubview_(icon)
        elif not self.simple:
            icon = A.NSImageView.alloc().initWithFrame_(((1, 9), (15, 15)))
            icon.setImage_(c.icons[row])
            view.addSubview_(icon)
        name = c.label(view, c.names[row], 13, color)
        name.setFrame_(((offset, 5 if self.simple else 8), (max(1, width - offset - 4), 19)))
        if not self.simple:
            y = 34
            for message, message_color in c.messages(result):
                h = message_height(message, width - 30)
                label = c.label(view, message, 11, message_color)
                label.setMaximumNumberOfLines_(0)
                label.setLineBreakMode_(A.NSLineBreakByWordWrapping)
                label.setFrame_(((25, y), (max(1, width - 30), h)))
                y += h
        return view


class ResultsController(F.NSObject):
    @objc.python_method
    def setup(self, paths):
        self.paths = list(paths)
        self.results = []
        self.names = display_names([Result(p) for p in paths])
        self.icons = [A.NSWorkspace.sharedWorkspace().iconForFile_(p) for p in paths]
        self.events = queue.Queue()
        self.cancel_event = threading.Event()
        self.finished = False
        self.closing = False
        self.simple_height = 157 + 27 * min(max(len(paths), 1), 8)
        self.simple = True
        self.build_window()
        self.refresh()
        self.timer = F.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.1, self, "tick:", None, True
        )
        self.thread = threading.Thread(target=self.work, daemon=False)
        self.thread.start()
        self.window.center()
        self.window.makeKeyAndOrderFront_(None)
        A.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)

    @objc.python_method
    def label(self, parent, text, size, color=None, *, digits=False, weight=A.NSFontWeightRegular):
        label = A.NSTextField.labelWithString_(text)
        label.setFont_(font(size, weight, digits))
        label.setTextColor_(color if color is not None else A.NSColor.labelColor())
        label.setLineBreakMode_(A.NSLineBreakByTruncatingMiddle)
        parent.addSubview_(label)
        return label

    @objc.python_method
    def button(self, parent, title, selector):
        button = A.NSButton.alloc().init()
        button.setTitle_(title)
        button.setBezelStyle_(A.NSBezelStyleRounded)
        button.setTarget_(self)
        button.setAction_(selector)
        parent.addSubview_(button)
        return button

    @objc.python_method
    def build_window(self):
        self.window = ResultsWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            ((0, 0), (520, self.simple_height)),
            A.NSWindowStyleMaskTitled
            | A.NSWindowStyleMaskClosable
            | A.NSWindowStyleMaskMiniaturizable,
            A.NSBackingStoreBuffered,
            False,
        )
        self.window.setTitle_("CheckTokens")
        self.window.setReleasedWhenClosed_(False)
        self.window.setDelegate_(self)
        self.views = [self.build_view(True), self.build_view(False)]
        self.views[1]["root"].setHidden_(True)
        self.layout()

    @objc.python_method
    def build_view(self, simple):
        root = ContentView.alloc().initWithFrame_(self.window.contentView().bounds())
        self.window.contentView().addSubview_(root)
        v = {"root": root, "simple": simple}
        segment = A.NSSegmentedControl.alloc().init()
        segment.setSegmentCount_(2)
        for i, title in enumerate(("Simple", "Details")):
            segment.setLabel_forSegment_(title, i)
            segment.setWidth_forSegment_(62, i)
        segment.setTrackingMode_(A.NSSegmentSwitchTrackingSelectOne)
        segment.setSelectedSegment_(0 if simple else 1)
        segment.setTarget_(self)
        segment.setAction_("changeView:")
        segment.sizeToFit()
        root.addSubview_(segment)
        v["segment"] = segment
        v["total"] = self.label(
            root, "0", 36 if simple else 38, digits=True, weight=A.NSFontWeightBold
        )
        v["unit"] = self.label(root, "tokens", 16, A.NSColor.secondaryLabelColor())
        v["badge"] = BadgeView.alloc().init()
        v["badge"].text = ""
        v["badge"].color = A.NSColor.secondaryLabelColor()
        root.addSubview_(v["badge"])
        v["status"] = self.label(root, "", 12, A.NSColor.secondaryLabelColor())
        v["details"] = self.button(root, "see Details", "showDetails:")
        v["details"].setBordered_(False)
        v["details"].setContentTintColor_(A.NSColor.linkColor())
        v["progress"] = A.NSProgressIndicator.alloc().init()
        v["progress"].setStyle_(A.NSProgressIndicatorStyleBar)
        v["progress"].setIndeterminate_(False)
        v["progress"].setMinValue_(0)
        v["progress"].setMaxValue_(max(1, len(self.paths)))
        root.addSubview_(v["progress"])
        v["separator"] = A.NSBox.alloc().init()
        v["separator"].setBoxType_(A.NSBoxSeparator)
        root.addSubview_(v["separator"])
        scroll = A.NSScrollView.alloc().init()
        scroll.setHasVerticalScroller_(True)
        scroll.setAutohidesScrollers_(True)
        scroll.setDrawsBackground_(not simple)
        scroll.setBackgroundColor_(A.NSColor.controlBackgroundColor())
        table = A.NSTableView.alloc().init()
        table.setStyle_(A.NSTableViewStylePlain)
        table.setBackgroundColor_(
            A.NSColor.clearColor() if simple else A.NSColor.controlBackgroundColor()
        )
        table.setIntercellSpacing_((0, 0))
        table.setSelectionHighlightStyle_(A.NSTableViewSelectionHighlightStyleNone)
        table.setAllowsColumnReordering_(False)
        table.setColumnAutoresizingStyle_(A.NSTableViewFirstColumnOnlyAutoresizingStyle)
        columns = (
            [("file", "FILE", 300), ("tokens", "TOKENS", 78)]
            if simple
            else [("file", "FILE", 400), ("share", "SHARE", 86), ("tokens", "TOKENS", 78)]
        )
        for key, title, width in columns:
            column = A.NSTableColumn.alloc().initWithIdentifier_(key)
            column.setTitle_(title)
            column.setWidth_(width)
            column.setMinWidth_(40 if key == "file" else width)
            column.setResizingMask_(
                A.NSTableColumnAutoresizingMask if key == "file" else A.NSTableColumnNoResizing
            )
            column.headerCell().setFont_(font(11, A.NSFontWeightSemibold))
            if key == "tokens":
                column.headerCell().setAlignment_(A.NSTextAlignmentRight)
            table.addTableColumn_(column)
        if simple:
            table.setHeaderView_(None)
        source = FileTableSource.alloc().init()
        source.setup(self, simple)
        table.setDataSource_(source)
        table.setDelegate_(source)
        scroll.setDocumentView_(table)
        root.addSubview_(scroll)
        v.update(table=table, scroll=scroll, source=source)
        v["note"] = self.label(
            root,
            "ⓘ  extracted text only"
            if simple
            else "Counts extracted text, not the full cost of an AI attachment.",
            11,
            A.NSColor.tertiaryLabelColor(),
        )
        v["note"].setMaximumNumberOfLines_(2)
        v["note"].setLineBreakMode_(A.NSLineBreakByWordWrapping)
        v["note"].setToolTip_("Counts extracted text, not the full cost of an AI attachment.")
        v["version"] = self.button(root, f"CheckTokens {__version__} · GitHub", "openGitHub:")
        v["version"].setBordered_(False)
        v["version"].setFont_(font(11))
        v["version"].setImage_(mark_image(14))
        v["version"].setImagePosition_(A.NSImageLeft)
        v["version"].setImageScaling_(A.NSImageScaleNone)
        v["version"].setImageHugsTitle_(True)
        v["version"].setHidden_(simple)
        v["copy"] = self.button(root, "Copy" if simple else "Copy results", "copy:")
        v["copy"].setKeyEquivalent_("c")
        v["copy"].setKeyEquivalentModifierMask_(A.NSEventModifierFlagCommand)
        v["action"] = self.button(root, "Cancel", "action:")
        return v

    @objc.python_method
    def layout(self):
        if not hasattr(self, "views"):
            return
        w, h = self.window.contentView().bounds().size
        for v in self.views:
            simple = v["simple"]
            width, height = (520, self.simple_height) if simple else (w, h)
            v["root"].setFrame_(((0, 0), (width, height)))
            margin = 18 if simple else 20
            v["total"].setFrame_(((margin, 16 if simple else 18), (200, 46)))
            segment_size = v["segment"].frame().size
            v["segment"].setFrameOrigin_(
                (
                    width - margin - segment_size.width,
                    (16 if simple else 18) + (46 - segment_size.height) / 2,
                )
            )
            v["status"].setFrame_(((margin, 60 if simple else 66), (width - 2 * margin, 18)))
            v["details"].setFrame_(((width - 110, 58), (92, 22)))
            v["progress"].setFrame_(
                ((margin, 90), (width - 2 * margin, 3))
                if simple
                else ((width - margin - 150, 72), (150, 5))
            )
            v["separator"].setFrame_(((margin, 90), (width - 2 * margin, 1)))
            v["scroll"].setFrame_(
                (
                    (margin, 97 if simple else 96),
                    (width - 2 * margin, height - 157 if simple else height - 182),
                )
            )
            v["table"].setFrameSize_(
                (v["scroll"].contentSize().width, max(1, v["scroll"].contentSize().height))
            )
            v["table"].sizeToFit()
            v["note"].setFrame_(
                (
                    (margin, height - 39 if simple else height - 76),
                    (270 if simple else width - 243, 18 if simple else 30),
                )
            )
            v["version"].setFrame_(((width - 223, height - 77), (203, 20)))
            v["copy"].setFrame_(
                ((width - 198 if simple else margin, height - 48), (82 if simple else 132, 32))
            )
            v["action"].setFrame_(
                ((width - 110 if simple else width - 130, height - 48), (92 if simple else 110, 32))
            )
            if not simple:
                v["table"].noteHeightOfRowsWithIndexesChanged_(
                    F.NSIndexSet.indexSetWithIndexesInRange_((0, len(self.paths)))
                )
        if hasattr(self, "report"):
            self.layout_header()

    @objc.python_method
    def layout_header(self):
        for v in self.views:
            width = v["root"].bounds().size.width
            badge = v["badge"]
            badge.sizeToFit()
            v["unit"].sizeToFit()
            unit_width = v["unit"].frame().size.width
            badge_width = badge.frame().size.width
            margin = 18 if v["simple"] else 20
            segment_width = v["segment"].frame().size.width
            available = width - 56 - unit_width - segment_width - 12
            if v["simple"]:
                available -= badge_width
            size = 36 if v["simple"] else 38
            while True:
                v["total"].setFont_(font(size, A.NSFontWeightBold, digits=True))
                v["total"].sizeToFit()
                if v["total"].frame().size.width <= available or size <= 18:
                    break
                size -= 1
            frame = v["total"].frame()
            unit_x = frame.origin.x + frame.size.width + 8
            v["unit"].setFrameOrigin_((unit_x, 37))
            if v["simple"]:
                badge.setFrameOrigin_((unit_x + unit_width + 8, 35))
            else:
                badge.setFrameOrigin_((width - margin - badge_width, 64))
                reserved = max(badge_width, 0 if v["progress"].isHidden() else 150)
                v["status"].setFrameSize_(
                    (
                        max(1, width - 2 * margin - (reserved + 12 if reserved else 0)),
                        v["status"].frame().size.height,
                    )
                )

    def windowDidResize_(self, notification):
        self.layout()

    def changeView_(self, sender):
        self.set_view(sender.selectedSegment() == 0)

    def showDetails_(self, sender):
        self.set_view(False)

    @objc.python_method
    def set_view(self, simple):
        if self.simple == simple:
            return
        self.simple = simple
        for v in self.views:
            v["segment"].setSelectedSegment_(0 if simple else 1)
        style = self.window.styleMask()
        self.window.setStyleMask_(
            style & ~A.NSWindowStyleMaskResizable
            if simple
            else style | A.NSWindowStyleMaskResizable
        )
        self.window.setContentMinSize_((520, self.simple_height) if simple else (520, 360))
        frame = self.window.frame()
        size = self.window.frameRectForContentRect_(
            ((0, 0), (520, self.simple_height) if simple else (640, 500))
        ).size
        self.window.setFrame_display_animate_(
            ((frame.origin.x, frame.origin.y + frame.size.height - size.height), size), True, False
        )
        self.views[0]["root"].setHidden_(not simple)
        self.views[1]["root"].setHidden_(simple)
        self.layout()
        self.refresh()

    @objc.python_method
    def result_at(self, row):
        return self.results[row] if row < len(self.results) else None

    @objc.python_method
    def problem_color(self, result):
        if result and result.error:
            return A.NSColor.systemRedColor()
        if result and result.warnings:
            return A.NSColor.systemOrangeColor()
        return None

    @objc.python_method
    def messages(self, result):
        if result is None:
            return []
        return [(w, A.NSColor.systemOrangeColor()) for w in result.warnings] + (
            [(result.error, A.NSColor.systemRedColor())] if result.error else []
        )

    @objc.python_method
    def work(self):
        try:
            for result in run_batch(self.paths, self.cancel_event):
                self.events.put(result)
        finally:
            self.events.put(None)

    def tick_(self, timer):
        changed = False
        while not self.events.empty():
            result = self.events.get_nowait()
            changed = True
            if result is None:
                self.finished = True
                self.timer.invalidate()
                break
            self.results.append(result)
        if changed:
            self.refresh()
        if self.finished and self.closing:
            self.close()

    @objc.python_method
    def refresh(self):
        self.report = report = make_report(self.results)
        n = len(self.paths)
        counted = report["counted_files"]
        failed = sum(r.error is not None for r in self.results)
        warnings = sum(len(r.warnings) for r in self.results)
        cancelled = self.cancel_event.is_set()
        running = not self.finished
        partial = not report["complete"] or cancelled
        color = A.NSColor.systemOrangeColor() if warnings else A.NSColor.systemRedColor()
        badge = f"{failed} failed · {warnings} {'warning' if warnings == 1 else 'warnings'}"
        status = f"{counted} of {n} files counted · {badge}"
        if cancelled:
            badge = f"Cancelled · {counted} of {n} counted"
            status = "Cancelling…" if running else badge
            color = A.NSColor.systemOrangeColor()
        elif running:
            badge = f"Counting {min(len(self.results) + 1, n)} of {n}…"
            status = f"{report['tokenizer']} · {badge.lower()}"
            color = A.NSColor.secondaryLabelColor()
        elif counted == 0:
            badge = f"All {n} {'file' if n == 1 else 'files'} failed"
            status = "No files could be counted."
        elif not partial:
            badge = f"All {n} {'file' if n == 1 else 'files'} counted"
            status = f"{report['tokenizer']} · {n} files, all counted"
            color = A.NSColor.systemGreenColor()
        for v in self.views:
            simple = v["simple"]
            v["total"].setStringValue_(f"{report['total_tokens']:,}")
            v["total"].setTextColor_(
                A.NSColor.secondaryLabelColor()
                if running or counted == 0
                else A.NSColor.controlAccentColor()
            )
            unit = "tokens so far" if running else "tokens"
            if not simple and partial and not running and counted:
                unit = "tokens · partial"
            v["unit"].setStringValue_(unit)
            v["badge"].setStringValue_(
                "partial"
                if simple and partial and not running and counted
                else ("" if simple or running else badge)
            )
            v["badge"].setTextColor_(color)
            detail_status = status
            if not simple and not running and not cancelled and counted:
                detail_status = f"{report['tokenizer']} · sum of {counted} per-file counts"
                if counted < n:
                    detail_status += f", {n - counted} not counted"
            v["status"].setStringValue_(detail_status)
            v["status"].setTextColor_(
                color if partial and not running else A.NSColor.secondaryLabelColor()
            )
            show_link = simple and partial and not running
            v["details"].setHidden_(not show_link)
            status_frame = v["status"].frame()
            v["status"].setFrameSize_(
                (374 if show_link else v["root"].bounds().size.width - 36, status_frame.size.height)
            )
            v["progress"].setHidden_(not running)
            v["progress"].setDoubleValue_(len(self.results))
            v["separator"].setHidden_(not simple or running)
            v["copy"].setEnabled_(bool(self.results))
            v["action"].setTitle_("Cancel" if running else "Close")
            v["action"].setKeyEquivalent_("" if running else "\r")
            v["table"].reloadData()
        self.window.setDefaultButtonCell_(
            None if running else self.views[0 if self.simple else 1]["action"].cell()
        )
        self.layout_header()

    def copy_(self, sender):
        if self.results:
            pasteboard = A.NSPasteboard.generalPasteboard()
            pasteboard.clearContents()
            pasteboard.setString_forType_(format_report(self.results), A.NSPasteboardTypeString)

    def openGitHub_(self, sender):
        A.NSWorkspace.sharedWorkspace().openURL_(
            F.NSURL.URLWithString_("https://github.com/NivailoPL/checktokens")
        )

    def action_(self, sender):
        if self.finished:
            self.close()
        else:
            self.cancel_event.set()
            self.refresh()

    def windowShouldClose_(self, sender):
        self.closing = True
        if self.finished:
            self.close()
        else:
            self.cancel_event.set()
        return False

    @objc.python_method
    def close(self):
        self.window.orderOut_(None)
        app = A.NSApplication.sharedApplication()
        app.stop_(None)
        # stop: takes effect after the next event. Wake the loop now so closing
        # never requires an extra keypress or mouse movement.
        event = A.NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(  # noqa: E501
            A.NSEventTypeApplicationDefined, (0, 0), 0, 0, 0, None, 0, 0, 0
        )
        app.postEvent_atStart_(event, True)


def show_results(paths):
    app = A.NSApplication.sharedApplication()
    app.setActivationPolicy_(A.NSApplicationActivationPolicyAccessory)
    if not paths:
        panel = A.NSOpenPanel.openPanel()
        panel.setCanChooseDirectories_(False)
        panel.setAllowsMultipleSelection_(True)
        panel.setMessage_("Select files to count their text tokens.")
        app.activateIgnoringOtherApps_(True)
        if panel.runModal() != A.NSModalResponseOK:
            return 0
        paths = [url.path() for url in panel.URLs()]
    controller = ResultsController.alloc().init()
    controller.setup(paths)
    try:
        app.run()
    finally:
        controller.cancel_event.set()
        controller.thread.join()
        controller.timer.invalidate()
    # Document errors are already shown; don't make Automator show a second error.
    return 0
