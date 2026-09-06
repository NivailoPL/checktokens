import sys
import threading

from checktokens import runner


def test_timeout_reaps_worker(monkeypatch):
    monkeypatch.setattr(
        runner, "worker_command", lambda p: [sys.executable, "-c", "import time; time.sleep(30)"]
    )
    result = runner.run_file("anything", threading.Event(), timeout=0.15)
    assert "limit" in result.error
    assert result.tokens is None


def test_cancel_before_start_does_not_spawn(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("Worker should not start")

    monkeypatch.setattr(runner.subprocess, "Popen", fail)
    event = threading.Event()
    event.set()
    assert list(runner.run_batch(["a", "b"], event))[1].error == "Cancelled."


def test_launch_failure(monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("cannot execute")

    monkeypatch.setattr(runner.subprocess, "Popen", fail)
    assert runner.run_file("a", threading.Event()).error


def test_crashed_worker(monkeypatch):
    monkeypatch.setattr(
        runner, "worker_command", lambda p: [sys.executable, "-c", "raise SystemExit(1)"]
    )
    assert "failed" in runner.run_file("a", threading.Event()).error


def test_cancel_running_worker_reaps_process(monkeypatch):
    original = runner.subprocess.Popen
    processes = []
    event = threading.Event()

    def start(*args, **kwargs):
        process = original(*args, **kwargs)
        processes.append(process)
        event.set()
        return process

    monkeypatch.setattr(runner.subprocess, "Popen", start)
    monkeypatch.setattr(
        runner, "worker_command", lambda p: [sys.executable, "-c", "import time; time.sleep(30)"]
    )
    assert runner.run_file("a", event).error == "Cancelled."
    assert processes[0].poll() is not None
