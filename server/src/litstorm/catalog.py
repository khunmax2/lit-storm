"""The LLM providers and Search Provider kinds this system has adapters for.

Kept apart from engines/storm/providers.py so the API can list them without
importing STORM (and torch with it). Adding a kind here is not enough: it
needs an adapter there (docs/web-app-design.md, การจัดการ Search Provider).
"""

# What each LLM provider needs. Anything that speaks the OpenAI API goes
# through "openai-compatible" with its own base URL.
LLM_PROVIDERS = {
    "gemini": {"prefix": "gemini/"},
    "openrouter": {"prefix": "openrouter/"},
    "groq": {"prefix": "groq/"},
    "openai": {"prefix": "openai/"},
    "openai-compatible": {"prefix": "openai/", "needs_base": True},
}

SEARCH_PROVIDERS = ("searxng", "tavily", "arxiv", "tci")

# What each Engine declares (docs/web-app-design.md, รุ่นสอง: กติกาที่ทุก
# Engine ใช้ร่วมกัน): the Search Provider kinds it can use, its stages for
# the progress bar, whether it needs a model that can call tools, and how
# many Search Providers one Run may search together (`max_sources`, 1 when
# absent). An Engine is offered only once `ready`; an Administrator can still
# switch a ready one off (litstorm.engine_settings). Order is the tabs' order.
ENGINES = {
    "storm": {
        "label": "STORM",
        "search": SEARCH_PROVIDERS,
        "stages": ("research", "outline", "article", "polish"),
        "needs_tools": False,
        "ready": True,
        # Search Providers one Run may search at once (MultiRM).
        "max_sources": 3,
    },
    "co-storm": {
        "label": "Co-STORM",
        "search": SEARCH_PROVIDERS,
        "stages": ("warmup", "discussion", "report"),
        "needs_tools": False,
        # A Discussion, not a Run: started from POST /api/discussions.
        "ready": True,
        "max_sources": 3,
    },
    "deep": {
        "label": "Deep Research",
        # Any provider: one its own client does not speak, or several, is
        # searched through litstorm.engines.sources.SearchBridge.
        "search": SEARCH_PROVIDERS,
        "stages": ("research", "report"),
        "needs_tools": False,
        "ready": True,
        "max_sources": 3,
    },
    "agent": {
        "label": "Agent Research",
        "search": SEARCH_PROVIDERS,  # as Deep Research: through the bridge
        "stages": ("plan", "research", "report"),
        "needs_tools": True,
        "ready": True,
        "max_sources": 3,
    },
}


def reasoning_kwargs(value, provider):
    """The call argument for a saved reasoning setting, or {} for unset.

    OpenRouter is sent its own `reasoning` object: LiteLLM drops
    `reasoning_effort` for it without a word (found in the Streamlit app).
    """
    value = (value or "").strip().lower()
    if not value:
        return {}
    kind, _, detail = value.partition(":")
    openrouter = provider == "openrouter"
    if value == "off":
        return {"reasoning": {"enabled": False}} if openrouter else {"reasoning_effort": "none"}
    if kind == "effort" and detail:
        return {"reasoning": {"effort": detail}} if openrouter else {"reasoning_effort": detail}
    if kind == "budget" and detail.isdigit():
        return {"reasoning": {"max_tokens": int(detail)}} if openrouter else {}
    return {}


def routing_kwargs(provider, kwargs):
    """OpenRouter spreads one model over many hosts, and some ignore a
    reasoning setting: measured, "enabled: false" still spent 500 tokens
    thinking when routed to one of them, and the reply came back empty.
    Route only to hosts that honour what we send."""
    if provider == "openrouter" and "reasoning" in kwargs:
        return {"extra_body": {"provider": {"require_parameters": True}}}
    return {}
