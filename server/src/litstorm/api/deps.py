"""What every request needs: a database session and the signed-in User.

Sessions are server-side rows keyed by a random cookie (docs/adr/0002). A
request that changes anything must also carry the session's CSRF token in a
header; the token is readable by the page (a second, non-httpOnly cookie) but
not by another site.
"""

import asyncio
import weakref
from datetime import datetime, timezone

import anyio
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select

from litstorm import db, security
from litstorm.db.models import AuthSession, User

SESSION_COOKIE = "litstorm_session"
CSRF_COOKIE = "litstorm_csrf"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


_slots = weakref.WeakKeyDictionary()  # event loop -> its Semaphore


def _request_slots():
    loop = asyncio.get_running_loop()
    slots = _slots.get(loop)
    if slots is None:
        slots = _slots[loop] = asyncio.Semaphore(db.capacity())
    return slots


async def database():
    """A database session, for no more requests at once than the pool has
    connections.

    FastAPI runs a request's sync dependencies, its handler and the check of
    its response as separate jobs on one pool of threads, and a request keeps
    its connection between them. With more requests than connections, every
    thread could end up waiting for a connection held by a request waiting for
    a thread: 100 Users submitting at once got 500s after the pool's timeout
    (docs/benchmarks/2026-09-30-concurrency.md). Requests beyond the pool wait
    here instead, on the event loop, holding neither.
    """
    async with _request_slots():
        session = db.sessions()()
        try:
            yield session
        finally:
            # Closing may roll back, a round trip: off the event loop.
            await anyio.to_thread.run_sync(session.close, limiter=anyio.CapacityLimiter(1))


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


def readable(session, model, row_id, user, what):
    """Like `own`, for reading only: the owner, or an Administrator the owner
    granted access to this Run or Discussion (litstorm.support), whose read
    is then recorded for the owner to see. Anyone else gets the same 404."""
    from litstorm import support, trash
    from litstorm.db.models import ResearchSession, Run

    try:
        return own(session, model, row_id, user)
    except HTTPException:
        if user.role != "admin":
            raise
    row = session.get(model, row_id)
    alive = row is not None and (
        trash.run_alive(session, row) if model is Run else trash.session_alive(session, row)
    )
    grant = None
    if alive and model is Run:
        grant = support.covering(session, user, run=row)
    elif alive and model is ResearchSession:
        grant = support.covering(session, user, research_session=row)
    if grant is None:
        raise HTTPException(404, "not_found")
    support.record(session, grant, what)
    return row


def by_email(session, email):
    return session.scalar(select(User).where(User.email == email.strip().lower()))
