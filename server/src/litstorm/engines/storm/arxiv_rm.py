"""Search arXiv itself, through its public API.

knowledge_storm ships a StanfordOvalArxivRM, but that is a client for a
private Stanford service — the class says so, the endpoint is a required
argument, and no URL for it is published. This talks to arxiv.org's own API,
which is open, needs no key, and returns the abstract as the passage.

An abstract is a better passage than a scraped web page: it is written to
stand alone, it is already the paper's summary, and the URL beside it is a
citation rather than a link to somebody's blog post about the paper.
"""

import logging
import threading
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlencode

import dspy
import requests

ENDPOINT = "http://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"

# arXiv asks for no more than one request every three seconds. STORM fires its
# searches from a thread pool, so the politeness has to live here rather than
# in the caller: one lock, and every thread waits its turn.
_MIN_INTERVAL = 3.0
TRIES = 3
RETRYABLE = {429, 500, 502, 503, 504}
_throttle = threading.Lock()
_last_call = 0.0


def _wait_turn():
    global _last_call
    with _throttle:
        gap = time.monotonic() - _last_call
        if gap < _MIN_INTERVAL:
            time.sleep(_MIN_INTERVAL - gap)
        _last_call = time.monotonic()


class ArxivRM(dspy.Retrieve):
    """Retrieve paper abstracts from arXiv for a query."""

    def __init__(self, k=3, sort_by="relevance", timeout=30):
        super().__init__(k=k)
        self.k = k
        self.sort_by = sort_by
        self.timeout = timeout
        self.usage = 0
        # Queries arXiv refused outright, and the last reason: the engine
        # reads these to tell "nothing was found" from "we were refused".
        self.refused = 0
        self.last_refusal = ""

    def get_usage_and_reset(self):
        usage = self.usage
        self.usage = 0
        return {"ArxivRM": usage}

    def _search(self, query):
        _wait_turn()
        url = f"{ENDPOINT}?" + urlencode(
            {
                "search_query": f"all:{query}",
                "start": 0,
                "max_results": self.k,
                "sortBy": self.sort_by,
                "sortOrder": "descending",
            }
        )
        # Three tries in all for what may pass (rate limit, server error),
        # with growing gaps, as for every outside request
        # (docs/web-app-design.md, การ retry คำขอที่ล้มเหลว).
        for attempt in range(TRIES):
            response = requests.get(
                url, timeout=self.timeout, headers={"User-Agent": "STORM/1.0"}
            )
            if response.status_code not in RETRYABLE or attempt == TRIES - 1:
                break
            time.sleep(_MIN_INTERVAL * (2**attempt))
            _wait_turn()
        response.raise_for_status()
        return ET.fromstring(response.text)

    @staticmethod
    def _entry_to_result(entry):
        def text(tag):
            found = entry.find(ATOM + tag)
            return " ".join(found.text.split()) if found is not None and found.text else ""

        abstract = text("summary")
        if not abstract:
            return None

        # The <id> is the abstract page; the paper itself is one hop away and
        # the abstract page is what a reader wants to land on.
        link = text("id")
        authors = [
            " ".join(a.find(ATOM + "name").text.split())
            for a in entry.findall(ATOM + "author")
            if a.find(ATOM + "name") is not None
        ]
        published = text("published")[:10]
        byline = ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")
        return {
            "url": link,
            "title": text("title"),
            "description": f"{byline} ({published})" if byline else published,
            "snippets": [abstract],
        }

    def forward(self, query_or_queries, exclude_urls=None):
        queries = (
            [query_or_queries]
            if isinstance(query_or_queries, str)
            else list(query_or_queries)
        )
        exclude_urls = set(exclude_urls or [])
        self.usage += len(queries)

        collected = []
        seen = set()
        for query in queries:
            try:
                root = self._search(query)
            except Exception as error:  # noqa: BLE001 - one bad query, not the run
                logging.error(f"arXiv search failed for {query!r}: {error}")
                self.refused += 1
                self.last_refusal = str(error)[:200]
                continue
            for entry in root.findall(ATOM + "entry"):
                result = self._entry_to_result(entry)
                if not result:
                    continue
                if result["url"] in exclude_urls or result["url"] in seen:
                    continue
                seen.add(result["url"])
                collected.append(result)
        return collected
