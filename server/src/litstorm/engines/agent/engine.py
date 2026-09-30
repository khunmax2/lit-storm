"""Agent Research (khunmax2/lit_agents-deep-research) as an Engine.

The library plans, searches and writes with agents on the OpenAI Agents SDK
(docs/web-app-design.md, รุ่นสอง: Agent Research): the fast and standard
levels run its IterativeResearcher, the deep level its DeepResearcher, which
researches each section of a plan side by side.

The library reads its settings from the environment when imported. Here the
models are built from the Run's settings and keys (never the environment),
and only the search service's address or key is put in this process's own
environment, where the library looks for it. The process is the Run's alone
(docs/adr/0003).

Its hooks, patched in this process only: every agent run is counted for
tokens; every search for searches, the pages it found (titles for the
report's sources) and progress; and the loop checks for a stop between
iterations.
"""

import asyncio
import os
import time

from litstorm import instructions, outcomes, sections
from litstorm.catalog import LLM_PROVIDERS, reasoning_kwargs, routing_kwargs
from litstorm.engines.base import EngineFailure

from . import normalize

# What the library's OpenAI-style client needs per provider; None: the SDK's own.
BASES = {
    "openrouter": "https://openrouter.ai/api/v1",
    "openai": None,
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "groq": "https://api.groq.com/openai/v1",
}
SEARCH = {"searxng": "searchxng", "tavily": "tavily"}

# Share of the level's time target the research loop may use before it
# writes. The deep level writes section by section, so it stops sooner.
GATHER_SHARE = {"iterative": 0.8, "deep": 0.6}

DEFAULTS = {"mode": "iterative", "max_iterations": 4}

LANGUAGE = {"th": "Thai", "en": "English"}


def _model(llm, api_key, timeout):
    from agents import ModelSettings, OpenAIChatCompletionsModel
    from openai import AsyncOpenAI

    provider = llm.get("provider", "")
    if provider not in LLM_PROVIDERS:
        raise EngineFailure(outcomes.BAD_CONFIGURATION, f"{provider!r} is not an LLM provider")
    base = llm.get("api_base") if provider == "openai-compatible" else BASES.get(provider)
    if provider == "openai-compatible" and not base:
        raise EngineFailure(outcomes.BAD_CONFIGURATION, "an OpenAI-compatible model needs an api_base")
    if not api_key:
        raise EngineFailure(outcomes.BAD_CONFIGURATION, f"no API key for {provider!r}")

    # The model's reasoning setting, as STORM sends it, carried in the body
    # of every request an agent makes.
    extra = dict(reasoning_kwargs(llm.get("reasoning"), provider))
    extra.update(routing_kwargs(provider, extra).get("extra_body", {}))
    ours = ModelSettings(extra_body=extra or None)

    class Settled(OpenAIChatCompletionsModel):
        async def get_response(self, system_instructions, input, model_settings, *args, **kwargs):
            return await super().get_response(system_instructions, input, ours.resolve(model_settings), *args, **kwargs)

        async def stream_response(self, system_instructions, input, model_settings, *args, **kwargs):
            async for event in super().stream_response(
                system_instructions, input, ours.resolve(model_settings), *args, **kwargs
            ):
                yield event

    client = AsyncOpenAI(api_key=api_key, base_url=base, timeout=timeout, max_retries=2)
    return Settled(model=llm["model"], openai_client=client)


class _Meter:
    """Tokens by model and searches by service, handed on stage by stage."""

    def __init__(self, names, search_name):
        self.names = names  # model id -> the name cost.estimate knows it by
        self.search_name = search_name
        self.tokens = {}
        self.searches = 0

    def add(self, model, usage):
        name = self.names.get(model, model)
        t = self.tokens.setdefault(name, {"prompt_tokens": 0, "completion_tokens": 0})
        t["prompt_tokens"] += int(getattr(usage, "input_tokens", 0) or 0)
        t["completion_tokens"] += int(getattr(usage, "output_tokens", 0) or 0)

    def flush(self, progress, stage):
        progress.usage(stage, llm=self.tokens, search={self.search_name: self.searches})
        self.tokens, self.searches = {}, 0


def planned_sections(planned, wanted, topic):
    """The deep researcher's plan held to the owner's headings: theirs, in
    their order, each keeping the key question the planner wrote for the
    section it matches; one it did not plan asks about the heading itself."""
    from deep_researcher.agents.planner_agent import ReportPlanSection

    out = []
    for heading, index in zip(wanted, sections.match(wanted, [s.title for s in planned])):
        question = planned[index].key_question if index is not None else f"{heading} ({topic})"
        out.append(ReportPlanSection(title=heading, key_question=question))
    return out


def _hook(meter, found, progress, cancel):
    """Patch the library, in this process, to report what it does."""
    from deep_researcher import iterative_research
    from deep_researcher.agents import baseclass
    from deep_researcher.tools import web_search

    run = baseclass.ResearchRunner.run.__func__

    async def counted_run(cls, *args, **kwargs):
        result = await run(cls, *args, **kwargs)
        agent = kwargs.get("starting_agent") or args[0]
        usage = getattr(getattr(result, "context_wrapper", None), "usage", None)
        if usage is not None:
            meter.add(getattr(agent.model, "model", str(agent.model)), usage)
        return result

    baseclass.ResearchRunner.run = classmethod(counted_run)

    for client in (web_search.SearchXNGClient, web_search.TavilyClient):
        search = client.search

        async def counted_search(self, query, *args, _search=search, **kwargs):
            meter.searches += 1
            return await _search(self, query, *args, **kwargs)

        client.search = counted_search

    scrape = web_search.scrape_urls

    async def recorded_scrape(items):
        for item in items:
            if item.url:
                found.setdefault(item.url, {"title": item.title, "description": item.description or ""})
        if items:
            progress.note("browsed", urls=sorted({i.url for i in items if i.url}))
        return await scrape(items)

    web_search.scrape_urls = recorded_scrape

    check = iterative_research.IterativeResearcher._check_constraints

    def stoppable(self):
        cancel.check()  # a stop asked for ends the Run between iterations
        return check(self)

    iterative_research.IterativeResearcher._check_constraints = stoppable


class AgentEngine:
    name = "agent"

    def run(self, config, secrets, workspace, progress, cancel):
        started = time.time()
        search = config.search
        kind = SEARCH.get(search.get("provider"))
        if kind is None:
            raise EngineFailure(outcomes.BAD_CONFIGURATION, f"Agent Research cannot search with {search.get('provider')!r}")
        # Where the library looks for its search service: this process only.
        if kind == "searchxng":
            os.environ["SEARCHXNG_HOST"] = search.get("endpoint", "")
            os.environ.pop("SEARCHXNG_ENGINES", None)
            if search.get("engines"):
                os.environ["SEARCHXNG_ENGINES"] = search["engines"]
        else:
            os.environ["TAVILY_API_KEY"] = secrets.search_api_key

        from agents import set_tracing_disabled
        from deep_researcher.deep_research import DeepResearcher
        from deep_researcher.iterative_research import IterativeResearcher
        from deep_researcher.llm_config import LLMConfig

        set_tracing_disabled(True)  # traces go to OpenAI; nothing leaves for them
        main = _model(config.llm, secrets.llm_api_key, config.request_timeout)
        fast = (
            _model(config.fast_llm, secrets.fast_llm_api_key, config.request_timeout)
            if config.fast_llm else main
        )
        llm_config = LLMConfig.__new__(LLMConfig)  # its __init__ reads the environment
        llm_config.search_provider = kind
        llm_config.reasoning_model, llm_config.main_model, llm_config.fast_model = main, main, fast

        names = {
            config.llm["model"]: LLM_PROVIDERS[config.llm["provider"]]["prefix"] + config.llm["model"],
        }
        if config.fast_llm:
            names[config.fast_llm["model"]] = LLM_PROVIDERS[config.fast_llm["provider"]]["prefix"] + config.fast_llm["model"]
        meter = _Meter(names, "SearXNG" if kind == "searchxng" else "Tavily")
        found = {}
        _hook(meter, found, progress, cancel)

        params = {**DEFAULTS, **(config.params or {})}
        mode = params.get("mode", "iterative")
        budget = (config.target_seconds or 300) * GATHER_SHARE.get(mode, 0.8) / 60
        language = LANGUAGE.get(config.language, "English")
        focus = instructions.focus(config)
        style = instructions.style(config)

        async def research():
            if mode == "deep":
                researcher = DeepResearcher(
                    max_iterations=int(params.get("max_iterations", 2)), max_time_minutes=budget,
                    verbose=False, config=llm_config,
                )
                plan, loops, write = (
                    researcher._build_report_plan, researcher._run_research_loops, researcher._create_final_report
                )

                async def staged_plan(query):
                    progress.stage("plan")
                    report_plan = await plan(query)
                    if config.sections:
                        report_plan.report_outline = planned_sections(report_plan.report_outline, config.sections, config.topic)
                    return report_plan

                async def staged_loops(report_plan):
                    meter.flush(progress, "plan")
                    progress.stage("research")
                    return await loops(report_plan)

                async def staged_write(*args, **kwargs):
                    meter.flush(progress, "research")
                    progress.stage("report")
                    return await write(*args, **kwargs)

                researcher._build_report_plan = staged_plan
                researcher._run_research_loops = staged_loops
                researcher._create_final_report = staged_write
                query = f"{config.topic}\n\nWrite the report in {language}."
                if focus:
                    query += f" Focus: {focus}"
                if style:
                    query += f"\n\nWriting style: {style}"
                if config.sections:
                    query += "\n\nThe report's sections, exactly these and in this order:\n" + "\n".join(
                        f"- {h}" for h in config.sections
                    )
                return await researcher.run(query)

            researcher = IterativeResearcher(
                max_iterations=int(params.get("max_iterations", 4)), max_time_minutes=budget,
                verbose=False, config=llm_config,
            )
            write = researcher._create_final_report

            async def staged_write(*args, **kwargs):
                meter.flush(progress, "research")
                progress.stage("report")
                return await write(*args, **kwargs)

            researcher._create_final_report = staged_write
            progress.stage("research")
            return await researcher.run(
                config.topic,
                output_instructions=f"Write the whole response in {language}, with headings (##) for its parts."
                + (f" Writing style: {style}" if style else ""),
                background_context=focus,
            )

        try:
            markdown = asyncio.run(research())
        finally:
            meter.flush(progress, "report")
        with open(os.path.join(workspace, "report.md"), "w", encoding="utf-8") as f:
            f.write(markdown or "")
        progress.note("elapsed", seconds=round(time.time() - started))

        progress.stage("normalize")
        report = normalize.normalize(markdown, config.topic, config.language, found)
        if not report["sources"]:
            raise EngineFailure(outcomes.EMPTY_REPORT, "the research found no sources it could cite")
        return report
