"""STORM as an Engine: research, outline, article, polish — one Run at a time.

The stages are called one by one rather than through STORMWikiRunner.run(),
so the Run can stop between them (docs/adr/0003). Each stage is wrapped by
knowledge_storm to record its tokens and search queries, which are reported
as the stage ends so a Run that fails later still has its cost on record.
"""

import os
import time

from knowledge_storm.storm_wiki.engine import (
    STORMWikiLMConfigs,
    STORMWikiRunner,
    STORMWikiRunnerArguments,
)
from knowledge_storm.storm_wiki.modules.callback import BaseCallbackHandler

from litstorm import outcomes, search_cache
from litstorm.engines.base import EngineFailure

from . import encoders, language, normalize, providers

# Settings an Administrator can change for every Run (docs/web-app-design.md,
# ค่าที่ผู้ใช้เลือกได้ต่อ Run). Owners do not see these.
DEFAULT_PARAMS = {
    "max_conv_turn": 3,
    "max_perspective": 3,
    "max_search_queries_per_turn": 3,
    "search_top_k": 3,
    "retrieve_top_k": 3,
    "max_thread_num": 4,
    "max_tokens": providers.DEFAULT_MAX_TOKENS,
}

STAGES = ("research", "outline", "article", "polish")

# How much of the depth level's time target research may use before its
# conversations stop asking; the rest is for writing.
GATHER_SHARE = 0.8

# Where each stage's cost is filed by knowledge_storm's decorator.
_METHOD = {
    "research": "run_knowledge_curation_module",
    "outline": "run_outline_generation_module",
    "article": "run_article_generation_module",
    "polish": "run_article_polishing_module",
}


class _ProgressCallbacks(BaseCallbackHandler):
    """Forward STORM's own callbacks as notes. Called from STORM's threads."""

    def __init__(self, progress):
        self.progress = progress

    def on_identify_perspective_end(self, perspectives, **kwargs):
        self.progress.note("perspectives", perspectives=list(perspectives))

    def on_dialogue_turn_end(self, dlg_turn, **kwargs):
        urls = sorted({r.url for r in dlg_turn.search_results})
        if urls:
            self.progress.note("browsed", urls=urls)


def _params(config):
    params = {**DEFAULT_PARAMS, **config.params}
    params["max_tokens"] = {**DEFAULT_PARAMS["max_tokens"], **params.get("max_tokens", {})}
    return params


def build_runner(config, secrets, output_dir):
    params = _params(config)
    try:
        # Research's many short calls go to the fast model when the Run has
        # one, with that model's own reply budget (docs/adr/0006).
        if config.fast_llm:
            fast = {k: v for k, v in config.fast_llm.items() if k not in ("id", "max_tokens")}
            budget = (config.fast_llm.get("max_tokens") or {}).get("conversation") or params["max_tokens"]["conversation"]
            talk = providers.build_lm(fast, secrets.fast_llm_api_key, budget, config.request_timeout)
        else:
            talk = providers.build_lm(
                config.llm,
                secrets.llm_api_key,
                params["max_tokens"]["conversation"],
                config.request_timeout,
            )
        write = providers.build_lm(
            config.llm,
            secrets.llm_api_key,
            params["max_tokens"]["writing"],
            config.request_timeout,
        )
        rm = providers.build_rm(
            config.search,
            secrets.search_api_key,
            params["search_top_k"],
            config.request_timeout,
        )
    except providers.ProviderConfigError as error:
        raise EngineFailure(outcomes.BAD_CONFIGURATION, str(error)) from error
    if config.search_cache_dir:
        rm = search_cache.CachedRM(
            rm, config.search_cache_dir, search_cache.identity(config.search, params["search_top_k"])
        )

    # The owner's model writes; research talks with the fast model if the
    # Run has one, else the owner's model with a smaller reply budget.
    lm_configs = STORMWikiLMConfigs()
    lm_configs.set_conv_simulator_lm(talk)
    lm_configs.set_question_asker_lm(talk)
    lm_configs.set_outline_gen_lm(write)
    lm_configs.set_article_gen_lm(write)
    lm_configs.set_article_polish_lm(write)

    args = STORMWikiRunnerArguments(
        output_dir=output_dir,
        max_conv_turn=params["max_conv_turn"],
        max_perspective=params["max_perspective"],
        max_search_queries_per_turn=params["max_search_queries_per_turn"],
        search_top_k=params["search_top_k"],
        retrieve_top_k=params["retrieve_top_k"],
        max_thread_num=params["max_thread_num"],
    )
    return STORMWikiRunner(args, lm_configs, rm)


class StormEngine:
    name = "storm"

    def run(self, config, secrets, workspace, progress, cancel):
        started = time.time()
        language.apply(config.language)
        output_dir = os.path.join(workspace, "storm")
        runner = build_runner(config, secrets, output_dir)

        # What STORMWikiRunner.run() sets up before its first stage. The
        # directory is fixed rather than named after the topic: the Run, not
        # the topic, is what a Run's files belong to.
        runner.topic = config.topic
        runner.article_dir_name = "article"
        runner.article_output_dir = os.path.join(output_dir, "article")
        os.makedirs(runner.article_output_dir, exist_ok=True)

        callbacks = _ProgressCallbacks(progress)
        conversations = runner.storm_knowledge_curation_module.conv_simulator
        if config.target_seconds:
            conversations.stop_at = started + GATHER_SHARE * config.target_seconds

        def stage(name, call):
            cancel.check()
            progress.stage(name)
            try:
                result = call()
            except BaseException:
                # knowledge_storm files a stage's cost only when it returns;
                # what a failed stage spent is still on the counters.
                progress.usage(
                    name,
                    llm=runner.lm_configs.collect_and_reset_lm_usage(),
                    search=runner.retriever.collect_and_reset_rm_usage(),
                )
                raise
            method = _METHOD[name]
            progress.usage(
                name,
                llm=runner.lm_cost.get(method, {}),
                search=runner.rm_cost.get(method, {}),
            )
            return result

        try:
            table = stage(
                "research",
                lambda: runner.run_knowledge_curation_module(callback_handler=callbacks),
            )
            cache = runner.retriever.rm
            if isinstance(cache, search_cache.CachedRM) and cache.hits:
                progress.note("search_cache", hits=cache.hits, misses=cache.misses)
            if conversations.cut_short:
                progress.note(
                    "research_cut_short",
                    conversations=conversations.cut_short,
                    seconds=round(time.time() - started),
                )
            # Research that found nothing: STORM would go on and crash while
            # ranking an empty table ("Expected 2D array"), after spending
            # on the outline. Stop here and say what happened.
            if not table.url_to_info:
                rm = runner.retriever.rm
                if getattr(rm, "refused", 0):
                    # Not an empty topic: the Search Provider said no, and
                    # kept saying it after retrying.
                    raise EngineFailure(
                        outcomes.RETRIES_EXHAUSTED,
                        f"the search provider refused {rm.refused} searches ({rm.last_refusal})",
                    )
                raise EngineFailure(outcomes.EMPTY_REPORT, "the research found no sources for this topic")
            outline = stage(
                "outline",
                lambda: runner.run_outline_generation_module(
                    information_table=table, callback_handler=callbacks
                ),
            )
            # What STORM writes is decided here; see clean_outline.
            if normalize.clean_outline(outline, config.topic):
                outline.dump_outline_to_file(
                    os.path.join(runner.article_output_dir, "storm_gen_outline.txt")
                )
            def write():
                encoders.attach(table, outline, config, secrets, progress)
                return runner.run_article_generation_module(
                    outline=outline, information_table=table, callback_handler=callbacks
                )

            draft = stage("article", write)
            polished = stage(
                "polish",
                lambda: runner.run_article_polishing_module(
                    draft_article=draft, remove_duplicate=False
                ),
            )
            # Polishing puts the lead first and renumbers every citation,
            # but STORM only rewrites the text: url_to_info.json keeps the
            # draft's numbers, and read together they cite the wrong source.
            # The polished article object has the right ones; save those.
            polished.dump_reference_to_file(
                os.path.join(runner.article_output_dir, normalize.POLISHED_REFERENCES)
            )
        finally:
            # The call log and the redacted model settings, whatever happened.
            try:
                runner.post_run()
            except Exception:  # noqa: BLE001 - bookkeeping must not mask the real error
                pass

        progress.stage("normalize")
        report, dropped = normalize.normalize(
            runner.article_output_dir, config.topic, config.language
        )
        if dropped:
            progress.note("dropped_citations", count=dropped)
        return report
