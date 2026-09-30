"""Co-STORM as an Engine: one Turn of a Discussion per process.

A Discussion is a conversation that lasts as long as its owner likes, so it
cannot live in one process the way a Run does (docs/web-app-design.md,
รุ่นสอง: Discussion). Each Turn is its own job: it loads the state the
previous Turn left, does one thing, and leaves the new state beside it —

    start   the warm start: background research, experts, the first mind map
    say     the owner speaks, and the table answers
    step    the table goes on for one utterance
    auto    the table goes on for `steps` utterances, checking for a stop
            between them
    report  a report from the mind map, as a Run's report

A Turn that fails or is killed writes nothing over the previous state, so
the Discussion carries on from the last Turn that finished.

The state is `CoStormRunner.to_dict()`. Upstream's `from_dict` rebuilds its
models from OPENAI_API_TYPE (its own FIXME), which is wrong for any provider
here; `_restore` does what it does with the models this Turn was given.
"""

import json
import os
import re
import time

from knowledge_storm.collaborative_storm.engine import (
    CollaborativeStormLMConfigs,
    CoStormRunner,
    RunnerArgument,
)
from knowledge_storm.collaborative_storm.modules.callback import BaseCallbackHandler
from knowledge_storm.dataclass import ConversationTurn, KnowledgeBase
from knowledge_storm.logging_wrapper import LoggingWrapper

from litstorm import outcomes, search_cache
from litstorm.discussion import ACTIONS, STATE, VIEW
from litstorm.engines.base import EngineFailure
from litstorm.engines.storm import normalize, providers

from . import encoders, language

AUTO_STEPS = 3

# The Administrator's knobs; the depth level sets the warm start's.
DEFAULT_PARAMS = {
    "warmstart_max_num_experts": 3,
    "warmstart_max_turn_per_experts": 2,
    "max_search_queries_per_turn": 3,
    # The round table asks fewer questions than STORM but leans harder on
    # each answer, so each search brings back more (the Streamlit app's 5).
    "retrieve_top_k": 5,
    "max_thread_num": 4,
    "max_tokens": {"conversation": 500, "writing": 3000},
}


class _Callbacks(BaseCallbackHandler):
    """Co-STORM's own callbacks, as notes the owner sees while waiting."""

    def __init__(self, progress):
        self.progress = progress

    def on_warmstart_update(self, message, **kwargs):
        self.progress.note("warmup", message=str(message)[:300])

    def on_expert_information_collection_end(self, info, **kwargs):
        urls = sorted({i.url for i in info or []})
        if urls:
            self.progress.note("browsed", urls=urls)


def _params(config):
    params = {**DEFAULT_PARAMS, **config.params}
    params["max_tokens"] = {**DEFAULT_PARAMS["max_tokens"], **params.get("max_tokens", {})}
    return params


def build_runner(config, secrets, encoder, callbacks=None):
    """A CoStormRunner for this Turn's settings, before any state is loaded."""
    params = _params(config)
    try:
        # As STORM's (docs/adr/0006): the many short calls that steer the
        # table go to the fast model when there is one; what the reader
        # reads — answers, polished utterances, the mind map, the report —
        # is the owner's model.
        if config.fast_llm:
            fast_spec = {k: v for k, v in config.fast_llm.items() if k not in ("id", "max_tokens")}
            budget = (config.fast_llm.get("max_tokens") or {}).get("conversation") or params["max_tokens"]["conversation"]
            fast = providers.build_lm(fast_spec, secrets.fast_llm_api_key, budget, config.request_timeout)
        else:
            fast = providers.build_lm(
                config.llm, secrets.llm_api_key, params["max_tokens"]["conversation"], config.request_timeout
            )
        # 3000 rather than the paper's 1000: a reasoning model spends part of
        # the budget thinking, and at 1000 answers came back cut off (the
        # Streamlit app, measured on Gemini).
        strong = providers.build_lm(
            config.llm, secrets.llm_api_key, params["max_tokens"]["writing"], config.request_timeout
        )
        rm = providers.build_rm(config.search, secrets.search_api_key, params["retrieve_top_k"], config.request_timeout)
    except providers.ProviderConfigError as error:
        raise EngineFailure(outcomes.BAD_CONFIGURATION, str(error)) from error
    if config.search_cache_dir:
        rm = search_cache.CachedRM(
            rm, config.search_cache_dir, search_cache.identity(config.search, params["retrieve_top_k"])
        )

    lm_config = CollaborativeStormLMConfigs()
    lm_config.set_question_answering_lm(strong)
    lm_config.set_discourse_manage_lm(fast)
    lm_config.set_utterance_polishing_lm(strong)
    lm_config.set_warmstart_outline_gen_lm(fast)
    lm_config.set_question_asking_lm(fast)
    lm_config.set_knowledge_base_lm(strong)

    argument = RunnerArgument(
        topic=config.topic,
        retrieve_top_k=params["retrieve_top_k"],
        max_search_queries_per_turn=params["max_search_queries_per_turn"],
        warmstart_max_num_experts=params["warmstart_max_num_experts"],
        warmstart_max_turn_per_experts=params["warmstart_max_turn_per_experts"],
        max_thread_num=params["max_thread_num"],
    )
    # The runner makes its own Encoder from ENCODER_API_TYPE in __init__;
    # nothing can be handed in, so it is replaced everywhere it was given.
    os.environ.setdefault("ENCODER_API_TYPE", "ollama")  # only to get through __init__
    runner = CoStormRunner(
        lm_config=lm_config,
        runner_argument=argument,
        logging_wrapper=LoggingWrapper(lm_config),
        rm=rm,
        callback_handler=callbacks,
    )
    _use_encoder(runner, encoder)
    return runner


def _use_encoder(runner, encoder):
    runner.encoder = encoder
    runner.knowledge_base.encoder = encoder
    runner.knowledge_base.information_insert_module.encoder = encoder
    manager = runner.discourse_manager
    manager.encoder = encoder
    for agent in (manager.experts or []) + [manager.moderator, manager.pure_rag_agent, manager.general_knowledge_provider]:
        if agent is not None and hasattr(agent, "encoder"):
            agent.encoder = encoder


def _restore(runner, state):
    """What CoStormRunner.from_dict does, with this Turn's models."""
    runner.conversation_history = [ConversationTurn.from_dict(t) for t in state["conversation_history"]]
    runner.warmstart_conv_archive = [ConversationTurn.from_dict(t) for t in state.get("warmstart_conv_archive", [])]
    runner.discourse_manager.deserialize_experts(state["experts"])
    runner.knowledge_base = KnowledgeBase.from_dict(
        data=state["knowledge_base"],
        knowledge_base_lm=runner.lm_config.knowledge_base_lm,
        node_expansion_trigger_count=runner.runner_argument.node_expansion_trigger_count,
        encoder=runner.encoder,
    )
    _use_encoder(runner, runner.encoder)


def _state(runner):
    """to_dict() without the models' settings: those carry the API base and
    other provider details, and the next Turn builds its own."""
    state = runner.to_dict()
    state.pop("lm_config", None)
    return state


def _usage(runner, rm):
    """Tokens per model and searches since the last call, from the runner's
    log (each Co-STORM stage resets the models' own counters as it ends)."""
    llm = {}
    for stage in runner.dump_logging_and_reset().values():
        for per_model in (stage.get("lm_usage") or {}).values():
            for model, used in per_model.items():
                slot = llm.setdefault(model, {"prompt_tokens": 0, "completion_tokens": 0})
                slot["prompt_tokens"] += int(used.get("prompt_tokens", 0) or 0)
                slot["completion_tokens"] += int(used.get("completion_tokens", 0) or 0)
    search = rm.get_usage_and_reset() if hasattr(rm, "get_usage_and_reset") else {}
    return llm, search


# A run of asterisks opening a line: a bold marker the model started and
# never closed (the Streamlit app's clean_utterance).
_UNCLOSED_BOLD = re.compile(r"^\s*\*{2,}\s*", re.MULTILINE)


def clean(text):
    return _UNCLOSED_BOLD.sub("", text or "").strip()


def _tree(node):
    return {
        "name": node.name,
        "count": len(node.content),
        "children": [_tree(child) for child in node.children],
    }


def view(runner, warmstart_turns):
    """What the Discussion page shows, read off the runner: who said what,
    the mind map, and the sources the citation numbers point at."""
    from knowledge_storm.collaborative_storm.modules.warmstart_hierarchical_chat import question_only

    kb = runner.knowledge_base
    turns = []
    for i, turn in enumerate(runner.conversation_history):
        text = clean(turn.utterance)
        if i < warmstart_turns and turn.utterance_type == "Original Question":
            # Saved before the warm start's parsing was fixed: the question
            # may still carry the answer the next line gives.
            text = question_only(text)
        turns.append(
            {
                "role": turn.role,
                "role_description": (turn.role_description or "").strip(),
                "type": turn.utterance_type,
                "text": text,
                "cited": sorted(set(turn.get_all_citation_index())),
                "warmup": i < warmstart_turns,
            }
        )
    return {
        "topic": runner.runner_argument.topic,
        "turns": turns,
        "mind_map": [_tree(child) for child in kb.root.children],
        "sources": {
            str(uuid): {"url": info.url, "title": info.title, "snippets": info.snippets}
            for uuid, info in kb.info_uuid_to_info_dict.items()
        },
        "experts": [getattr(e, "role_name", str(e)) for e in runner.discourse_manager.experts or []],
    }


def _write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


def report_files(runner, text, directory):
    """Write the report as STORM's polished article and references, so one
    normalizer serves both (engines/storm/normalize.py).

    Co-STORM numbers every snippet, so one page can hold several numbers.
    Keyed by URL, all but one would cite nothing (the Streamlit app found six
    such on its first try): the lowest number speaks for its URL, and the
    page keeps every snippet cited under any of its numbers.
    """
    kb = runner.knowledge_base
    canonical, by_url = {}, {}
    for uuid in sorted(kb.info_uuid_to_info_dict):
        info = kb.info_uuid_to_info_dict[uuid]
        first = by_url.setdefault(info.url, uuid)
        canonical[uuid] = first
    text = re.sub(r"\[(\d+)\]", lambda m: f"[{canonical.get(int(m.group(1)), int(m.group(1)))}]", text or "")
    url_to_info = {}
    for uuid, info in sorted(kb.info_uuid_to_info_dict.items()):
        entry = url_to_info.setdefault(
            info.url, {"url": info.url, "title": info.title, "description": info.description or "", "snippets": []}
        )
        entry["snippets"].extend(s for s in info.snippets if s not in entry["snippets"])
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, "storm_gen_article_polished.txt"), "w", encoding="utf-8") as f:
        f.write(text)
    _write_json(
        os.path.join(directory, normalize.POLISHED_REFERENCES),
        {"url_to_unified_index": by_url, "url_to_info": url_to_info},
    )


def opens_with_introduction(text):
    """Whether the report's first section is an introduction, which
    `promote_lead` makes the lead."""
    for line in (text or "").splitlines():
        match = normalize.HEADING.match(line)
        if match:
            return normalize.is_lead_like(match.group(2))
        if line.strip():
            return False
    return False


def with_lead(runner, topic, text, progress):
    """The report with a lead written for it, as STORM's polish stage writes
    one, by the owner's model with STORM's own prompt (switched to the
    report's language with the rest). Co-STORM writes none, and a mind map
    that does not open with an introduction left the report without one —
    measured on the first English Discussion."""
    import dspy
    from knowledge_storm.storm_wiki.modules.article_polish import WriteLeadSection

    lm = runner.lm_config.utterance_polishing_lm
    with dspy.settings.context(lm=lm, show_guidelines=False):
        lead = dspy.Predict(WriteLeadSection)(topic=topic, draft_page=text).lead_section or ""
    progress.usage("report", llm=lm.get_usage_and_reset(), search={})
    lead = lead.split("The lead section:")[-1]
    # Prose only: a heading here would be taken for the report's first section.
    lead = "\n".join(line for line in lead.splitlines() if not normalize.HEADING.match(line)).strip()
    return f"# {normalize.LEAD_HEADING}\n\n{lead}\n\n{text}" if lead else text


def promote_lead(report):
    """Co-STORM writes no lead; its mind map usually opens with an
    introduction ("บทนำ", "Introduction"), which is the lead in all but name.
    Measured on the first Thai Discussion: an empty lead and "บทนำ" as the
    first section."""
    sections = report["sections"]
    if report["lead"] or not sections:
        return
    first = sections[0]
    if normalize.is_lead_like(first["heading"]) and not first["children"] and first["body"]:
        report["lead"] = first["body"]
        sections.pop(0)


class CoStormEngine:
    name = "co-storm"

    def run(self, config, secrets, workspace, progress, cancel):
        turn = config.discussion or {}
        action = turn.get("action")
        if action not in ACTIONS:
            raise EngineFailure(outcomes.BAD_CONFIGURATION, f"{action!r} is not a Turn: {ACTIONS}")
        if action != "start" and not turn.get("state_from"):
            raise EngineFailure(outcomes.BAD_CONFIGURATION, "this Turn has no Discussion to continue")

        language.apply(config.language)
        encoder = encoders.for_turn(config, secrets)
        runner = build_runner(config, secrets, encoder, _Callbacks(progress))
        rm = runner.rm
        warmstart_turns = 0
        if action != "start":
            with open(turn["state_from"], encoding="utf-8") as f:
                state = json.load(f)
            _restore(runner, state)
            warmstart_turns = state.get("warmstart_turns", 0)

        def stage(name, call):
            cancel.check()
            progress.stage(name)
            try:
                return call()
            finally:
                llm, search = _usage(runner, rm)
                progress.usage(name, llm=llm, search=search)

        report = None
        started = time.time()
        if action == "start":
            stage("warmup", runner.warm_start)
            warmstart_turns = len(runner.conversation_history)
            if not runner.knowledge_base.info_uuid_to_info_dict:
                if getattr(rm, "refused", 0):
                    raise EngineFailure(
                        outcomes.RETRIES_EXHAUSTED,
                        f"the search provider refused {rm.refused} searches ({rm.last_refusal})",
                    )
                raise EngineFailure(outcomes.EMPTY_REPORT, "the warm start found no sources for this topic")
        elif action == "say":
            text = (turn.get("text") or "").strip()
            if not text:
                raise EngineFailure(outcomes.BAD_CONFIGURATION, "nothing was said")
            # The owner's words go in as they are; the table then answers.
            runner.step(user_utterance=text)
            stage("discussion", runner.step)
        elif action in ("step", "auto"):
            steps = 1 if action == "step" else max(1, min(int(turn.get("steps") or AUTO_STEPS), 10))
            for _ in range(steps):
                stage("discussion", runner.step)
        else:
            text = stage("report", runner.generate_report)
            if not (text or "").strip():
                raise EngineFailure(outcomes.EMPTY_REPORT, "the mind map gave no report text")
            if not opens_with_introduction(text):
                text = with_lead(runner, config.topic, text, progress)
            directory = os.path.join(workspace, "report")
            report_files(runner, text, directory)
            report, dropped = normalize.normalize(directory, config.topic, config.language)
            report["engine"] = "co-storm"
            promote_lead(report)
            if dropped:
                progress.note("dropped_citations", count=dropped)

        if isinstance(rm, search_cache.CachedRM) and rm.hits:
            progress.note("search_cache", hits=rm.hits, misses=rm.misses)
        if encoder.fell_back:
            progress.note("embedding", fallback=True, provider=encoder.provider, message=encoder.fell_back)
        state = _state(runner)
        state["warmstart_turns"] = warmstart_turns
        _write_json(os.path.join(workspace, STATE), state)
        _write_json(os.path.join(workspace, VIEW), view(runner, warmstart_turns))
        progress.note("turn", action=action, seconds=round(time.time() - started, 1),
                      turns=len(runner.conversation_history))
        return report
