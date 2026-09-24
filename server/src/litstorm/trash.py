"""The Trash: 30 days to change your mind (docs/web-app-design.md, ถังขยะ).

Deleting a Project, a Research Session or a Report moves it here. Only the
thing deleted is marked; what is inside it is hidden because its parent is.
Restoring the parent brings everything back as it was.

Work inside is stopped first: waiting Runs are cancelled (their quota comes
back, as for any Run cancelled before it started) and running ones are asked
to stop, so no Run writes into something being deleted.

After 30 days the purge deletes the content for good — topic, events, files,
the report — but keeps each Run's accounting row: its month, status, refund
flag and cost. Deleting a report does not give quota back
(docs/web-app-implementation-plan.md), and a month's figures do not change
after the fact.
"""

import os
import shutil
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import delete, exists, or_, select, text, update

from litstorm.db.models import (
    ACTIVE,
    CANCELLED,
    CANCELLING,
    FINAL,
    RUNNING,
    WAITING,
    Project,
    ResearchSession,
    Run,
    RunEvent,
)

RETENTION = timedelta(days=30)
PURGE_LOCK = 7_211_002  # advisory lock id: one purge at a time


def _now():
    return datetime.now(timezone.utc)


def purge_at(trashed_at):
    return trashed_at + RETENTION


# --- what is alive -------------------------------------------------------------


def session_alive(session, rs):
    if rs is None or rs.trashed_at is not None:
        return False
    project = session.get(Project, rs.project_id)
    return project is not None and project.trashed_at is None


def run_alive(session, run):
    if run is None or run.trashed_at is not None or run.purged_at is not None or run.session_id is None:
        return False
    return session_alive(session, session.get(ResearchSession, run.session_id))


# --- moving to the Trash ------------------------------------------------------------


def _stop(session, run_filter):
    """Cancel what is waiting, ask what is running to stop."""
    now = _now()
    session.execute(
        update(Run)
        .where(run_filter, Run.status.in_(WAITING))
        .values(status=CANCELLED, reason="cancelled", finished_at=now, cancel_requested_at=now, quota_refunded=True)
    )
    session.execute(
        update(Run).where(run_filter, Run.status == RUNNING).values(status=CANCELLING, cancel_requested_at=now)
    )


def trash_project(session, project):
    sessions = select(ResearchSession.id).where(ResearchSession.project_id == project.id)
    _stop(session, Run.session_id.in_(sessions))
    project.trashed_at = _now()


def trash_session(session, rs):
    _stop(session, Run.session_id == rs.id)
    rs.trashed_at = _now()


def trash_run(session, run):
    """A Report goes to the Trash with its Run. Only a finished Run: one still
    going is cancelled first, from its own card."""
    if run.status not in FINAL:
        raise HTTPException(409, "run_not_finished")
    run.trashed_at = _now()


# --- listing and restoring ------------------------------------------------------------


def listing(session, owner):
    """What the owner can restore: things they deleted themselves, not the
    contents of something they deleted."""
    items = []
    for p in session.scalars(
        select(Project).where(Project.owner_id == owner.id, Project.trashed_at.is_not(None))
    ):
        items.append(("project", p.id, p.name, p.trashed_at))
    for rs in session.scalars(
        select(ResearchSession)
        .join(Project, Project.id == ResearchSession.project_id)
        .where(
            ResearchSession.owner_id == owner.id,
            ResearchSession.trashed_at.is_not(None),
            Project.trashed_at.is_(None),
        )
    ):
        items.append(("session", rs.id, rs.title, rs.trashed_at))
    for run in session.scalars(
        select(Run)
        .join(ResearchSession, ResearchSession.id == Run.session_id)
        .join(Project, Project.id == ResearchSession.project_id)
        .where(
            Run.owner_id == owner.id,
            Run.trashed_at.is_not(None),
            Run.purged_at.is_(None),
            ResearchSession.trashed_at.is_(None),
            Project.trashed_at.is_(None),
        )
    ):
        items.append(("run", run.id, run.report_title or run.topic, run.trashed_at))
    return sorted(items, key=lambda item: item[3], reverse=True)


_KINDS = {"project": Project, "session": ResearchSession, "run": Run}


def restore(session, owner, kind, row_id):
    table = _KINDS.get(kind)
    row = session.get(table, row_id) if table else None
    if row is None or row.owner_id != owner.id or row.trashed_at is None:
        raise HTTPException(404, "not_found")
    if getattr(row, "purged_at", None) is not None or _now() >= purge_at(row.trashed_at):
        raise HTTPException(410, "already_purged")
    row.trashed_at = None
    return row


# --- purging for good -----------------------------------------------------------------


def purge(session, runs_dir, now=None):
    """Delete for good what has been in the Trash for 30 days. Returns how
    many Runs were purged. Safe to call often and from several Workers."""
    now = now or _now()
    if not session.scalar(text("select pg_try_advisory_xact_lock(:id)"), {"id": PURGE_LOCK}):
        return 0
    cutoff = now - RETENTION
    expired = or_(Run.trashed_at < cutoff, ResearchSession.trashed_at < cutoff, Project.trashed_at < cutoff)
    runs = session.scalars(
        select(Run)
        .join(ResearchSession, ResearchSession.id == Run.session_id)
        .join(Project, Project.id == ResearchSession.project_id)
        # A Run still stopping is left for next time, so it cannot write
        # into a directory that is gone.
        .where(Run.purged_at.is_(None), Run.status.not_in(ACTIVE), expired)
    ).all()
    for run in runs:
        session.execute(delete(RunEvent).where(RunEvent.run_id == run.id))
        shutil.rmtree(os.path.join(runs_dir, str(run.id)), ignore_errors=True)
        run.purged_at = now
        run.session_id = None
        run.topic = ""
        run.report_title = None
        run.message = None
        run.request_key = None
        run.source_count = None
        # Keep only what accounting needs: which model it was.
        run.config = {"llm": {"label": run.config.get("llm", {}).get("label", "")}}
    session.flush()

    # Sessions and Projects go once nothing points at them any more.
    has_runs = exists().where(Run.session_id == ResearchSession.id)
    session.execute(
        delete(ResearchSession).where(
            ~has_runs,
            or_(
                ResearchSession.trashed_at < cutoff,
                ResearchSession.project_id.in_(select(Project.id).where(Project.trashed_at < cutoff)),
            ),
        )
    )
    has_sessions = exists().where(ResearchSession.project_id == Project.id)
    session.execute(delete(Project).where(~has_sessions, Project.trashed_at < cutoff))
    session.commit()
    return len(runs)
