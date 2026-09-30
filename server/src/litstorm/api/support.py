"""Support Access Grants (litstorm.support): the owner grants, lists and
revokes; an Administrator sees what they have been granted. Reading the
granted Run or Discussion goes through the usual read endpoints
(deps.readable)."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_, select

from litstorm import support
from litstorm.api import deps
from litstorm.db.models import DISCUSSION, ResearchSession, Run, SupportAccess, SupportGrant, User

router = APIRouter(prefix="/api", tags=["support"])


class AdminChoice(BaseModel):
    id: str
    name: str
    email: str


class AccessOut(BaseModel):
    at: datetime
    what: str


class GrantOut(BaseModel):
    id: str
    admin: AdminChoice
    owner_email: str
    kind: str  # "run" | "discussion"
    run_id: str | None
    session_id: str | None
    title: str
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    live: bool
    accesses: list[AccessOut]


class GrantIn(BaseModel):
    admin_id: uuid.UUID
    run_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None


def _admin_choice(user):
    return AdminChoice(id=str(user.id), name=user.name, email=user.email)


def grant_out(session, g):
    admin = session.get(User, g.admin_id)
    owner = session.get(User, g.owner_id)
    run = support.runs_of(session, g)
    rs = session.get(ResearchSession, g.session_id) if g.session_id else None
    accesses = session.scalars(
        select(SupportAccess).where(SupportAccess.grant_id == g.id).order_by(SupportAccess.at.desc()).limit(50)
    ).all()
    return GrantOut(
        id=str(g.id), admin=_admin_choice(admin), owner_email=owner.email,
        kind="discussion" if g.session_id else "run",
        run_id=str(g.run_id) if g.run_id else None, session_id=str(g.session_id) if g.session_id else None,
        title=(rs.title if rs else (run.report_title or run.topic if run else "")),
        created_at=g.created_at, expires_at=g.expires_at, revoked_at=g.revoked_at, live=support.live(g),
        accesses=[AccessOut(at=a.at, what=a.what) for a in accesses],
    )


# --- the owner's side ---------------------------------------------------------------


@router.get("/support/admins", response_model=list[AdminChoice])
def administrators(user=Depends(deps.current_user), session=Depends(deps.database)):
    """Whom the owner can ask for help."""
    return [_admin_choice(a) for a in support.administrators(session, user)]


@router.post("/grants", response_model=GrantOut, status_code=201)
def create_grant(body: GrantIn, user=Depends(deps.current_user), session=Depends(deps.database)):
    if (body.run_id is None) == (body.session_id is None):
        raise HTTPException(422, "grant_one_thing")
    admin = session.get(User, body.admin_id)
    if admin is None or admin.role != "admin" or not admin.is_active or admin.id == user.id:
        raise HTTPException(422, "not_an_administrator")
    run = rs = None
    if body.run_id is not None:
        run = deps.own(session, Run, body.run_id, user)
        if run.turn is not None:
            # A Turn is read with its Discussion; grant the Discussion.
            raise HTTPException(422, "grant_the_discussion")
    else:
        rs = deps.own(session, ResearchSession, body.session_id, user)
        if rs.kind != DISCUSSION:
            # A topic of Runs is granted Run by Run, as the owner chooses.
            raise HTTPException(422, "grant_a_run")
    g = support.grant(session, user, admin, run=run, research_session=rs)
    session.commit()
    return grant_out(session, g)


@router.get("/grants", response_model=list[GrantOut])
def my_grants(
    run_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
    user=Depends(deps.current_user),
    session=Depends(deps.database),
):
    """The owner's grants, newest first; for one Run or Discussion if asked."""
    query = select(SupportGrant).where(SupportGrant.owner_id == user.id)
    if run_id is not None:
        query = query.where(SupportGrant.run_id == run_id)
    if session_id is not None:
        query = query.where(SupportGrant.session_id == session_id)
    return [grant_out(session, g) for g in session.scalars(query.order_by(SupportGrant.created_at.desc()).limit(100))]


@router.delete("/grants/{grant_id}", response_model=GrantOut)
def revoke(grant_id: uuid.UUID, user=Depends(deps.current_user), session=Depends(deps.database)):
    g = session.get(SupportGrant, grant_id)
    if g is None or g.owner_id != user.id:
        raise HTTPException(404, "not_found")
    if g.revoked_at is None:
        g.revoked_at = datetime.now(timezone.utc)
        session.commit()
    return grant_out(session, g)


# --- the Administrator's side ---------------------------------------------------------


@router.get("/admin/support", response_model=list[GrantOut])
def granted_to_me(user=Depends(deps.admin), session=Depends(deps.database)):
    """What owners have granted this Administrator: live ones, and those that
    ended in the last week."""
    since = datetime.now(timezone.utc) - timedelta(days=7)
    rows = session.scalars(
        select(SupportGrant)
        .where(SupportGrant.admin_id == user.id, or_(SupportGrant.expires_at > since, SupportGrant.revoked_at > since))
        .order_by(SupportGrant.created_at.desc())
    )
    return [grant_out(session, g) for g in rows]
