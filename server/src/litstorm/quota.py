"""Monthly quota and per-User limits (docs/web-app-design.md, โควตา Run รายเดือน).

Quota is read off the Runs themselves rather than kept in a ledger beside
them. A Run belongs to exactly one quota month, fixed when it was submitted,
and has exactly one status and one refund flag, so it cannot be charged or
refunded twice, and a Run that crosses into a new month still counts against
the month it was booked in:

    reserved  waiting in the queue, or waiting for a new model or provider
    used      started, and not refunded
    free      neither: never started and cancelled, or refunded

The quota resets because the month key changes (Asia/Bangkok, limits.py);
nothing has to run at midnight.
"""

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import and_, func, select

from litstorm import limits
from litstorm.db.models import ACTIVE, WAITING, Run, User


@dataclass(frozen=True)
class Effective:
    monthly_quota: int
    max_concurrent: int
    max_queued: int


def effective(user, configured):
    """The User's limits: their own override where set, else the default."""

    def pick(override, default):
        return default if override is None else override

    return Effective(
        monthly_quota=pick(user.monthly_run_quota, configured.monthly_run_quota),
        max_concurrent=pick(user.max_concurrent_runs, configured.max_concurrent_per_user),
        max_queued=pick(user.max_queued_runs, configured.max_queued_per_user),
    )


@dataclass(frozen=True)
class Usage:
    month: str
    limit: int
    used: int
    reserved: int
    refunded: int

    @property
    def remaining(self):
        return max(0, self.limit - self.used - self.reserved)


def usage(session, user, month=None, configured=None):
    month = month or limits.quota_month()
    configured = configured or limits.load(session)
    row = session.execute(
        select(
            func.count().filter(Run.status.in_(WAITING)),
            func.count().filter(and_(Run.started_at.is_not(None), Run.quota_refunded.is_(False))),
            func.count().filter(Run.quota_refunded.is_(True)),
        ).where(Run.owner_id == user.id, Run.quota_month == month)
    ).one()
    reserved, used, refunded = row
    return Usage(month, effective(user, configured).monthly_quota, used, reserved, refunded)


def check_submit(session, user):
    """Refuse a new Run the User has no room for. Locks the User's row, so
    two submissions at once cannot both take the last slot."""
    session.execute(select(User.id).where(User.id == user.id).with_for_update())
    configured = limits.load(session)
    mine = effective(user, configured)
    waiting = session.scalar(
        select(func.count()).select_from(Run).where(Run.owner_id == user.id, Run.status.in_(WAITING))
    )
    if waiting >= mine.max_queued:
        raise HTTPException(429, "queue_full")
    if usage(session, user, configured=configured).remaining <= 0:
        raise HTTPException(429, "quota_exhausted")


def active_by_owner():
    """Per owner: Runs holding a processing slot. For the claim query."""
    return (
        select(Run.owner_id, func.count().label("active"))
        .where(Run.status.in_(ACTIVE))
        .group_by(Run.owner_id)
        .subquery()
    )

