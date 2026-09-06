"""Exercise real AppKit views without launching document workers or changing the clipboard."""

import queue
import sys
import threading

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="AppKit requires macOS")


@pytest.fixture
def controller():
    import AppKit as A

    from checktokens.core import Result, display_names
    from checktokens.macos import ResultsController

    app = A.NSApplication.sharedApplication()
    app.setActivationPolicy_(A.NSApplicationActivationPolicyAccessory)
    created = []

    def create(paths):
        c = ResultsController.alloc().init()
        c.paths = paths
        c.results = []
        c.names = display_names([Result(p) for p in paths])
        c.icons = [A.NSWorkspace.sharedWorkspace().iconForFile_(p) for p in paths]
        c.events = queue.Queue()
        c.cancel_event = threading.Event()
        c.finished = False
        c.closing = False
        c.simple_height = 157 + 27 * min(max(len(paths), 1), 8)
        c.simple = True
        c.build_window()
        c.refresh()
        created.append(c)
        return c

    yield create
    for c in created:
        c.window.setDelegate_(None)
        c.window.orderOut_(None)


@pytest.mark.parametrize("count,height", [(1, 184), (8, 373), (60, 373)])
def test_simple_size_and_all_pending_rows(controller, count, height):
    import AppKit as A

    c = controller([f"/tmp/file-{i}.txt" for i in range(count)])
    assert c.window.contentView().bounds().size.height == height
    assert not c.window.styleMask() & A.NSWindowStyleMaskResizable
    assert c.views[0]["table"].numberOfRows() == count
    if count <= 8:
        assert c.views[0]["table"].frame().size.height <= c.views[0]["scroll"].contentSize().height
    assert not c.views[0]["copy"].isEnabled()
    assert c.window.defaultButtonCell() is None
    assert c.views[0]["action"].keyEquivalent() == ""


def test_switch_preserves_top_left_and_results(controller):
    import AppKit as A

    from checktokens.core import Result

    c = controller(["/tmp/a.md"])
    c.results = [Result(c.paths[0], 12)]
    c.finished = True
    c.refresh()
    before = c.window.frame()
    c.set_view(False)
    after = c.window.frame()
    assert before.origin.x == after.origin.x
    assert before.origin.y + before.size.height == after.origin.y + after.size.height
    assert c.window.contentView().bounds().size == (640, 500)
    assert c.window.styleMask() & A.NSWindowStyleMaskResizable
    assert c.views[1]["total"].stringValue() == "12"
    assert c.window.defaultButtonCell() == c.views[1]["action"].cell()
    c.set_view(True)
    assert c.window.contentView().bounds().size == (520, 184)


def test_partial_results_copy_and_escape(controller):
    from checktokens.core import Result

    c = controller(["/tmp/a.md", "/tmp/b.md"])
    c.results = [Result(c.paths[0], 42)]
    c.refresh()
    assert all(v["copy"].isEnabled() for v in c.views)
    assert all(v["action"].keyEquivalent() == "" for v in c.views)
    c.window.cancelOperation_(None)
    assert c.cancel_event.is_set()
    assert c.views[0]["total"].stringValue() == "42"
    c.finished = True
    c.refresh()
    assert c.views[1]["badge"].text == "Cancelled · 1 of 2 counted"
    assert c.views[0]["copy"].isEnabled()


def test_warnings_keep_tokens_and_wrap_when_narrowed(controller):
    from checktokens.core import Result

    c = controller(["/first/a.md", "/second/a.md"])
    message = "A long diagnostic that must remain readable when the window narrows. " * 5
    c.results = [Result(c.paths[0], 42, warnings=[message]), Result(c.paths[1], error="Missing.")]
    c.finished = True
    c.set_view(False)
    assert c.names == c.paths
    table = c.views[1]["table"]
    source = c.views[1]["source"]
    row = source.tableView_viewForTableColumn_row_(table, table.tableColumns()[2], 0)
    assert row.subviews()[0].stringValue() == "42"
    wide = source.tableView_heightOfRow_(table, 0)
    c.window.setContentSize_((520, 360))
    c.layout()
    narrow = source.tableView_heightOfRow_(table, 0)
    assert narrow > wide > 52
    assert c.views[0]["details"].isHidden() is False


def test_zero_success_is_distinct_from_all_failed(controller):
    from checktokens.core import Result

    c = controller(["/tmp/empty.txt"])
    c.results = [Result(c.paths[0], 0)]
    c.finished = True
    c.refresh()
    assert c.views[1]["badge"].text == "All 1 file counted"
    c.results = [Result(c.paths[0], error="Missing.")]
    c.refresh()
    assert c.views[1]["badge"].text == "All 1 file failed"
    assert c.views[0]["total"].stringValue() == "0"


def test_large_total_does_not_overlap_status_badge(controller):
    from checktokens.core import Result

    c = controller(["/tmp/large.txt"])
    c.results = [Result(c.paths[0], 1234567890, warnings=["Incomplete text."])]
    c.finished = True
    c.set_view(False)
    c.window.setContentSize_((520, 360))
    c.layout()
    v = c.views[1]
    unit = v["unit"].frame()
    badge = v["badge"].frame()
    assert unit.origin.x + unit.size.width <= badge.origin.x


def test_queue_completion_updates_both_views(controller):
    import Foundation as F

    from checktokens.core import Result

    c = controller(["/tmp/a.txt", "/tmp/b.txt"])
    c.timer = F.NSTimer.timerWithTimeInterval_target_selector_userInfo_repeats_(
        100, c, "tick:", None, True
    )
    c.events.put(Result(c.paths[0], 7))
    c.events.put(Result(c.paths[1], error="Missing."))
    c.events.put(None)
    c.tick_(c.timer)
    assert c.finished
    assert not c.timer.isValid()
    for v in c.views:
        assert v["total"].stringValue() == "7"
        assert v["action"].title() == "Close"
        assert v["progress"].isHidden()
        assert v["copy"].isEnabled()


def test_command_shortcuts_switch_view(controller):
    import AppKit as A

    c = controller(["/tmp/a.txt"])
    for key, simple in [("2", False), ("1", True)]:
        event = A.NSEvent.keyEventWithType_location_modifierFlags_timestamp_windowNumber_context_characters_charactersIgnoringModifiers_isARepeat_keyCode_(  # noqa: E501
            A.NSEventTypeKeyDown,
            (0, 0),
            A.NSEventModifierFlagCommand,
            0,
            c.window.windowNumber(),
            None,
            key,
            key,
            False,
            0,
        )
        assert c.window.performKeyEquivalent_(event)
        assert c.simple is simple
