"""Global defaults an Administrator sets, and the Bangkok quota month.

Defaults are the ones agreed for local testing (docs/web-app-design.md):
two Runs at once in the whole system, one per User, five waiting per User,
ten a month, an hour per Run.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from litstorm.db.models import SystemSetting

KEY = "limits"
QUOTA_ZONE = ZoneInfo("Asia/Bangkok")


class Limits(BaseModel):
    max_concurrent_total: int = Field(default=2, ge=1)
    max_concurrent_per_user: int = Field(default=1, ge=1)
    max_queued_per_user: int = Field(default=5, ge=1)
    monthly_run_quota: int = Field(default=10, ge=0)
    run_deadline_minutes: int = Field(default=60, ge=5)
    # STORM's knobs (engines/storm/engine.py DEFAULT_PARAMS); owners do not
    # choose these.
    storm_params: dict = Field(
        default_factory=lambda: {"max_conv_turn": 3, "max_perspective": 3, "search_top_k": 3}
    )


def load(session):
    row = session.get(SystemSetting, KEY)
    return Limits(**(row.value if row else {}))


def save(session, value):
    row = session.get(SystemSetting, KEY) or SystemSetting(key=KEY)
    row.value = value.model_dump()
    session.add(row)


def quota_month(at=None):
    """The month a Run is charged to: Bangkok time, as "YYYY-MM"."""
    at = at or datetime.now(QUOTA_ZONE)
    return at.astimezone(QUOTA_ZONE).strftime("%Y-%m")
