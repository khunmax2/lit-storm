"""Discussions: Co-STORM, one Turn at a time (litstorm.discussion).

Starting one makes a Research Session of kind "discussion" and queues its
first Turn, the warm start. Each later Turn is asked for here and waits in
the same queue as Runs; the page polls the Discussion to see it done.
"""

import json
import os
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from litstorm import discussion, limits, modes, quota
from litstorm.api import deps
from litstorm.api.research import (
    RunOut,
    _commit_once,
    _existing,
    _pick,
    _snapshot,
    run_out,
)
from litstorm.db.models import (
    DISCUSSION,
    QUEUED,
    SUCCEEDED,
    LlmModel,
    Project,
    ResearchSession,
    Run,
    SearchProvider,
)

router = APIRouter(prefix="/api/discussions", tags=["discussions"])

ENGINE = "co-storm"


class DiscussionIn(BaseModel):
    topic: str = Field(min_length=3, max_length=500)
    language: str = Field(pattern="^(th|en)$")
    llm_model_id: uuid.UUID | None = None
    search_provider_id: uuid.UUID | None = None
    depth: Literal["fast", "standard", "deep"] = "standard"
    project_id: uuid.UUID | None = None
    request_key: str | None = Field(default=None, max_length=64)


class TurnIn(BaseModel):
    action: Literal["say", "step", "auto", "report", "start"]
    text: str = Field(default="", max_length=2000)
    steps: int = Field(default=3, ge=1, le=10)
    # Set when the owner agreed to take another quota unit because the
    # block of Turns is used up.
    extend: bool = False
    request_key: str | None = Field(default=None, max_length=64)


class AllowanceOut(BaseModel):
    per_block: int
    blocks: int
    used: int
    remaining: int


class ReportRef(BaseModel):
    run_id: str
    title: str | None
    source_count: int | None
    finished_at: str | None


class DiscussionOut(BaseModel):
    id: str
    project_id: str | None
    project_name: str | None
    title: str
    language: str
    depth: str
    model_label: str
    search_label: str
    turns: list[RunOut]
    allowance: AllowanceOut
    # The Turn waiting or running now, if any.
    current: RunOut | None
    # What the last finished Turn left: who said what, the mind map, the
    # sources (engines/costorm/engine.py, view). None before the warm start.
    view: dict | None
    reports: list[ReportRef]


def _load_view(rows):
    run, _ = discussion.last_state(rows)
    if run is None:
        return None
    try:
        with open(os.path.join(discussion.workspace(run), discussion.VIEW), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def discussion_out(session, rs):
    rows = discussion.turns(session, rs)
    configured = limits.load(session)
    allowed = discussion.allowance(rows, configured.turns_per_quota)
    first = rows[0] if rows else None
    last = rows[-1] if rows else None
    project = session.get(Project, rs.project_id) if rs.project_id else None
    current = discussion.in_progress(rows)
    return DiscussionOut(
        id=str(rs.id),
        project_id=str(project.id) if project else None,
        project_name=project.name if project else None,
        title=rs.title,
        language=first.language if first else "th",
        depth=first.config.get("depth", "standard") if first else "standard",
        model_label=(last.config.get("llm", {}).get("label", "") if last else ""),
        search_label=(last.config.get("search", {}).get("label", "") if last else ""),
        turns=[run_out(r) for r in rows],
        allowance=AllowanceOut(
            per_block=allowed.per_block, blocks=allowed.blocks, used=allowed.used, remaining=allowed.remaining
        ),
        current=run_out(current) if current else None,
        view=_load_view(rows),
        reports=[
            ReportRef(
                run_id=str(r.id), title=r.report_title, source_count=r.source_count,
                finished_at=r.finished_at.isoformat() if r.finished_at else None,
            )
            for r in rows
            if r.status == SUCCEEDED and (r.turn or {}).get("action") == "report"
        ],
    )


def _discussion(session, session_id, user, lock=False):
    rs = deps.own(session, ResearchSession, session_id, user)
    if rs.kind != DISCUSSION:
        raise HTTPException(404, "not_found")
    if lock:
        # Two Turns asked for at once: only one gets through the checks.
        session.execute(select(ResearchSession.id).where(ResearchSession.id == rs.id).with_for_update())
    return rs


def new_turn(session, user, rs, asked, model=None, provider=None, depth=None, language=None, extend=False):
    """Queue a Turn after checking it may be asked now. Commits."""
    rows = discussion.turns(session, rs)
    if discussion.in_progress(rows):
        raise HTTPException(409, "turn_in_progress")
    action = asked.get("action")
    started = any(r.status == SUCCEEDED and (r.turn or {}).get("action") == "start" for r in rows)
    if action == "start" and started:
        raise HTTPException(409, "already_started")
    if action != "start" and not started:
        raise HTTPException(409, "not_started")
    if action == "say" and not (asked.get("text") or "").strip():
        raise HTTPException(422, "nothing_said")

    configured = limits.load(session)
    allowed = discussion.allowance(rows, configured.turns_per_quota)
    units = 0
    if allowed.remaining <= 0:
        # Nothing paid for yet (the first warm start, or one whose quota came
        # back) takes a unit as a matter of course; a used-up block only when
        # the owner has agreed to extend.
        if allowed.blocks > 0 and not extend:
            raise HTTPException(409, "turns_exhausted")
        units = 1
    quota.check_submit(session, user, units=units)

    last = rows[-1] if rows else None
    model = model or (session.get(LlmModel, last.llm_model_id) if last else None)
    provider = provider or (session.get(SearchProvider, last.search_provider_id) if last else None)
    if model is None or provider is None:
        raise HTTPException(422, "choice_not_available")
    depth = depth or (last.config.get("depth", "standard") if last else "standard")
    language = language or (last.language if last else "th")
    turn = {"action": action}
    if action == "say":
        turn["text"] = asked["text"].strip()
    if action == "auto":
        turn["steps"] = int(asked.get("steps") or 3)
    run = Run(
        session_id=rs.id,
        owner_id=user.id,
        engine=ENGINE,
        topic=rs.title,
        language=language,
        llm_model_id=model.id,
        search_provider_id=provider.id,
        config=_snapshot(session, model, provider, depth, ENGINE),
        status=QUEUED,
        quota_month=limits.quota_month(),
        quota_units=units,
        turn=turn,
        request_key=asked.get("request_key"),
    )
    session.add(run)
    # The model or provider switched off since the last Turn: the Turn waits
    # for its owner to choose again, as a Run would (worker.queue).
    from litstorm.worker.queue import park_unavailable

    session.flush()
    park_unavailable(session)
    return _commit_once(session, user, asked.get("request_key")) or run


@router.post("", response_model=DiscussionOut, status_code=201)
def start(body: DiscussionIn, user=Depends(deps.current_user), session=Depends(deps.database)):
    earlier = _existing(session, user, body.request_key)
    if earlier:
        return discussion_out(session, session.get(ResearchSession, earlier.session_id))
    if ENGINE not in modes.offered(session):
        raise HTTPException(422, "engine_not_available")
    model = _pick(session, LlmModel, body.llm_model_id)
    provider = _pick(session, SearchProvider, body.search_provider_id)
    if not modes.search_fits(ENGINE, provider):
        raise HTTPException(422, "search_not_for_engine")
    if not modes.model_fits(ENGINE, model):
        raise HTTPException(422, "model_cannot_use_tools")
    project = deps.own(session, Project, body.project_id, user) if body.project_id else None
    rs = ResearchSession(
        project_id=project.id if project else None, owner_id=user.id, title=body.topic.strip()[:300], kind=DISCUSSION
    )
    session.add(rs)
    session.flush()
    run = new_turn(
        session, user, rs, {"action": "start", "request_key": body.request_key},
        model=model, provider=provider, depth=body.depth, language=body.language,
    )
    return discussion_out(session, session.get(ResearchSession, run.session_id))


@router.get("/{session_id}", response_model=DiscussionOut)
def get(session_id: uuid.UUID, user=Depends(deps.current_user), session=Depends(deps.database)):
    return discussion_out(session, _discussion(session, session_id, user))


@router.post("/{session_id}/turns", response_model=RunOut, status_code=201)
def ask(session_id: uuid.UUID, body: TurnIn, user=Depends(deps.current_user), session=Depends(deps.database)):
    earlier = _existing(session, user, body.request_key)
    if earlier:
        return run_out(earlier)
    rs = _discussion(session, session_id, user, lock=True)
    asked = {"action": body.action, "text": body.text, "steps": body.steps, "request_key": body.request_key}
    return run_out(new_turn(session, user, rs, asked, extend=body.extend))
