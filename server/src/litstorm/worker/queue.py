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
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select, text, update

from litstorm import cost, discussion, embedding, limits, quota, security, settings
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
    # The Administrator's prices, USD per million tokens, by the name each
    # model reports its usage under (cost.estimate).
    prices: dict = field(default_factory=dict)


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
        # A Discussion's Turn first: its owner is waiting on the page for
        # it (docs/web-app-design.md, รุ่นสอง: Discussion). False sorts first.
        .order_by(Run.turn.is_(None), User.last_run_started_at.asc().nulls_first(), Run.queued_at)
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
    secrets, llm, fast = _secrets(session, run)
    extra, extra_keys = _extra_searches(session, run)
    secrets = replace(secrets, search_extra_api_keys=tuple(extra_keys))
    session.commit()

    config = RunConfig(
        run_id=str(run.id),
        engine=run.engine,
        topic=run.topic,
        language=run.language,
        llm=llm,
        search={k: v for k, v in run.config["search"].items() if k != "label" and v},
        search_extra=extra,
        params=run.config.get("params", {}),
        fast_llm=fast,
        embedding=run.config.get("embedding", {}),
        target_seconds=60.0 * run.config["target_minutes"] if run.config.get("target_minutes") else None,
        search_cache_dir=settings.get().search_cache_dir,
        refinement=run.config.get("refinement", []),
        sections=run.config.get("sections", []),
        instructions=run.config.get("instructions", {}),
        discussion={**run.turn, "state_from": discussion.state_from(session, run)} if run.turn else {},
    )
    deadline = 60.0 * run.config.get("deadline_minutes", configured.run_deadline_minutes)
    return Claim(run.id, token, config, secrets, deadline, prices=_prices(session, run, fast))


def _prices(session, run, fast):
    """Each model's price as the Administrator set it, if they did."""
    from litstorm.catalog import LLM_PROVIDERS

    prices = {}
    for model_id in (run.llm_model_id, fast.get("id") if fast else None):
        model = session.get(LlmModel, uuid.UUID(str(model_id))) if model_id else None
        if model is not None and model.price_in_per_mtok is not None and model.price_out_per_mtok is not None:
            name = LLM_PROVIDERS.get(model.provider, {}).get("prefix", "") + model.model
            prices[name] = (model.price_in_per_mtok, model.price_out_per_mtok)
            if model.id == run.llm_model_id:
                prices["*"] = prices[name]  # any name not listed is the main model's
    return prices


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
    fast, fast_key = _fast(session, run)
    return Secrets(
        llm_api_key=llm_key,
        search_api_key=search_key,
        embedding_api_key=_embedding_key(session, run),
        fast_llm_api_key=fast_key,
    ), llm, fast


def _extra_searches(session, run):
    """The Run's other Search Providers that are still on, and their keys.
    One switched off since the Run was queued is left out rather than parking
    the Run: its first provider decides that, and the rest are extra."""
    kept, keys = [], []
    for search in run.config.get("search_extra") or []:
        provider = session.get(SearchProvider, uuid.UUID(search["id"])) if search.get("id") else None
        if provider is None or not provider.enabled:
            continue
        kept.append({k: v for k, v in search.items() if k != "id" and v})
        keys.append(security.decrypt(provider.api_key_ciphertext) if provider.api_key_ciphertext else "")
    return kept, keys


def _fast(session, run):
    """The fast model the Run was started with, and its key, if that model
    is still on; otherwise nothing, and the main model does it all
    (litstorm.roles)."""
    kept = run.config.get("fast_llm") or {}
    model = session.get(LlmModel, uuid.UUID(kept["id"])) if kept.get("id") else None
    if model is None or not model.enabled:
        return {}, ""
    fast = {k: v for k, v in kept.items() if k != "label" and v}
    credential = session.get(LlmCredential, fast["provider"])
    if credential is None:
        return {}, ""
    if credential.api_base:
        fast["api_base"] = credential.api_base
    return fast, security.decrypt(credential.api_key_ciphertext)


def _embedding_key(session, run):
    """The key for the embedding service the Run was started with, from the
    LLM credential of its provider (litstorm.embedding.key_for)."""
    kept = run.config.get("embedding") or {}
    if kept.get("provider", embedding.BUILTIN) == embedding.BUILTIN:
        return ""
    value = embedding.Embedding(provider=kept["provider"], model=kept.get("model", ""), api_base=kept.get("api_base"))
    return embedding.key_for(value, session.get(LlmCredential, value.provider))


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


# The engine's notes an owner is shown on the Run, not only in its log.
NOTE_KINDS = ("research_cut_short", "embedding", "search_cache", "sources_skipped", "rewritten")


def add_note(session, claim, kind, data):
    if kind == "embedding" and not data.get("fallback"):
        return  # the service worked: nothing to tell
    run = session.scalar(select(Run).where(_held(claim)).with_for_update())
    if run is not None:
        run.notes = {**(run.notes or {}), kind: {k: v for k, v in data.items() if k != "kind"}}
    session.commit()


def finish(session, claim, outcome, report_title=None, source_count=None):
    """Write the final status once. False if the Run was no longer ours."""
    tokens_in, tokens_out, searches, by_model = cost.totals(outcome.usage)
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
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            search_calls=searches,
            cost_usd=cost.estimate(by_model, prices=claim.prices),
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
