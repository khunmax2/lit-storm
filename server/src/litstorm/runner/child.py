"""The process one Run lives in: `python -m litstorm.runner.child <run_dir>`.

Reads the config snapshot from the Run's directory and the credentials from
stdin, runs the Engine, and writes outcome.json last. The supervisor treats a
process that exits without outcome.json as having crashed.
"""

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

    if report_mod.is_empty(report):
        _write_outcome(run_dir, "failed", outcomes.EMPTY_REPORT, "the engine produced nothing to read")
        return
    report_mod.write(report, files.path(run_dir, files.REPORT))
    _write_outcome(run_dir, "succeeded", outcomes.SUCCEEDED)


def main():
    run_dir = sys.argv[1]
    raw = json.loads(sys.stdin.read() or "{}")
    run(run_dir, Secrets(**raw))


if __name__ == "__main__":
    main()
