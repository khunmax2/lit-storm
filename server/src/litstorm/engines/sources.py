"""A Run's Search Providers, for every Engine (docs/web-app-design.md,
รุ่นสอง: ค้นหลายแหล่งต่อ Run).

`build_search` is the retriever STORM and Co-STORM hand their runners: the
Run's provider, or up to three searched as one (MultiRM).

Deep Research (Node) and Agent Research search through code of their own,
which speaks to SearXNG or Tavily and nothing else. For any other source, or
several, `SearchBridge` puts that same retriever behind a SearXNG-shaped
address on this machine (`GET /search?q=...&format=json`) and the Engine is
pointed at it as if at a SearXNG instance. A Run whose one source the Engine
already speaks keeps the Engine's own client (`bridged`).
"""

import json
import logging
import threading
from contextlib import nullcontext
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from litstorm import outcomes, search_cache
from litstorm.engines.base import EngineFailure

log = logging.getLogger("litstorm.sources")

# Results the bridge answers per query. Deep Research keeps 5 of what it is
# given and Agent Research has its model pick 5, as both do from SearXNG.
BRIDGE_RESULTS = 10
# A result's text, at most: a page's raw content (Tavily) is not a snippet.
CONTENT_CHARS = 2000


def build_search(config, secrets, k):
    """The Run's retriever: its Search Provider, or several searched as one.
    With several, each query's budget of `k` results is shared out evenly,
    and each source keeps a cache of its own."""
    from knowledge_storm.rm import MultiRM

    from litstorm.engines.storm import providers

    searches = [(config.search, secrets.search_api_key)]
    keys = list(secrets.search_extra_api_keys) + [""] * len(config.search_extra)
    searches += list(zip(config.search_extra, keys))
    each = -(-k // len(searches))  # k shared out, rounded up
    built = []
    for search, key in searches:
        rm = providers.build_rm(search, key, each, config.request_timeout)
        if config.search_cache_dir:
            rm = search_cache.CachedRM(rm, config.search_cache_dir, search_cache.identity(search, each))
        built.append(rm)
    if len(built) == 1:
        return built[0]
    names = [s.get("label") or s.get("provider") for s, _ in searches]
    return MultiRM(built, k=k, names=names)


def bridged(config, native):
    """Whether this Run needs the bridge: a source the Engine's own client
    cannot reach (`native`: the provider kinds it speaks), or more than one."""
    return bool(config.search_extra) or config.search.get("provider") not in native


def bridge_for(config, secrets, native):
    """A started SearchBridge when the Run needs one, else a context that
    gives None. Use as `with bridge_for(...) as bridge:`."""
    if not bridged(config, native):
        return nullcontext(None)
    from litstorm.engines.storm.providers import ProviderConfigError

    try:
        rm = build_search(config, secrets, BRIDGE_RESULTS)
    except ProviderConfigError as error:
        raise EngineFailure(outcomes.BAD_CONFIGURATION, str(error)) from error
    return SearchBridge(rm, _name(config))


def _name(config):
    labels = [s.get("label") or s.get("provider") for s in [config.search, *config.search_extra]]
    return " + ".join(labels)


class SearchBridge:
    """The Run's retriever behind a SearXNG-shaped address on 127.0.0.1,
    for the life of a `with` block."""

    def __init__(self, rm, name="search"):
        self.rm = rm
        self.name = name
        self._server = None

    def __enter__(self):
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self._server.daemon_threads = True
        threading.Thread(target=self._server.serve_forever, name="search-bridge", daemon=True).start()
        return self

    def __exit__(self, *exc):
        self._server.shutdown()
        self._server.server_close()

    @property
    def url(self):
        return f"http://127.0.0.1:{self._server.server_address[1]}/search"

    def usage(self):
        """Searches by source since the last call, as the Engines report them."""
        if hasattr(self.rm, "get_usage_and_reset"):
            return self.rm.get_usage_and_reset()
        return {}

    def answer(self, query):
        """What SearXNG would answer, from the Run's sources."""
        found = self.rm.forward(query, exclude_urls=[]) if query.strip() else []
        results = []
        for r in found:
            snippets = [s for s in (r.get("snippets") or []) if s]
            content = (" ".join(snippets) or r.get("description") or "").strip()[:CONTENT_CHARS]
            if r.get("url"):
                results.append({"url": r["url"], "title": r.get("title") or r["url"], "content": content})
        return {
            "query": query,
            "number_of_results": len(results),
            "results": results,
            "unresponsive_engines": [],
        }

    def _handler(self):
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 - http.server's name
                url = urlparse(self.path)
                if url.path.rstrip("/") != "/search":
                    self.send_error(404)
                    return
                query = (parse_qs(url.query).get("q") or [""])[0]
                try:
                    body = json.dumps(bridge.answer(query), ensure_ascii=False).encode()
                except Exception:  # noqa: BLE001 - one failed search is an empty answer, as SearXNG's would be
                    log.exception("search bridge: %r failed", query)
                    body = json.dumps({"query": query, "results": [], "unresponsive_engines": []}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass  # the Run's log has the Engine's own account

        return Handler
