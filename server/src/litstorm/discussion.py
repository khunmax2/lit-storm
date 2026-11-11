"""A Discussion's Turns: what may be asked next, and what it costs.

A Discussion (docs/CONTEXT.md) is a Research Session whose Runs are Turns,
run by Co-STORM one at a time (engines/costorm). The rules
(docs/web-app-design.md, รุ่นสอง: Discussion):

- Starting takes one quota unit and opens a block of `turns_per_quota`
  Turns (20 by default), the warm start and every report included.
- When the block is used up the owner may extend: the Turn that extends
  takes the next unit and opens the next block.
- One Turn at a time. A Turn waits in the Run queue, ahead of new Runs.
- A Turn continues from the state the last finished Turn left, so a Turn
  that fails, is stopped or loses its Worker costs only itself.

Everything is read off the Turns' rows. A Turn whose quota came back — it
failed for a reason that refunds (litstorm.outcomes), or was cancelled
before it started — uses no Turn, and a block opened by one is not paid for.
"""

import os
from dataclasses import dataclass

from sqlalchemy import select

from litstorm import settings
from litstorm.db.models import ACTIVE, SUCCEEDED, WAITING, Run

STATE = "costorm_state.json"
VIEW = "discussion.json"
ACTIONS = ("start", "say", "step", "auto", "report")


@dataclass(frozen=True)
class Allowance:
    per_block: int
    blocks: int  # units paid for
    used: int  # Turns taken, waiting ones included

    @property
    def remaining(self):
        return max(0, self.per_block * self.blocks - self.used)


def turns(session, rs):
    """The Discussion's Turns, oldest first."""
    return session.scalars(
        select(Run).where(Run.session_id == rs.id, Run.turn.is_not(None)).order_by(Run.queued_at)
    ).all()


def allowance(rows, per_block):
    kept = [r for r in rows if not r.quota_refunded]
    return Allowance(per_block=per_block, blocks=sum(r.quota_units for r in kept), used=len(kept))


def report_ready(rows):
    """Whether a report would hold anything the last one did not: the table
    has finished a Turn other than a report since (the warm start counts). A
    Turn that did not finish said nothing new."""
    for r in reversed(rows):
        if r.status == SUCCEEDED:
            return (r.turn or {}).get("action") != "report"
    return False


def first_report(session, run_id):
    """After a warm start that worked, the first report, queued for the owner:
    it is what they started for, and they may not know a report is theirs to
    ask for. Only once per Discussion, and only while its block has a Turn
    left; every later report waits for the owner. The queued Turn, or None."""
    from litstorm import limits
    from litstorm.db.models import QUEUED, ResearchSession

    run = session.get(Run, run_id)
    if run is None or run.status != SUCCEEDED or (run.turn or {}).get("action") != "start":
        return None
    rows = turns(session, session.get(ResearchSession, run.session_id))
    if in_progress(rows) or any((r.turn or {}).get("action") == "report" for r in rows):
        return None
    if allowance(rows, limits.load(session).turns_per_quota).remaining <= 0:
        return None
    report = Run(
        session_id=run.session_id,
        owner_id=run.owner_id,
        engine=run.engine,
        topic=run.topic,
        language=run.language,
        llm_model_id=run.llm_model_id,
        search_provider_id=run.search_provider_id,
        config=dict(run.config),
        status=QUEUED,
        quota_month=limits.quota_month(),
        quota_units=0,
        turn={"action": "report", "auto": True},
    )
    session.add(report)
    session.commit()
    return report


def in_progress(rows):
    """The Turn waiting or running, if any."""
    return next((r for r in rows if r.status in WAITING or r.status in ACTIVE), None)


def workspace(run):
    return os.path.join(settings.get().runs_dir, str(run.id), "work")


def last_state(rows, before=None):
    """The latest finished Turn that left a state, and the state's path."""
    for run in sorted(
        (r for r in rows if r.status == SUCCEEDED and r.id != before and r.finished_at is not None),
        key=lambda r: r.finished_at,
        reverse=True,
    ):
        path = os.path.join(workspace(run), STATE)
        if os.path.exists(path):
            return run, path
    return None, None


def state_from(session, run):
    """Where Turn `run` continues from; None for the warm start."""
    if (run.turn or {}).get("action") == "start":
        return None
    rows = session.scalars(
        select(Run).where(Run.session_id == run.session_id, Run.turn.is_not(None))
    ).all()
    return last_state(rows, before=run.id)[1]
