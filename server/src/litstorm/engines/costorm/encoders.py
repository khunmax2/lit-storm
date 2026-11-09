"""The encoder a Co-STORM Turn uses, from the system's embedding service.

Co-STORM places every snippet it collects in the mind map by similarity, and
asks for vectors all through a Turn, not once up front as STORM's article
stage does (engines/storm/encoders.py). Its own `Encoder` reaches only
OpenAI or Azure, configured by environment variables; this one is built from
the Discussion's embedding setting (litstorm.embedding), and has the two
methods Co-STORM calls: `encode` and `get_total_token_usage`.

No vector outlives the Turn: the mind map is saved as names and snippets, and
every comparison is between vectors made in the same Turn. So a Turn whose
service does not answer its first request can use the built-in model for the
whole Turn, and say so — but one whose service fails half-way cannot mix the
two, and fails instead.
"""

import threading

from litstorm import embedding
from litstorm.engines.storm.encoders import ApiEncoder


class TurnEncoder:
    def __init__(self, config, secrets):
        kept = config.embedding or {}
        self.provider = kept.get("provider") or embedding.BUILTIN
        self.fell_back = None
        self._api = None
        if self.provider != embedding.BUILTIN:
            self._api = ApiEncoder(kept, secrets.embedding_api_key, config.request_timeout)
        self._local = None
        self._lock = threading.Lock()

    def probe(self):
        """Ask the service once; on failure use the built-in model for the Turn."""
        if self._api is None:
            return
        try:
            self._api.warm(["Songkran", "สงกรานต์"])
        except embedding.EmbeddingError as error:
            self.fell_back = str(error)[:300]
            self._api = None

    def _builtin(self):
        with self._lock:
            if self._local is None:
                from sentence_transformers import SentenceTransformer

                self._local = SentenceTransformer(embedding.BUILTIN_MODEL)
        return self._local

    def encode(self, texts, max_workers=5):  # noqa: ARG002 - Co-STORM's signature
        if self._api is not None:
            return self._api.encode(texts)
        return self._builtin().encode(texts)

    def get_total_token_usage(self, reset=False):
        used = self._api.tokens if self._api is not None else 0
        if reset and self._api is not None:
            self._api.tokens = 0
        return used


def for_turn(config, secrets):
    encoder = TurnEncoder(config, secrets)
    encoder.probe()
    return encoder
