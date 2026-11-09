"""Question refinement: before a Run, a few questions that make the topic
clearer (docs/web-app-design.md, ขัดเกลาโจทย์). The owner answers or skips
them; the answers travel with the Run and steer its research.

One small call to the owner's chosen model, from the API: no Worker, no
quota, a daily cap instead.
"""

import json
import re

from litstorm.catalog import LLM_PROVIDERS, reasoning_kwargs, routing_kwargs

TIMEOUT = 60
MAX_QUESTIONS = 5

PROMPT = """Someone is about to start a long, automatic research run on the topic below. \
Before it starts, ask them 3 to 5 short questions whose answers would most change what the \
report should cover: its scope, angle, audience, period or place, or what they already know. \
Do not ask what the topic already says. Write the questions in {language}.

Topic: {topic}

Answer with a JSON array of strings and nothing else."""

LANGUAGE = {"th": "Thai", "en": "English"}


class RefineError(RuntimeError):
    """The model could not be asked, or said nothing usable."""


def questions(model, api_key, api_base, topic, language):
    import litellm

    if not api_key:
        raise RefineError("no API key stored for this model's provider")
    kwargs = {"api_key": api_key, "timeout": TIMEOUT, "num_retries": 1}
    if api_base:
        kwargs["api_base"] = api_base
    kwargs.update(reasoning_kwargs(model.reasoning, model.provider))
    kwargs.update(routing_kwargs(model.provider, kwargs))
    try:
        response = litellm.completion(
            model=LLM_PROVIDERS[model.provider]["prefix"] + model.model,
            messages=[{"role": "user", "content": PROMPT.format(language=LANGUAGE.get(language, "English"), topic=topic)}],
            max_tokens=max(800, (model.max_tokens or {}).get("conversation", 0)),
            drop_params=True,
            **kwargs,
        )
    except Exception as error:  # noqa: BLE001 - the owner can still start without it
        raise RefineError(f"{type(error).__name__}: {error}"[:300]) from error
    found = parse(response.choices[0].message.content or "")
    if not found:
        raise RefineError("the model gave no questions")
    return found


def parse(text):
    """The questions in a reply: a JSON array if there is one, else one per line."""
    match = re.search(r"\[.*\]", text, re.S)
    items = []
    if match:
        try:
            items = [str(x) for x in json.loads(match.group(0)) if str(x).strip()]
        except ValueError:
            items = []
    if not items:
        items = [re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line) for line in text.splitlines()]
    return [q.strip().strip('"').strip() for q in items if q.strip()][:MAX_QUESTIONS]


def focus(refinement):
    """The answered questions as one line for the research prompts, or ""."""
    parts = [f"{qa['question'].strip()} {qa['answer'].strip()}" for qa in refinement or [] if qa.get("answer", "").strip()]
    return "; ".join(parts)
