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


def test_arxiv_skips_blank_queries(monkeypatch):
    from litstorm.engines.storm import arxiv_rm

    asked = []

    class Resp:
        status_code, text = 200, "<feed></feed>"

        def raise_for_status(self):
            pass

    monkeypatch.setattr(arxiv_rm.requests, "get", lambda url, **kw: asked.append(url) or Resp())
    monkeypatch.setattr(arxiv_rm, "_wait_turn", lambda: None)
    rm = arxiv_rm.ArxivRM(k=2)
    rm.forward(["", "   ", "graph neural networks"])
    assert len(asked) == 1 and "graph" in asked[0]
    assert rm.refused == 0 and rm.get_usage_and_reset() == {"ArxivRM": 1}


@pytest.mark.parametrize("kind", ["searxng", "tavily", "arxiv", "tci"])
def test_every_search_provider_builds_the_retriever_a_run_uses(kind):
    """The admin's test button calls each service over plain HTTP, so it
    passes even when the retriever a Run builds cannot load its client
    library. Build the real one for every kind on offer."""
    from litstorm.catalog import SEARCH_PROVIDERS
    from litstorm.engines.storm import providers

    assert set(SEARCH_PROVIDERS) == {"searxng", "tavily", "arxiv", "tci"}, "add the new kind to this test"
    search = {"provider": kind, "endpoint": "http://searxng.test"}
    rm = providers.build_rm(search, api_key="tvly-test-0000", k=3, timeout=5)
    assert rm.k == 3


def test_searxng_skips_blank_queries_and_one_it_rejects(monkeypatch):
    """A blank query from STORM once ended a whole Run: SearXNG answers an
    empty q with 400, which was taken for a wrong address."""
    import requests

    from knowledge_storm.rm import SearXNG, SearXNGConfigError

    asked = []

    class Resp:
        def __init__(self, code):
            self.status_code = code

        def raise_for_status(self):
            pass

        def json(self):
            return {"results": [{"url": "https://a.test/" + asked[-1], "title": "A", "content": "c"}]}

    def get(url, headers, params, timeout):
        asked.append(params["q"])
        return Resp(400 if params["q"] == "bad" else 200)

    monkeypatch.setattr(requests, "get", get)
    rm = SearXNG("http://searxng.test", k=1)
    found = rm.forward(["", "  ", "songkran", "bad", "rag"])
    assert asked == ["songkran", "bad", "rag"]  # blanks never sent
    assert [r["url"] for r in found] == ["https://a.test/songkran", "https://a.test/rag"]
    assert rm.get_usage_and_reset() == {"SearXNG": 3}

    monkeypatch.setattr(requests, "get", lambda *a, **kw: Resp(404))
    with pytest.raises(SearXNGConfigError):  # a wrong address still says so
        SearXNG("http://searxng.test/nope", k=1).forward("songkran")


def test_searxng_counts_queries_its_engines_refused(monkeypatch):
    """When every engine behind the instance is refusing, a run that found
    nothing should say so, not that the topic has no sources."""
    import requests

    from knowledge_storm.rm import SearXNG

    class Resp:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"results": [], "unresponsive_engines": [["brave", "Suspended: too many requests"],
                                                            ["duckduckgo", "timeout"]]}

    monkeypatch.setattr(requests, "get", lambda *a, **kw: Resp())
    rm = SearXNG("http://searxng.test", k=3)
    assert rm.forward(["songkran", "rag"]) == []
    assert rm.refused == 2
    assert rm.last_refusal == "brave: Suspended: too many requests, duckduckgo: timeout"


def test_tavily_skips_blank_queries_and_one_it_rejects(monkeypatch):
    """Tavily answers a blank query with "Query is missing", which ended two
    Thai Runs in the benchmark. A bad key must still fail loudly."""
    from tavily.errors import BadRequestError, InvalidAPIKeyError

    from knowledge_storm.rm import TavilySearchRM

    rm = TavilySearchRM(tavily_search_api_key="tvly-test", k=2)
    asked = []

    def search(query, **kw):
        asked.append(query)
        if query == "bad":
            raise BadRequestError("Query is too long.")
        return {"results": [{"url": f"https://a.test/{query}", "title": "A", "content": "c"}]}

    monkeypatch.setattr(rm.tavily_client, "search", search)
    found = rm.forward(["", "   ", "songkran", "bad"])
    assert asked == ["songkran", "bad"]  # blanks never sent
    assert [r["url"] for r in found] == ["https://a.test/songkran"]
    assert rm.refused == 1 and "too long" in rm.last_refusal

    def locked(query, **kw):
        raise InvalidAPIKeyError("Unauthorized: missing or invalid API key.")

    monkeypatch.setattr(rm.tavily_client, "search", locked)
    with pytest.raises(InvalidAPIKeyError):
        rm.forward("songkran")


def _tci(monkeypatch, answers):
    """A fake ThaiJO: `answers` maps strict=True/False to its result list,
    or to a status code to answer with."""
    import requests

    from litstorm.engines.storm import tci_rm

    asked = []

    class Resp:
        def __init__(self, code, result=None):
            self.status_code, self._result = code, result

        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.HTTPError(f"{self.status_code} Server Error")

        def json(self):
            return {"result": self._result, "total": len(self._result or [])}

    def post(url, json, timeout, headers):
        asked.append((json["term"], json["strict"]))
        answer = answers[json["strict"]]
        return Resp(answer) if isinstance(answer, int) else Resp(200, answer)

    monkeypatch.setattr(tci_rm.requests, "post", post)
    monkeypatch.setattr(tci_rm.time, "sleep", lambda s: None)
    return tci_rm.TciRM(k=2), asked


def _article(n, title_th="", title_en="", abstract="บทคัดย่อ"):
    return {
        "articleUrl": f"https://so01.tci-thaijo.org/index.php/j/article/view/{n}",
        "thaijoUrl": "https://so01.tci-thaijo.org/index.php/j",
        "title": {"th_TH": title_th, "en_US": title_en},
        "abstract_clean": {"th_TH": abstract, "en_US": ""},
        "authors": [{"full_name": {"th_TH": "สมชาย ใจดี", "en_US": "Somchai Jaidee"}}],
        "datePublished": "2025-06-29T17:00:00+0000",
    }


def test_tci_asks_strictly_then_loosely_and_keeps_k(monkeypatch):
    """ThaiJO's strict search wants every word; STORM's long questions
    mostly find nothing that way, so the loose search's first k are kept."""
    rm, asked = _tci(monkeypatch, {True: [], False: [_article(i, f"บทความ {i}") for i in range(5)]})
    found = rm.forward(["  ", "ผลกระทบของการนอนดึกต่อสุขภาพจิตในวัยรุ่นไทย"])
    assert asked == [("ผลกระทบของการนอนดึกต่อสุขภาพจิตในวัยรุ่นไทย", True),
                     ("ผลกระทบของการนอนดึกต่อสุขภาพจิตในวัยรุ่นไทย", False)]
    assert [r["title"] for r in found] == ["บทความ 0", "บทความ 1"]
    assert found[0]["url"].endswith("/article/view/0")  # the article, not its journal
    assert found[0]["snippets"] == ["บทคัดย่อ"]
    assert found[0]["description"] == "สมชาย ใจดี (2025-06-29)"
    assert rm.get_usage_and_reset() == {"TciRM": 1}


def test_tci_strict_hits_are_enough_and_empty_abstracts_are_skipped(monkeypatch):
    rm, asked = _tci(monkeypatch, {True: [_article(1, title_en="PM2.5", abstract=""), _article(2, "ฝุ่น")],
                                  False: [_article(9)]})
    found = rm.forward("PM2.5 เชียงใหม่")
    assert [q[1] for q in asked] == [True]
    assert [r["title"] for r in found] == ["ฝุ่น"]


def test_tci_counts_a_refusal(monkeypatch):
    rm, asked = _tci(monkeypatch, {True: 503, False: 503})
    assert rm.forward("สงกรานต์") == []
    assert len(asked) == 3  # three tries in all, then given up
    assert rm.refused == 1 and "503" in rm.last_refusal
