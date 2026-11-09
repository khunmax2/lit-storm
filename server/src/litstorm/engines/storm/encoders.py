"""The encoder STORM's article stage uses to match snippets to sections.

STORM compares every collected snippet with each line of a section's outline
and hands the closest ones to the writer (storm_dataclass.py,
prepare_table_for_retrieval). Its own model is English-only; a Run may name
an embedding service instead (litstorm.embedding).

With a service, every text the stage will ask about — the snippets and the
outline's lines — is sent up front, in batches. If that fails the Run falls
back to the built-in model for all of them: vectors from two models cannot
be compared, and a report that matched a little worse beats no report.
"""

import time

import numpy as np

from litstorm import embedding


class ApiEncoder:
    """SentenceTransformer's `encode`, over vectors fetched ahead of time."""

    def __init__(self, config, api_key, timeout):
        self.config = config
        self.api_key = api_key
        self.timeout = timeout
        self.vectors = {}
        self.tokens = 0

    def warm(self, texts):
        missing = list(dict.fromkeys(t for t in texts if t not in self.vectors))
        if not missing:
            return
        found, tokens = embedding.embed(missing, self.config, self.api_key, self.timeout)
        self.tokens += tokens
        self.vectors.update(zip(missing, (np.asarray(v, dtype=np.float32) for v in found)))

    def encode(self, texts):
        one = isinstance(texts, str)
        texts = [texts] if one else list(texts)
        # A line the stage did not announce: fetched now, from STORM's threads.
        self.warm(texts)
        out = np.stack([self.vectors[t] for t in texts]) if texts else np.zeros((0, 1), dtype=np.float32)
        return out[0] if one else out


def outline_lines(outline):
    """What STORM will ask the table about while writing: each first-level
    section's outline as a list (article_generation.py, generate_article)."""
    lines = []
    sections = outline.get_first_level_section_names() if outline else []
    for name in sections:
        lines.extend(outline.get_outline_as_list(root_section_name=name, add_hashtags=False))
    return lines or ([outline.root.section_name] if outline else [])


def attach(table, outline, config, secrets, progress):
    """Give `table` the Run's encoder before the article stage prepares it."""
    kept = config.embedding or {}
    provider = kept.get("provider") or embedding.BUILTIN
    if provider == embedding.BUILTIN:
        return  # STORM loads its own
    snippets = [s for info in table.url_to_info.values() for s in info.snippets]
    encoder = ApiEncoder(kept, secrets.embedding_api_key, config.request_timeout)
    started = time.monotonic()
    try:
        encoder.warm(snippets + outline_lines(outline))
    except embedding.EmbeddingError as error:
        progress.note(
            "embedding", provider=provider, model=kept.get("model"), fallback=True, message=str(error)[:300]
        )
        return
    table.encoder = encoder
    progress.note(
        "embedding", provider=provider, model=kept.get("model"), fallback=False,
        texts=len(encoder.vectors), tokens=encoder.tokens, seconds=round(time.monotonic() - started, 2),
    )
