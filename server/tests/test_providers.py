"""Retry ceilings: three tries in all, and none for errors retrying cannot fix."""

import pytest

pytestmark = pytest.mark.slow  # imports knowledge_storm


class _Err(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _model(monkeypatch, errors):
    from litstorm.engines.storm import providers

    model = providers.BoundedGoogleModel(model="gemini/x", api_key="k", timeout=5, max_tokens=10)
    calls = []

    def fail(prompt, **kwargs):
        calls.append(1)
        raise errors.pop(0) if errors else _Err(500)

    monkeypatch.setattr(model, "basic_request", fail)
    monkeypatch.setattr("time.sleep", lambda s: None)
    return model, calls


def test_transient_errors_are_tried_three_times_in_all(monkeypatch):
    model, calls = _model(monkeypatch, [_Err(429), _Err(503), _Err(500)])
    with pytest.raises(_Err):
        model.request("hi")
    assert len(calls) == 3


def test_a_bad_key_is_not_retried(monkeypatch):
    model, calls = _model(monkeypatch, [_Err(401)])
    with pytest.raises(_Err):
        model.request("hi")
    assert len(calls) == 1


def test_openrouter_reasoning_is_only_routed_to_hosts_that_honour_it():
    from litstorm.engines.storm import providers

    llm = {"provider": "openrouter", "model": "a/b", "reasoning": "off"}
    lm = providers.build_lm(llm, "k", 100, 30)
    assert lm.kwargs["reasoning"] == {"enabled": False}
    assert lm.kwargs["extra_body"] == {"provider": {"require_parameters": True}}

    plain = providers.build_lm({"provider": "openrouter", "model": "a/b"}, "k", 100, 30)
    assert "extra_body" not in plain.kwargs


def test_litellm_gets_two_retries():
    from litstorm.engines.storm import providers

    lm = providers.build_lm({"provider": "openrouter", "model": "a/b"}, "k", 100, 30)
    assert lm.kwargs["num_retries"] == 2
    assert lm.kwargs["timeout"] == 30


def test_arxiv_retries_a_rate_limit_then_counts_the_refusal(monkeypatch):
    from litstorm.engines.storm import arxiv_rm

    calls = []

    class Resp:
        def __init__(self, code):
            self.status_code, self.text = code, "<feed></feed>"

        def raise_for_status(self):
            if self.status_code >= 400:
                import requests

                raise requests.HTTPError(f"{self.status_code} Client Error")

    monkeypatch.setattr(arxiv_rm.requests, "get", lambda *a, **kw: calls.append(1) or Resp(429))
    monkeypatch.setattr(arxiv_rm.time, "sleep", lambda s: None)
    monkeypatch.setattr(arxiv_rm, "_wait_turn", lambda: None)
    rm = arxiv_rm.ArxivRM(k=2)
    assert rm.forward("graph neural networks") == []
    assert len(calls) == 3  # three tries in all
    assert rm.refused == 1 and "429" in rm.last_refusal


def test_arxiv_does_not_retry_a_bad_request(monkeypatch):
    from litstorm.engines.storm import arxiv_rm

    calls = []

    class Resp:
        status_code, text = 400, ""

        def raise_for_status(self):
            import requests

            raise requests.HTTPError("400 Client Error")

    monkeypatch.setattr(arxiv_rm.requests, "get", lambda *a, **kw: calls.append(1) or Resp())
    monkeypatch.setattr(arxiv_rm, "_wait_turn", lambda: None)
    arxiv_rm.ArxivRM(k=2).forward("x")
    assert len(calls) == 1


@pytest.mark.parametrize("kind", ["searxng", "tavily", "arxiv"])
def test_every_search_provider_builds_the_retriever_a_run_uses(kind):
    """The admin's test button calls each service over plain HTTP, so it
    passes even when the retriever a Run builds cannot load its client
    library. Build the real one for every kind on offer."""
    from litstorm.catalog import SEARCH_PROVIDERS
    from litstorm.engines.storm import providers

    assert set(SEARCH_PROVIDERS) == {"searxng", "tavily", "arxiv"}, "add the new kind to this test"
    search = {"provider": kind, "endpoint": "http://searxng.test"}
    rm = providers.build_rm(search, api_key="tvly-test-0000", k=3, timeout=5)
    assert rm.k == 3
