"""Start one Run in a process of its own and watch it to the end.

This is the part of the Worker that stays alive while STORM blocks for
minutes at a time, so it is what renews the Run's lease (`heartbeat`), what
notices the owner asking to stop (`should_cancel`), and what enforces the two
ceilings the child cannot enforce on itself (docs/adr/0003):

* a stop that has not happened within `cancel_grace` of being asked for is
  forced by killing the process;
* a Run still going at `deadline` seconds is killed and failed as timed out.

Whatever the child's finished stages wrote stays in the Run's directory.
"""

import json
import logging
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field

from litstorm import outcomes
from litstorm.runner import files

logger = logging.getLogger(__name__)

CANCEL_GRACE = 30.0  # seconds from asking to stop to killing
DEADLINE = 60 * 60.0  # the Run's wall-clock ceiling, set by admins


@dataclass
class Outcome:
    status: str  # "succeeded" | "failed" | "cancelled"
    reason: str  # one of litstorm.outcomes
    message: str = ""
    report_path: str | None = None
    usage: list = field(default_factory=list)  # the child's usage events, in order

    @property
    def refunds_quota(self):
        # A Run that started and was then cancelled has cost something; the
        # quota is kept (docs/web-app-design.md, การยกเลิก Run).
        return self.status == "failed" and outcomes.refunds_quota(self.reason)


class _EventTail:
    """Read events.jsonl as the child appends to it, whole lines only."""

    def __init__(self, path):
        self.path = path
        self.offset = 0
        self.partial = b""

    def read(self):
        try:
            with open(self.path, "rb") as f:
                f.seek(self.offset)
                chunk = f.read()
        except FileNotFoundError:
            return []
        self.offset += len(chunk)
        data = self.partial + chunk
        *lines, self.partial = data.split(b"\n")
        return [json.loads(line) for line in lines if line.strip()]


def write_config(run_dir, config):
    os.makedirs(run_dir, exist_ok=True)
    with open(files.path(run_dir, files.CONFIG), "w", encoding="utf-8") as f:
        json.dump(config.__dict__, f, ensure_ascii=False, indent=2)


def _secrets_json(secrets, **extra):
    return json.dumps(
        {
            "llm_api_key": secrets.llm_api_key,
            "search_api_key": secrets.search_api_key,
            "embedding_api_key": secrets.embedding_api_key,
            "fast_llm_api_key": secrets.fast_llm_api_key,
            **extra,
        }
    ).encode()


# knowledge_storm opens its files without naming an encoding; on a Windows
# host that is cp1252, which cannot hold Thai.
_ENV = {**os.environ, "PYTHONUTF8": "1"}


def start(run_dir, secrets, spare=None):
    """Launch the child, or hand the Run to a spare one. Credentials go
    through stdin, never to disk.

    The child is told our pid, and exits if we do (child._exit_when_orphaned).
    """
    proc = spare.take() if spare else None
    if proc is not None:
        try:
            proc.stdin.write(_secrets_json(secrets, run_dir=run_dir) + b"\n")
            proc.stdin.close()
        except OSError:
            # It died between being checked and being handed the Run: start
            # one the ordinary way.
            proc.kill()
        else:
            spare.refill()
            return proc
    with open(files.path(run_dir, "stderr.log"), "wb") as stderr:
        proc = subprocess.Popen(
            [sys.executable, "-m", "litstorm.runner.child", run_dir, str(os.getpid())],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=stderr,
            env=_ENV,
        )
    proc.stdin.write(_secrets_json(secrets))
    proc.stdin.close()
    if spare:
        spare.refill()
    return proc


class Spare:
    """One Run process started ahead of time, its libraries already loaded.

    Loading STORM takes about 8 seconds, every Run, before any work starts
    (docs/benchmarks/2026-09-30-baseline.md). A spare pays that while nothing
    is waiting; the next Run takes it and a new spare starts behind it. The
    spare exits if the Worker does, like any Run's process.
    """

    def __init__(self, preload=("litstorm.engines.storm.engine", "sentence_transformers")):
        self.preload = tuple(preload)
        self._lock = threading.Lock()
        self._proc = None

    def refill(self):
        with self._lock:
            if self._proc is None or self._proc.poll() is not None:
                self._proc = subprocess.Popen(
                    [sys.executable, "-m", "litstorm.runner.child", "--spare", str(os.getpid()), *self.preload],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    # Until it is given a Run it has nowhere to write; the
                    # child points this at the Run's stderr.log then.
                    stderr=subprocess.DEVNULL,
                    env=_ENV,
                )

    def take(self):
        """The spare, if one is alive; None otherwise."""
        with self._lock:
            proc, self._proc = self._proc, None
        return proc if proc is not None and proc.poll() is None else None

    def close(self):
        proc = self.take()
        if proc is not None:
            proc.kill()
            proc.wait()


def supervise(
    run_dir,
    config,
    secrets,
    *,
    deadline=DEADLINE,
    cancel_grace=CANCEL_GRACE,
    should_cancel=lambda: False,
    heartbeat=lambda: None,
    on_event=lambda event: None,
    poll_interval=0.5,
    spare=None,
):
    """Run `config` to its end and say how it ended."""
    write_config(run_dir, config)
    proc = start(run_dir, secrets, spare)
    tail = _EventTail(files.path(run_dir, files.EVENTS))
    usage = []
    started = time.monotonic()
    cancel_asked_at = None
    forced = None  # the Outcome to report if we end the process ourselves

    def drain():
        for event in tail.read():
            if event.get("type") == "usage":
                usage.append(event)
            try:
                on_event(event)
            except Exception:  # noqa: BLE001 - a listener's fault must not orphan the Run
                logger.exception("on_event failed for %s", event.get("type"))

    while proc.poll() is None:
        drain()
        heartbeat()
        now = time.monotonic()

        if cancel_asked_at is None and should_cancel():
            cancel_asked_at = now
            open(files.path(run_dir, files.CANCEL), "w").close()

        if cancel_asked_at is not None and now - cancel_asked_at >= cancel_grace:
            proc.kill()
            forced = Outcome("cancelled", outcomes.CANCELLED, "stopped by force after the grace period")
            break
        if now - started >= deadline:
            proc.kill()
            forced = Outcome("failed", outcomes.TIMED_OUT, f"still running after {deadline:.0f}s")
            break
        time.sleep(poll_interval)

    proc.wait()
    drain()
    outcome = forced or _read_outcome(run_dir, proc.returncode)

    # Asked to stop, but finished first: the owner said stop, so the Run is
    # cancelled — and the report it made is kept for them to read.
    if cancel_asked_at is not None and outcome.status == "succeeded":
        outcome = Outcome("cancelled", outcomes.CANCELLED, "finished while stopping")

    report = files.path(run_dir, files.REPORT)
    outcome.report_path = report if os.path.exists(report) else None
    outcome.usage = usage
    return outcome


def _read_outcome(run_dir, returncode):
    try:
        with open(files.path(run_dir, files.OUTCOME), encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return Outcome(
            "failed",
            outcomes.ENGINE_ERROR,
            f"the run's process exited with code {returncode} and no outcome",
        )
    return Outcome(data["status"], data["reason"], data.get("message", ""))
