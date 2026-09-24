"""The Run queue in Postgres: claim, renew, finish, and sweep.

Every write a Worker makes to a Run it holds is conditional on the Run's
`claim_token` and an active status. A Worker that lost its lease — the sweep
marked the Run interrupted — therefore cannot write a final status over it
(docs/web-app-design.md, พฤติกรรมที่ต้องรักษาใน transaction).

Claiming takes a transaction-scoped advisory lock, so two Workers cannot both
see one free slot and both fill it. Which Run gets a slot is FIFO for now;
alternating between Users arrives with the rest of the queue rules in step 3.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text, update

from litstorm import limits, security
from litstorm.db.models import (
    ACTIVE,
    CANCELLING,
    INTERRUPTED,
    QUEUED,
    RUNNING,
    LlmCredential,
    Run,
    SearchProvider,
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


def claim(session):
    """Take the oldest queued Run if the system has a free slot, or None."""
    session.execute(text("select pg_advisory_xact_lock(:id)"), {"id": CLAIM_LOCK})
    configured = limits.load(session)
    active = session.scalar(select(func.count()).select_from(Run).where(Run.status.in_(ACTIVE)))
    if active >= configured.max_concurrent_total:
        session.rollback()
        return None

    run = session.scalar(
        select(Run)
        .where(Run.status == QUEUED)
        .order_by(Run.queued_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if run is None:
        session.rollback()
        return None

    token = uuid.uuid4()
    now = _now()
    run.status = RUNNING
    run.claim_token = token
    run.started_at = now
    run.lease_expires_at = now + LEASE
    run.stage = None
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
