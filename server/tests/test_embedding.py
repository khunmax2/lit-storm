"""The embedding service: one setting for the system, kept with each Run, its
key from the provider's LLM credential, and a fallback to STORM's own model
when the service fails mid-Run."""

from types import SimpleNamespace

import numpy as np
import pytest

from conftest import make_user
from test_api_runs import configured  # noqa: F401  (fixture)


class _Resp:
    def __init__(self, code, body=None, text=""):
        self.status_code, self._body, self.text = code, body, text

    def json(self):
        return self._body


def _service(monkeypatch, fail=None):
    """A fake /embeddings: each text's vector is [len, 1]; answers in reverse
    order, as the API is allowed to. `fail` is a status code to answer with."""
    import requests

    calls = []

    def post(url, json, headers, timeout):
        calls.append((url, json, headers))
        if fail:
            return _Resp(fail, text="nope")
        data = [{"index": i, "embedding": [float(len(t)), 1.0]} for i, t in enumerate(json["input"])]
        return _Resp(200, {"data": data[::-1], "usage": {"prompt_tokens": len(json["input"])}})

    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr("time.sleep", lambda s: None)
    return calls


CONFIG = {"provider": "openrouter", "model": "baai/bge-m3", "api_base": "https://openrouter.ai/api/v1"}


def test_embed_batches_keeps_order_and_counts_tokens(monkeypatch):
    from litstorm import embedding

    calls = _service(monkeypatch)
    texts = [f"t{'x' * i}" for i in range(70)]
    vectors, tokens = embedding.embed(texts, CONFIG, "sk-or-1")
    assert [v[0] for v in vectors] == [float(len(t)) for t in texts]
    assert len(calls) == 5 and tokens == 70  # 4 × 16 + 6, side by side
    assert {c[0] for c in calls} == {"https://openrouter.ai/api/v1/embeddings"}
    assert calls[0][2] == {"Authorization": "Bearer sk-or-1"}


def test_a_refusal_is_not_retried_but_a_rate_limit_is(monkeypatch):
    from litstorm import embedding

    calls = _service(monkeypatch, fail=401)
    with pytest.raises(embedding.EmbeddingError, match="401"):
        embedding.embed(["a"], CONFIG, "bad")
    assert len(calls) == 1
    calls = _service(monkeypatch, fail=429)
    with pytest.raises(embedding.EmbeddingError):
        embedding.embed(["a"], CONFIG, "k")
    assert len(calls) == embedding.TRIES


class _Outline:
    root = SimpleNamespace(section_name="Songkran")

    def get_first_level_section_names(self):
        return ["History", "Customs"]

    def get_outline_as_list(self, root_section_name, add_hashtags):
        return [root_section_name, f"{root_section_name} today"]


def _table():
    info = SimpleNamespace(snippets=["water festival", "new year"])
    return SimpleNamespace(url_to_info={"https://a.test": info})


def _run(provider="openrouter"):
    config = SimpleNamespace(embedding={**CONFIG, "provider": provider}, request_timeout=5)
    notes = []
    progress = SimpleNamespace(note=lambda kind, **d: notes.append((kind, d)))
    return config, SimpleNamespace(embedding_api_key="sk-or-1"), progress, notes


def test_the_article_stage_gets_every_vector_up_front(monkeypatch):
    from litstorm.engines.storm import encoders

    calls = _service(monkeypatch)
    table = _table()
    config, secrets, progress, notes = _run()
    encoders.attach(table, _Outline(), config, secrets, progress)
    assert len(calls) == 1  # snippets and outline lines, one batch
    assert table.encoder.encode("History").shape == (2,)
    assert table.encoder.encode(["water festival", "new year"]).shape == (2, 2)
    assert len(calls) == 1  # both answered from what was fetched
    assert notes[0][0] == "embedding" and notes[0][1]["fallback"] is False and notes[0][1]["texts"] == 6


def test_a_failing_service_falls_back_to_the_built_in_model(monkeypatch):
    from litstorm.engines.storm import encoders

    _service(monkeypatch, fail=500)
    table = _table()
    config, secrets, progress, notes = _run()
    encoders.attach(table, _Outline(), config, secrets, progress)
    assert not hasattr(table, "encoder")  # STORM loads its own for all of them
    assert notes[0][1]["fallback"] is True and "500" in notes[0][1]["message"]


def test_built_in_asks_nothing(monkeypatch):
    from litstorm.engines.storm import encoders

    calls = _service(monkeypatch)
    table = _table()
    config, secrets, progress, notes = _run(provider="builtin")
    encoders.attach(table, _Outline(), config, secrets, progress)
    assert not calls and not notes and not hasattr(table, "encoder")


def test_encoded_vectors_are_what_storm_compares(monkeypatch):
    """The table's own retrieval works on what the encoder gives back."""
    from litstorm.engines.storm import encoders

    _service(monkeypatch)
    enc = encoders.ApiEncoder(CONFIG, "k", 5)
    matrix = enc.encode(["a", "bbb"])
    assert isinstance(matrix, np.ndarray) and matrix.dtype == np.float32


# --- the setting and the Run ------------------------------------------------------


@pytest.mark.db
def test_the_setting_is_checked_and_a_run_keeps_it_without_the_key(admin, browser, configured, db):
    from litstorm.db.models import Run

    assert admin.get("/api/admin/embedding").json()["provider"] == "builtin"
    assert admin.put("/api/admin/embedding", json={"provider": "openrouter"}).json()["detail"] == "model_required"
    r = admin.put("/api/admin/embedding", json={"provider": "openai-compatible", "model": "bge-m3"})
    assert r.json()["detail"] == "api_base_required"
    r = admin.put("/api/admin/embedding", json={"provider": "openrouter", "model": " baai/bge-m3 "})
    assert r.status_code == 200 and r.json()["has_key"] is True
    assert r.json()["resolved_base"] == "https://openrouter.ai/api/v1"

    user = make_user(admin, browser)
    run = user.post("/api/sessions", json={"topic": "Songkran", "language": "th"}).json()["runs"][0]
    db.expire_all()
    kept = db.get(Run, run["id"]).config["embedding"]
    assert kept == {"provider": "openrouter", "model": "baai/bge-m3", "api_base": "https://openrouter.ai/api/v1"}
    assert "sk-test" not in str(kept)


@pytest.mark.db
def test_the_worker_hands_the_run_its_providers_key(admin, browser, configured, db):
    from litstorm import db as db_mod
    from litstorm.worker import queue

    admin.put("/api/admin/embedding", json={"provider": "openrouter", "model": "baai/bge-m3"})
    user = make_user(admin, browser)
    user.post("/api/sessions", json={"topic": "Songkran", "language": "th"})
    with db_mod.sessions()() as s:
        claim = queue.claim(s)
    assert claim.config.embedding["model"] == "baai/bge-m3"
    assert claim.secrets.embedding_api_key == "sk-test-0000"


@pytest.mark.db
def test_a_stored_key_is_not_sent_to_another_address(admin, browser, configured, db):
    """Ollama on this machine needs no key; the openai-compatible key stored
    for some other server must not go to it."""
    from litstorm import db as db_mod
    from litstorm.worker import queue

    admin.put("/api/admin/llm-credentials/openai-compatible",
              json={"api_key": "sk-other-server", "api_base": "https://llm.example.org/v1"})
    r = admin.put("/api/admin/embedding", json={"provider": "openai-compatible", "model": "bge-m3",
                                                "api_base": "http://host.docker.internal:11434/v1"})
    assert r.json()["has_key"] is False
    user = make_user(admin, browser)
    user.post("/api/sessions", json={"topic": "Songkran", "language": "th"})
    with db_mod.sessions()() as s:
        claim = queue.claim(s)
    assert claim.config.embedding["api_base"] == "http://host.docker.internal:11434/v1"
    assert claim.secrets.embedding_api_key == ""


@pytest.mark.db
def test_the_test_button_tries_the_form(admin, monkeypatch):
    calls = _service(monkeypatch)
    r = admin.post("/api/admin/embedding/check", json={"provider": "builtin"}).json()
    assert r["ok"] and not calls
    r = admin.post("/api/admin/embedding/check",
                   json={"provider": "openai-compatible", "model": "bge-m3", "api_base": "http://ollama.test/v1"}).json()
    assert r["ok"] and r["message"] == "2 dimensions"
    assert calls[0][0] == "http://ollama.test/v1/embeddings"
