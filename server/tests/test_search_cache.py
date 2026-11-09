"""Search results kept for a day: the same query to the same provider is
answered from disk, costs no search, and a refusal is not kept."""

import os
import time

from litstorm import search_cache


class _Inner:
    def __init__(self, answer=None):
        self.asked = []
        self.answer = answer
        self.usage = 0
        self.refused = 0
        self.last_refusal = ""
        self.k = 3

    def forward(self, queries, exclude_urls=[]):  # noqa: B006
        self.asked.extend(queries)
        self.usage += len(queries)
        if self.answer is not None:
            return list(self.answer)
        return [{"url": f"https://a.test/{q}", "title": q, "description": "", "snippets": [q]} for q in queries]

    def get_usage_and_reset(self):
        used, self.usage = self.usage, 0
        return {"Inner": used}


def _cached(tmp_path, inner, search=None):
    search = search or {"provider": "searxng", "endpoint": "http://searxng.test", "engines": None}
    return search_cache.CachedRM(inner, str(tmp_path), search_cache.identity(search, 3))


def test_a_repeated_query_is_answered_from_disk_and_costs_nothing(tmp_path):
    inner = _Inner()
    first = _cached(tmp_path, inner)
    assert [r["url"] for r in first(query_or_queries=["songkran"])] == ["https://a.test/songkran"]
    assert inner.get_usage_and_reset() == {"Inner": 1}

    again = _cached(tmp_path, inner)  # another Run
    assert [r["url"] for r in again(query_or_queries=[" songkran ", "rag"])] == [
        "https://a.test/songkran", "https://a.test/rag"
    ]
    assert inner.asked == ["songkran", "rag"]
    assert (again.hits, again.misses) == (1, 1)
    assert again.get_usage_and_reset() == {"Inner": 1}  # only rag was searched


def test_another_provider_or_engine_list_is_another_search(tmp_path):
    inner = _Inner()
    _cached(tmp_path, inner)(query_or_queries=["songkran"])
    academic = {"provider": "searxng", "endpoint": "http://searxng.test", "engines": "arxiv,pubmed"}
    _cached(tmp_path, inner, academic)(query_or_queries=["songkran"])
    assert inner.asked == ["songkran", "songkran"]


def test_an_empty_answer_is_not_kept(tmp_path):
    inner = _Inner(answer=[])
    inner.refused = 1
    cached = _cached(tmp_path, inner)
    cached(query_or_queries=["songkran"])
    cached(query_or_queries=["songkran"])
    assert inner.asked == ["songkran", "songkran"]
    assert cached.refused == 1  # the engine still reads the inner retriever's refusals


def test_a_day_old_answer_is_searched_again_and_swept(tmp_path):
    inner = _Inner()
    _cached(tmp_path, inner)(query_or_queries=["songkran"])
    (path,) = [os.path.join(r, n) for r, _, names in os.walk(tmp_path) for n in names]
    old = time.time() - search_cache.TTL - 60
    os.utime(path, (old, old))
    _cached(tmp_path, inner)(query_or_queries=["songkran"])
    assert inner.asked == ["songkran", "songkran"]

    os.utime(path, (old, old))
    assert search_cache.sweep(str(tmp_path)) == 1
    assert not os.path.exists(path)


def test_excluded_urls_stay_excluded_on_a_hit(tmp_path):
    inner = _Inner()
    _cached(tmp_path, inner)(query_or_queries=["songkran"])
    hit = _cached(tmp_path, inner)(query_or_queries=["songkran"], exclude_urls=["https://a.test/songkran"])
    assert hit == []
