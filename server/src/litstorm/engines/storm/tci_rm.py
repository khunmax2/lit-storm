"""Search Thai academic journals through TCI-ThaiJO's public search API.

ThaiJO hosts the journals of the Thai-Journal Citation Index: articles in
Thai and English, each with its abstract, which is the passage. Nothing
else here finds Thai research: the academic engines behind SearXNG return
almost nothing in Thai (docs/web-app-design.md, SearXNG LDR-academic).

The API needs no key. Its strict search (matching_strategy "all") wants
every word of the query in the article, so STORM's long questions (measured
2026-09-30) mostly find nothing; then the query is asked again loosely,
ranked by relevance, and only the first k are kept. A loose answer can stray
from the topic. The same two-step search the Open Deep Research app used.

ThaiJO moved its search in November 2026 from /api/articles/search/ (now a
404) to /api/v1/articles/search, the one its own site calls. It answers
`hits`, and leaves each hit's abstract out unless asked to highlight.
"""

import logging
import time

import dspy
import requests

ENDPOINT = "https://www.tci-thaijo.org/api/v1/articles/search"
TRIES = 3
RETRYABLE = {429, 500, 502, 503, 504}


def _text(field, prefer="th_TH"):
    """ThaiJO keeps each text by locale; take the preferred, else any."""
    if not isinstance(field, dict):
        return (field or "").strip() if isinstance(field, str) else ""
    other = "en_US" if prefer == "th_TH" else "th_TH"
    for locale in (prefer, other, *field):
        value = field.get(locale)
        if isinstance(value, str) and value.strip():
            return " ".join(value.split())
    return ""


class TciRM(dspy.Retrieve):
    """Retrieve article abstracts from TCI-ThaiJO for a query."""

    def __init__(self, k=3, timeout=30):
        super().__init__(k=k)
        self.k = k
        self.timeout = timeout
        self.usage = 0
        # Queries ThaiJO refused, and the last reason: the engine reads these
        # to tell "nothing was found" from "we were refused".
        self.refused = 0
        self.last_refusal = ""

    def get_usage_and_reset(self):
        usage = self.usage
        self.usage = 0
        return {"TciRM": usage}

    def _search(self, query, strict):
        body = {"q": query, "page": 1, "per_page": self.k, "highlight": True, "facets": False}
        if strict:
            body["matching_strategy"] = "all"
        # Three tries in all for what may pass, with growing gaps
        # (docs/web-app-design.md, การ retry คำขอที่ล้มเหลว).
        for attempt in range(TRIES):
            response = requests.post(ENDPOINT, json=body, timeout=self.timeout,
                                     headers={"User-Agent": "lit-storm/2"})
            if response.status_code not in RETRYABLE or attempt == TRIES - 1:
                break
            time.sleep(2**attempt)
        response.raise_for_status()
        return response.json().get("hits") or []

    @staticmethod
    def _to_result(item):
        # article_url is the article's page; journal_url is only its journal's.
        url = item.get("article_url")
        abstract = _text(item.get("abstracts"))
        if not url or not abstract:
            return None
        # Authors are kept by locale, a list of names in each.
        by_locale = item.get("authors") if isinstance(item.get("authors"), dict) else {}
        names = by_locale.get("th_TH") or by_locale.get("en_US") or next(iter(by_locale.values()), [])
        authors = [" ".join(n.split()) for n in names or [] if isinstance(n, str) and n.strip()]
        # A local date ("2025-06-30T00:00:00+07:00"): its first ten letters are the day in Thailand.
        published = (item.get("date_published") or "")[:10]
        if published.startswith("1970"):
            published = ""  # the epoch: ThaiJO's way of saying no date
        if not published:
            return {"url": url, "title": _text(item.get("titles")) or url,
                    "description": ", ".join(authors[:3]), "snippets": [abstract]}
        byline = ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")
        return {
            "url": url,
            "title": _text(item.get("titles")) or url,
            "description": f"{byline} ({published})" if byline else published,
            "snippets": [abstract],
        }

    def forward(self, query_or_queries, exclude_urls=None):
        queries = [query_or_queries] if isinstance(query_or_queries, str) else list(query_or_queries)
        queries = [q.strip() for q in queries if q and q.strip()]
        exclude_urls = set(exclude_urls or [])
        self.usage += len(queries)

        collected, seen = [], set()
        for query in queries:
            try:
                items = self._search(query, strict=True) or self._search(query, strict=False)
            except Exception as error:  # noqa: BLE001 - one bad query, not the run
                logging.error(f"TCI search failed for {query!r}: {error}")
                self.refused += 1
                self.last_refusal = str(error)[:200]
                continue
            for item in items[: self.k]:
                result = self._to_result(item)
                if not result or result["url"] in exclude_urls or result["url"] in seen:
                    continue
                seen.add(result["url"])
                collected.append(result)
        return collected
