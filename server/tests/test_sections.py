"""The sections an owner wants (litstorm.sections): theirs at the top, in
their order, under their names; what goes under each is the Engine's."""

from types import SimpleNamespace

import pytest

from conftest import make_user
from test_api_runs import configured  # noqa: F401  (fixture)


def test_what_was_typed_becomes_headings():
    from litstorm import sections

    typed = ["# ประวัติ", "", "  - Customs ", "1. Economy", "customs", "2) ผลกระทบ"] + [f"S{i}" for i in range(20)]
    assert sections.clean(typed)[:4] == ["ประวัติ", "Customs", "Economy", "ผลกระทบ"]
    assert len(sections.clean(typed)) == sections.MAX_SECTIONS


def test_each_heading_finds_the_section_planned_for_it():
    from litstorm import sections

    planned = ["History and origins", "Economy", "Economic impact (2024)", "Water fights"]
    assert sections.match(["economy", "History", "Food", "Economic impact"], planned) == [1, 0, None, 2]


@pytest.mark.slow
def test_storm_writes_the_owners_sections_with_its_own_subsections():
    from knowledge_storm.interface import ArticleSectionNode

    from litstorm.engines.storm import normalize

    def node(name, *children):
        n = ArticleSectionNode(name)
        n.children = list(children)
        return n

    outline = SimpleNamespace(root=node("Songkran", node("History", node("Origins")), node("Tourism", node("Numbers")), node("Food")))
    normalize.use_sections(outline, ["Tourism", "ประเพณี", "History"])
    assert [(n.section_name, [c.section_name for c in n.children]) for n in outline.root.children] == [
        ("Tourism", ["Numbers"]), ("ประเพณี", []), ("History", ["Origins"]),
    ]


@pytest.mark.slow
def test_agent_research_plans_the_owners_sections():
    from deep_researcher.agents.planner_agent import ReportPlanSection

    from litstorm.engines.agent.engine import planned_sections

    planned = [ReportPlanSection(title="Economic effects", key_question="How much money?"),
               ReportPlanSection(title="Background", key_question="Where from?")]
    out = planned_sections(planned, ["Background", "Economic effects", "Safety"], "Songkran")
    assert [(s.title, s.key_question) for s in out] == [
        ("Background", "Where from?"), ("Economic effects", "How much money?"), ("Safety", "Safety (Songkran)"),
    ]


@pytest.mark.db
def test_a_run_keeps_its_sections_where_its_mode_uses_them(admin, browser, configured, db):
    from litstorm import db as db_mod
    from litstorm.worker import queue

    model, _ = configured
    user = make_user(admin, browser)
    body = {"topic": "Songkran", "language": "th"}
    r = user.post("/api/sessions", json={**body, "sections": ["# ประวัติ", "เศรษฐกิจ", ""]})
    run = r.json()["runs"][0]
    assert run["sections"] == ["ประวัติ", "เศรษฐกิจ"]
    with db_mod.sessions()() as s:
        assert queue.claim(s).config.sections == ["ประวัติ", "เศรษฐกิจ"]

    engines = {e["id"]: e for e in user.get("/api/options").json()["engines"]}
    assert engines["storm"]["sections_at"] == ["fast", "standard", "deep"]
    assert engines["agent"]["sections_at"] == ["deep"]  # its deep mode plans sections
    assert engines["deep"]["sections_at"] == []

    searxng = admin.post("/api/admin/search-providers",
                         json={"label": "S", "kind": "searxng", "endpoint": "http://s.test"}).json()
    admin.put(f"/api/admin/llm-models/{model['id']}", json={**model, "supports_tools": True})
    agent = {**body, "engine": "agent", "search_provider_id": searxng["id"], "sections": ["A"]}
    assert user.post("/api/sessions", json={**agent, "depth": "standard"}).json()["detail"] == "sections_not_for_mode"
    assert user.post("/api/sessions", json={**agent, "depth": "deep"}).status_code == 201
