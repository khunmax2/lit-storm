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

SEARCH_PROVIDERS = ("searxng", "tavily", "arxiv")
