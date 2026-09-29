"""The tables. Vocabulary follows docs/CONTEXT.md.

Owner-scoped rows carry `owner_id` directly (Runs too, not only through their
Session) so every query that must be limited to one User can be, without a
join that someone later forgets.
"""

import uuid
from datetime import datetime

from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    type_annotation_map = {dict: JSONB, uuid.UUID: UUID(as_uuid=True)}


def _now():
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True)  # stored lower-cased
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20))  # "user" | "admin"
    password_hash: Mapped[str | None] = mapped_column(Text)
    # Set when an Administrator issues a reset: the User must choose a new
    # password before anything else.
    must_set_password: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    ui_language: Mapped[str] = mapped_column(String(2), default="th")
    # Per-User overrides of the global defaults; null means "use the default".
    monthly_run_quota: Mapped[int | None] = mapped_column(Integer)
    max_concurrent_runs: Mapped[int | None] = mapped_column(Integer)
    max_queued_runs: Mapped[int | None] = mapped_column(Integer)
    # When this User's most recent Run started: the queue serves whoever has
    # waited longest since their last turn.
    last_run_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _now()


class AuthSession(Base):
    """A signed-in browser. Not a Research Session."""

    __tablename__ = "auth_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = _now()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PasswordSetupToken(Base):
    """A one-time link to set a password. One live link per User: issuing a
    new one replaces the old (the primary key is the user)."""

    __tablename__ = "password_setup_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    purpose: Mapped[str] = mapped_column(String(10))  # "setup" | "reset"
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _now()


class SystemSetting(Base):
    """Global settings and one-off facts, such as the first-run setup being done."""

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB)


class LlmCredential(Base):
    """One API key per LLM provider (openrouter, gemini, ...), encrypted."""

    __tablename__ = "llm_credentials"

    provider: Mapped[str] = mapped_column(String(40), primary_key=True)
    api_key_ciphertext: Mapped[str] = mapped_column(Text)
    api_base: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = _now()


class LlmModel(Base):
    __tablename__ = "llm_models"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    label: Mapped[str] = mapped_column(String(200))
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(200))
    # "", "off", "effort:minimal", "budget:800" (engines/storm/providers.py)
    reasoning: Mapped[str] = mapped_column(String(40), default="")
    # Reply budgets, e.g. {"conversation": 1500, "writing": 4000}.
    max_tokens: Mapped[dict] = mapped_column(JSONB, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    # USD per million tokens, when LiteLLM's price table does not know it.
    price_in_per_mtok: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    price_out_per_mtok: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    # Whether the model called a tool when tested; None until tested. Engines
    # that drive tools offer only models with True (litstorm.modes).
    supports_tools: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = _now()

    __table_args__ = (
        Index("one_default_llm_model", "is_default", unique=True, postgresql_where=text("is_default")),
    )


class SearchProvider(Base):
    __tablename__ = "search_providers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    label: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(40))  # "searxng" | "tavily" | "arxiv"
    endpoint: Mapped[str | None] = mapped_column(Text)
    engines: Mapped[str | None] = mapped_column(Text)  # SearXNG's engines= filter
    api_key_ciphertext: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = _now()

    __table_args__ = (
        Index("one_default_search_provider", "is_default", unique=True, postgresql_where=text("is_default")),
    )


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = _now()
    trashed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ResearchSession(Base):
    __tablename__ = "research_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # None: not filed in any Project.
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"), index=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = _now()
    trashed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# Run statuses (docs/web-app-design.md, วงจรชีวิตของ Run).
QUEUED = "queued"
NEEDS_SELECTION = "needs_selection"
RUNNING = "running"
CANCELLING = "cancelling"
SUCCEEDED = "succeeded"
FAILED = "failed"
CANCELLED = "cancelled"
INTERRUPTED = "interrupted"
ACTIVE = (RUNNING, CANCELLING)
# Waiting for a slot: reserves quota and counts toward the queue limit, but
# holds no processing slot.
WAITING = (QUEUED, NEEDS_SELECTION)
FINAL = (SUCCEEDED, FAILED, CANCELLED, INTERRUPTED)


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Null once purged: the row stays, for quota and cost, without its Session.
    session_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("research_sessions.id"), index=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    # Set when "try again" made this Run from a failed one.
    parent_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("runs.id"))
    engine: Mapped[str] = mapped_column(String(40))
    topic: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(2))
    llm_model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("llm_models.id"))
    search_provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("search_providers.id"))
    # What the Run was started with, secrets excluded: model, provider and
    # engine params as they were at submission, so later changes to the
    # settings do not rewrite history.
    config: Mapped[dict] = mapped_column(JSONB)

    status: Mapped[str] = mapped_column(String(20), default=QUEUED)
    stage: Mapped[str | None] = mapped_column(String(40))
    reason: Mapped[str | None] = mapped_column(String(40))  # litstorm.outcomes
    message: Mapped[str | None] = mapped_column(Text)
    # The Bangkok calendar month the Run's quota is charged to, "2026-09".
    quota_month: Mapped[str] = mapped_column(String(7))
    quota_refunded: Mapped[bool] = mapped_column(Boolean, default=False)

    queued_at: Mapped[datetime] = _now()
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # The Worker holding the Run. Every write from a Worker checks the
    # token, so one that lost its lease cannot overwrite a final status.
    claim_token: Mapped[uuid.UUID | None] = mapped_column()
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    report_title: Mapped[str | None] = mapped_column(Text)
    source_count: Mapped[int | None] = mapped_column(Integer)
    # What the owner should know about how the Run went, by kind: it wrote
    # from what it had when time ran short, its embedding service failed,
    # some searches came from the cache (worker.queue.NOTE_KINDS).
    notes: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    trashed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The browser's id for one press of "Start" (see migration 0002).
    request_key: Mapped[str | None] = mapped_column(String(64))
    # Content deleted for good; what is left is accounting (migration 0003).
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tokens_in: Mapped[int | None] = mapped_column(BigInteger)
    tokens_out: Mapped[int | None] = mapped_column(BigInteger)
    search_calls: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))

    __table_args__ = (
        Index("runs_queue", "queued_at", postgresql_where=text("status = 'queued'")),
        Index("runs_one_per_request", "owner_id", "request_key", unique=True,
              postgresql_where=text("request_key is not null")),
        Index("runs_owner_month", "owner_id", "quota_month"),
        Index("runs_trashed", "trashed_at", postgresql_where=text("trashed_at is not null")),
        Index("runs_active_lease", "lease_expires_at", postgresql_where=text("status in ('running','cancelling')")),
    )


class RunEvent(Base):
    """What the Run's process reported: stages, notes, usage."""

    __tablename__ = "run_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    at: Mapped[datetime] = _now()
    type: Mapped[str] = mapped_column(String(20))
    data: Mapped[dict] = mapped_column(JSONB)
