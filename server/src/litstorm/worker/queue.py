"""The Run queue in Postgres: claim, renew, finish, and sweep.

Every write a Worker makes to a Run it holds is conditional on the Run's
`claim_token` and an active status. A Worker that lost its lease — the sweep
marked the Run interrupted — therefore cannot write a final status over it
(docs/web-app-design.md, พฤติกรรมที่ต้องรักษาใน transaction).

Claiming takes a transaction-scoped advisory lock, so two Workers cannot both
see one free slot and both fill it. When a slot is free the queue takes turns
between Users (docs/web-app-design.md, การจัดสรรคิวระหว่างผู้ใช้): among Users
with a Run waiting and room under their own ceiling, the one whose last Run
started longest ago goes next, with their oldest Run. Someone who queued ten
Runs does not make everyone else wait for all ten.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select, text, update

from litstorm import limits, quota, security
from litstorm.db.models import (
    ACTIVE,
    CANCELLING,
    INTERRUPTED,
    QUEUED,
    RUNNING,
    NEEDS_SELECTION,
    LlmCredential,
    LlmModel,
    Run,
    SearchProvider,
    User,
)
from litstorm.engines.base import RunConfig, Secrets

LEASE = timedelta(seconds=60)
CLAIM_LOCK = 7_211_001  # arbitrary, fixed: the advisory lock id for claims


@dataclass
class Claim:
    run_id: uuid.UUID
    token: uuid.UUID
    config: RunConfig
    secrets: Secrets
    deadline_seconds: float


def _now():
    return datetime.now(timezone.utc)


def park_unavailable(session):
    """Queued Runs whose model or provider an Administrator turned off wait
    for their owner to choose again. They keep their quota reservation and
    their place is given up (docs/web-app-design.md, การปิดใช้งานโมเดล)."""
    disabled_models = select(LlmModel.id).where(LlmModel.enabled.is_(False))
    disabled_providers = select(SearchProvider.id).where(SearchProvider.enabled.is_(False))
    return session.execute(
        update(Run)
        .where(
            Run.status == QUEUED,
            or_(Run.llm_model_id.in_(disabled_models), Run.search_provider_id.in_(disabled_providers)),
        )
        .values(status=NEEDS_SELECTION)
    ).rowcount


def _next_run(session, configured):
    """The Run whose turn it is, locked, or None."""
    active = quota.active_by_owner()
    ceiling = func.coalesce(User.max_concurrent_runs, configured.max_concurrent_per_user)
    return session.scalar(
        select(Run)
        .join(User, User.id == Run.owner_id)
        .outerjoin(active, active.c.owner_id == Run.owner_id)
        .where(
            Run.status == QUEUED,
            User.is_active.is_(True),
            func.coalesce(active.c.active, 0) < ceiling,
        )
        .order_by(User.last_run_started_at.asc().nulls_first(), Run.queued_at)
        .limit(1)
        .with_for_update(of=Run, skip_locked=True)
    )


def claim(session):
    """Take the next Run if the system has a free slot, or None."""
    session.execute(text("select pg_advisory_xact_lock(:id)"), {"id": CLAIM_LOCK})
    configured = limits.load(session)
    park_unavailable(session)
    active = session.scalar(select(func.count()).select_from(Run).where(Run.status.in_(ACTIVE)))
    if active >= configured.max_concurrent_total:
        session.commit()
        return None

    run = _next_run(session, configured)
    if run is None:
        session.commit()
        return None

    token = uuid.uuid4()
    now = _now()
    run.status = RUNNING
    run.claim_token = token
    run.started_at = now
    run.lease_expires_at = now + LEASE
    run.stage = None
    session.execute(update(User).where(User.id == run.owner_id).values(last_run_started_at=now))
    secrets, llm = _secrets(session, run)
    session.commit()

    config = RunConfig(
        run_id=str(run.id),
        engine=run.engine,
        topic=run.topic,
        language=run.language,
        llm=llm,
        search={k: v for k, v in run.config["search"].items() if k != "label" and v},
        params=run.config.get("params", {}),
    )
    deadline = 60.0 * run.config.get("deadline_minutes", configured.run_deadline_minutes)
    return Claim(run.id, token, config, secrets, deadline)


def _secrets(session, run):
    """Credentials for this Run, decrypted only now, in the Worker."""
    llm = {k: v for k, v in run.config["llm"].items() if k != "label" and v}
    credential = session.get(LlmCredential, llm["provider"])
    llm_key = ""
    if credential:
        llm_key = security.decrypt(credential.api_key_ciphertext)
        if credential.api_base:
            llm["api_base"] = credential.api_base
    provider = session.get(SearchProvider, run.search_provider_id)
    search_key = security.decrypt(provider.api_key_ciphertext) if provider else ""
    return Secrets(llm_api_key=llm_key, search_api_key=search_key), llm


def _held(claim):
    return (Run.id == claim.run_id) & (Run.claim_token == claim.token) & Run.status.in_(ACTIVE)


def renew(session, claim):
    """Extend the lease. False when the Run is no longer ours."""
    held = session.execute(update(Run).where(_held(claim)).values(lease_expires_at=_now() + LEASE)).rowcount
    session.commit()
    return bool(held)


def cancel_requested(session, claim):
    status = session.scalar(select(Run.status).where(Run.id == claim.run_id))
    return status == CANCELLING


def set_stage(session, claim, stage):
    session.execute(update(Run).where(_held(claim)).values(stage=stage))
    session.commit()


def finish(session, claim, outcome, report_title=None, source_count=None):
    """Write the final status once. False if the Run was no longer ours."""
    done = session.execute(
        update(Run)
        .where(_held(claim))
        .values(
            status=outcome.status,
            reason=outcome.reason,
            message=(outcome.message or None),
            quota_refunded=outcome.refunds_quota,
            finished_at=_now(),
            lease_expires_at=None,
            report_title=report_title,
            source_count=source_count,
        )
    ).rowcount
    session.commit()
    return bool(done)


def sweep_interrupted(session):
    """Runs whose Worker stopped renewing: interrupted, quota back, and never
    restarted on their own (docs/web-app-design.md, Run ถูกขัดจังหวะ)."""
    swept = session.execute(
        update(Run)
        .where(Run.status.in_(ACTIVE), Run.lease_expires_at < _now())
        .values(
            status=INTERRUPTED,
            reason="interrupted",
            message="the Worker running this Run stopped",
            quota_refunded=True,
            finished_at=_now(),
            lease_expires_at=None,
        )
    ).rowcount
    session.commit()
    return swept
