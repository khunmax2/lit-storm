"""API tokens: how another program acts on a User's behalf through the MCP
server (docs/adr/0009).

A token is "dlk_" and 43 random characters. Only its SHA-256 is kept, as a
browser session's is (security.hash_token); the token itself is shown once,
when made. Each carries scopes:

- read: list Runs, see their status, read their reports. No quota.
- research: start and cancel Runs. Uses the owner's quota.

A token acts as its User and never as more: an Administrator's token has no
administrator powers (the MCP server offers none). An integration account
(users.kind) is a User no one signs in as, made by an Administrator for
another system, with its own quota and the modes it may start.

The Administrator's switches live in system_settings["mcp"]: the server on
or off, and whether ordinary Users may make their own tokens.
"""

import secrets
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel
from sqlalchemy import select

from litstorm import security
from litstorm.db.models import ApiToken, SystemSetting, User

PREFIX = "dlk_"
SCOPES = ("read", "research")
# Lifetimes a token may be given, in days; None (no expiry) only for an
# integration account's, which a system holds rather than a person.
LIFETIMES = (30, 90, 365)
DEFAULT_LIFETIME = 90
# How stale last_used_at may get before a call writes it again.
TOUCH = timedelta(minutes=1)
KEY = "mcp"


class Settings(BaseModel):
    # On by default: nothing can call it without a token, and every token is
    # made on purpose by its owner or an Administrator.
    enabled: bool = True
    users_create_tokens: bool = True


def load(session):
    row = session.get(SystemSetting, KEY)
    return Settings(**(row.value if row else {}))


def save(session, value):
    row = session.get(SystemSetting, KEY) or SystemSetting(key=KEY)
    row.value = value.model_dump()
    session.add(row)


def _now():
    return datetime.now(timezone.utc)


def may_create(session, user):
    """Whether `user` may make a token for themselves."""
    settings = load(session)
    return settings.enabled and (settings.users_create_tokens or user.role == "admin")


def issue(session, user, name, scopes, days, created_by=None):
    """A new token for `user`: the token, shown once, and its row."""
    scopes = [s for s in SCOPES if s in set(scopes)]
    if not scopes:
        raise ValueError("a token needs at least one scope")
    token = PREFIX + secrets.token_urlsafe(32)
    row = ApiToken(
        user_id=user.id,
        name=name.strip()[:100],
        token_hash=security.hash_token(token),
        prefix=token[: len(PREFIX) + 4],
        scopes=scopes,
        created_by=created_by.id if created_by is not None else user.id,
        expires_at=_now() + timedelta(days=days) if days else None,
    )
    session.add(row)
    session.flush()
    return token, row


def revoke(session, row):
    if row.revoked_at is None:
        row.revoked_at = _now()


def state(row, now=None):
    """"live", "expired" or "revoked"."""
    now = now or _now()
    if row.revoked_at is not None:
        return "revoked"
    if row.expires_at is not None and row.expires_at <= now:
        return "expired"
    return "live"


class Refused(Exception):
    """Why a token was not accepted: one of the reasons below, for a 401
    or 403 that says which without telling a stranger which tokens exist."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def authenticate(session, raw):
    """The User and token a presented token stands for. Raises Refused.

    `raw` is the Authorization header's value or the bare token.
    """
    if not load(session).enabled:
        raise Refused("mcp_disabled")
    token = (raw or "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if not token.startswith(PREFIX):
        raise Refused("no_token")
    row = session.scalar(select(ApiToken).where(ApiToken.token_hash == security.hash_token(token)))
    if row is None or state(row) != "live":
        raise Refused("bad_token")
    user = session.get(User, row.user_id)
    if user is None or not user.is_active:
        raise Refused("bad_token")
    now = _now()
    if row.last_used_at is None or now - row.last_used_at > TOUCH:
        row.last_used_at = now
        session.commit()
    return user, row


def require(token, scope):
    """Refused unless the token carries `scope`."""
    if scope not in (token.scopes or []):
        raise Refused(f"needs_{scope}_scope")
