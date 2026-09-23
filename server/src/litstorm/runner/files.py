"""The files one Run's directory holds, shared by the supervisor and the child.

    <run_dir>/config.json       the config snapshot (no secrets)
    <run_dir>/events.jsonl      what the child reports, one JSON object a line
    <run_dir>/cancel.requested  present once the owner has asked to stop
    <run_dir>/outcome.json      how the child ended, written last
    <run_dir>/report.json       the report, when there is one
    <run_dir>/work/             the Engine's own files, kept whatever happens
"""

import os

CONFIG = "config.json"
EVENTS = "events.jsonl"
CANCEL = "cancel.requested"
OUTCOME = "outcome.json"
REPORT = "report.json"
WORK = "work"


def path(run_dir, name):
    return os.path.join(run_dir, name)
