"""Search results kept for 24 hours, shared by every Run on the machine.

The same query to the same Search Provider within a day is answered from
disk: inside one Run, where STORM's conversations often ask alike, and across
Runs, as when a Run is retried or a topic asked again (docs/web-app-design.md,
รุ่นสอง: วิธีเร่ง). Fewer searches also means fewer engines refusing SearXNG
for asking too often.

One JSON file per query, named by a hash of the provider and the query. An
empty answer is not kept, so a query refused today is asked again. The
Worker deletes files past their day (`sweep`).
"""

import hashlib
import json
import os
import time

TTL = 24 * 3600


class CachedRM:
    """A retriever in front of another, with the same interface.

    Everything but the search itself (usage, refusals, k) is the inner
    retriever's, so a cache hit costs nothing and counts as no search.
    """

    def __init__(self, rm, directory, identity, ttl=TTL):
        self.rm = rm
        self.directory = directory
        self.identity = identity
        self.ttl = ttl
        self.hits = 0
        self.misses = 0

    def __getattr__(self, name):
        return getattr(self.rm, name)

    def __call__(self, *args, **kwargs):
        return self.forward(*args, **kwargs)

    def _path(self, query):
        key = hashlib.sha256(json.dumps([self.identity, query], ensure_ascii=False).encode()).hexdigest()
        return os.path.join(self.directory, key[:2], key + ".json")

    def _get(self, query):
        path = self._path(query)
        try:
            if time.time() - os.path.getmtime(path) > self.ttl:
                return None
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def _put(self, query, results):
        path = self._path(query)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = f"{path}.{os.getpid()}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False)
            os.replace(tmp, path)
        except OSError:
            pass  # a cache that cannot write is only slower

    def forward(self, query_or_queries, exclude_urls=[]):  # noqa: B006 - the retrievers' own signature
        queries = [query_or_queries] if isinstance(query_or_queries, str) else list(query_or_queries)
        found = []
        for query in queries:
            query = (query or "").strip()
            if not query:
                continue
            kept = self._get(query)
            if kept is None:
                self.misses += 1
                kept = self.rm.forward([query], exclude_urls=exclude_urls)
                if kept:
                    self._put(query, kept)
            else:
                self.hits += 1
            found.extend(r for r in kept if r.get("url") not in exclude_urls)
        return found


def identity(search, k):
    """What makes two searches the same: the provider, where it is, which
    engines, and how many results."""
    return [search.get("provider"), search.get("endpoint"), search.get("engines"), k]


def sweep(directory, ttl=TTL):
    """Delete results past their day; the number deleted."""
    gone = 0
    cutoff = time.time() - ttl
    for root, _, names in os.walk(directory):
        for name in names:
            path = os.path.join(root, name)
            try:
                if os.path.getmtime(path) < cutoff:
                    os.remove(path)
                    gone += 1
            except OSError:
                pass
    return gone
