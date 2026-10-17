"""Topic interpretation: what a Run makes of its topic before it researches
(docs/adr/0014; docs/web-app-design.md, การตีความหัวเรื่อง).

A topic as typed is often a few words. A Run's first stage asks the model
for research's short calls, once, how the topic should be read:

- as one clear research question;
- its scope, where the topic implies one (a period, a place, a population);
- what was assumed where the topic was open;
- search terms in English and in Thai: a Thai topic searched in English as
  well finds what Thai alone did not;
- what searching should leave out.

The owner's answers to the clarifying questions and the Project's search
scope go in with the topic, so the reading follows them. What comes back
steers the Engine through instructions.focus, beside those answers; the
report keeps the owner's topic as its title and shows the reading as its
method. Nothing waits on it: a model that cannot be asked, or says nothing
usable, leaves the Run to research the topic as typed.
"""

import json
import os
import re
from dataclasses import replace

from litstorm import refine
from litstorm.catalog import LLM_PROVIDERS, reasoning_kwargs, routing_kwargs

STAGE = "interpret"
TIMEOUT = 45  # seconds; the Run's own request timeout when shorter
MAX_TOKENS = 900
MAX_ITEMS = 6
MAX_ITEM = 160  # characters
MAX_QUESTION = 400
THAI = re.compile(r"[฀-๿]")
LANGUAGE = {"th": "Thai", "en": "English"}

PROMPT = """An automatic literature-research run is about to start on the topic below. \
Before it searches, say how the topic should be read.

Topic: {topic}
{notes}
Infer only what the topic and the notes support. Do not add a period, place, population or \
angle they do not imply; where the topic is open, keep the broad reading and say so as an \
assumption.

"exclude" lists only matter that shares words with the topic but is about something else (for \
"remote work": remote sensing, remote controls), or what the notes say to leave out. Never list \
the topic's own subject in another place, period, group or level (for "flood risk in Hat Yai": \
not "floods in other provinces"; for "tablets in Thai high schools": not "tablets in primary \
schools"): research from there still informs the topic, and the scope already says where the \
focus is. When unsure, leave it out; most topics need [].

Answer with one JSON object and nothing else:
{{
  "question": "the topic as one clear research question, in {language}",
  "scope": ["each period, place, population or field the topic implies, in {language}"],
  "assumptions": ["each thing you assumed where the topic was open, in {language}"],
  "keywords": {{"en": ["3 to 6 English search phrases"], "th": ["3 to 6 Thai search phrases"]}},
  "exclude": ["unrelated matter searching would wrongly pull in, in {language}"]
}}
Use [] for a list with nothing in it."""


def prompt(config):
    notes = []
    answers = refine.focus(config.refinement)
    if answers:
        notes.append(f"The owner's answers to clarifying questions: {answers}")
    scope = (config.instructions or {}).get("search_scope", "")
    if scope:
        notes.append(f"The owner's search scope for this project: {scope}")
    return PROMPT.format(
        topic=config.topic,
        notes="".join(f"{n}\n" for n in notes),
        language=LANGUAGE.get(config.language, "English"),
    )


def run(config, secrets, workspace, progress, cancel):
    """The Run's config with its topic's reading, or as it was if none came."""
    cancel.check()
    progress.stage(STAGE)
    llm = config.fast_llm or config.llm
    api_key = secrets.fast_llm_api_key if config.fast_llm else secrets.llm_api_key
    budget = (llm.get("max_tokens") or (config.params or {}).get("max_tokens") or {}).get("conversation") or 0
    try:
        text, used = _ask(llm, api_key, prompt(config), min(config.request_timeout, TIMEOUT), max(MAX_TOKENS, budget))
    except Exception as error:  # noqa: BLE001 - the Run researches the topic as typed
        progress.note("interpretation", failed=f"{type(error).__name__}: {error}"[:300])
        return config
    progress.usage(STAGE, llm={LLM_PROVIDERS[llm["provider"]]["prefix"] + llm["model"]: used}, search={})
    found = parse(text)
    if found is None:
        progress.note("interpretation", failed="the model's answer was not a reading of the topic")
        return config
    # English search terms always; Thai ones for a Thai report or topic, where
    # they find Thai sources, and not for an English one, where they would
    # pull Thai sources into an English report.
    found["searched"] = ["en", "th"] if config.language == "th" or THAI.search(config.topic) else ["en"]
    with open(os.path.join(workspace, "interpretation.json"), "w", encoding="utf-8") as f:
        json.dump(found, f, ensure_ascii=False, indent=2)
    progress.note("interpretation", **found)
    return replace(config, interpretation=found)


def _ask(llm, api_key, text, timeout, max_tokens):
    import litellm

    if llm.get("provider") not in LLM_PROVIDERS:
        raise ValueError(f"{llm.get('provider')!r} is not an LLM provider")
    if not api_key:
        raise ValueError("no API key stored for the model's provider")
    kwargs = {"api_key": api_key, "timeout": timeout, "num_retries": 1}
    if llm.get("api_base"):
        kwargs["api_base"] = llm["api_base"]
    kwargs.update(reasoning_kwargs(llm.get("reasoning"), llm["provider"]))
    kwargs.update(routing_kwargs(llm["provider"], kwargs))
    response = litellm.completion(
        model=LLM_PROVIDERS[llm["provider"]]["prefix"] + llm["model"],
        messages=[{"role": "user", "content": text}],
        max_tokens=max_tokens,
        drop_params=True,
        **kwargs,
    )
    usage = getattr(response, "usage", None)
    used = {
        "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
        "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
    }
    return response.choices[0].message.content or "", used


def parse(text):
    """The reading in a reply, cleaned and bounded; None without a question."""
    match = re.search(r"\{.*\}", text or "", re.S)
    if not match:
        return None
    try:
        raw = json.loads(match.group(0))
    except ValueError:
        return None
    if not isinstance(raw, dict):
        return None
    question = " ".join(str(raw.get("question") or "").split())[:MAX_QUESTION]
    if not question:
        return None
    keywords = raw.get("keywords") if isinstance(raw.get("keywords"), dict) else {}
    return {
        "question": question,
        "scope": _items(raw.get("scope")),
        "assumptions": _items(raw.get("assumptions")),
        "keywords": {"en": _items(keywords.get("en")), "th": _items(keywords.get("th"))},
        "exclude": _items(raw.get("exclude")),
    }


def _items(value):
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    kept = []
    for item in value:
        text = " ".join(str(item).split())[:MAX_ITEM] if isinstance(item, (str, int, float)) else ""
        if text and text.lower() not in {k.lower() for k in kept}:
            kept.append(text)
    return kept[:MAX_ITEMS]


def searched_terms(found):
    """The search terms the research was given, by language ("searched")."""
    keywords = found.get("keywords") or {}
    return {lang: list(keywords.get(lang) or []) for lang in found.get("searched") or ["en"] if keywords.get(lang)}


def focus(config):
    """The reading as one line for the research prompts, or ""."""
    found = config.interpretation or {}
    if not found.get("question"):
        return ""
    terms = [t for words in searched_terms(found).values() for t in words]
    parts = [f"research question: {found['question']}"]
    if found.get("scope"):
        parts.append("scope: " + ", ".join(found["scope"]))
    if terms:
        parts.append("search terms: " + ", ".join(terms))
    if found.get("exclude"):
        parts.append("leave out: " + ", ".join(found["exclude"]))
    return "; ".join(parts)
