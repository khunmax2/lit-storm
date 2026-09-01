"""Co-STORM: the round table, wired to this deployment's settings.

STORM runs to completion on its own and hands back an article. Co-STORM keeps
a conversation going instead — several expert agents and a moderator talking
about the topic — and lets a person speak into it at any point, then writes
the report from whatever the table ended up covering.

The models come from the same two roles the rest of the app uses (see
``demo_util.lm_settings``), so a deployment configures its provider once. What
Co-STORM needs on top of that is an *embedding* model: every snippet it
collects is placed in a mind map by similarity, not by asking a model where it
goes. That is a second service, and a provider that resells chat completions
does not necessarily sell embeddings — hence `encoder_settings` below, and its
own error when the answer is "nowhere".
"""

import json
import os
import re

import auth
import dspy
import demo_util
import search_sources
from demo_util import LMConfigError

from knowledge_storm.collaborative_storm.modules.collaborative_storm_utils import (
    extract_and_remove_citations,
)
from knowledge_storm.collaborative_storm.engine import (
    CollaborativeStormLMConfigs,
    CoStormRunner,
    RunnerArgument,
)
from knowledge_storm.lm import LitellmModel
from knowledge_storm.logging_wrapper import LoggingWrapper
from knowledge_storm.utils import truncate_filename

# Embedding services this app knows how to reach, and the key each reads.
# The names are `knowledge_storm.encoder`'s own ENCODER_API_TYPE values.
ENCODERS = {
    "gemini": "GOOGLE_API_KEY",
    "openai": "OPENAI_API_KEY",
    "azure": "AZURE_API_KEY",
}


class EmptyReport(RuntimeError):
    """The mind map produced no report text.

    Not a crash: the report is written a section at a time, and a model that
    returns nothing for every section leaves an empty string behind. The
    discussion is untouched and can be asked again.
    """


# How many results each search brings back. STORM's page asks for 3; the round
# table asks fewer questions but leans harder on each answer, so it asks for
# more.
RETRIEVE_TOP_K = 5


def encoder_settings():
    """(service, key) for the embedding model, or raise `LMConfigError`.

    Defaults to the chat provider, because for Gemini and OpenAI the same key
    buys both. Providers that only resell chat completions — OpenRouter, Groq —
    have no embedding endpoint at all, so those deployments have to name a
    service of their own in ENCODER_PROVIDER.
    """
    name = (
        auth.setting("ENCODER_PROVIDER") or auth.setting("LLM_PROVIDER") or "gemini"
    ).strip().lower()
    if name not in ENCODERS:
        raise LMConfigError(
            f"{name!r} has no embedding model this app can call, and Co-STORM "
            "sorts every source it finds by similarity. Set ENCODER_PROVIDER "
            "to one of: " + ", ".join(sorted(ENCODERS))
        )
    key = auth.setting(ENCODERS[name])
    if not key:
        raise LMConfigError(
            f"{ENCODERS[name]} is missing, and embeddings are set to {name!r}, "
            "which reads its key from there."
        )
    return name, key


def _prepare_encoder():
    """Point `knowledge_storm.encoder.Encoder` at a model it can reach.

    The runner builds its own encoder from the environment, with no way to
    hand one in, so the choice is published there before it is constructed.
    """
    name, key = encoder_settings()
    os.environ["ENCODER_API_TYPE"] = name
    os.environ[ENCODERS[name]] = key


def build_runner(topic, callback_handler=None):
    """A `CoStormRunner` for `topic`, built from the current settings.

    Unlike `demo_util.set_storm_runner`, this is not cached: a runner carries
    one discussion and its mind map, so it belongs to the conversation on
    screen rather than to the session.
    """
    _prepare_encoder()

    (fast_model, fast_kwargs), (strong_model, strong_kwargs) = demo_util.lm_settings()
    # 3000 rather than the paper's 1000, because a reasoning model spends part
    # of this budget thinking before it writes a word — Gemini 3.6 Flash burns
    # about 600 tokens on that — and whatever is left is what the reader sees.
    # At 1000 the answers came back cut off mid-sentence, or empty.
    fast_lm = LitellmModel(model=fast_model, max_tokens=500, **fast_kwargs)
    strong_lm = LitellmModel(model=strong_model, max_tokens=3000, **strong_kwargs)

    lm_config = CollaborativeStormLMConfigs()
    lm_config.set_question_answering_lm(strong_lm)
    lm_config.set_discourse_manage_lm(fast_lm)
    lm_config.set_utterance_polishing_lm(strong_lm)
    lm_config.set_warmstart_outline_gen_lm(fast_lm)
    lm_config.set_question_asking_lm(fast_lm)
    lm_config.set_knowledge_base_lm(strong_lm)

    argument = RunnerArgument(topic=topic, retrieve_top_k=RETRIEVE_TOP_K)
    return CoStormRunner(
        lm_config=lm_config,
        runner_argument=argument,
        logging_wrapper=LoggingWrapper(lm_config),
        rm=search_sources.build(k=argument.retrieve_top_k),
        callback_handler=callback_handler,
    )


def citation_dict(runner):
    """{citation number: {url, title, snippets}} for everything collected.

    Co-STORM numbers its sources once, across the whole discussion, so the
    [1] in an expert's reply and the [1] in the finished report are the same
    source. This is that numbering, in the shape the article page already
    knows how to render.
    """
    return {
        index: {
            "url": info.url,
            "title": info.title,
            "snippets": info.snippets,
        }
        for index, info in runner.knowledge_base.info_uuid_to_info_dict.items()
    }


def mind_map(runner):
    """The mind map as an indented outline, with a count of sources per node.

    Read straight off the tree rather than asked for: `get_knowledge_base_summary`
    would write a nicer paragraph, but it spends a model call every time the
    page is drawn.
    """
    return runner.knowledge_base.get_node_hierarchy_string(
        include_indent=True,
        include_hash_tag=False,
        include_node_content_count=True,
    )


def save_report(runner, report, topic):
    """Write the discussion's report where the library will find it.

    The two filenames are STORM's, so a Co-STORM report opens on the same
    article page, with the same bibliography and the same downloads. The
    transcript is saved beside them under a name of its own — a round table is
    not the persona interviews the article page knows how to draw, and
    pretending otherwise would mislabel who said what.
    """
    if not (report or "").strip():
        # Checked here as well as by the caller: this is the function that
        # creates the folder, and a folder holding an empty article would
        # show up in the library as a run that had worked.
        raise EmptyReport("refusing to save an empty report")

    folder = truncate(topic)
    directory = os.path.join(demo_util.working_dir(), folder)
    os.makedirs(directory, exist_ok=True)

    with open(
        os.path.join(directory, "storm_gen_article_polished.txt"),
        "w",
        encoding="utf-8",
    ) as handle:
        handle.write(report)

    citations = citation_dict(runner)
    url_to_info = {
        "url_to_unified_index": {
            entry["url"]: index for index, entry in citations.items()
        },
        "url_to_info": {
            entry["url"]: {
                "url": entry["url"],
                "title": entry["title"],
                "snippets": entry["snippets"],
                "description": "",
            }
            for entry in citations.values()
        },
    }
    with open(
        os.path.join(directory, "url_to_info.json"), "w", encoding="utf-8"
    ) as handle:
        json.dump(url_to_info, handle, indent=2, ensure_ascii=False)

    with open(
        os.path.join(directory, "costorm_conversation.json"), "w", encoding="utf-8"
    ) as handle:
        json.dump(
            [turn.to_dict() for turn in runner.conversation_history],
            handle,
            indent=2,
            ensure_ascii=False,
        )
    return folder


def truncate(topic):
    """The folder name for `topic`, matching what the STORM page uses."""
    return truncate_filename(topic.replace(" ", "_").replace("/", "_"))


class SuggestFollowUps(dspy.Signature):
    """Suggest what a curious person would ask this round table next.

    You are given the topic, what the reader wants the discussion for, and the
    conversation so far. Propose three questions that would push the
    discussion somewhere it has not been yet.

    Each question must open a different line of enquiry — three rewordings of
    the same question are worth one question. Ask what a well-read outsider
    would ask: what has been asserted without evidence, what has been left
    out, who disagrees, what it would mean in practice.

    Output exactly three lines, one question per line. No numbering, no
    bullets, no preamble.
    """

    topic = dspy.InputField(prefix="Topic: ", format=str)
    intent = dspy.InputField(prefix="What the reader wants this for: ", format=str)
    conversation = dspy.InputField(prefix="The discussion so far:\n", format=str)
    language = dspy.InputField(prefix="Write the questions in this language: ")
    questions = dspy.OutputField(prefix="Three questions, one per line:\n", format=str)


def _recent_conversation(runner, turns=6):
    """The tail of the discussion, as plain speaker/utterance lines."""
    lines = []
    for turn in runner.conversation_history[-turns:]:
        text, _ = extract_and_remove_citations(turn.utterance)
        lines.append(f"{turn.role}: {text}")
    return "\n".join(lines)


def suggest_questions(runner, intent, language, wanted=3):
    """Questions the reader might put to the table next.

    One model call, not one per suggestion: asking three times over gives
    three rewordings of whatever the last speaker just said, and costs three
    times as much to do it. The fast model writes these — they are a page of
    prompts, not the research.
    """
    with dspy.settings.context(
        lm=runner.lm_config.question_asking_lm, show_guidelines=False
    ):
        raw = dspy.Predict(SuggestFollowUps)(
            topic=runner.runner_argument.topic,
            intent=intent or "no particular purpose given",
            conversation=_recent_conversation(runner),
            language=language,
        ).questions

    questions = []
    for line in (raw or "").splitlines():
        # Models number these however they like, whatever the prompt says.
        line = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
        if line and line not in questions:
            questions.append(line)
    return questions[:wanted]
