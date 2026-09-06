"""Small native result window; all parsing happens outside the UI process."""

import queue
import threading

import AppKit as A
import Foundation as F
import objc

from .core import format_report
from .runner import run_batch


class ResultsController(F.NSObject):
    @objc.python_method
    def setup(self, paths):
        self.paths = paths
        self.results = []
        self.events = queue.Queue()
        self.cancel_event = threading.Event()
        self.finished = False
        self.closing = False
        self.window = A.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            ((0, 0), (640, 460)),
            A.NSWindowStyleMaskTitled
            | A.NSWindowStyleMaskClosable
            | A.NSWindowStyleMaskMiniaturizable
            | A.NSWindowStyleMaskResizable,
            A.NSBackingStoreBuffered,
            False,
        )
        self.window.setTitle_("CheckTokens")
        self.window.setReleasedWhenClosed_(False)
        self.window.setMinSize_((480, 320))
        self.window.setDelegate_(self)
        content = self.window.contentView()
        self.status = A.NSTextField.labelWithString_(f"Counting {len(paths)} files…")
        self.status.setFrame_(((20, 421), (600, 22)))
        self.status.setAutoresizingMask_(A.NSViewWidthSizable | A.NSViewMinYMargin)
        content.addSubview_(self.status)

        scroll = A.NSScrollView.alloc().initWithFrame_(((20, 65), (600, 344)))
        scroll.setHasVerticalScroller_(True)
        scroll.setBorderType_(A.NSBezelBorder)
        scroll.setAutoresizingMask_(A.NSViewWidthSizable | A.NSViewHeightSizable)
        self.text = A.NSTextView.alloc().initWithFrame_(((0, 0), (580, 344)))
        self.text.setEditable_(False)
        self.text.setSelectable_(True)
        self.text.setFont_(A.NSFont.systemFontOfSize_(14))
        self.text.setTextContainerInset_((12, 12))
        self.text.setVerticallyResizable_(True)
        self.text.setHorizontallyResizable_(False)
        self.text.setMaxSize_((1e7, 1e7))
        self.text.setAutoresizingMask_(A.NSViewWidthSizable)
        self.text.textContainer().setWidthTracksTextView_(True)
        scroll.setDocumentView_(self.text)
        content.addSubview_(scroll)

        self.copy_button = self.button("Copy results", "copy:", (20, 18, 140, 32))
        self.copy_button.setEnabled_(False)
        self.action_button = self.button("Cancel", "action:", (510, 18, 110, 32))
        self.action_button.setAutoresizingMask_(A.NSViewMinXMargin)
        self.action_button.setKeyEquivalent_("\r")
        self.timer = F.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.1, self, "tick:", None, True
        )
        self.thread = threading.Thread(target=self.work, daemon=False)
        self.thread.start()
        self.window.center()
        self.window.makeKeyAndOrderFront_(None)
        A.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)

    @objc.python_method
    def button(self, title, selector, rect):
        button = A.NSButton.alloc().initWithFrame_(((rect[0], rect[1]), (rect[2], rect[3])))
        button.setTitle_(title)
        button.setBezelStyle_(A.NSBezelStyleRounded)
        button.setTarget_(self)
        button.setAction_(selector)
        self.window.contentView().addSubview_(button)
        return button

    @objc.python_method
    def work(self):
        try:
            for result in run_batch(self.paths, self.cancel_event):
                self.events.put(result)
        finally:
            self.events.put(None)

    def tick_(self, timer):
        while not self.events.empty():
            result = self.events.get_nowait()
            if result is None:
                self.finished = True
                self.timer.invalidate()
                self.action_button.setTitle_("Close")
                self.copy_button.setEnabled_(True)
                self.status.setStringValue_("Cancelled" if self.cancel_event.is_set() else "Done")
                if self.closing:
                    self.close()
                break
            self.results.append(result)
            self.status.setStringValue_(
                f"Processed {len(self.results)} of {len(self.paths)} files…"
            )
            self.text.setString_(format_report(self.results))

    def copy_(self, sender):
        pasteboard = A.NSPasteboard.generalPasteboard()
        pasteboard.clearContents()
        pasteboard.setString_forType_(format_report(self.results), A.NSPasteboardTypeString)

    def action_(self, sender):
        if self.finished:
            self.close()
        else:
            self.cancel_event.set()
            self.status.setStringValue_("Cancelling…")

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
        A.NSApplication.sharedApplication().stop_(None)


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
