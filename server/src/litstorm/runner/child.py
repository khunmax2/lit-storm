"""The process one Run lives in: `python -m litstorm.runner.child <run_dir>`.

Reads the config snapshot from the Run's directory and the credentials from
stdin, runs the Engine, and writes outcome.json last. The supervisor treats a
process that exits without outcome.json as having crashed.
"""

import importlib
import json
import os
import sys
import threading
import time
import traceback

from litstorm import engines, outcomes
from litstorm import report as report_mod
from litstorm.engines.base import Cancelled, EngineFailure, RunConfig, Secrets
from litstorm.runner import files


class FileProgress:
    """Progress written as JSON lines. STORM calls it from many threads."""

    def __init__(self, run_dir):
        self._path = files.path(run_dir, files.EVENTS)
        self._lock = threading.Lock()

    def _write(self, event):
        event["t"] = time.time()
        line = json.dumps(event, ensure_ascii=False)
        with self._lock, open(self._path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()

    def stage(self, name):
        self._write({"type": "stage", "stage": name})

    def note(self, kind, **data):
        self._write({"type": "note", "kind": kind, **data})

    def usage(self, stage, llm, search):
        self._write({"type": "usage", "stage": stage, "llm": llm, "search": search})


class FileCancelToken:
    def __init__(self, run_dir):
        self._path = files.path(run_dir, files.CANCEL)

    def requested(self):
        return os.path.exists(self._path)

    def check(self):
        if self.requested():
            raise Cancelled()


def _write_outcome(run_dir, status, reason, message=""):
    tmp = files.path(run_dir, files.OUTCOME + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"status": status, "reason": reason, "message": message}, f)
    os.replace(tmp, files.path(run_dir, files.OUTCOME))


def run(run_dir, secrets):
    with open(files.path(run_dir, files.CONFIG), encoding="utf-8") as f:
        config = RunConfig.from_dict(json.load(f))
    workspace = files.path(run_dir, files.WORK)
    os.makedirs(workspace, exist_ok=True)
    progress = FileProgress(run_dir)
    cancel = FileCancelToken(run_dir)

    try:
        report = engines.get(config.engine).run(config, secrets, workspace, progress, cancel)
    except Cancelled:
        _write_outcome(run_dir, "cancelled", outcomes.CANCELLED)
        return
    except EngineFailure as error:
        _write_outcome(run_dir, "failed", error.reason, str(error))
        return
    except Exception as error:  # noqa: BLE001 - every failure is sorted, none escapes
        progress.note("traceback", text=traceback.format_exc())
        _write_outcome(run_dir, "failed", outcomes.classify(error), f"{type(error).__name__}: {error}")
        return

    if report is None and config.discussion:
        # A Discussion's Turn that is not a report: what it made is the
        # state and the view it left in its workspace (engines/costorm).
        _write_outcome(run_dir, "succeeded", outcomes.SUCCEEDED)
        return
    if report_mod.is_empty(report):
        _write_outcome(run_dir, "failed", outcomes.EMPTY_REPORT, "the engine produced nothing to read")
        return
    report_mod.write(report, files.path(run_dir, files.REPORT))
    _write_outcome(run_dir, "succeeded", outcomes.SUCCEEDED)


def _exit_when_orphaned(parent_pid):
    """Stop if the supervisor goes away, however it goes.

    Without this a crashed Worker would leave the Run spending tokens with
    nobody watching, after the Run had been marked interrupted
    (docs/web-app-design.md). The parent is watched directly rather than
    through a pipe: on Windows a thread blocked reading a pipe stalls other
    threads that touch the same handle, and numpy's import does.
    """
    if sys.platform == "win32":
        import ctypes

        synchronize, infinite = 0x00100000, 0xFFFFFFFF
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(synchronize, False, parent_pid)
        if handle:
            kernel32.WaitForSingleObject(handle, infinite)
    else:
        # Orphans are re-parented, so the parent's id stops being ours.
        while os.getppid() == parent_pid:
            time.sleep(1)
    os._exit(4)


def _spare(parent_pid, preload):
    """Load the libraries a Run needs, then wait to be given one
    (supervisor.Spare). The Run's directory arrives with the credentials."""
    threading.Thread(target=_exit_when_orphaned, args=(parent_pid,), daemon=True).start()
    for name in preload:
        try:
            importlib.import_module(name)
        except Exception:  # noqa: BLE001 - the Run will import it again and say what is wrong
            pass
    raw = json.loads(sys.stdin.readline() or "{}")
    run_dir = raw.pop("run_dir")
    # What an ordinary Run's process writes to stderr.log from its start.
    log = os.open(files.path(run_dir, "stderr.log"), os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
    os.dup2(log, 2)
    os.close(log)
    return run_dir, raw


def main():
    if sys.argv[1] == "--spare":
        run_dir, raw = _spare(int(sys.argv[2]), sys.argv[3:])
    else:
        run_dir = sys.argv[1]
        parent_pid = int(sys.argv[2]) if len(sys.argv) > 2 else os.getppid()
        raw = json.loads(sys.stdin.read() or "{}")
        threading.Thread(target=_exit_when_orphaned, args=(parent_pid,), daemon=True).start()
    run(run_dir, Secrets(**raw))
    sys.stderr.flush()
    # Skip the interpreter's shutdown: STORM's thread pools can keep it
    # waiting, and everything that matters is on disk, outcome.json last.
    os._exit(0)


if __name__ == "__main__":
    main()
