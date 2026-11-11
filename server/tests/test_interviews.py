"""A STORM Run's interviews: what each perspective asked the topic expert,
what the expert searched and answered (STORM's conversation_log.json), served
for the web app to show beside the Run."""

import json
import os

import pytest

from conftest import make_user
from test_api_runs import configured  # noqa: F401 - a fixture

pytestmark = pytest.mark.db

LOG = [
    {
        "perspective": "Basic fact writer: Basic fact writer focusing on broadly covering the basic facts about the topic.",
        "dlg_turns": [
            {
                "user_utterance": "What is solar power?",
                "agent_utterance": "Light turned into electricity [1], mostly by panels [2].",
                "search_queries": ["solar power basics", "", "  "],
                "search_results": [
                    {"url": "https://a.example.org/x", "title": "A", "snippets": ["long text"], "description": "d"},
                    {"url": "https://b.example.org/y", "title": "B", "snippets": ["more"], "description": "d"},
                ],
            }
        ],
    },
    {"perspective": "An engineer", "dlg_turns": []},
]


def _keep(run_id, log):
    from litstorm import settings

    folder = os.path.join(settings.get().runs_dir, run_id, "work", "storm", "article")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "conversation_log.json"), "w", encoding="utf-8") as f:
        json.dump(log, f)


def test_the_interviews_are_served_to_their_owner_without_the_pages_read(admin, browser, configured):  # noqa: F811
    user = make_user(admin, browser)
    run = user.post("/api/sessions", json={"topic": "Solar power", "language": "en"}).json()["runs"][0]
    assert user.get(f"/api/runs/{run['id']}/interviews").status_code == 404  # nothing kept yet
    _keep(run["id"], LOG)
    got = user.get(f"/api/runs/{run['id']}/interviews")
    assert got.status_code == 200 and got.headers["cache-control"] == "private, no-store"
    assert got.json() == {
        "perspectives": [
            {
                "name": "Basic fact writer",
                "description": "Basic fact writer focusing on broadly covering the basic facts about the topic.",
                "turns": [
                    {
                        "question": "What is solar power?",
                        "queries": ["solar power basics"],
                        "answer": "Light turned into electricity [1], mostly by panels [2].",
                        # [n] in the answer is the nth page found for this question; the pages' text stays behind.
                        "sources": [
                            {"title": "A", "url": "https://a.example.org/x"},
                            {"title": "B", "url": "https://b.example.org/y"},
                        ],
                    }
                ],
            },
            {"name": "An engineer", "description": "", "turns": []},
        ]
    }
    other = make_user(admin, browser, email="other@example.org")
    assert other.get(f"/api/runs/{run['id']}/interviews").status_code == 404  # not theirs


def test_a_log_that_cannot_be_read_is_not_found(admin, browser, configured):  # noqa: F811
    user = make_user(admin, browser)
    run = user.post("/api/sessions", json={"topic": "Solar power", "language": "en"}).json()["runs"][0]
    _keep(run["id"], {"not": "a list"})
    assert user.get(f"/api/runs/{run['id']}/interviews").json()["detail"] == "no_interviews"
