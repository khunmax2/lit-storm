"""Agent Research tells its loop's steps as "flow" notes (engines/agent/flow.py)."""

import asyncio
from types import SimpleNamespace

import pytest

NAMES = ("run", "_generate_observations", "_evaluate_gaps", "_select_agents", "_execute_tools", "_create_final_report")


class Progress:
    def __init__(self):
        self.notes = []

    def note(self, kind, **data):
        self.notes.append((kind, data))


@pytest.fixture
def researcher(monkeypatch):
    """The library's IterativeResearcher with its agents stubbed out, and
    every method the hook patches put back afterwards."""
    from deep_researcher.iterative_research import IterativeResearcher as R

    for name in NAMES:
        monkeypatch.setattr(R, name, getattr(R, name))

    async def observe(self, query, background_context=""):
        return "I need to   look at sources.\nFirst policy."

    async def evaluate(self, query, background_context=""):
        return SimpleNamespace(research_complete=self.iteration >= 2, outstanding_gaps=[f"Gap {self.iteration}"])

    async def select(self, gap, query, background_context=""):
        return SimpleNamespace(tasks=[
            SimpleNamespace(agent="WebSearchAgent", query="Thailand PM2.5 policy", entity_website=None),
            SimpleNamespace(agent="SiteCrawlerAgent", query="PCD actions", entity_website="pcd.go.th"),
        ])

    async def execute(self, tasks):
        return {"a": SimpleNamespace(sources=["https://a.test", "https://b.test"]),
                "b": SimpleNamespace(sources=["https://b.test"])}

    async def write(self, query, length="", instructions=""):
        return "# Report"

    async def run(self, query, output_length="", output_instructions="", background_context=""):
        # The library's loop, without its agents.
        while True:
            self.iteration += 1
            await self._generate_observations(query)
            gaps = await self._evaluate_gaps(query)
            if gaps.research_complete:
                break
            plan = await self._select_agents(gaps.outstanding_gaps[0], query)
            await self._execute_tools(plan.tasks)
        return await self._create_final_report(query)

    for name, fn in zip(NAMES, (run, observe, evaluate, select, execute, write)):
        monkeypatch.setattr(R, name, fn)

    def make():
        r = R.__new__(R)
        r.iteration, r.max_iterations = 0, 4
        return r

    return make


def test_an_iterative_run_tells_each_step_in_the_main_lane(researcher):
    from litstorm.engines.agent import flow

    progress = Progress()
    flow.hook(progress)
    assert asyncio.run(researcher().run("PM2.5 in Thai cities")) == "# Report"

    events = [d for kind, d in progress.notes if kind == "flow"]
    assert [e["event"] for e in events] == [
        "round", "phase", "observed", "phase", "gap", "phase", "tasks", "phase", "found",
        "round", "phase", "observed", "phase", "gap",
        "write",
    ]
    assert {e["lane"] for e in events} == {"main"}
    assert events[0] == {"event": "round", "lane": "main", "round": 1, "max": 4}
    assert events[2]["text"] == "I need to look at sources. First policy."  # whitespace folded
    assert events[4] == {"event": "gap", "lane": "main", "round": 1, "gap": "Gap 1", "complete": False}
    assert events[6]["queries"] == [
        {"agent": "search", "query": "Thailand PM2.5 policy", "site": None},
        {"agent": "crawl", "query": "PCD actions", "site": "pcd.go.th"},
    ]
    assert events[8] == {"event": "found", "lane": "main", "round": 1, "sources": 2,
                         "urls": ["https://a.test", "https://b.test"]}
    assert events[13]["complete"] is True


def test_the_deep_level_puts_each_section_in_its_own_lane(researcher):
    from litstorm.engines.agent import flow

    progress = Progress()
    f = flow.hook(progress)
    plan = SimpleNamespace(report_outline=[
        SimpleNamespace(title="Sources", key_question="Where does PM2.5 come from?"),
        SimpleNamespace(title="Policy", key_question="What do cities do?"),
    ])
    f.plan(plan)

    async def both():
        await asyncio.gather(*(researcher().run(s.key_question) for s in plan.report_outline))

    asyncio.run(both())
    events = [d for kind, d in progress.notes if kind == "flow"]
    assert events[0] == {"event": "plan", "sections": [{"id": "s1", "title": "Sources"}, {"id": "s2", "title": "Policy"}]}
    assert {e["lane"] for e in events[1:]} == {"s1", "s2"}
    assert [e["event"] for e in events if e.get("lane") == "s2"][-1] == "write"
