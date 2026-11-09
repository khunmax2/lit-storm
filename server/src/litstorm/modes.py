"""Which research modes (Engines) are offered, and what each can be run with.

An Engine is offered when it is ready (catalog.ENGINES) and the
Administrator has not switched it off (docs/web-app-design.md, แท็บโหมด:
no tab that cannot be used). Its Search Providers must be of a kind it
declares; an Engine that drives tools needs a model whose test showed it can
call them.
"""

from pydantic import BaseModel

from litstorm.catalog import ENGINES
from litstorm.db.models import SystemSetting

KEY = "engines"


class EngineSettings(BaseModel):
    disabled: list[str] = []
    # Modes whose new Runs research the topic as typed, without reading it
    # first (litstorm.interpret); every mode that can reads it by default.
    uninterpreted: list[str] = []


def load(session):
    row = session.get(SystemSetting, KEY)
    return EngineSettings(**(row.value if row else {}))


def save(session, value):
    row = session.get(SystemSetting, KEY) or SystemSetting(key=KEY)
    row.value = value.model_dump()
    session.add(row)


def offered(session, off=None):
    """The Engines an owner can start, in the tabs' order. A remote one
    also needs its service's address and key (litstorm.medical). `off`:
    the modes switched off, when asking about a change not yet saved."""
    from litstorm import medical

    off = set(load(session).disabled) if off is None else set(off)
    return [
        name for name, e in ENGINES.items()
        if e["ready"] and name not in off and (not e.get("remote") or medical.configured(session))
    ]


def interprets(session, engine):
    """Whether a new Run of this mode reads its topic first (litstorm.interpret)."""
    return bool(ENGINES.get(engine, {}).get("interprets")) and engine not in load(session).uninterpreted


def search_fits(engine, provider):
    return provider.kind in ENGINES[engine]["search"]


def model_fits(engine, model):
    # Unknown until the model's test has been run: not offered for an
    # Engine that needs tools, rather than failing a Run half-way.
    return not ENGINES[engine]["needs_tools"] or model.supports_tools is True
