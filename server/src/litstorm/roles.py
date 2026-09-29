"""The fast model: one model, set by the Administrator for the whole system,
for the many short calls of research (asking, answering, choosing what to
search); the owner's chosen model keeps writing (docs/adr/0006).

Unset, or turned off, every stage uses the owner's model, as in the first
release. A Run keeps the fast model it started with, as it keeps its main
one; if that model is turned off before the Run starts, the Run uses its
main model rather than waiting (the owner could not choose another).
"""

import uuid

from pydantic import BaseModel

from litstorm.db.models import LlmModel, SystemSetting

KEY = "model_roles"


class Roles(BaseModel):
    fast_model_id: str | None = None


def load(session):
    row = session.get(SystemSetting, KEY)
    return Roles(**(row.value if row else {}))


def save(session, value):
    row = session.get(SystemSetting, KEY) or SystemSetting(key=KEY)
    row.value = value.model_dump()
    session.add(row)


def fast_model(session):
    """The fast model if one is set and on; else None."""
    wanted = load(session).fast_model_id
    if not wanted:
        return None
    model = session.get(LlmModel, uuid.UUID(wanted))
    return model if model is not None and model.enabled else None


def snapshot(model):
    """What a Run keeps of a model it will call: never the key."""
    return {
        "id": str(model.id),
        "label": model.label,
        "provider": model.provider,
        "model": model.model,
        "reasoning": model.reasoning,
        "max_tokens": model.max_tokens or {},
    }
