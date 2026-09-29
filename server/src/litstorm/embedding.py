"""The embedding service: turns text into vectors so STORM can pick, for each
section it writes, the collected snippets closest to that section.

One setting for the whole system, chosen by an Administrator (docs/web-app-
design.md, รุ่นสอง: บริการ embedding). "builtin" is the model STORM ships
with (paraphrase-MiniLM-L6-v2, English only, baked into the image). Every
other choice is an OpenAI-style /embeddings endpoint: OpenRouter, OpenAI,
Gemini, or any server that speaks the same API, such as Ollama.

Kept free of STORM and torch: the API imports it to test a setting, the
Run's process to call the service.
"""

import time
from concurrent.futures import ThreadPoolExecutor

import requests
from pydantic import BaseModel

from litstorm.db.models import SystemSetting

KEY = "embedding"
BUILTIN = "builtin"
BUILTIN_MODEL = "paraphrase-MiniLM-L6-v2"

# Where each provider's OpenAI-style API lives. None: the setting names it.
BASES = {
    "openrouter": "https://openrouter.ai/api/v1",
    "openai": "https://api.openai.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "openai-compatible": None,
}
PROVIDERS = (BUILTIN, *BASES)

BATCH = 16
PARALLEL = 8
# Long pages (Tavily's raw content) are cut before they are sent: the
# built-in model reads only the first 128 word pieces anyway, and an API
# refuses input past its window.
MAX_CHARS = 2000
TRIES = 3


class Embedding(BaseModel):
    provider: str = BUILTIN
    model: str = ""
    # Required for "openai-compatible"; otherwise the provider's own.
    api_base: str | None = None


class EmbeddingError(RuntimeError):
    """The service did not give back one vector per text."""


def load(session):
    row = session.get(SystemSetting, KEY)
    return Embedding(**(row.value if row else {}))


def save(session, value):
    row = session.get(SystemSetting, KEY) or SystemSetting(key=KEY)
    row.value = value.model_dump()
    session.add(row)


def problem(value, stored_base=None):
    """What is wrong with a setting, or None."""
    if value.provider not in PROVIDERS:
        return "unknown_provider"
    if value.provider == BUILTIN:
        return None
    if not value.model.strip():
        return "model_required"
    if not base_url(value, stored_base):
        return "api_base_required"
    return None


def base_url(value, stored_base=None):
    """The API base for a setting: its own, else the provider's, else the
    base stored with the provider's key."""
    return ((value.api_base or "").strip() or BASES.get(value.provider) or (stored_base or "").strip()).rstrip("/")


def key_for(value, credential):
    """The key to send, from the provider's stored LLM credential.

    A setting that names its own address for "openai-compatible" gets no
    key: the stored one belongs to whatever server the credential names, and
    is not sent anywhere else. Ollama needs none.
    """
    if value.provider == BUILTIN or credential is None:
        return ""
    if value.provider == "openai-compatible" and (value.api_base or "").strip():
        if (credential.api_base or "").strip().rstrip("/") != value.api_base.strip().rstrip("/"):
            return ""
    from litstorm import security

    return security.decrypt(credential.api_key_ciphertext)


def snapshot(value, credential=None):
    """What a Run keeps of the setting: never the key."""
    if value.provider == BUILTIN:
        return {"provider": BUILTIN, "model": BUILTIN_MODEL}
    stored = credential.api_base if credential else None
    return {"provider": value.provider, "model": value.model.strip(), "api_base": base_url(value, stored)}


def embed(texts, config, api_key, timeout=60.0):
    """(vectors, prompt tokens) for `texts`, in order, from an OpenAI-style
    /embeddings endpoint. Raises EmbeddingError when it cannot."""
    url = config["api_base"].rstrip("/") + "/embeddings"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def one(start):
        batch = [(t or " ")[:MAX_CHARS] for t in texts[start : start + BATCH]]
        body = _post(url, headers, {"model": config["model"], "input": batch}, timeout)
        data = sorted(body.get("data") or [], key=lambda d: d.get("index", 0))
        if len(data) != len(batch) or not all(d.get("embedding") for d in data):
            raise EmbeddingError(f"asked for {len(batch)} vectors, got {len(data)}")
        return [d["embedding"] for d in data], int((body.get("usage") or {}).get("prompt_tokens") or 0)

    # Small batches side by side: measured on OpenRouter, 136 texts took 6.1s
    # as three batches in turn and 2.7s as nine at once. A server that works
    # through them one by one (Ollama on one GPU) is no slower for it.
    with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
        answers = list(pool.map(one, range(0, len(texts), BATCH)))
    return [v for vectors, _ in answers for v in vectors], sum(tokens for _, tokens in answers)


def _post(url, headers, payload, timeout):
    last = None
    for attempt in range(TRIES):
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=timeout)
        except requests.RequestException as error:
            last = f"{type(error).__name__}: {error}"
        else:
            if r.status_code < 400:
                try:
                    return r.json()
                except ValueError:
                    raise EmbeddingError(f"{url} did not answer with JSON")
            last = f"{r.status_code}: {r.text[:200]}"
            # A bad key, an unknown model, a wrong address: trying again will
            # not fix them (docs/web-app-design.md, การ retry คำขอที่ล้มเหลว).
            if 400 <= r.status_code < 500 and r.status_code not in (408, 429):
                break
        if attempt + 1 < TRIES:
            time.sleep(2**attempt)
    raise EmbeddingError(last or "no answer")


def check(value, api_key, stored_base=None):
    """(ok, message, seconds) for one small real call, for the test button."""
    wrong = problem(value, stored_base)
    if wrong:
        return False, wrong, 0.0
    started = time.monotonic()
    if value.provider == BUILTIN:
        return True, f"{BUILTIN_MODEL} (built in)", 0.0
    config = snapshot(value)
    config["api_base"] = base_url(value, stored_base)
    try:
        vectors, _ = embed(["สงกรานต์ประเพณีไทย", "Songkran, the Thai New Year"], config, api_key, timeout=30)
    except EmbeddingError as error:
        return False, str(error)[:300], time.monotonic() - started
    return True, f"{len(vectors[0])} dimensions", time.monotonic() - started
