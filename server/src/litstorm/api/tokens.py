"""API tokens and integration accounts, for the MCP server (docs/adr/0009).

A User manages their own tokens under /api/me/tokens; an Administrator sees
and revokes everyone's, turns the server on or off, and makes integration
accounts for other systems, with their tokens.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from litstorm import limits, quota, settings, tokens
from litstorm.api import deps
from litstorm.catalog import ENGINES
from litstorm.db.models import INTEGRATION, ApiToken, Run, User

router = APIRouter(prefix="/api", tags=["tokens"])

MCP_PATH = "/api/mcp"


class TokenOut(BaseModel):
    id: str
    name: str
    prefix: str
    scopes: list[str]
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    state: str  # live | expired | revoked
    owner_id: str
    owner_name: str = ""
    owner_kind: str = "person"


class NewTokenOut(BaseModel):
    """The token itself, shown this once, and its record."""

    token: str
    record: TokenOut


class TokenIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    scopes: list[str] = Field(default_factory=lambda: list(tokens.SCOPES), min_length=1)
    days: int | None = tokens.DEFAULT_LIFETIME


def token_out(row, owner=None):
    return TokenOut(
        id=str(row.id), name=row.name, prefix=row.prefix, scopes=list(row.scopes or []),
        created_at=row.created_at, expires_at=row.expires_at, last_used_at=row.last_used_at,
        state=tokens.state(row), owner_id=str(row.user_id),
        owner_name=owner.name if owner else "", owner_kind=owner.kind if owner else "person",
    )


def _checked(body, allow_forever=False):
    if any(s not in tokens.SCOPES for s in body.scopes):
        raise HTTPException(422, "unknown_scope")
    if body.days is None and not allow_forever:
        raise HTTPException(422, "token_needs_expiry")
    if body.days is not None and body.days not in tokens.LIFETIMES:
        raise HTTPException(422, "unknown_lifetime")


# --- a User's own ---------------------------------------------------------


class ConnectionOut(BaseModel):
    """What a client needs to reach the server, for the setup page."""

    url: str
    enabled: bool
    may_create: bool
    scopes: list[str]
    lifetimes: list[int]


@router.get("/me/connection", response_model=ConnectionOut)
def connection(user=Depends(deps.current_user), session=Depends(deps.database)):
    return ConnectionOut(
        url=settings.get().public_url.rstrip("/") + MCP_PATH,
        enabled=tokens.load(session).enabled,
        may_create=tokens.may_create(session, user),
        scopes=list(tokens.SCOPES),
        lifetimes=list(tokens.LIFETIMES),
    )


@router.get("/me/tokens", response_model=list[TokenOut])
def my_tokens(user=Depends(deps.current_user), session=Depends(deps.database)):
    rows = session.scalars(select(ApiToken).where(ApiToken.user_id == user.id).order_by(ApiToken.created_at.desc()))
    return [token_out(r, user) for r in rows]


@router.post("/me/tokens", response_model=NewTokenOut, status_code=201)
def make_token(body: TokenIn, user=Depends(deps.current_user), session=Depends(deps.database)):
    if not tokens.may_create(session, user):
        raise HTTPException(403, "tokens_not_allowed")
    _checked(body)
    token, row = tokens.issue(session, user, body.name, body.scopes, body.days)
    session.commit()
    return NewTokenOut(token=token, record=token_out(row, user))


@router.delete("/me/tokens/{token_id}", status_code=204)
def revoke_mine(token_id: uuid.UUID, user=Depends(deps.current_user), session=Depends(deps.database)):
    row = session.get(ApiToken, token_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(404, "not_found")
    tokens.revoke(session, row)
    session.commit()


# --- the Administrator's ----------------------------------------------------


admin = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(deps.admin)])


@admin.get("/mcp", response_model=tokens.Settings)
def get_mcp(session=Depends(deps.database)):
    return tokens.load(session)


@admin.put("/mcp", response_model=tokens.Settings)
def put_mcp(body: tokens.Settings, session=Depends(deps.database)):
    tokens.save(session, body)
    session.commit()
    return body


@admin.get("/tokens", response_model=list[TokenOut])
def all_tokens(session=Depends(deps.database)):
    rows = session.execute(select(ApiToken, User).join(User, User.id == ApiToken.user_id).order_by(ApiToken.created_at.desc()))
    return [token_out(t, u) for t, u in rows]


@admin.delete("/tokens/{token_id}", status_code=204)
def revoke_any(token_id: uuid.UUID, session=Depends(deps.database)):
    row = session.get(ApiToken, token_id)
    if row is None:
        raise HTTPException(404, "not_found")
    tokens.revoke(session, row)
    session.commit()


class IntegrationOut(BaseModel):
    id: str
    name: str
    is_active: bool
    monthly_run_quota: int | None
    max_concurrent_runs: int | None
    max_queued_runs: int | None
    allowed_engines: list[str] | None
    created_at: datetime
    quota_limit: int
    quota_used: int
    runs: int
    cost_usd: float
    tokens: list[TokenOut]


class IntegrationIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    monthly_run_quota: int | None = Field(default=None, ge=0)
    max_concurrent_runs: int | None = Field(default=None, ge=0)
    max_queued_runs: int | None = Field(default=None, ge=0)
    # Null: every mode the server offers.
    allowed_engines: list[str] | None = None


class IntegrationPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    is_active: bool | None = None
    monthly_run_quota: int | None = Field(default=None, ge=0)
    max_concurrent_runs: int | None = Field(default=None, ge=0)
    max_queued_runs: int | None = Field(default=None, ge=0)
    allowed_engines: list[str] | None = None


def _integration(session, account_id):
    user = session.get(User, account_id)
    if user is None or user.kind != INTEGRATION:
        raise HTTPException(404, "not_found")
    return user


def _engines(wanted):
    if wanted is not None and any(e not in ENGINES for e in wanted):
        raise HTTPException(422, "unknown_engine")
    return wanted


def integration_out(session, user, configured):
    usage = quota.usage(session, user, configured=configured)
    runs, cost = session.execute(
        select(func.count(), func.coalesce(func.sum(Run.cost_usd), 0)).where(Run.owner_id == user.id)
    ).one()
    rows = session.scalars(select(ApiToken).where(ApiToken.user_id == user.id).order_by(ApiToken.created_at.desc()))
    return IntegrationOut(
        id=str(user.id), name=user.name, is_active=user.is_active,
        monthly_run_quota=user.monthly_run_quota, max_concurrent_runs=user.max_concurrent_runs,
        max_queued_runs=user.max_queued_runs, allowed_engines=user.allowed_engines, created_at=user.created_at,
        quota_limit=usage.limit, quota_used=usage.used, runs=runs, cost_usd=float(cost),
        tokens=[token_out(t, user) for t in rows],
    )


@admin.get("/integrations", response_model=list[IntegrationOut])
def list_integrations(session=Depends(deps.database)):
    configured = limits.load(session)
    users = session.scalars(select(User).where(User.kind == INTEGRATION).order_by(User.created_at))
    return [integration_out(session, u, configured) for u in users]


@admin.post("/integrations", response_model=IntegrationOut, status_code=201)
def create_integration(body: IntegrationIn, session=Depends(deps.database)):
    """An account for another system. It has no password and never signs
    in; its address is made up, unique, and reaches no one."""
    user = User(
        email=f"integration-{uuid.uuid4().hex[:12]}@integrations.invalid",
        name=body.name.strip(), role="user", kind=INTEGRATION, must_set_password=False,
        monthly_run_quota=body.monthly_run_quota, max_concurrent_runs=body.max_concurrent_runs,
        max_queued_runs=body.max_queued_runs, allowed_engines=_engines(body.allowed_engines),
    )
    session.add(user)
    session.commit()
    return integration_out(session, user, limits.load(session))


@admin.patch("/integrations/{account_id}", response_model=IntegrationOut)
def patch_integration(account_id: uuid.UUID, body: IntegrationPatch, session=Depends(deps.database)):
    user = _integration(session, account_id)
    changes = body.model_dump(exclude_unset=True)
    if "allowed_engines" in changes:
        _engines(changes["allowed_engines"])
    for key, value in changes.items():
        setattr(user, key, value)
    session.commit()
    return integration_out(session, user, limits.load(session))


class IntegrationTokenIn(TokenIn):
    days: int | None = None  # a system's key may be made without expiry


@admin.post("/integrations/{account_id}/tokens", response_model=NewTokenOut, status_code=201)
def make_integration_token(
    account_id: uuid.UUID, body: IntegrationTokenIn, me=Depends(deps.admin), session=Depends(deps.database)
):
    user = _integration(session, account_id)
    _checked(body, allow_forever=True)
    token, row = tokens.issue(session, user, body.name, body.scopes, body.days, created_by=me)
    session.commit()
    return NewTokenOut(token=token, record=token_out(row, user))
