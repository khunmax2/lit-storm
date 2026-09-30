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


DEPTHS = ("fast", "standard", "deep")


class DepthLevel(BaseModel):
    """What one depth level means (docs/web-app-design.md, รุ่นสอง: ระดับ
    ความลึก). Owners choose the level; the numbers behind it are the
    Administrator's, so a Run's cost still has a ceiling."""

    # The time the level is meant to take; the second release's graceful
    # finish aims at it. The hard deadline is run_deadline_minutes.
    target_minutes: int = Field(ge=1)
    # STORM's knobs (engines/storm/engine.py DEFAULT_PARAMS).
    storm: dict
    # Agent Research's: "iterative" with max_iterations rounds, or "deep",
    # which plans sections and researches each (engines/agent/engine.py).
    agent: dict = Field(default_factory=dict)
    # Deep Research's: how many searches a step makes, and how many steps
    # deep it follows leads (engines/deep/engine.py).
    deep: dict = Field(default_factory=dict)
    # Co-STORM's warm start: how many experts research the topic before the
    # Discussion opens (engines/costorm/engine.py).
    costorm: dict = Field(default_factory=dict)


def _default_depths():
    # "standard" is exactly what every Run used before levels existed, so
    # measurements from before and after compare. The others are the Streamlit
    # app's levels (run_options.py), which were tried with users.
    return {
        "fast": DepthLevel(
            target_minutes=2,
            storm={"max_perspective": 2, "max_conv_turn": 2, "max_search_queries_per_turn": 2,
                   "search_top_k": 3, "retrieve_top_k": 3},
            agent={"mode": "iterative", "max_iterations": 2},
            deep={"breadth": 2, "depth": 1},
            costorm={"warmstart_max_num_experts": 2},
        ),
        "standard": DepthLevel(
            target_minutes=5,
            storm={"max_perspective": 3, "max_conv_turn": 3, "max_search_queries_per_turn": 3,
                   "search_top_k": 3, "retrieve_top_k": 3},
            agent={"mode": "iterative", "max_iterations": 4},
            deep={"breadth": 3, "depth": 2},
            costorm={"warmstart_max_num_experts": 3},
        ),
        "deep": DepthLevel(
            target_minutes=12,
            storm={"max_perspective": 5, "max_conv_turn": 4, "max_search_queries_per_turn": 4,
                   "search_top_k": 5, "retrieve_top_k": 8},
            agent={"mode": "deep", "max_iterations": 2},
            deep={"breadth": 4, "depth": 3},
            costorm={"warmstart_max_num_experts": 4},
        ),
    }


class Limits(BaseModel):
    # A fresh install's ceiling; an Administrator's saved value wins
    # (docs/web-app-design.md, เพดาน Run พร้อมกันทั้งระบบ).
    max_concurrent_total: int = Field(default=6, ge=1)
    max_concurrent_per_user: int = Field(default=1, ge=1)
    max_queued_per_user: int = Field(default=5, ge=1)
    monthly_run_quota: int = Field(default=10, ge=0)
    run_deadline_minutes: int = Field(default=60, ge=5)
    # Question refinement takes no quota, so it has a cap of its own:
    # requests per User per Bangkok day (docs/web-app-design.md, ขัดเกลาโจทย์).
    refinements_per_day: int = Field(default=30, ge=0)
    # A Discussion's Turns per quota unit, the report included
    # (docs/web-app-design.md, รุ่นสอง: Discussion).
    turns_per_quota: int = Field(default=20, ge=1)
    depth_levels: dict[str, DepthLevel] = Field(default_factory=_default_depths)

    def depth(self, name):
        """A level's settings; a level the Administrator never saved gets its
        default, and so does an Engine's part saved before that Engine existed."""
        level = self.depth_levels.get(name)
        default = _default_depths()[name]
        if level is None:
            return default
        missing = {part: getattr(default, part) for part in ("agent", "deep", "costorm") if not getattr(level, part)}
        return level.model_copy(update=missing) if missing else level


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
