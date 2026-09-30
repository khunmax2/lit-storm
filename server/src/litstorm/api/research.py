"""Projects, Research Sessions, Runs and their Reports — the owner's side.

Every row is looked up through `deps.own`, so another User's id is a 404.
"""

import os
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError

from litstorm import limits, modes, quota, sections, settings, trash
from litstorm import report as report_mod
from litstorm.api import deps
from litstorm.catalog import ENGINES
from litstorm.db.models import (
    CANCELLED,
    CANCELLING,
    DISCUSSION,
    FAILED,
    INTERRUPTED,
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


class ModelChoice(Choice):
    supports_tools: bool | None = None


class SearchChoice(Choice):
    kind: str


class DepthChoice(BaseModel):
    id: str  # "fast" | "standard" | "deep"
    target_minutes: int


class EngineChoice(BaseModel):
    """A research mode the owner can start, and what it can be started with."""

    id: str
    label: str
    search_kinds: list[str]
    stages: list[str]
    needs_tools: bool
    max_sources: int = 1
    # The depth levels at which the owner may set the report's sections.
    sections_at: list[str] = []


class Options(BaseModel):
    engines: list[EngineChoice]
    models: list[ModelChoice]
    search_providers: list[SearchChoice]
    languages: list[str]
    depth_levels: list[DepthChoice]


def engine_choice(name, configured):
    e = ENGINES[name]
    return EngineChoice(
        id=name, label=e["label"], search_kinds=list(e["search"]), stages=list(e["stages"]),
        needs_tools=e["needs_tools"], max_sources=e.get("max_sources", 1),
        sections_at=[d for d in limits.DEPTHS if takes_sections(configured, name, d)],
    )


def takes_sections(configured, engine, depth):
    """Where the owner's headings mean something: STORM's outline, and the
    report plan Agent Research makes at a level set to its deep mode."""
    if engine == "storm":
        return True
    return engine == "agent" and configured.depth(depth).agent.get("mode") == "deep"


@router.get("/options", response_model=Options)
def options(user=Depends(deps.current_user), session=Depends(deps.database)):
    models = session.scalars(select(LlmModel).where(LlmModel.enabled).order_by(LlmModel.label))
    providers = session.scalars(select(SearchProvider).where(SearchProvider.enabled).order_by(SearchProvider.label))
    configured = limits.load(session)
    return Options(
        engines=[engine_choice(name, configured) for name in modes.offered(session)],
        models=[
            ModelChoice(id=str(m.id), label=m.label, is_default=m.is_default, supports_tools=m.supports_tools)
            for m in models
        ],
        search_providers=[
            SearchChoice(id=str(p.id), label=p.label, is_default=p.is_default, kind=p.kind) for p in providers
        ],
        languages=list(report_mod.LANGUAGES),
        depth_levels=[DepthChoice(id=d, target_minutes=configured.depth(d).target_minutes) for d in limits.DEPTHS],
    )


# --- Projects -------------------------------------------------------------------


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class SessionSummary(BaseModel):
    id: str
    title: str
    created_at: datetime
    last_status: str | None
    kind: str = "research"  # "research" | "discussion"


class ProjectDefaults(BaseModel):
    """What the composer starts with inside the Project. Each is a
    suggestion the owner can change before starting; one that no longer
    exists (a model switched off) is simply not preselected."""

    language: Literal["th", "en"] | None = None
    llm_model_id: uuid.UUID | None = None
    search_provider_id: uuid.UUID | None = None
    extra_search_provider_ids: list[uuid.UUID] = Field(default_factory=list, max_length=3)
    depth: Literal["fast", "standard", "deep"] | None = None
    sections: list[str] = Field(default_factory=list, max_length=20)


class ProjectOut(BaseModel):
    id: str
    name: str
    created_at: datetime
    defaults: ProjectDefaults = ProjectDefaults()
    # The Project instructions (litstorm.instructions).
    search_scope: str = ""
    writing_style: str = ""


class ProjectPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    defaults: ProjectDefaults | None = None
    search_scope: str | None = Field(default=None, max_length=2000)
    writing_style: str | None = Field(default=None, max_length=2000)


class ProjectDetail(ProjectOut):
    sessions: list[SessionSummary]


def project_out(p):
    return ProjectOut(
        id=str(p.id), name=p.name, created_at=p.created_at,
        defaults=ProjectDefaults(**(p.defaults or {})),
        search_scope=p.search_scope or "", writing_style=p.writing_style or "",
    )


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


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: uuid.UUID, body: ProjectPatch, user=Depends(deps.current_user), session=Depends(deps.database)
):
    """Rename a Project, or set what research in it starts with. Runs
    already made keep what they were started with."""
    project = deps.own(session, Project, project_id, user)
    if body.name is not None:
        project.name = body.name.strip()
    if body.defaults is not None:
        defaults = body.defaults.model_copy(update={"sections": sections.clean(body.defaults.sections)})
        project.defaults = defaults.model_dump(mode="json", exclude_defaults=True)
    if body.search_scope is not None:
        project.search_scope = body.search_scope.strip() or None
    if body.writing_style is not None:
        project.writing_style = body.writing_style.strip() or None
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
            .where(Run.session_id.in_([s.id for s in sessions]), Run.trashed_at.is_(None))
            .order_by(Run.queued_at)
        ):
            last[run.session_id] = run.status
    return ProjectDetail(
        **project_out(project).model_dump(),
        sessions=[
            SessionSummary(
                id=str(s.id), title=s.title, created_at=s.created_at, last_status=last.get(s.id), kind=s.kind
            )
            for s in sessions
        ],
    )


# --- Research Sessions and Runs -------------------------------------------------------


class QuestionAnswer(BaseModel):
    question: str = Field(max_length=300)
    answer: str = Field(default="", max_length=1000)


class RefineIn(BaseModel):
    topic: str = Field(min_length=3, max_length=500)
    language: str = Field(pattern="^(th|en)$")
    llm_model_id: uuid.UUID | None = None


class RefineOut(BaseModel):
    questions: list[str]


@router.post("/refine", response_model=RefineOut)
def refine_topic(body: RefineIn, user=Depends(deps.current_user), session=Depends(deps.database)):
    """A few questions to make the topic clearer before a Run. Takes no
    quota; counted against a daily cap per User instead."""
    from litstorm import refine, security
    from litstorm.db.models import LlmCredential, QuestionRefinement

    day_start = datetime.now(limits.QUOTA_ZONE).replace(hour=0, minute=0, second=0, microsecond=0)
    asked = session.scalar(
        select(func.count()).select_from(QuestionRefinement).where(
            QuestionRefinement.user_id == user.id, QuestionRefinement.created_at >= day_start
        )
    )
    if asked >= limits.load(session).refinements_per_day:
        raise HTTPException(429, "refine_limit")
    model = _pick(session, LlmModel, body.llm_model_id)
    credential = session.get(LlmCredential, model.provider)
    key = security.decrypt(credential.api_key_ciphertext) if credential else ""
    session.add(QuestionRefinement(user_id=user.id))
    session.commit()  # counted whether or not the model answers: it was asked
    try:
        found = refine.questions(model, key, credential.api_base if credential else None, body.topic.strip(), body.language)
    except refine.RefineError:
        raise HTTPException(502, "refine_failed")
    return RefineOut(questions=found)


class RunIn(BaseModel):
    topic: str = Field(min_length=3, max_length=500)
    language: str = Field(pattern="^(th|en)$")
    llm_model_id: uuid.UUID | None = None  # default model when absent
    search_provider_id: uuid.UUID | None = None  # default provider when absent
    # More Search Providers to search beside it, for an Engine that can
    # (catalog.ENGINES max_sources): STORM, up to two more. The first may be
    # repeated here; what counts is after that is taken out.
    extra_search_provider_ids: list[uuid.UUID] = Field(default_factory=list, max_length=3)
    # The report's top-level sections, one per item (litstorm.sections).
    sections: list[str] = Field(default_factory=list, max_length=20)
    depth: Literal["fast", "standard", "deep"] = "standard"
    engine: str = "storm"  # a research mode from GET /api/options
    # The clarifying questions asked before starting, with the owner's
    # answers; an unanswered one is skipped (POST /api/refine).
    refinement: list["QuestionAnswer"] = Field(default_factory=list, max_length=5)
    # The page's id for one press of "Start". Sending the same key again
    # returns the Run it already made instead of making another.
    request_key: str | None = Field(default=None, max_length=64)


class SessionIn(RunIn):
    """A new Session starts with its first Run."""


class RunOut(BaseModel):
    id: str
    session_id: str
    parent_run_id: str | None
    topic: str
    language: str
    engine: str
    engine_label: str
    model_label: str
    search_label: str
    depth: str
    status: str
    quota_month: str
    stage: str | None
    reason: str | None
    message: str | None
    quota_refunded: bool
    queued_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    report_title: str | None
    source_count: int | None
    # How the Run went, by kind (worker.queue.NOTE_KINDS).
    notes: dict = {}
    # The clarifying questions the owner answered before it started.
    refinement: list[QuestionAnswer] = []
    # The report's sections, as the owner set them.
    sections: list[str] = []
    # The Project instructions it was started with.
    instructions: dict = {}
    # A Discussion's Turn: {"action", "text", "steps"}; None for a Run.
    turn: dict | None = None
    quota_units: int = 1


def run_out(run):
    return RunOut(
        id=str(run.id),
        session_id=str(run.session_id),
        parent_run_id=str(run.parent_run_id) if run.parent_run_id else None,
        topic=run.topic,
        language=run.language,
        engine=run.engine,
        engine_label=ENGINES.get(run.engine, {}).get("label", run.engine),
        model_label=run.config.get("llm", {}).get("label", ""),
        search_label=" + ".join(
            [run.config.get("search", {}).get("label", "")]
            + [x.get("label", "") for x in run.config.get("search_extra") or []]
        ),
        depth=run.config.get("depth", "standard"),
        status=run.status,
        quota_month=run.quota_month,
        stage=run.stage,
        reason=run.reason,
        message=run.message,
        quota_refunded=run.quota_refunded,
        queued_at=run.queued_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        report_title=run.report_title,
        source_count=run.source_count,
        notes=run.notes or {},
        refinement=run.config.get("refinement", []),
        sections=run.config.get("sections", []),
        instructions=run.config.get("instructions", {}),
        turn=run.turn,
        quota_units=run.quota_units if run.quota_units is not None else 1,
    )


class SessionOut(BaseModel):
    id: str
    project_id: str | None  # None: filed in no Project
    project_name: str | None
    title: str
    created_at: datetime
    runs: list[RunOut]
    kind: str = "research"  # "discussion": GET /api/discussions/{id} shows it
    # Shown to an Administrator under a Support Access Grant: nothing can be
    # changed from it.
    read_only: bool = False


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


def _snapshot(session, model, provider, depth="standard", engine="storm"):
    """The parts of a Run's config that come from the current settings,
    including what its depth level means today for its Engine."""
    configured = limits.load(session)
    level = configured.depth(depth)
    params = dict({"agent": level.agent, "deep": level.deep, "co-storm": level.costorm}.get(engine, level.storm))
    if model.max_tokens:
        params["max_tokens"] = model.max_tokens
    return {
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
        # The research model, when the Administrator set one other than this
        # Run's model (litstorm.roles).
        **_fast(session, model),
        "embedding": _embedding(session),
        "depth": depth,
        "target_minutes": level.target_minutes,
        "deadline_minutes": configured.run_deadline_minutes,
    }


def _fast(session, model):
    from litstorm import roles

    fast = roles.fast_model(session)
    return {"fast_llm": roles.snapshot(fast)} if fast is not None and fast.id != model.id else {}


def _embedding(session):
    from litstorm import embedding
    from litstorm.db.models import LlmCredential

    value = embedding.load(session)
    credential = session.get(LlmCredential, value.provider) if value.provider != embedding.BUILTIN else None
    return embedding.snapshot(value, credential)


def _existing(session, owner, request_key):
    if not request_key:
        return None
    return session.scalar(select(Run).where(Run.owner_id == owner.id, Run.request_key == request_key))


def _commit_once(session, owner, request_key):
    """Commit a new Run. If the same request raced in beside it and won,
    return that Run instead (the unique index decided); otherwise None."""
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        earlier = _existing(session, owner, request_key)
        if earlier is None:
            raise
        return earlier
    return None


def _search_snapshot(provider):
    return {
        "id": str(provider.id), "label": provider.label, "provider": provider.kind,
        "endpoint": provider.endpoint, "engines": provider.engines,
    }


def _extra_searches(session, body, first):
    """The other Search Providers the owner ticked, checked as the first is."""
    wanted = list(dict.fromkeys(i for i in body.extra_search_provider_ids if i != first.id))
    if not wanted:
        return []
    if len(wanted) + 1 > ENGINES[body.engine].get("max_sources", 1):
        raise HTTPException(422, "too_many_sources")
    extra = []
    for provider_id in wanted:
        provider = _pick(session, SearchProvider, provider_id)
        if not modes.search_fits(body.engine, provider):
            raise HTTPException(422, "search_not_for_engine")
        extra.append(_search_snapshot(provider))
    return extra


def _instructions(session, research_session):
    """The Project's instructions, copied into the Run as they are now."""
    from litstorm import instructions

    project = session.get(Project, research_session.project_id) if research_session.project_id else None
    kept = instructions.snapshot(project)
    return {"instructions": kept} if kept else {}


def new_run(session, owner, research_session, body, parent_run_id=None):
    """A queued Run with its config snapshot. Secrets are not in it.

    Checks the owner's queue limit and monthly quota first, under a lock on
    the owner's row, so the check and the insert are one step
    (docs/web-app-design.md, ส่งงานหนึ่งครั้ง).
    """
    if body.engine not in modes.offered(session):
        raise HTTPException(422, "engine_not_available")
    # Co-STORM talks in Turns, in a Discussion of its own (api/discussions.py).
    if body.engine == "co-storm" or research_session.kind == DISCUSSION:
        raise HTTPException(422, "use_discussion")
    model = _pick(session, LlmModel, body.llm_model_id)
    provider = _pick(session, SearchProvider, body.search_provider_id)
    # What the page offers for the mode, checked again here: a Run that
    # could only fail half-way is refused before it takes quota.
    if not modes.search_fits(body.engine, provider):
        raise HTTPException(422, "search_not_for_engine")
    if not modes.model_fits(body.engine, model):
        raise HTTPException(422, "model_cannot_use_tools")
    extra = _extra_searches(session, body, provider)
    wanted = sections.clean(body.sections)
    if wanted and not takes_sections(limits.load(session), body.engine, body.depth):
        raise HTTPException(422, "sections_not_for_mode")
    quota.check_submit(session, owner)
    run = Run(
        session_id=research_session.id,
        owner_id=owner.id,
        parent_run_id=parent_run_id,
        engine=body.engine,
        topic=body.topic.strip(),
        language=body.language,
        llm_model_id=model.id,
        search_provider_id=provider.id,
        config={
            **_snapshot(session, model, provider, body.depth, body.engine),
            "refinement": [qa.model_dump() for qa in body.refinement if qa.answer.strip()],
            **({"search_extra": extra} if extra else {}),
            **({"sections": wanted} if wanted else {}),
            **_instructions(session, research_session),
        },
        status=QUEUED,
        quota_month=limits.quota_month(),
        request_key=body.request_key,
    )
    session.add(run)
    return run


def session_out(session, rs):
    runs = session.scalars(
        select(Run).where(Run.session_id == rs.id, Run.trashed_at.is_(None)).order_by(Run.queued_at.desc())
    )
    project = session.get(Project, rs.project_id) if rs.project_id else None
    return SessionOut(
        id=str(rs.id),
        project_id=str(project.id) if project else None,
        project_name=project.name if project else None,
        title=rs.title,
        created_at=rs.created_at,
        runs=[run_out(r) for r in runs],
        kind=rs.kind,
    )


class NewSessionIn(SessionIn):
    project_id: uuid.UUID | None = None  # None: filed in no Project


@router.post("/sessions", response_model=SessionOut, status_code=201)
def create_unfiled_session(body: NewSessionIn, user=Depends(deps.current_user), session=Depends(deps.database)):
    """Research from the home page: a Project is optional, as in ChatGPT,
    Claude and Gemini, and the Session can be filed later."""
    project = deps.own(session, Project, body.project_id, user) if body.project_id else None
    return _start_session(session, user, project, body)


@router.post("/projects/{project_id}/sessions", response_model=SessionOut, status_code=201)
def create_session(
    project_id: uuid.UUID, body: SessionIn, user=Depends(deps.current_user), session=Depends(deps.database)
):
    return _start_session(session, user, deps.own(session, Project, project_id, user), body)


def _start_session(session, user, project, body):
    earlier = _existing(session, user, body.request_key)
    if earlier:
        return session_out(session, session.get(ResearchSession, earlier.session_id))
    rs = ResearchSession(project_id=project.id if project else None, owner_id=user.id, title=body.topic.strip()[:300])
    session.add(rs)
    session.flush()
    new_run(session, user, rs, body)
    earlier = _commit_once(session, user, body.request_key)
    if earlier:
        return session_out(session, session.get(ResearchSession, earlier.session_id))
    return session_out(session, rs)


class RecentSession(BaseModel):
    id: str
    title: str
    project_id: str | None
    project_name: str | None
    last_status: str | None
    updated_at: datetime
    kind: str = "research"


def _sessions(session, user, limit):
    """The owner's live topics, latest activity first. A topic with no Run
    left outside the Trash counts from when it was made."""
    latest = (
        select(Run.session_id, func.max(Run.queued_at).label("at"))
        .where(Run.owner_id == user.id, Run.trashed_at.is_(None), Run.session_id.is_not(None))
        .group_by(Run.session_id)
        .subquery()
    )
    at = func.coalesce(latest.c.at, ResearchSession.created_at)
    rows = session.execute(
        select(ResearchSession, Project.name, at)
        .outerjoin(Project, Project.id == ResearchSession.project_id)
        .outerjoin(latest, latest.c.session_id == ResearchSession.id)
        .where(
            ResearchSession.owner_id == user.id,
            ResearchSession.trashed_at.is_(None),
            or_(ResearchSession.project_id.is_(None), Project.trashed_at.is_(None)),
        )
        .order_by(at.desc())
        .limit(limit)
    ).all()
    out = []
    for rs, project_name, updated in rows:
        status = session.scalar(
            select(Run.status)
            .where(Run.session_id == rs.id, Run.trashed_at.is_(None))
            .order_by(Run.queued_at.desc())
            .limit(1)
        )
        out.append(
            RecentSession(
                id=str(rs.id), title=rs.title, project_id=str(rs.project_id) if rs.project_id else None,
                project_name=project_name, last_status=status, updated_at=updated, kind=rs.kind,
            )
        )
    return out


@router.get("/sessions/recent", response_model=list[RecentSession])
def recent_sessions(
    limit: int = Query(12, ge=1, le=50), user=Depends(deps.current_user), session=Depends(deps.database)
):
    """The latest topics, for the sidebar and the home page."""
    return _sessions(session, user, limit)


@router.get("/sessions", response_model=list[RecentSession])
def list_sessions(
    limit: int = Query(200, ge=1, le=500), user=Depends(deps.current_user), session=Depends(deps.database)
):
    """Every live topic, filed or not, for the All research page."""
    return _sessions(session, user, limit)


class MoveIn(BaseModel):
    project_id: uuid.UUID | None  # None: take it out of its Project


@router.patch("/sessions/{session_id}", response_model=SessionOut)
def move_session(
    session_id: uuid.UUID, body: MoveIn, user=Depends(deps.current_user), session=Depends(deps.database)
):
    """File a topic in a Project, move it to another, or take it out. Its
    Runs and Reports go with it; nothing about them changes."""
    rs = deps.own(session, ResearchSession, session_id, user)
    project = deps.own(session, Project, body.project_id, user) if body.project_id else None
    rs.project_id = project.id if project else None
    session.commit()
    return session_out(session, rs)


@router.get("/sessions/{session_id}", response_model=SessionOut)
def get_session(session_id: uuid.UUID, user=Depends(deps.current_user), session=Depends(deps.database)):
    # Readable under a grant only for a Discussion's grant, which names the
    # topic; a Run's grant names that Run alone (litstorm.support).
    rs = deps.readable(session, ResearchSession, session_id, user, "discussion")
    out = session_out(session, rs)
    out.read_only = rs.owner_id != user.id
    return out


@router.post("/sessions/{session_id}/runs", response_model=RunOut, status_code=201)
def create_run(
    session_id: uuid.UUID, body: RunIn, user=Depends(deps.current_user), session=Depends(deps.database)
):
    rs = deps.own(session, ResearchSession, session_id, user)
    earlier = _existing(session, user, body.request_key)
    if earlier:
        return run_out(earlier)
    run = new_run(session, user, rs, body)
    return run_out(_commit_once(session, user, body.request_key) or run)


class SelectionIn(BaseModel):
    llm_model_id: uuid.UUID
    search_provider_id: uuid.UUID


@router.post("/runs/{run_id}/selection", response_model=RunOut)
def choose_again(
    run_id: uuid.UUID, body: SelectionIn, user=Depends(deps.current_user), session=Depends(deps.database)
):
    """A Run parked because its model or provider was turned off gets a new
    one and goes to the back of its owner's queue. It is the same Run, with
    the same quota reservation: nothing is charged again."""
    run = deps.own(session, Run, run_id, user)
    model = _pick(session, LlmModel, body.llm_model_id)
    provider = _pick(session, SearchProvider, body.search_provider_id)
    snapshot = {**run.config, **_snapshot(session, model, provider, run.config.get("depth", "standard"), run.engine)}
    moved = session.execute(
        update(Run)
        .where(Run.id == run.id, Run.status == NEEDS_SELECTION)
        .values(
            status=QUEUED,
            llm_model_id=model.id,
            search_provider_id=provider.id,
            config=snapshot,
            queued_at=datetime.now(timezone.utc),
        )
    ).rowcount
    if not moved:
        raise HTTPException(409, "not_waiting_for_selection")
    session.commit()
    session.refresh(run)
    return run_out(run)


@router.post("/runs/{run_id}/retry", response_model=RunOut, status_code=201)
def retry(run_id: uuid.UUID, user=Depends(deps.current_user), session=Depends(deps.database)):
    """Try a Run again: a new Run in the same Session, with the same topic
    and settings, linked back to this one, whose history is kept. It starts
    from the beginning (docs/web-app-design.md, ผู้ใช้สั่งลองใหม่).

    If the model or provider it used has since been turned off, the new Run
    waits for the owner to choose again instead of failing.
    """
    old = deps.own(session, Run, run_id, user)
    if old.status not in (FAILED, INTERRUPTED, CANCELLED):
        raise HTTPException(409, "cannot_retry")
    if old.turn is not None:
        # A Turn is asked again as a new Turn, under the Discussion's rules.
        from litstorm.api import discussions

        rs = deps.own(session, ResearchSession, old.session_id, user)
        return run_out(discussions.new_turn(session, user, rs, old.turn))
    model = session.get(LlmModel, old.llm_model_id)
    provider = session.get(SearchProvider, old.search_provider_id)
    available = model is not None and model.enabled and provider is not None and provider.enabled
    quota.check_submit(session, user)
    run = Run(
        session_id=old.session_id,
        owner_id=user.id,
        parent_run_id=old.id,
        engine=old.engine,
        topic=old.topic,
        language=old.language,
        llm_model_id=old.llm_model_id,
        search_provider_id=old.search_provider_id,
        config={
            **_snapshot(session, model, provider, old.config.get("depth", "standard"), old.engine),
            "refinement": old.config.get("refinement", []),
            **({"search_extra": old.config["search_extra"]} if old.config.get("search_extra") else {}),
            **({"sections": old.config["sections"]} if old.config.get("sections") else {}),
            # The instructions it was started with, not the Project's now.
            **({"instructions": old.config["instructions"]} if old.config.get("instructions") else {}),
        } if available else old.config,
        status=QUEUED if available else NEEDS_SELECTION,
        quota_month=limits.quota_month(),
    )
    session.add(run)
    session.commit()
    return run_out(run)


class QuotaOut(BaseModel):
    month: str
    limit: int
    used: int
    reserved: int
    remaining: int


@router.get("/me/quota", response_model=QuotaOut)
def my_quota(user=Depends(deps.current_user), session=Depends(deps.database)):
    u = quota.usage(session, user)
    return QuotaOut(month=u.month, limit=u.limit, used=u.used, reserved=u.reserved, remaining=u.remaining)


class EventOut(BaseModel):
    id: int
    at: datetime
    type: str
    data: dict


class RunDetail(RunOut):
    events: list[EventOut]
    read_only: bool = False


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
    run = deps.readable(session, Run, run_id, user, "run")
    helping = run.owner_id != user.id
    events = session.scalars(
        select(RunEvent).where(RunEvent.run_id == run.id, RunEvent.id > after).order_by(RunEvent.id).limit(500)
    )
    # An Administrator the owner asked for help sees every note, tracebacks
    # included: that is what the help is for.
    shown = [
        EventOut(id=e.id, at=e.at, type=e.type, data=e.data)
        for e in events
        if e.type in ("stage", "usage") or (e.type == "note" and (helping or e.data.get("kind") in _SHOWN_NOTES))
    ]
    return RunDetail(**run_out(run).model_dump(), events=shown, read_only=helping)


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


# --- the Trash -------------------------------------------------------------------


@router.delete("/projects/{project_id}", status_code=204)
def trash_project(project_id: uuid.UUID, user=Depends(deps.current_user), session=Depends(deps.database)):
    trash.trash_project(session, deps.own(session, Project, project_id, user))
    session.commit()


@router.delete("/sessions/{session_id}", status_code=204)
def trash_session(session_id: uuid.UUID, user=Depends(deps.current_user), session=Depends(deps.database)):
    trash.trash_session(session, deps.own(session, ResearchSession, session_id, user))
    session.commit()


@router.delete("/runs/{run_id}", status_code=204)
def trash_run(run_id: uuid.UUID, user=Depends(deps.current_user), session=Depends(deps.database)):
    run = deps.own(session, Run, run_id, user)
    if run.turn is not None:
        # A Turn is part of its Discussion's conversation; the Discussion
        # goes to the Trash as a whole.
        raise HTTPException(409, "part_of_discussion")
    trash.trash_run(session, run)
    session.commit()


class TrashItem(BaseModel):
    kind: str  # "project" | "session" | "run"
    id: str
    title: str
    trashed_at: datetime
    purge_at: datetime


@router.get("/trash", response_model=list[TrashItem])
def list_trash(user=Depends(deps.current_user), session=Depends(deps.database)):
    return [
        TrashItem(kind=k, id=str(i), title=title, trashed_at=at, purge_at=trash.purge_at(at))
        for k, i, title, at in trash.listing(session, user)
    ]


@router.post("/trash/{kind}/{item_id}/restore", status_code=204)
def restore(kind: str, item_id: uuid.UUID, user=Depends(deps.current_user), session=Depends(deps.database)):
    trash.restore(session, user, kind, item_id)
    session.commit()


# --- Reports -------------------------------------------------------------------


def _report(session, run_id, user, what="report"):
    run = deps.readable(session, Run, run_id, user, what)
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

    _, report = _report(session, run_id, user, "export")
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
