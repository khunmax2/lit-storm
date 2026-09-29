"""What every request needs: a database session and the signed-in User.

Sessions are server-side rows keyed by a random cookie (docs/adr/0002). A
request that changes anything must also carry the session's CSRF token in a
header; the token is readable by the page (a second, non-httpOnly cookie) but
not by another site.
"""

from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select

from litstorm import db, security
from litstorm.db.models import AuthSession, User

SESSION_COOKIE = "litstorm_session"
CSRF_COOKIE = "litstorm_csrf"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def database():
    with db.sessions()() as session:
        yield session


def _signed_in(request, session):
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None, None
    row = session.get(AuthSession, security.hash_token(token))
    if row is None or row.expires_at <= datetime.now(timezone.utc):
        return None, None
    user = session.get(User, row.user_id)
    if user is None or not user.is_active or user.must_set_password:
        return None, None
    return user, row


def current_user(request: Request, session=Depends(database)) -> User:
    user, auth = _signed_in(request, session)
    if user is None:
        raise HTTPException(401, "not_signed_in")
    if request.method not in SAFE_METHODS and not security.same(
        request.headers.get(CSRF_HEADER), auth.csrf_token
    ):
        raise HTTPException(403, "csrf")
    return user


def admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "admin_only")
    return user


def own(session, model, row_id, user):
    """The row, if it exists, is not in the Trash, and belongs to `user`.

    Anything else is a 404 — including someone else's row, so ids cannot be
    probed for existence.
    """
    from litstorm import trash
    from litstorm.db.models import ResearchSession, Run

    row = session.get(model, row_id)
    if row is None or row.owner_id != user.id or getattr(row, "trashed_at", None):
        raise HTTPException(404, "not_found")
    # Inside something that is in the Trash counts as in the Trash.
    if model is ResearchSession and not trash.session_alive(session, row):
        raise HTTPException(404, "not_found")
    if model is Run and not trash.run_alive(session, row):
        raise HTTPException(404, "not_found")
    return row


def by_email(session, email):
    return session.scalar(select(User).where(User.email == email.strip().lower()))
