"""A Project's defaults and instructions (docs/web-app-design.md, รุ่นสอง:
โครงร่างที่ผู้ใช้กำหนดและ Project): research started in the Project keeps
a copy of its instructions; research started elsewhere has none."""

from types import SimpleNamespace

import pytest

from conftest import make_user
from test_api_runs import configured  # noqa: F401  (fixture)


def test_the_search_scope_joins_the_clarifying_answers():
    from litstorm import instructions

    config = SimpleNamespace(
        refinement=[{"question": "Where?", "answer": "Chiang Mai"}],
        instructions={"search_scope": "Peer-reviewed sources after 2020", "writing_style": "Short paragraphs"},
    )
    assert instructions.focus(config) == "Where? Chiang Mai; Peer-reviewed sources after 2020"
    assert instructions.style(config) == "Short paragraphs"
    assert instructions.focus(SimpleNamespace(refinement=[], instructions={})) == ""


@pytest.mark.slow
def test_the_writing_style_goes_to_the_prompts_that_write():
    from knowledge_storm.storm_wiki.modules import article_generation, knowledge_curation

    from litstorm.engines.storm import language

    try:
        language.apply("th", style="Write for secondary-school students.")
        assert "secondary-school students" in article_generation.WriteSection.__doc__
        assert "secondary-school students" not in knowledge_curation.AskQuestion.__doc__
        language.apply("en")
        assert "secondary-school students" not in article_generation.WriteSection.__doc__
    finally:
        language.apply("en")


@pytest.mark.db
def test_a_project_keeps_its_defaults_and_its_runs_keep_its_instructions(admin, browser, configured, db):
    from litstorm import db as db_mod
    from litstorm.worker import queue

    model, search = configured
    user = make_user(admin, browser)
    project = user.post("/api/projects", json={"name": "Thesis"}).json()
    assert project["defaults"] == {"language": None, "llm_model_id": None, "search_provider_id": None,
                                   "extra_search_provider_ids": [], "depth": None, "sections": []}
    r = user.patch(f"/api/projects/{project['id']}", json={
        "defaults": {"language": "en", "depth": "deep", "search_provider_id": search["id"], "sections": ["# History", "Economy"]},
        "search_scope": " Peer-reviewed sources after 2020 ",
        "writing_style": "Short paragraphs, no jargon.",
    })
    assert r.status_code == 200, r.text
    saved = user.get(f"/api/projects/{project['id']}").json()
    assert saved["defaults"]["depth"] == "deep" and saved["defaults"]["sections"] == ["History", "Economy"]
    assert saved["search_scope"] == "Peer-reviewed sources after 2020"

    inside = user.post(f"/api/projects/{project['id']}/sessions", json={"topic": "Songkran", "language": "en"}).json()
    run = inside["runs"][0]
    assert run["instructions"] == {"search_scope": "Peer-reviewed sources after 2020",
                                   "writing_style": "Short paragraphs, no jargon."}
    outside = user.post("/api/sessions", json={"topic": "Songkran", "language": "en"}).json()
    assert outside["runs"][0]["instructions"] == {}

    # Changing the instructions, or moving the topic out, leaves the Run as it was.
    user.patch(f"/api/projects/{project['id']}", json={"search_scope": "", "writing_style": "Long form."})
    user.patch(f"/api/sessions/{inside['id']}", json={"project_id": None})
    assert user.get(f"/api/sessions/{inside['id']}").json()["runs"][0]["instructions"]["writing_style"] == "Short paragraphs, no jargon."

    with db_mod.sessions()() as s:
        claim = queue.claim(s)
    assert claim.config.instructions["search_scope"] == "Peer-reviewed sources after 2020"

    # A Run started in the Project now takes what it says now.
    later = user.post(f"/api/projects/{project['id']}/sessions", json={"topic": "Loy Krathong", "language": "en"}).json()
    assert later["runs"][0]["instructions"] == {"writing_style": "Long form."}


@pytest.mark.db
def test_another_users_project_cannot_be_changed(admin, browser, configured):
    alice = make_user(admin, browser, email="alice@example.org")
    bob = make_user(admin, browser, email="bob@example.org")
    project = alice.post("/api/projects", json={"name": "Mine"}).json()
    assert bob.patch(f"/api/projects/{project['id']}", json={"name": "Yours"}).status_code == 404
