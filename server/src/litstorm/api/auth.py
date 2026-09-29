"""First-run setup, signing in and out, and setting a password from a link."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from litstorm import security, settings
from litstorm.api import deps
from litstorm.db.models import AuthSession, PasswordSetupToken, SearchProvider, SystemSetting, User

router = APIRouter(prefix="/api", tags=["auth"])

SESSION_DAYS = 14
LINK_HOURS = 24
SETUP_DONE = "setup_done"


class MeOut(BaseModel):
    id: str
    email: str
    name: str
    role: str
    ui_language: str


def me_out(user):
    return MeOut(id=str(user.id), email=user.email, name=user.name, role=user.role, ui_language=user.ui_language)


def _start_session(response, session, user):
    token, token_hash = security.new_token()
    csrf, _ = security.new_token()
    session.add(
        AuthSession(
            token_hash=token_hash,
            user_id=user.id,
            csrf_token=csrf,
            expires_at=datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS),
        )
    )
    secure = settings.get().cookie_secure
    max_age = SESSION_DAYS * 24 * 3600
    response.set_cookie(
        deps.SESSION_COOKIE, token, httponly=True, samesite="lax", secure=secure, max_age=max_age, path="/"
    )
    response.set_cookie(
        deps.CSRF_COOKIE, csrf, httponly=False, samesite="lax", secure=secure, max_age=max_age, path="/"
    )


def issue_link(session, user):
    """A one-time set-password link for `user`, replacing any earlier one."""
    token, token_hash = security.new_token()
    expires = datetime.now(timezone.utc) + timedelta(hours=LINK_HOURS)
    session.execute(delete(PasswordSetupToken).where(PasswordSetupToken.user_id == user.id))
    session.add(
        PasswordSetupToken(
            user_id=user.id,
            token_hash=token_hash,
            purpose="reset" if user.password_hash else "setup",
            expires_at=expires,
        )
    )
    return f"{settings.get().public_url}/set-password#{token}", expires


# --- first-run setup ------------------------------------------------------


class SetupStatus(BaseModel):
    needed: bool
    code_configured: bool


class SetupIn(BaseModel):
    code: str
    email: EmailStr
    name: str = Field(min_length=1, max_length=200)
    password: str


@router.get("/setup", response_model=SetupStatus)
def setup_status(session=Depends(deps.database)):
    done = session.get(SystemSetting, SETUP_DONE) is not None
    return SetupStatus(needed=not done, code_configured=bool(settings.get().bootstrap_code))


@router.post("/setup", response_model=MeOut)
def setup(body: SetupIn, response: Response, session=Depends(deps.database)):
    code = settings.get().bootstrap_code
    if not code:
        raise HTTPException(409, "bootstrap_code_missing")
    if not security.same(body.code.strip(), code):
        raise HTTPException(403, "bootstrap_code_wrong")
    try:
        password_hash = security.hash_password(body.password)
    except security.WeakPassword:
        raise HTTPException(422, "weak_password")

    # The marker row is the lock: two setups racing both insert it, and the
    # primary key lets exactly one commit. It stays after restarts.
    session.add(SystemSetting(key=SETUP_DONE, value={"at": datetime.now(timezone.utc).isoformat()}))
    admin = User(
        email=body.email.strip().lower(),
        name=body.name.strip(),
        role="admin",
        password_hash=password_hash,
        must_set_password=False,
    )
    session.add(admin)
    _seed_defaults(session)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "setup_done")
    _start_session(response, session, admin)
    session.commit()
    return me_out(admin)


def _seed_defaults(session):
    """The SearXNG that ships in the Compose stack, so the first Run needs only
    an LLM key (docs/web-app-design.md, บริการที่มีให้ตั้งแต่ติดตั้ง)."""
    import os

    # Thai journals: open, no key, and the one source here with Thai research.
    session.add(SearchProvider(label="TCI-ThaiJO", kind="tci"))
    url = os.environ.get("LITSTORM_SEARXNG_URL")
    if url:
        session.add(SearchProvider(label="SearXNG", kind="searxng", endpoint=url, is_default=True))
        # The same instance, asked only its academic engines (the set
        # searxng-LDR-academic turns on; stack/searxng/settings.yml).
        session.add(
            SearchProvider(label="SearXNG LDR-academic", kind="searxng", endpoint=url, engines=ACADEMIC_ENGINES)
        )


ACADEMIC_ENGINES = (
    "arxiv,crossref,europepmc,google scholar,openairedatasets,openairepublications,"
    "openalex,pdbe,pubmed,semantic scholar"
)


# --- signing in -----------------------------------------------------------


class LoginIn(BaseModel):
    email: str
    password: str


@router.post("/auth/login", response_model=MeOut)
def login(body: LoginIn, response: Response, session=Depends(deps.database)):
    user = deps.by_email(session, body.email)
    # One answer for every failure, so the form cannot be used to find
    # which addresses have accounts.
    if (
        user is None
        or not user.is_active
        or user.must_set_password
        or not security.verify_password(user.password_hash, body.password)
    ):
        raise HTTPException(401, "invalid_credentials")
    _start_session(response, session, user)
    session.commit()
    return me_out(user)


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response, session=Depends(deps.database)):
    token = request.cookies.get(deps.SESSION_COOKIE)
    if token:
        session.execute(delete(AuthSession).where(AuthSession.token_hash == security.hash_token(token)))
        session.commit()
    response.delete_cookie(deps.SESSION_COOKIE, path="/")
    response.delete_cookie(deps.CSRF_COOKIE, path="/")


@router.get("/me", response_model=MeOut)
def me(user=Depends(deps.current_user)):
    return me_out(user)


class LanguageIn(BaseModel):
    ui_language: str = Field(pattern="^(th|en)$")


@router.put("/me/language", response_model=MeOut)
def set_language(body: LanguageIn, user=Depends(deps.current_user), session=Depends(deps.database)):
    user = session.merge(user)
    user.ui_language = body.ui_language
    session.commit()
    return me_out(user)


# --- set a password from a link -------------------------------------------


class LinkStatus(BaseModel):
    valid: bool
    email: str | None = None
    purpose: str | None = None


class SetPasswordIn(BaseModel):
    token: str
    password: str


def _link(session, token):
    from sqlalchemy import select

    row = session.scalar(
        select(PasswordSetupToken).where(PasswordSetupToken.token_hash == security.hash_token(token))
    )
    if row is None or row.expires_at <= datetime.now(timezone.utc):
        return None
    return row


@router.post("/auth/password-link", response_model=LinkStatus)
def check_link(body: SetPasswordIn, session=Depends(deps.database)):
    """Whether a link still works — POST, so the token stays out of logs."""
    row = _link(session, body.token)
    if row is None:
        return LinkStatus(valid=False)
    user = session.get(User, row.user_id)
    return LinkStatus(valid=True, email=user.email, purpose=row.purpose)


@router.post("/auth/password", response_model=MeOut)
def set_password(body: SetPasswordIn, response: Response, session=Depends(deps.database)):
    row = _link(session, body.token)
    if row is None:
        raise HTTPException(410, "link_invalid")
    try:
        password_hash = security.hash_password(body.password)
    except security.WeakPassword:
        raise HTTPException(422, "weak_password")
    user = session.get(User, row.user_id)
    if not user.is_active:
        raise HTTPException(410, "link_invalid")
    user.password_hash = password_hash
    user.must_set_password = False
    session.delete(row)  # used once
    session.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    _start_session(response, session, user)
    session.commit()
    return me_out(user)
