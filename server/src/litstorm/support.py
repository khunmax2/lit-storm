"""Support Access Grants (docs/CONTEXT.md; docs/web-app-design.md,
2026-09-23 สิทธิ์ผู้ดูแลต่อเนื้อหางานวิจัย).

An Administrator reads nobody's research by default. An owner who wants
help with a Run grants one named Administrator read access to that Run — or
to a Discussion, with all its Turns — for 24 hours. The owner can revoke it
at once, and sees each time it was used. Reading is all it allows: every
request that changes something still checks the owner.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select

from litstorm.db.models import Run, SupportAccess, SupportGrant, User

LIFETIME = timedelta(hours=24)


def _now():
    return datetime.now(timezone.utc)


def live(grant, at=None):
    return grant.revoked_at is None and grant.expires_at > (at or _now())


def covering(session, admin, run=None, research_session=None):
    """The Administrator's live grant that covers this Run or this
    Discussion, or None. A Discussion's grant covers its Turns."""
    if admin.role != "admin" or not admin.is_active:
        return None
    targets = []
    if run is not None:
        targets.append(SupportGrant.run_id == run.id)
        if run.turn is not None and run.session_id is not None:
            targets.append(SupportGrant.session_id == run.session_id)
    if research_session is not None:
        targets.append(SupportGrant.session_id == research_session.id)
    if not targets:
        return None
    now = _now()
    return session.scalar(
        select(SupportGrant)
        .where(
            SupportGrant.admin_id == admin.id,
            SupportGrant.revoked_at.is_(None),
            SupportGrant.expires_at > now,
            or_(*targets),
        )
        .order_by(SupportGrant.expires_at.desc())
        .limit(1)
    )


def record(session, grant, what):
    session.add(SupportAccess(grant_id=grant.id, what=what))
    session.commit()


def grant(session, owner, admin, run=None, research_session=None):
    """A new grant, live for 24 hours from now."""
    row = SupportGrant(
        owner_id=owner.id,
        admin_id=admin.id,
        run_id=run.id if run is not None else None,
        session_id=research_session.id if research_session is not None else None,
        expires_at=_now() + LIFETIME,
    )
    session.add(row)
    return row


def administrators(session, owner):
    """Who the owner can ask for help: active Administrators other than them."""
    return session.scalars(
        select(User).where(User.role == "admin", User.is_active.is_(True), User.id != owner.id).order_by(User.name)
    ).all()


def runs_of(session, grant_row):
    """For listing: the Run a grant names, or the Discussion's first Turn."""
    if grant_row.run_id is not None:
        return session.get(Run, grant_row.run_id)
    return session.scalar(
        select(Run).where(Run.session_id == grant_row.session_id).order_by(Run.queued_at).limit(1)
    )
