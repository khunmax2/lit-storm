"""The admin page's "Test" buttons: one small real call to a model or a
Search Provider, so a wrong key shows up now rather than in a user's Run.

Runs in the API with LiteLLM and plain HTTP, not through STORM, so the API
does not load the research engine. The answer never repeats the key.
"""

import time

import requests

from litstorm.catalog import LLM_PROVIDERS, reasoning_kwargs, routing_kwargs

TIMEOUT = 30


def _short(error):
    text = f"{type(error).__name__}: {error}"
    return text[:300]


def llm(model, credential_key, api_base=None):
    """(ok, message, seconds) for one tiny completion."""
    import litellm

    if not credential_key:
        return False, "no API key stored for this provider", 0.0
    kwargs = {"api_key": credential_key, "timeout": TIMEOUT, "num_retries": 0}
    if api_base:
        kwargs["api_base"] = api_base
    kwargs.update(reasoning_kwargs(model.reasoning, model.provider))
    kwargs.update(routing_kwargs(model.provider, kwargs))
    budget = (model.max_tokens or {}).get("conversation", 500)
    started = time.monotonic()
    try:
        response = litellm.completion(
            model=LLM_PROVIDERS[model.provider]["prefix"] + model.model,
            messages=[{"role": "user", "content": "Reply with the single word: ok"}],
            max_tokens=budget,
            drop_params=True,
            **kwargs,
        )
    except Exception as error:  # noqa: BLE001 - every failure is the answer
        return False, _short(error), time.monotonic() - started
    seconds = time.monotonic() - started
    text = (response.choices[0].message.content or "").strip()
    if not text:
        # The same trap STORM falls into: a thinking model spends the whole
        # budget thinking and says nothing.
        return False, f"the model answered with no text within {budget} tokens — raise the budget or lower its reasoning", seconds
    return True, text[:80], seconds


def search(provider, api_key):
    """(ok, message, seconds) for one real search."""
    started = time.monotonic()
    query = "retrieval augmented generation"
    try:
        if provider.kind == "searxng":
            url = provider.endpoint.rstrip("/")
            url = url if url.endswith("/search") else url + "/search"
            params = {"q": query, "format": "json"}
            if provider.engines:
                params["engines"] = provider.engines
            r = requests.get(url, params=params, timeout=TIMEOUT)
            if r.status_code == 403:
                return False, "SearXNG refused format=json: enable json under search.formats", time.monotonic() - started
            r.raise_for_status()
            found = len(r.json().get("results", []))
        elif provider.kind == "tavily":
            r = requests.post(
                "https://api.tavily.com/search",
                json={"api_key": api_key, "query": query, "max_results": 3},
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            found = len(r.json().get("results", []))
        elif provider.kind == "arxiv":
            r = requests.get(
                "http://export.arxiv.org/api/query",
                params={"search_query": f"all:{query}", "max_results": 3},
                timeout=TIMEOUT,
                headers={"User-Agent": "lit-storm/1.0"},
            )
            r.raise_for_status()
            found = r.text.count("<entry>")
        else:
            return False, f"no check for {provider.kind!r}", 0.0
    except Exception as error:  # noqa: BLE001
        return False, _short(error), time.monotonic() - started
    seconds = time.monotonic() - started
    if not found:
        return False, "the search answered with no results", seconds
    return True, f"{found} results", seconds
