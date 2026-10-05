"""What Agent Research is doing, step by step, for the web app's flow canvas
(web: AgentFlowCanvas).

The library's loop (deep_researcher.iterative_research.IterativeResearcher)
goes round: observe what it knows, find the next knowledge gap, pick search
tasks for it, run them; until the gap agent says the research is complete or
it runs out of rounds or time; then it writes. The deep level first plans
sections and runs one such loop per section at once.

Each step is told as a "flow" note: the step itself, and what came of it,
in the words the agents used (English: their prompts are, and the owner
chose to keep it so, 2026-10-06). A note names its lane: "main", or the
section's id at the deep level.

    plan      sections [{id, title}]                     deep level only
    round     lane, round, max                           a round begins
    phase     lane, round, phase                         observe | gap | select | search
    observed  lane, round, text
    gap       lane, round, gap, complete
    tasks     lane, round, queries [{agent, query, site}]
    found     lane, round, sources, urls
    write     lane                                       the lane's writer
    compose                                              deep: all sections into one
"""

TEXT = 500  # characters of an agent's own words kept in a note
URLS = 8  # pages named per round; the count is of all of them


def _clip(text, n=TEXT):
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


class Flow:
    def __init__(self, progress):
        self.progress = progress
        self.lanes = {}  # a section's key question -> its lane

    def note(self, event, **data):
        self.progress.note("flow", event=event, **data)

    def plan(self, report_plan):
        sections = []
        for i, section in enumerate(report_plan.report_outline):
            lane = f"s{i + 1}"
            self.lanes[section.key_question] = lane
            sections.append({"id": lane, "title": _clip(section.title, 120)})
        self.note("plan", sections=sections)

    def lane_for(self, query):
        return self.lanes.get(query, "main")


def hook(progress):
    """Patch the loop, in this process, to tell its steps. Returns the Flow,
    whose `plan` the deep level calls once its sections are known."""
    from deep_researcher import iterative_research

    flow = Flow(progress)
    Researcher = iterative_research.IterativeResearcher

    def lane(self):
        return getattr(self, "_lit_lane", "main")

    run = Researcher.run

    async def run_in_lane(self, query, *args, **kwargs):
        self._lit_lane = flow.lane_for(query)
        return await run(self, query, *args, **kwargs)

    observe = Researcher._generate_observations

    async def observed(self, *args, **kwargs):
        flow.note("round", lane=lane(self), round=self.iteration, max=self.max_iterations)
        flow.note("phase", lane=lane(self), round=self.iteration, phase="observe")
        text = await observe(self, *args, **kwargs)
        flow.note("observed", lane=lane(self), round=self.iteration, text=_clip(text))
        return text

    evaluate = Researcher._evaluate_gaps

    async def evaluated(self, *args, **kwargs):
        flow.note("phase", lane=lane(self), round=self.iteration, phase="gap")
        result = await evaluate(self, *args, **kwargs)
        gaps = getattr(result, "outstanding_gaps", None) or []
        flow.note(
            "gap", lane=lane(self), round=self.iteration,
            gap=_clip(gaps[0], 300) if gaps else "", complete=bool(getattr(result, "research_complete", False)),
        )
        return result

    select = Researcher._select_agents

    async def selected(self, *args, **kwargs):
        flow.note("phase", lane=lane(self), round=self.iteration, phase="select")
        plan = await select(self, *args, **kwargs)
        queries = [
            {"agent": "crawl" if "Crawl" in (t.agent or "") else "search", "query": _clip(t.query, 200),
             "site": t.entity_website or None}
            for t in getattr(plan, "tasks", None) or []
        ]
        flow.note("tasks", lane=lane(self), round=self.iteration, queries=queries)
        return plan

    execute = Researcher._execute_tools

    async def executed(self, *args, **kwargs):
        flow.note("phase", lane=lane(self), round=self.iteration, phase="search")
        results = await execute(self, *args, **kwargs)
        urls = list(dict.fromkeys(u for r in (results or {}).values() for u in (getattr(r, "sources", None) or [])))
        flow.note("found", lane=lane(self), round=self.iteration, sources=len(urls), urls=urls[:URLS])
        return results

    write = Researcher._create_final_report

    async def written(self, *args, **kwargs):
        flow.note("write", lane=lane(self))
        return await write(self, *args, **kwargs)

    Researcher.run = run_in_lane
    Researcher._generate_observations = observed
    Researcher._evaluate_gaps = evaluated
    Researcher._select_agents = selected
    Researcher._execute_tools = executed
    Researcher._create_final_report = written
    return flow
