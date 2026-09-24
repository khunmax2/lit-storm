"""Projects, Research Sessions, Runs and their Reports — the owner's side.

Every row is looked up through `deps.own`, so another User's id is a 404.
"""

import os
import tempfile
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from litstorm import limits, settings
from litstorm import report as report_mod
from litstorm.api import deps
from litstorm.db.models import (
    CANCELLED,
    CANCELLING,
    NEEDS_SELECTION,
    QUEUED,
    RUNNING,
    LlmModel,
    Project,
    ResearchSession,
    Run,
    RunEvent,
    SearchProvider,
)

router = APIRouter(prefix="/api", tags=["research"])


# --- what a Run can be started with ----------------------------------------


class Choice(BaseModel):
    id: str
    label: str
    is_default: bool


class Options(BaseModel):
    models: list[Choice]
    search_providers: list[Choice]
    languages: list[str]


@router.get("/options", response_model=Options)
def options(user=Depends(deps.current_user), session=Depends(deps.database)):
    models = session.scalars(select(LlmModel).where(LlmModel.enabled).order_by(LlmModel.label))
    providers = session.scalars(select(SearchProvider).where(SearchProvider.enabled).order_by(SearchProvider.label))
    return Options(
        models=[Choice(id=str(m.id), label=m.label, is_default=m.is_default) for m in models],
        search_providers=[Choice(id=str(p.id), label=p.label, is_default=p.is_default) for p in providers],
        languages=list(report_mod.LANGUAGES),
    )


# --- Projects -------------------------------------------------------------------


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class SessionSummary(BaseModel):
    id: str
    title: str
    created_at: datetime
    last_status: str | None


class ProjectOut(BaseModel):
    id: str
    name: str
    created_at: datetime


class ProjectDetail(ProjectOut):
    sessions: list[SessionSummary]


def project_out(p):
    return ProjectOut(id=str(p.id), name=p.name, created_at=p.created_at)


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(user=Depends(deps.current_user), session=Depends(deps.database)):
    rows = session.scalars(
        select(Project)
        .where(Project.owner_id == user.id, Project.trashed_at.is_(None))
        .order_by(Project.created_at.desc())
    )
    return [project_out(p) for p in rows]


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectIn, user=Depends(deps.current_user), session=Depends(deps.database)):
    project = Project(owner_id=user.id, name=body.name.strip())
    session.add(project)
    session.commit()
    return project_out(project)


@router.get("/projects/{project_id}", response_model=ProjectDetail)
def get_project(project_id: uuid.UUID, user=Depends(deps.current_user), session=Depends(deps.database)):
    project = deps.own(session, Project, project_id, user)
    sessions = session.scalars(
        select(ResearchSession)
        .where(ResearchSession.project_id == project.id, ResearchSession.trashed_at.is_(None))
        .order_by(ResearchSession.created_at.desc())
    ).all()
    last = {}
    if sessions:
        for run in session.scalars(
            select(Run)
            .where(Run.session_id.in_([s.id for s in sessions]))
            .order_by(Run.queued_at)
        ):
            last[run.session_id] = run.status
    return ProjectDetail(
        **project_out(project).model_dump(),
        sessions=[
            SessionSummary(id=str(s.id), title=s.title, created_at=s.created_at, last_status=last.get(s.id))
            for s in sessions
        ],
    )


# --- Research Sessions and Runs -------------------------------------------------------


class RunIn(BaseModel):
    topic: str = Field(min_length=3, max_length=500)
    language: str = Field(pattern="^(th|en)$")
    llm_model_id: uuid.UUID | None = None  # default model when absent
    search_provider_id: uuid.UUID | None = None  # default provider when absent


class SessionIn(RunIn):
    """A new Session starts with its first Run."""


class RunOut(BaseModel):
    id: str
    session_id: str
    parent_run_id: str | None
    topic: str
    language: str
    model_label: str
    search_label: str
    status: str
    stage: str | None
    reason: str | None
    message: str | None
    quota_refunded: bool
    queued_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    report_title: str | None
    source_count: int | None


def run_out(run):
    return RunOut(
        id=str(run.id),
        session_id=str(run.session_id),
        parent_run_id=str(run.parent_run_id) if run.parent_run_id else None,
        topic=run.topic,
        language=run.language,
        model_label=run.config.get("llm", {}).get("label", ""),
        search_label=run.config.get("search", {}).get("label", ""),
        status=run.status,
        stage=run.stage,
        reason=run.reason,
        message=run.message,
        quota_refunded=run.quota_refunded,
        queued_at=run.queued_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        report_title=run.report_title,
        source_count=run.source_count,
    )


class SessionOut(BaseModel):
    id: str
    project_id: str
    title: str
    created_at: datetime
    runs: list[RunOut]


def _pick(session, table, wanted_id):
    """The enabled row asked for, or the default one."""
    if wanted_id is not None:
        row = session.get(table, wanted_id)
        if row is None or not row.enabled:
            raise HTTPException(422, "choice_not_available")
        return row
    row = session.scalar(select(table).where(table.is_default, table.enabled))
    if row is None:
        raise HTTPException(422, "no_default_configured")
    return row


def new_run(session, owner, research_session, body, parent_run_id=None):
    """A queued Run with its config snapshot. Secrets are not in it."""
    model = _pick(session, LlmModel, body.llm_model_id)
    provider = _pick(session, SearchProvider, body.search_provider_id)
    configured = limits.load(session)
    params = dict(configured.storm_params)
    if model.max_tokens:
        params["max_tokens"] = model.max_tokens
    run = Run(
        session_id=research_session.id,
        owner_id=owner.id,
        parent_run_id=parent_run_id,
        engine="storm",
        topic=body.topic.strip(),
        language=body.language,
        llm_model_id=model.id,
        search_provider_id=provider.id,
        config={
            "llm": {
                "label": model.label,
                "provider": model.provider,
                "model": model.model,
                "reasoning": model.reasoning,
            },
            "search": {
                "label": provider.label,
                "provider": provider.kind,
                "endpoint": provider.endpoint,
                "engines": provider.engines,
            },
            "params": params,
            "deadline_minutes": configured.run_deadline_minutes,
        },
        status=QUEUED,
        quota_month=limits.quota_month(),
    )
    session.add(run)
    return run


def session_out(session, rs):
    runs = session.scalars(select(Run).where(Run.session_id == rs.id).order_by(Run.queued_at.desc()))
    return SessionOut(
        id=str(rs.id), project_id=str(rs.project_id), title=rs.title, created_at=rs.created_at,
        runs=[run_out(r) for r in runs],
    )


@router.post("/projects/{project_id}/sessions", response_model=SessionOut, status_code=201)
def create_session(
    project_id: uuid.UUID, body: SessionIn, user=Depends(deps.current_user), session=Depends(deps.database)
):
    project = deps.own(session, Project, project_id, user)
    rs = ResearchSession(project_id=project.id, owner_id=user.id, title=body.topic.strip()[:300])
    session.add(rs)
    session.flush()
    new_run(session, user, rs, body)
    session.commit()
    return session_out(session, rs)


@router.get("/sessions/{session_id}", response_model=SessionOut)
def get_session(session_id: uuid.UUID, user=Depends(deps.current_user), session=Depends(deps.database)):
    return session_out(session, deps.own(session, ResearchSession, session_id, user))


@router.post("/sessions/{session_id}/runs", response_model=RunOut, status_code=201)
def create_run(
    session_id: uuid.UUID, body: RunIn, user=Depends(deps.current_user), session=Depends(deps.database)
):
    rs = deps.own(session, ResearchSession, session_id, user)
    run = new_run(session, user, rs, body)
    session.commit()
    return run_out(run)


class EventOut(BaseModel):
    id: int
    at: datetime
    type: str
    data: dict


class RunDetail(RunOut):
    events: list[EventOut]


# Notes an owner sees while waiting. Tracebacks and the like stay in the
# database for whoever debugs; they are not the owner's reading.
_SHOWN_NOTES = {"perspectives", "browsed", "dropped_citations"}


@router.get("/runs/{run_id}", response_model=RunDetail)
def get_run(
    run_id: uuid.UUID,
    after: int = Query(0, ge=0),
    user=Depends(deps.current_user),
    session=Depends(deps.database),
):
    run = deps.own(session, Run, run_id, user)
    events = session.scalars(
        select(RunEvent).where(RunEvent.run_id == run.id, RunEvent.id > after).order_by(RunEvent.id).limit(500)
    )
    shown = [
        EventOut(id=e.id, at=e.at, type=e.type, data=e.data)
        for e in events
        if e.type in ("stage", "usage") or (e.type == "note" and e.data.get("kind") in _SHOWN_NOTES)
    ]
    return RunDetail(**run_out(run).model_dump(), events=shown)


@router.post("/runs/{run_id}/cancel", response_model=RunOut)
def cancel_run(run_id: uuid.UUID, user=Depends(deps.current_user), session=Depends(deps.database)):
    """Stop a Run. One still waiting stops now; one running is asked to stop
    and becomes "cancelling" until the Worker confirms (design: การยกเลิก Run).

    Both are conditional updates, so a cancel racing the Worker's claim or
    finish changes nothing it should not.
    """
    run = deps.own(session, Run, run_id, user)
    now = datetime.now(timezone.utc)
    stopped = session.execute(
        update(Run)
        .where(Run.id == run.id, Run.status.in_((QUEUED, NEEDS_SELECTION)))
        .values(status=CANCELLED, reason="cancelled", finished_at=now, cancel_requested_at=now, quota_refunded=True)
    ).rowcount
    asked = 0
    if not stopped:
        asked = session.execute(
            update(Run)
            .where(Run.id == run.id, Run.status == RUNNING)
            .values(status=CANCELLING, cancel_requested_at=now)
        ).rowcount
    session.commit()
    session.refresh(run)
    # Asking twice is harmless; asking a finished Run is not a thing.
    if not stopped and not asked and run.status != CANCELLING:
        raise HTTPException(409, "cannot_cancel")
    return run_out(run)


# --- Reports -------------------------------------------------------------------


def _report(session, run_id, user):
    run = deps.own(session, Run, run_id, user)
    path = os.path.join(settings.get().runs_dir, str(run.id), "report.json")
    if not os.path.exists(path):
        raise HTTPException(404, "no_report")
    return run, report_mod.load(path)


@router.get("/runs/{run_id}/report")
def get_report(run_id: uuid.UUID, user=Depends(deps.current_user), session=Depends(deps.database)):
    _, report = _report(session, run_id, user)
    return report


def _filename(report, ext):
    safe = "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in report["title"]).strip()[:80]
    return f"{safe or 'report'}.{ext}"


@router.get("/runs/{run_id}/export")
def export_report(
    run_id: uuid.UUID,
    format: str = Query(pattern="^(html|md|pdf)$"),
    evidence: bool = False,
    user=Depends(deps.current_user),
    session=Depends(deps.database),
):
    from urllib.parse import quote

    _, report = _report(session, run_id, user)
    name = _filename(report, format)
    disposition = f"attachment; filename*=UTF-8''{quote(name)}"
    if format == "html":
        from litstorm.render import html

        return Response(
            html.render(report, with_evidence=evidence),
            media_type="text/html; charset=utf-8",
            headers={"Content-Disposition": disposition},
        )
    if format == "md":
        from litstorm.render import markdown

        return Response(
            markdown.render(report, with_evidence=evidence),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": disposition},
        )
    from starlette.background import BackgroundTask

    from litstorm.render import pdf

    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    pdf.render(report, path, with_evidence=evidence)
    return FileResponse(
        path, media_type="application/pdf", headers={"Content-Disposition": disposition},
        background=BackgroundTask(os.remove, path),
    )
