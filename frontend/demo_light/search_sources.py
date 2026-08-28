"""Which search engine STORM researches with, and the keys it needs.

STORM ships seven retrieval classes but takes exactly one at a time, so this
is a choice rather than a set of switches.

Keys are kept in a file beside secrets.toml, not in the database. The app
talks to Supabase as the signed-in user, so anything a member's session can
read, that member can read — and every member has to be able to search. A
search key in a table would therefore be a search key every account can pull
out. On disk it stays with the deployment, where the model keys already are.
"""

import json
import os

import auth

SETTINGS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".streamlit", "search_sources.json"
)

# Everything knowledge_storm/rm.py offers, and what it takes to run it.
#   key      the secret it needs, or None when it needs none
#   builder  how to construct it, given (key, k)
#   note     why it is not offered, when it is not
SOURCES = {
    "duckduckgo": {
        "label": "DuckDuckGo",
        "key": None,
        "free": True,
        "signup": "",
    },
    "tavily": {
        "label": "Tavily",
        "key": "TAVILY_API_KEY",
        "free": False,
        "signup": "https://app.tavily.com/home",
    },
    "serper": {
        "label": "Serper (Google)",
        "key": "SERPER_API_KEY",
        "free": False,
        "signup": "https://serper.dev/api-key",
    },
    "brave": {
        "label": "Brave Search",
        "key": "BRAVE_API_KEY",
        "free": False,
        "signup": "https://brave.com/search/api/",
    },
    "you": {
        "label": "You.com",
        "key": "YDC_API_KEY",
        "free": False,
        "signup": "https://api.you.com/",
    },
    # Present in the library, not offerable from here.
    "arxiv": {
        "label": "arXiv (Stanford Oval)",
        "key": None,
        "free": True,
        "unavailable": "needs_endpoint",
    },
    "vector": {
        "label": "Your own documents",
        "key": None,
        "free": True,
        "unavailable": "needs_collection",
    },
}

OFFERED = [name for name, s in SOURCES.items() if "unavailable" not in s]
DEFAULT = "duckduckgo"


def load():
    """The saved choice and keys. Never leaves the server."""
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as handle:
            saved = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        saved = {}
    if saved.get("source") not in OFFERED:
        saved["source"] = DEFAULT
    saved.setdefault("keys", {})
    return saved


def save(source, keys):
    """Write the choice and any keys given. A blank key leaves the old one."""
    current = load()
    merged = dict(current["keys"])
    for name, value in keys.items():
        value = (value or "").strip()
        if value:
            merged[name] = value
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as handle:
        json.dump({"source": source, "keys": merged}, handle, indent=2)
    os.chmod(SETTINGS_PATH, 0o600)


def forget(key_name):
    """Drop one key."""
    current = load()
    current["keys"].pop(key_name, None)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as handle:
        json.dump(current, handle, indent=2)
    os.chmod(SETTINGS_PATH, 0o600)


def secret_for(source_name):
    """The key a source will be given: the saved one, else the environment.

    secrets.toml still wins nothing here — it is read as a fallback, so a
    deployment that already sets the key in the environment keeps working
    without anyone opening this page.
    """
    key_name = SOURCES[source_name]["key"]
    if not key_name:
        return None
    return load()["keys"].get(key_name) or auth.setting(key_name)


def hint(source_name):
    """(is set, last four) for showing a key without showing it."""
    value = secret_for(source_name)
    if not value:
        return False, ""
    return True, value[-4:]


class SearchConfigError(RuntimeError):
    """The chosen source cannot be built with what it has been given."""


def _construct(name, secret, k):
    """The retriever for one source, built from an explicit key.

    Nothing is read from disk here, so a key can be tried before it is saved.
    """
    from knowledge_storm.rm import (
        BraveRM,
        DuckDuckGoSearchRM,
        SerperRM,
        TavilySearchRM,
        YouRM,
    )

    source = SOURCES[name]
    if "unavailable" in source:
        raise SearchConfigError(source["unavailable"])
    if source["key"] and not secret:
        raise SearchConfigError(f"{source['label']} needs {source['key']}.")

    if name == "duckduckgo":
        return DuckDuckGoSearchRM(k=k, safe_search="On", region="us-en")
    if name == "tavily":
        # Tavily can return the page itself, which saves STORM fetching it.
        return TavilySearchRM(
            tavily_search_api_key=secret, k=k, include_raw_content=True
        )
    if name == "serper":
        return SerperRM(
            serper_search_api_key=secret,
            query_params={"autocorrect": True, "num": k},
        )
    if name == "brave":
        return BraveRM(brave_search_api_key=secret, k=k)
    if name == "you":
        return YouRM(ydc_api_key=secret, k=k)
    raise SearchConfigError(f"{name} cannot be built from this page.")


def build(k=3):
    """The retriever STORM should research with, from what is saved."""
    name = load()["source"]
    return _construct(name, secret_for(name), k)


def check(source_name, secret=None, query="Songkran festival traditions"):
    """Run one real search against a source. Returns (ok, message, urls).

    `secret` lets a key be tried before it is saved; without one the saved
    key, or the environment's, is used.
    """
    if "unavailable" in SOURCES[source_name]:
        return False, SOURCES[source_name]["unavailable"], []
    try:
        rm = _construct(source_name, secret or secret_for(source_name), k=3)
        results = rm.forward(query, exclude_urls=[])
    except SearchConfigError as error:
        return False, str(error), []
    except Exception as error:  # noqa: BLE001 - any provider, any failure
        return False, f"{type(error).__name__}: {error}", []

    urls = [r.get("url", "") for r in results or [] if r.get("url")]
    if not urls:
        return False, "no_results", []
    return True, "", urls
