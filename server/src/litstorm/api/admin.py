"""What only an Administrator does: accounts, models, Search Providers, limits.

Stored keys never leave the server: an admin sees the last four characters
(docs/web-app-design.md, หน้าตั้งค่าบริการภายนอก).
"""

import uuid
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from litstorm import checks, embedding, limits, quota, security
from litstorm.api import deps
from litstorm.api.auth import issue_link
from litstorm.catalog import LLM_PROVIDERS, SEARCH_PROVIDERS
from litstorm.db.models import AuthSession, LlmCredential, LlmModel, Run, SearchProvider, User

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(deps.admin)])


# --- users ----------------------------------------------------------------


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str
    is_active: bool
    has_password: bool
    monthly_run_quota: int | None
    max_concurrent_runs: int | None
    max_queued_runs: int | None
    created_at: datetime
    # This month's quota, as the User sees it.
    quota_limit: int | None = None
    quota_used: int | None = None
    quota_reserved: int | None = None


def user_out(user, usage=None):
    return UserOut(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        has_password=bool(user.password_hash) and not user.must_set_password,
        monthly_run_quota=user.monthly_run_quota,
        max_concurrent_runs=user.max_concurrent_runs,
        max_queued_runs=user.max_queued_runs,
        created_at=user.created_at,
        quota_limit=usage.limit if usage else None,
        quota_used=usage.used if usage else None,
        quota_reserved=usage.reserved if usage else None,
    )


class UserIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=200)
    role: str = Field(default="user", pattern="^(user|admin)$")


class LinkOut(BaseModel):
    user: UserOut
    link: str
    expires_at: datetime


class UserPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    role: str | None = Field(default=None, pattern="^(user|admin)$")
    is_active: bool | None = None
    # Explicit null clears an override back to the global default.
    monthly_run_quota: int | None = Field(default=None, ge=0)
    max_concurrent_runs: int | None = Field(default=None, ge=0)
    max_queued_runs: int | None = Field(default=None, ge=0)


@router.get("/users", response_model=list[UserOut])
def list_users(session=Depends(deps.database)):
    configured = limits.load(session)
    return [
        user_out(u, quota.usage(session, u, configured=configured))
        for u in session.scalars(select(User).order_by(User.created_at))
    ]


@router.post("/users", response_model=LinkOut, status_code=201)
def create_user(body: UserIn, session=Depends(deps.database)):
    user = User(email=body.email.strip().lower(), name=body.name.strip(), role=body.role, must_set_password=True)
    session.add(user)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "email_taken")
    link, expires = issue_link(session, user)
    session.commit()
    return LinkOut(user=user_out(user), link=link, expires_at=expires)


@router.post("/users/{user_id}/link", response_model=LinkOut)
def reset_link(user_id: uuid.UUID, admin=Depends(deps.admin), session=Depends(deps.database)):
    """Issue a set-password link. For an account that has a password this is
    a reset: the old password stops working and the User is signed out
    everywhere until they choose a new one."""
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(404, "not_found")
    link, expires = issue_link(session, user)
    if user.password_hash:
        user.must_set_password = True
        session.execute(AuthSession.__table__.delete().where(AuthSession.user_id == user.id))
    session.commit()
    return LinkOut(user=user_out(user), link=link, expires_at=expires)


@router.patch("/users/{user_id}", response_model=UserOut)
def patch_user(user_id: uuid.UUID, body: UserPatch, admin=Depends(deps.admin), session=Depends(deps.database)):
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(404, "not_found")
    changes = body.model_dump(exclude_unset=True)
    if user.id == admin.id and (changes.get("role") == "user" or changes.get("is_active") is False):
        raise HTTPException(409, "cannot_demote_self")
    for key, value in changes.items():
        setattr(user, key, value)
    if changes.get("is_active") is False:
        session.execute(AuthSession.__table__.delete().where(AuthSession.user_id == user.id))
    session.commit()
    return user_out(user)


# --- LLM credentials and models --------------------------------------------


class CredentialOut(BaseModel):
    provider: str
    key_hint: str
    api_base: str | None


class CredentialIn(BaseModel):
    api_key: str = Field(min_length=1)
    api_base: str | None = None


@router.get("/llm-credentials", response_model=list[CredentialOut])
def list_credentials(session=Depends(deps.database)):
    rows = {c.provider: c for c in session.scalars(select(LlmCredential))}
    return [
        CredentialOut(
            provider=name,
            key_hint=security.hint(security.decrypt(rows[name].api_key_ciphertext)) if name in rows else "",
            api_base=rows[name].api_base if name in rows else None,
        )
        for name in LLM_PROVIDERS
    ]


@router.put("/llm-credentials/{provider}", response_model=CredentialOut)
def put_credential(provider: str, body: CredentialIn, session=Depends(deps.database)):
    if provider not in LLM_PROVIDERS:
        raise HTTPException(404, "unknown_provider")
    if LLM_PROVIDERS[provider].get("needs_base") and not body.api_base:
        raise HTTPException(422, "api_base_required")
    row = session.get(LlmCredential, provider) or LlmCredential(provider=provider)
    row.api_key_ciphertext = security.encrypt(body.api_key.strip())
    row.api_base = body.api_base
    session.add(row)
    session.commit()
    return CredentialOut(provider=provider, key_hint=security.hint(body.api_key.strip()), api_base=row.api_base)


@router.delete("/llm-credentials/{provider}", status_code=204)
def delete_credential(provider: str, session=Depends(deps.database)):
    row = session.get(LlmCredential, provider)
    if row:
        session.delete(row)
        session.commit()


class ModelIn(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    provider: str
    model: str = Field(min_length=1, max_length=200)
    reasoning: str = ""
    max_tokens: dict = Field(default_factory=dict)
    enabled: bool = True
    is_default: bool = False
    # USD per million tokens; leave empty to use LiteLLM's price table.
    price_in_per_mtok: Decimal | None = Field(default=None, ge=0)
    price_out_per_mtok: Decimal | None = Field(default=None, ge=0)


class ModelOut(ModelIn):
    id: str


def model_out(m):
    return ModelOut(
        id=str(m.id), label=m.label, provider=m.provider, model=m.model, reasoning=m.reasoning,
        max_tokens=m.max_tokens or {}, enabled=m.enabled, is_default=m.is_default,
        price_in_per_mtok=m.price_in_per_mtok, price_out_per_mtok=m.price_out_per_mtok,
    )


def _park(session):
    """Turning a model or provider off parks the queued Runs that chose it,
    now rather than when the Worker next looks, so their owners see it."""
    from litstorm.worker.queue import park_unavailable

    park_unavailable(session)


def _clear_default(session, table, wanted, keep_id=None):
    """Unset the current default before a new one is written: one default
    at most is enforced by a unique index, checked row by row."""
    if wanted:
        query = update(table).values(is_default=False)
        if keep_id is not None:
            query = query.where(table.id != keep_id)
        session.execute(query)


@router.get("/llm-models", response_model=list[ModelOut])
def list_models(session=Depends(deps.database)):
    return [model_out(m) for m in session.scalars(select(LlmModel).order_by(LlmModel.created_at))]


def _check_model(body):
    if body.provider not in LLM_PROVIDERS:
        raise HTTPException(422, "unknown_provider")
    if body.is_default and not body.enabled:
        raise HTTPException(422, "default_must_be_enabled")


@router.post("/llm-models", response_model=ModelOut, status_code=201)
def create_model(body: ModelIn, session=Depends(deps.database)):
    _check_model(body)
    _clear_default(session, LlmModel, body.is_default)
    row = LlmModel(**body.model_dump())
    session.add(row)
    session.commit()
    return model_out(row)


@router.put("/llm-models/{model_id}", response_model=ModelOut)
def update_model(model_id: uuid.UUID, body: ModelIn, session=Depends(deps.database)):
    _check_model(body)
    row = session.get(LlmModel, model_id)
    if row is None:
        raise HTTPException(404, "not_found")
    _clear_default(session, LlmModel, body.is_default, keep_id=row.id)
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    session.flush()
    _park(session)
    session.commit()
    return model_out(row)


# --- Search Providers -------------------------------------------------------


class SearchIn(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    kind: str
    endpoint: str | None = None
    engines: str | None = None
    # Absent keeps the stored key; "" removes it.
    api_key: str | None = None
    enabled: bool = True
    is_default: bool = False


class SearchOut(BaseModel):
    id: str
    label: str
    kind: str
    endpoint: str | None
    engines: str | None
    key_hint: str
    enabled: bool
    is_default: bool


def search_out(p):
    return SearchOut(
        id=str(p.id), label=p.label, kind=p.kind, endpoint=p.endpoint, engines=p.engines,
        key_hint=security.hint(security.decrypt(p.api_key_ciphertext)), enabled=p.enabled,
        is_default=p.is_default,
    )


def _check_search(body):
    if body.kind not in SEARCH_PROVIDERS:
        raise HTTPException(422, "unknown_kind")
    if body.kind == "searxng" and not body.endpoint:
        raise HTTPException(422, "endpoint_required")
    if body.is_default and not body.enabled:
        raise HTTPException(422, "default_must_be_enabled")


def _apply_search(row, body):
    data = body.model_dump(exclude={"api_key"})
    for key, value in data.items():
        setattr(row, key, value)
    if body.api_key is not None:
        row.api_key_ciphertext = security.encrypt(body.api_key.strip()) if body.api_key.strip() else None


@router.get("/search-providers", response_model=list[SearchOut])
def list_search(session=Depends(deps.database)):
    return [search_out(p) for p in session.scalars(select(SearchProvider).order_by(SearchProvider.created_at))]


@router.post("/search-providers", response_model=SearchOut, status_code=201)
def create_search(body: SearchIn, session=Depends(deps.database)):
    _check_search(body)
    _clear_default(session, SearchProvider, body.is_default)
    row = SearchProvider()
    _apply_search(row, body)
    session.add(row)
    session.commit()
    return search_out(row)


@router.put("/search-providers/{provider_id}", response_model=SearchOut)
def update_search(provider_id: uuid.UUID, body: SearchIn, session=Depends(deps.database)):
    _check_search(body)
    row = session.get(SearchProvider, provider_id)
    if row is None:
        raise HTTPException(404, "not_found")
    _clear_default(session, SearchProvider, body.is_default, keep_id=row.id)
    _apply_search(row, body)
    session.flush()
    _park(session)
    session.commit()
    return search_out(row)


# --- test buttons ---------------------------------------------------------------------------


class CheckOut(BaseModel):
    ok: bool
    message: str
    seconds: float
    # A few titles the search found, so the Administrator sees what it returns.
    samples: list[str] = []


@router.post("/llm-models/{model_id}/test", response_model=CheckOut)
def test_model(model_id: uuid.UUID, session=Depends(deps.database)):
    model = session.get(LlmModel, model_id)
    if model is None:
        raise HTTPException(404, "not_found")
    credential = session.get(LlmCredential, model.provider)
    key = security.decrypt(credential.api_key_ciphertext) if credential else ""
    ok, message, seconds = checks.llm(model, key, credential.api_base if credential else None)
    return CheckOut(ok=ok, message=message, seconds=round(seconds, 2))


class ModelDraftIn(BaseModel):
    provider: str
    model: str = Field(min_length=1, max_length=200)
    reasoning: str = ""
    max_tokens: dict = Field(default_factory=dict)
    # Absent: test with the key and base already stored for the provider.
    api_key: str | None = None
    api_base: str | None = None


@router.post("/llm-models/check", response_model=CheckOut)
def check_model_draft(body: ModelDraftIn, session=Depends(deps.database)):
    """Test the model in the dialog before it is saved, with a key typed
    there or the one stored for its provider."""
    if body.provider not in LLM_PROVIDERS:
        raise HTTPException(422, "unknown_provider")
    credential = session.get(LlmCredential, body.provider)
    key = (body.api_key or "").strip() or (security.decrypt(credential.api_key_ciphertext) if credential else "")
    base = (body.api_base or "").strip() or (credential.api_base if credential else None)
    if LLM_PROVIDERS[body.provider].get("needs_base") and not base:
        return CheckOut(ok=False, message="this provider needs an API base URL", seconds=0.0)
    draft = SimpleNamespace(
        provider=body.provider, model=body.model.strip(), reasoning=body.reasoning, max_tokens=body.max_tokens
    )
    ok, message, seconds = checks.llm(draft, key, base)
    return CheckOut(ok=ok, message=message, seconds=round(seconds, 2))


@router.post("/search-providers/{provider_id}/test", response_model=CheckOut)
def test_search(provider_id: uuid.UUID, session=Depends(deps.database)):
    provider = session.get(SearchProvider, provider_id)
    if provider is None:
        raise HTTPException(404, "not_found")
    ok, message, seconds, samples = checks.search(provider, security.decrypt(provider.api_key_ciphertext))
    return CheckOut(ok=ok, message=message, seconds=round(seconds, 2), samples=samples)


class SearchDraftIn(BaseModel):
    kind: str
    endpoint: str | None = None
    engines: str | None = None
    # Absent while editing: test with the key already stored for `id`.
    api_key: str | None = None
    id: uuid.UUID | None = None
    query: str | None = Field(default=None, max_length=200)


@router.post("/search-providers/check", response_model=CheckOut)
def check_search_draft(body: SearchDraftIn, session=Depends(deps.database)):
    """Test what is in the dialog before it is saved, so a key can be tried
    where it is typed."""
    if body.kind not in SEARCH_PROVIDERS:
        raise HTTPException(422, "unknown_kind")
    key = body.api_key
    if key is None and body.id is not None:
        stored = session.get(SearchProvider, body.id)
        key = security.decrypt(stored.api_key_ciphertext) if stored else None
    draft = SimpleNamespace(kind=body.kind, endpoint=(body.endpoint or "").strip(), engines=(body.engines or "").strip())
    ok, message, seconds, samples = checks.search(draft, (key or "").strip(), body.query)
    return CheckOut(ok=ok, message=message, seconds=round(seconds, 2), samples=samples)


# --- embedding service ------------------------------------------------------
# One for the whole system (litstorm.embedding). Its key is the LLM
# credential of its provider, so there is no key field of its own.


class EmbeddingOut(embedding.Embedding):
    # The address a Run would call, once the provider's and the stored
    # credential's are taken into account; empty for the built-in model.
    resolved_base: str = ""
    has_key: bool = False


def _embedding_out(session, value):
    credential = session.get(LlmCredential, value.provider) if value.provider != embedding.BUILTIN else None
    return EmbeddingOut(
        **value.model_dump(),
        resolved_base="" if value.provider == embedding.BUILTIN else embedding.base_url(
            value, credential.api_base if credential else None
        ),
        has_key=bool(embedding.key_for(value, credential)),
    )


@router.get("/embedding", response_model=EmbeddingOut)
def get_embedding(session=Depends(deps.database)):
    return _embedding_out(session, embedding.load(session))


@router.put("/embedding", response_model=EmbeddingOut)
def put_embedding(body: embedding.Embedding, session=Depends(deps.database)):
    body = body.model_copy(update={"model": body.model.strip(), "api_base": (body.api_base or "").strip() or None})
    credential = session.get(LlmCredential, body.provider)
    wrong = embedding.problem(body, credential.api_base if credential else None)
    if wrong:
        raise HTTPException(422, wrong)
    embedding.save(session, body)
    session.commit()
    return _embedding_out(session, body)


@router.post("/embedding/check", response_model=CheckOut)
def check_embedding(body: embedding.Embedding, session=Depends(deps.database)):
    """Test the setting in the form before it is saved."""
    body = body.model_copy(update={"model": body.model.strip(), "api_base": (body.api_base or "").strip() or None})
    credential = session.get(LlmCredential, body.provider)
    ok, message, seconds = embedding.check(
        body, embedding.key_for(body, credential), credential.api_base if credential else None
    )
    return CheckOut(ok=ok, message=message, seconds=round(seconds, 2))


# --- usage ---------------------------------------------------------------------------------------
# What an Administrator sees of other people's research: who, when, how
# much, with which model, and how it ended — never the topic or the report
# (docs/web-app-design.md, สิทธิ์ผู้ดูแลต่อเนื้อหางานวิจัย).


class UsageRow(BaseModel):
    user_id: str
    email: str
    runs: int
    succeeded: int
    failed: int
    refunded: int
    tokens_in: int
    tokens_out: int
    search_calls: int
    cost_usd: Decimal | None
    # True when some Run's cost is unknown, so the sum is a lower bound.
    cost_incomplete: bool


class UsageOut(BaseModel):
    month: str
    rows: list[UsageRow]
    total_cost_usd: Decimal | None


@router.get("/usage", response_model=UsageOut)
def usage(month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"), session=Depends(deps.database)):
    month = month or limits.quota_month()
    started = Run.started_at.is_not(None)
    rows = session.execute(
        select(
            User.id,
            User.email,
            func.count(Run.id).filter(started),
            func.count(Run.id).filter(Run.status == "succeeded"),
            func.count(Run.id).filter(Run.status.in_(("failed", "interrupted"))),
            func.count(Run.id).filter(Run.quota_refunded.is_(True)),
            func.coalesce(func.sum(Run.tokens_in), 0),
            func.coalesce(func.sum(Run.tokens_out), 0),
            func.coalesce(func.sum(Run.search_calls), 0),
            func.sum(Run.cost_usd),
            func.count(Run.id).filter(started, Run.finished_at.is_not(None), Run.cost_usd.is_(None)),
        )
        .join(Run, (Run.owner_id == User.id) & (Run.quota_month == month))
        .group_by(User.id, User.email)
        .order_by(User.email)
    ).all()
    out = [
        UsageRow(
            user_id=str(r[0]), email=r[1], runs=r[2], succeeded=r[3], failed=r[4], refunded=r[5],
            tokens_in=r[6], tokens_out=r[7], search_calls=r[8], cost_usd=r[9], cost_incomplete=r[10] > 0,
        )
        for r in rows
    ]
    total = sum((r.cost_usd for r in out if r.cost_usd is not None), Decimal(0))
    return UsageOut(month=month, rows=out, total_cost_usd=total if out else None)


class AdminRunOut(BaseModel):
    id: str
    email: str
    status: str
    reason: str | None
    model_label: str
    queued_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    tokens_in: int | None
    tokens_out: int | None
    search_calls: int | None
    cost_usd: Decimal | None
    quota_refunded: bool


@router.get("/runs", response_model=list[AdminRunOut])
def recent_runs(limit: int = Query(default=100, le=500), session=Depends(deps.database)):
    rows = session.execute(
        select(Run, User.email).join(User, User.id == Run.owner_id).order_by(Run.queued_at.desc()).limit(limit)
    ).all()
    return [
        AdminRunOut(
            id=str(run.id), email=email, status=run.status, reason=run.reason,
            model_label=run.config.get("llm", {}).get("label", ""),
            queued_at=run.queued_at, started_at=run.started_at, finished_at=run.finished_at,
            tokens_in=run.tokens_in, tokens_out=run.tokens_out, search_calls=run.search_calls,
            cost_usd=run.cost_usd, quota_refunded=run.quota_refunded,
        )
        for run, email in rows
    ]


# --- limits -------------------------------------------------------------------


@router.get("/limits", response_model=limits.Limits)
def get_limits(session=Depends(deps.database)):
    return limits.load(session)


@router.put("/limits", response_model=limits.Limits)
def put_limits(body: limits.Limits, session=Depends(deps.database)):
    limits.save(session, body)
    session.commit()
    return body
