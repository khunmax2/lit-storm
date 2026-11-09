"""Build STORM's language model and retriever from a Run's settings.

The provider table is copied from the Streamlit app's demo_util.py and the
retrievers from its search_sources.py (the app was removed on 2026-09-30),
minus everything that read settings off disk: here every value arrives in
the RunConfig or the Secrets.

Retries follow docs/web-app-design.md: one request and at most two more
(three in all), with growing gaps. LiteLLM counts `num_retries` on top of the
first call, so it is 2. Google's SDK is wrapped by knowledge_storm with eight
tries, which is overridden below.
"""

import backoff

from knowledge_storm.lm import GoogleModel, LitellmModel

from .arxiv_rm import ArxivRM
from .tci_rm import TciRM

RETRIES = 2  # after the first request, so three in all
TRIES = RETRIES + 1

from litstorm.catalog import (  # noqa: F401 - re-exported
    LLM_PROVIDERS,
    SEARCH_PROVIDERS,
    reasoning_kwargs,
    routing_kwargs,
)

# How much one reply may spend. The conversation stages run hundreds of
# times and answer in a sentence; the writing stages write sections.
DEFAULT_MAX_TOKENS = {"conversation": 500, "writing": 3000}


class ProviderConfigError(ValueError):
    """The Run's settings do not describe something we can call."""


def _permanent(error):
    """A Google error that trying again will not fix: a bad key, a bad
    request, a model that does not exist. Those stop the Run at once
    (docs/web-app-design.md, การ retry คำขอที่ล้มเหลว)."""
    code = getattr(error, "code", None)
    return isinstance(code, int) and 400 <= code < 500 and code not in (408, 429)


class BoundedGoogleModel(GoogleModel):
    """GoogleModel with our retry ceiling and a request timeout."""

    def __init__(self, model, api_key, timeout, **kwargs):
        super().__init__(model=model, api_key=api_key, **kwargs)
        from google import genai
        from google.genai import types

        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(timeout * 1000)),
        )

    @backoff.on_exception(backoff.expo, Exception, max_tries=TRIES, giveup=_permanent)
    def request(self, prompt, **kwargs):
        return self.basic_request(prompt, **kwargs)


def model_id(llm):
    provider = llm.get("provider", "")
    if provider not in LLM_PROVIDERS:
        raise ProviderConfigError(
            f"{provider!r} is not an LLM provider: {sorted(LLM_PROVIDERS)}"
        )
    if not llm.get("model"):
        raise ProviderConfigError("no model named")
    return LLM_PROVIDERS[provider]["prefix"] + llm["model"]


def build_lm(llm, api_key, max_tokens, timeout):
    """One language model, for every stage that uses this token budget."""
    provider = llm.get("provider", "")
    model = model_id(llm)
    if not api_key:
        raise ProviderConfigError(f"no API key for {provider!r}")

    kwargs = {"temperature": 1.0, "top_p": 0.9}
    kwargs.update(reasoning_kwargs(llm.get("reasoning"), provider))
    kwargs.update(routing_kwargs(provider, kwargs))

    if provider == "gemini":
        return BoundedGoogleModel(
            model=model, api_key=api_key, timeout=timeout, max_tokens=max_tokens, **kwargs
        )

    if LLM_PROVIDERS[provider].get("needs_base"):
        if not llm.get("api_base"):
            raise ProviderConfigError(f"{provider!r} needs an api_base")
        kwargs["api_base"] = llm["api_base"]
    return LitellmModel(
        model=model,
        api_key=api_key,
        max_tokens=max_tokens,
        num_retries=RETRIES,
        timeout=timeout,
        **kwargs,
    )


def build_rm(search, api_key, k, timeout):
    """The retriever for the one Search Provider this Run uses."""
    provider = search.get("provider", "")
    if provider == "searxng":
        from knowledge_storm.rm import SearXNG

        if not search.get("endpoint"):
            raise ProviderConfigError("SearXNG needs an endpoint")
        return SearXNG(
            searxng_api_url=search["endpoint"],
            searxng_api_key=api_key or None,
            k=k,
            engines=search.get("engines"),
        )
    if provider == "tavily":
        from knowledge_storm.rm import TavilySearchRM

        if not api_key:
            raise ProviderConfigError("Tavily needs an API key")
        return TavilySearchRM(tavily_search_api_key=api_key, k=k, include_raw_content=True)
    if provider == "arxiv":
        return ArxivRM(k=k, timeout=timeout)
    if provider == "tci":
        return TciRM(k=k, timeout=timeout)
    raise ProviderConfigError(
        f"{provider!r} is not a Search Provider: {list(SEARCH_PROVIDERS)}"
    )
