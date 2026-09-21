"""What a model can be asked to do, according to whoever serves it.

Only one provider here publishes this, and it publishes exactly the
distinction the settings page needs. OpenRouter's model list carries a
`supported_parameters` array, and of its 446 models:

* 314 list `reasoning` — the model thinks, and can be told not to;
* 178 also list `reasoning_effort` — and can be told *how much*;
* the rest list neither, and have nothing to turn off.

That matches every measurement taken by hand: llama-4-scout and gpt-4o-mini
spent zero tokens thinking and list neither, qwen3.7-flash spent 170 and
lists `reasoning` alone, deepseek-v4.1-flash spent 2366 and lists both.

No other provider here publishes anything comparable, so for them the
answer is `UNKNOWN` and the page falls back to what the test button
measured — which is weaker, because it only knows after someone has run it,
but it is honest about which it is.
"""

import json
import urllib.request

import streamlit as st

CATALOGUE = "https://openrouter.ai/api/v1/models"

# What a model supports, as far as we can tell.
NONE = "none"  # it does not think
ON_OFF = "on_off"  # it thinks, and can be told not to
EFFORT = "effort"  # it thinks, and can be told how hard
UNKNOWN = "unknown"  # nobody said, so do not pretend

# OpenRouter's reasoning.effort values. Offered in this order because it is
# the order of increasing cost, and the cost is the reason to care.
EFFORT_LEVELS = ("minimal", "low", "medium", "high")


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _openrouter_catalogue():
    """{model id: set of supported parameter names}, or {} if unreachable.

    Six hours because a model's parameters change when the model changes,
    which is not often, and a settings page should not spend a network
    round trip on every rerun.

    Fetched without the key: the list is public, and sending a credential to
    a call that does not need one is how credentials end up in logs.
    """
    try:
        with urllib.request.urlopen(CATALOGUE, timeout=8) as response:
            data = json.load(response).get("data") or []
    except Exception:  # noqa: BLE001 - offline, rate limited, changed shape
        return {}
    return {
        entry["id"]: set(entry.get("supported_parameters") or [])
        for entry in data
        if entry.get("id")
    }


def thinking(provider, model):
    """One of NONE, ON_OFF, EFFORT or UNKNOWN for this provider and model."""
    if (provider or "").strip().lower() != "openrouter":
        return UNKNOWN
    model = (model or "").strip()
    if not model:
        return UNKNOWN
    catalogue = _openrouter_catalogue()
    if not catalogue:
        return UNKNOWN
    supported = catalogue.get(model)
    if supported is None:
        # A model id the catalogue does not carry. It may be a typo, or a
        # model added since this was cached; either way, claiming it cannot
        # think would be a guess.
        return UNKNOWN
    if "reasoning_effort" in supported:
        return EFFORT
    if "reasoning" in supported:
        return ON_OFF
    return NONE


def refresh():
    """Forget the catalogue, for the page's own retry."""
    _openrouter_catalogue.clear()
