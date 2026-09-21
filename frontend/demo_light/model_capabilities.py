"""How a given model can be asked to think, according to whoever serves it.

Two sources, because no single one covers the providers here.

**OpenRouter publishes a per-model `reasoning` object**, and its
documentation describes it as a control specification rather than trivia:

    "supported_efforts": ["high", "medium", "low", "minimal"],
    "default_effort": "medium",
    "supports_max_tokens": true,
    "mandatory": false

with the rules spelled out — filter the selector to `supported_efforts`,
which is in descending order; pre-select `default_effort`; show a token
budget when `supports_max_tokens`; and when `mandatory` is true, *hide the
disable control, because the model rejects it*.

That is worth following exactly, because guessing is wrong in both
directions: `deepseek-v4.1-flash` accepts only `["max", "high", "low"]` —
not `minimal`, not `medium` — and `gemini-3.6-flash` cannot be turned off
at all. A menu of four levels offered to either is a menu of things that
will not happen.

**litellm knows the rest.** `get_supported_openai_params` answers per model
for Gemini, OpenAI, xAI, Anthropic and Groq, and litellm translates its own
`reasoning_effort` into each provider's native form — Gemini's
`thinkingBudget`, Anthropic's `budget_tokens`. Its vocabulary is
`none, minimal, low, medium, high`.

The two must not be crossed. litellm does *not* list `reasoning_effort` as
supported for OpenRouter, and `litellm.drop_params` is on, so sending it
there is dropped in silence: measured, `reasoning_effort="none"` still
spent 584 reasoning tokens where OpenRouter's own `reasoning` object spent
0. A control that looks like it worked and did nothing is worse than no
control, so each provider is sent the form it actually reads.
"""

import json
import urllib.request

import streamlit as st

CATALOGUE = "https://openrouter.ai/api/v1/models"

# What kind of control this model deserves.
NONE = "none"  # it does not think
TOGGLE = "toggle"  # on or off, no levels
EFFORT = "effort"  # named levels, and we know which
BUDGET = "budget"  # a token allowance rather than a level
UNKNOWN = "unknown"  # nobody said; fall back to what was measured

# litellm's vocabulary, for the providers it speaks for. OpenRouter's own
# levels come from the catalogue and are not this list.
LITELLM_EFFORTS = ("minimal", "low", "medium", "high")


def _shape(kind, efforts=(), default=None, mandatory=False, budget=False, source=""):
    return {
        "kind": kind,
        "efforts": tuple(efforts),
        "default": default,
        # True when the model refuses to be switched off, so the page must
        # not offer it. OpenRouter says so per model; nothing else does.
        "mandatory": bool(mandatory),
        "budget": bool(budget),
        "source": source,
    }


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _openrouter_catalogue():
    """{model id: its reasoning object or None}, or {} if unreachable.

    Six hours: a model's capabilities change when the model does, which is
    not often, and a settings page should not spend a round trip per rerun.

    Fetched without the key. The list is public, and sending a credential to
    a call that does not need one is how credentials end up in logs.
    """
    try:
        with urllib.request.urlopen(CATALOGUE, timeout=8) as response:
            data = json.load(response).get("data") or []
    except Exception:  # noqa: BLE001 - offline, rate limited, changed shape
        return {}
    return {entry["id"]: entry.get("reasoning") for entry in data if entry.get("id")}


def _from_openrouter(model):
    catalogue = _openrouter_catalogue()
    if not catalogue:
        return _shape(UNKNOWN, source="openrouter unreachable")
    if model not in catalogue:
        # An id the catalogue does not carry: a typo, or newer than the
        # cache. Claiming it cannot think would be a guess.
        return _shape(UNKNOWN, source="not in catalogue")

    reasoning = catalogue[model]
    if not reasoning:
        return _shape(NONE, source="openrouter")

    mandatory = bool(reasoning.get("mandatory"))
    efforts = reasoning.get("supported_efforts")
    if efforts:
        return _shape(
            EFFORT,
            efforts=efforts,
            default=reasoning.get("default_effort"),
            mandatory=mandatory,
            budget=bool(reasoning.get("supports_max_tokens")),
            source="openrouter",
        )
    if reasoning.get("supports_max_tokens"):
        return _shape(BUDGET, mandatory=mandatory, budget=True, source="openrouter")
    # A reasoning object with neither: it thinks and can be switched, and
    # that is all the catalogue claims.
    return _shape(TOGGLE, mandatory=mandatory, source="openrouter")


def _from_litellm(provider, model):
    """What litellm says, for the providers OpenRouter does not front."""
    try:
        import litellm

        supported = (
            litellm.get_supported_openai_params(
                model=model, custom_llm_provider=provider
            )
            or []
        )
    except Exception:  # noqa: BLE001 - unknown provider, changed signature
        return _shape(UNKNOWN, source="litellm could not say")

    if "reasoning_effort" in supported:
        # litellm has no per-model level list, so its whole vocabulary is
        # offered and the test button is what proves a level took effect.
        return _shape(EFFORT, efforts=LITELLM_EFFORTS, source="litellm")

    # "No reasoning_effort" and "no idea what this model is" look identical
    # from that call, and the difference matters: the engine sets
    # LITELLM_LOCAL_MODEL_COST_MAP, so litellm answers from the list bundled
    # with the installed version. `gemini-3.6-flash` is not in it and came
    # back without reasoning_effort — read as "does not think", which for a
    # model newer than the library is a confident wrong answer.
    if not _litellm_knows(provider, model):
        return _shape(UNKNOWN, source="newer than litellm's model list")
    return _shape(NONE, source="litellm")


def _litellm_knows(provider, model):
    """Whether litellm's model list carries this model at all."""
    try:
        import litellm

        known = litellm.model_cost
    except Exception:  # noqa: BLE001
        return False
    return any(
        name in known for name in (model, f"{provider}/{model}", model.split("/")[-1])
    )


def thinking(provider, model):
    """The control this provider and model support. Always a dict."""
    provider = (provider or "").strip().lower()
    model = (model or "").strip()
    if not provider or not model:
        return _shape(UNKNOWN, source="nothing chosen")
    if provider == "openrouter":
        return _from_openrouter(model)
    if provider == "openai-compatible":
        # An endpoint, not a service: what is behind it is unknowable from
        # here, and litellm would answer for openai rather than for whatever
        # this is.
        return _shape(UNKNOWN, source="an endpoint, not a known service")
    return _from_litellm(provider, model)


def refresh():
    """Forget the catalogue, for the page's own retry."""
    _openrouter_catalogue.clear()
