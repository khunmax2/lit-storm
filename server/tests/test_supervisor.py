"""The supervisor against the fake engine: every way a Run can end."""

import json
import threading

import pytest

from litstorm import outcomes
from litstorm.engines.base import RunConfig, Secrets
from litstorm.runner import files
from litstorm.runner.supervisor import supervise


def config(script, language="en", run_id="r1"):
    return RunConfig(
        run_id=run_id,
        engine="fake",
        topic="A topic",
        language=language,
        llm={"provider": "openai", "model": "x"},
        search={"provider": "arxiv"},
        params={"script": script},
    )


def fast(run_dir, cfg, **kwargs):
    kwargs.setdefault("poll_interval", 0.05)
    return supervise(str(run_dir), cfg, Secrets(llm_api_key="sk-secret"), **kwargs)


def test_success_writes_report_and_records_usage(tmp_path):
    outcome = fast(tmp_path, config([{"stage": "research"}, {"stage": "polish"}]))

    assert outcome.status == "succeeded"
    assert outcome.report_path == str(tmp_path / files.REPORT)
    assert [u["stage"] for u in outcome.usage] == ["research", "polish"]
    assert not outcome.refunds_quota


def test_secrets_never_reach_the_run_directory(tmp_path):
    fast(tmp_path, config([{"stage": "research"}]))

    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert "sk-secret" not in path.read_text(encoding="utf-8", errors="ignore"), path


def test_failure_reason_decides_the_refund(tmp_path):
    outcome = fast(tmp_path / "a", config([{"fail": outcomes.RETRIES_EXHAUSTED}]))
    assert (outcome.status, outcome.reason) == ("failed", outcomes.RETRIES_EXHAUSTED)
    assert outcome.refunds_quota

    outcome = fast(tmp_path / "b", config([{"fail": outcomes.REFUSED}]))
    assert outcome.reason == outcomes.REFUSED
    assert not outcome.refunds_quota


def test_cancel_stops_at_the_next_stage(tmp_path):
    asked = threading.Event()
    script = [{"stage": "research"}, {"sleep": 0.5}, {"stage": "outline"}, {"sleep": 5}]

    def on_event(event):
        if event.get("stage") == "research":
            asked.set()

    outcome = fast(tmp_path, config(script), should_cancel=asked.is_set, on_event=on_event)

    assert (outcome.status, outcome.reason) == ("cancelled", outcomes.CANCELLED)
    assert outcome.message == ""  # stopped by itself, not killed
    assert [u["stage"] for u in outcome.usage] == ["research"]
    assert not outcome.refunds_quota


def test_cancel_is_forced_after_the_grace_period(tmp_path):
    asked = threading.Event()
    outcome = fast(
        tmp_path,
        config([{"stage": "research"}, {"hang": True}]),
        should_cancel=asked.is_set,
        on_event=lambda e: e.get("stage") == "research" and asked.set(),
        cancel_grace=1.0,
    )
    assert outcome.status == "cancelled"
    assert "force" in outcome.message


def test_cancel_that_loses_to_completion_keeps_the_report(tmp_path):
    # Asked to stop after the last stage began: the engine finishes anyway.
    asked = threading.Event()

    def on_event(event):
        if event.get("stage") == "polish":
            asked.set()

    outcome = fast(
        tmp_path,
        config([{"stage": "polish"}, {"sleep": 0.5}]),
        should_cancel=asked.is_set,
        on_event=on_event,
    )
    assert outcome.status == "cancelled"
    assert outcome.report_path is not None


def test_deadline_kills_a_hung_run_and_refunds(tmp_path):
    outcome = fast(tmp_path, config([{"stage": "research"}, {"hang": True}]), deadline=1.5)

    assert (outcome.status, outcome.reason) == ("failed", outcomes.TIMED_OUT)
    assert outcome.refunds_quota
    assert [u["stage"] for u in outcome.usage] == ["research"]


def test_a_process_that_dies_silently_is_an_engine_error(tmp_path):
    outcome = fast(tmp_path, config([{"stage": "research"}, {"crash": True}]))

    assert (outcome.status, outcome.reason) == ("failed", outcomes.ENGINE_ERROR)
    assert "code 3" in outcome.message
    assert outcome.refunds_quota


def test_heartbeat_keeps_beating_while_the_engine_blocks(tmp_path):
    beats = []
    fast(tmp_path, config([{"sleep": 1.0}]), heartbeat=lambda: beats.append(1))
    assert len(beats) >= 5


@pytest.mark.slow
def test_two_runs_at_once_keep_their_own_language(tmp_path):
    """The reason for one process per Run (docs/adr/0003)."""
    results = {}

    def go(code):
        outcome = fast(
            tmp_path / code,
            config([{"language_probe": True, "hold": 3.0}], language=code, run_id=code),
            on_event=lambda e: e.get("kind") == "language" and results.__setitem__(code, e["prompt"]),
        )
        assert outcome.status == "succeeded"

    threads = [threading.Thread(target=go, args=(code,)) for code in ("th", "en")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert "Thai" in results["th"]
    assert "Thai" not in results["en"]


def test_config_snapshot_is_kept_with_the_run(tmp_path):
    fast(tmp_path, config([]))
    saved = json.loads((tmp_path / files.CONFIG).read_text(encoding="utf-8"))
    assert saved["engine"] == "fake"
    assert "sk-secret" not in json.dumps(saved)


def test_a_listener_that_raises_does_not_stop_supervision(tmp_path):
    def boom(event):
        raise UnicodeEncodeError("charmap", "ไทย", 0, 1, "cannot print")

    outcome = fast(tmp_path, config([{"stage": "research"}]), on_event=boom)
    assert outcome.status == "succeeded"


def _alive(pid):
    import os
    import subprocess
    import sys

    if sys.platform == "win32":
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True
        ).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def test_the_run_stops_when_its_supervisor_dies(tmp_path):
    """A crashed Worker must not leave its Run spending with nobody watching."""
    import subprocess
    import sys
    import time

    script = f"""
import sys
sys.path.insert(0, {str(tmp_path.parent)!r})
from litstorm.engines.base import RunConfig, Secrets
from litstorm.runner.supervisor import supervise
cfg = RunConfig(run_id="o", engine="fake", topic="t", language="en",
    llm={{}}, search={{}}, params={{"script": [{{"pid": True}}, {{"hang": True}}]}})
supervise({str(tmp_path)!r}, cfg, Secrets(), poll_interval=0.05)
"""
    supervisor = subprocess.Popen([sys.executable, "-c", script])
    events = tmp_path / files.EVENTS
    pid = None
    for _ in range(200):
        if events.exists():
            for line in events.read_text(encoding="utf-8").splitlines():
                event = json.loads(line)
                if event.get("kind") == "pid":
                    pid = event["pid"]
        if pid:
            break
        time.sleep(0.05)
    assert pid, "the child never reported its pid"

    supervisor.kill()
    supervisor.wait()
    for _ in range(100):
        if not _alive(pid):
            break
        time.sleep(0.05)
    assert not _alive(pid)


def test_thai_files_can_be_written_whatever_the_host_locale(tmp_path):
    outcome = fast(tmp_path, config([{"write_thai": True}]))
    assert outcome.status == "succeeded", outcome.message
    assert (tmp_path / "work" / "thai.txt").read_text(encoding="utf-8") == "สงกรานต์"


def test_a_spare_process_takes_the_next_run(tmp_path):
    """The Worker keeps one process loaded ahead of time; a Run handed to it
    ends as any other does, and a new spare starts behind it."""
    from litstorm.runner.supervisor import Spare

    spare = Spare(preload=())
    spare.refill()
    first = spare._proc
    try:
        outcome = fast(tmp_path / "a", config([{"stage": "research"}]), spare=spare)
        assert outcome.status == "succeeded" and outcome.report_path
        assert first.returncode == 0  # the spare ran it
        assert spare._proc is not None and spare._proc is not first  # and was replaced
        # Its stderr went to the Run's directory, as a fresh process's does.
        assert (tmp_path / "a" / "stderr.log").exists()
        for path in (tmp_path / "a").rglob("*"):
            if path.is_file():
                assert "sk-secret" not in path.read_text(encoding="utf-8", errors="ignore"), path
    finally:
        spare.close()


def test_a_dead_spare_is_not_used(tmp_path):
    from litstorm.runner.supervisor import Spare

    spare = Spare(preload=())
    spare.refill()
    spare._proc.kill()
    spare._proc.wait()
    try:
        outcome = fast(tmp_path, config([{"stage": "research"}]), spare=spare)
        assert outcome.status == "succeeded"
    finally:
        spare.close()
