"""What only an Administrator does: accounts, models, Search Providers, limits.

Stored keys never leave the server: an admin sees the last four characters
(docs/web-app-design.md, หน้าตั้งค่าบริการภายนอก).
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from litstorm import limits, security
from litstorm.api import deps
from litstorm.api.auth import issue_link
from litstorm.catalog import LLM_PROVIDERS, SEARCH_PROVIDERS
from litstorm.db.models import AuthSession, LlmCredential, LlmModel, SearchProvider, User

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


def user_out(user):
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
    return [user_out(u) for u in session.scalars(select(User).order_by(User.created_at))]


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


class ModelOut(ModelIn):
    id: str


def model_out(m):
    return ModelOut(
        id=str(m.id), label=m.label, provider=m.provider, model=m.model, reasoning=m.reasoning,
        max_tokens=m.max_tokens or {}, enabled=m.enabled, is_default=m.is_default,
    )


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
    session.commit()
    return search_out(row)


# --- limits -------------------------------------------------------------------


@router.get("/limits", response_model=limits.Limits)
def get_limits(session=Depends(deps.database)):
    return limits.load(session)


@router.put("/limits", response_model=limits.Limits)
def put_limits(body: limits.Limits, session=Depends(deps.database)):
    limits.save(session, body)
    session.commit()
    return body
