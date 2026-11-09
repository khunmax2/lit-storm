"""Depth levels: the owner picks fast, standard or deep; the numbers behind
each are the Administrator's, and a Run keeps the ones it started with."""

import uuid

import pytest

from conftest import make_user
from test_api_runs import configured  # noqa: F401  (fixture)

pytestmark = pytest.mark.db


def start(user, **extra):
    r = user.post("/api/sessions", json={"topic": "Songkran", "language": "th", **extra})
    assert r.status_code == 201, r.text
    return r.json()["runs"][0]


def stored(db, run):
    from litstorm.db.models import Run

    db.expire_all()
    return db.get(Run, uuid.UUID(run["id"])).config


def test_standard_is_what_runs_used_before_levels(admin, browser, configured, db):
    user = make_user(admin, browser)
    run = start(user)
    assert run["depth"] == "standard"
    config = stored(db, run)
    assert (config["depth"], config["target_minutes"]) == ("standard", 5)
    # The first release's settings, unchanged.
    assert {k: config["params"][k] for k in ("max_perspective", "max_conv_turn", "search_top_k")} == {
        "max_perspective": 3, "max_conv_turn": 3, "search_top_k": 3,
    }


def test_each_level_brings_its_own_numbers(admin, browser, configured, db):
    user = make_user(admin, browser)
    fast = stored(db, start(user, depth="fast"))
    deep = stored(db, start(user, depth="deep"))
    assert (fast["params"]["max_perspective"], fast["target_minutes"]) == (2, 2)
    assert (deep["params"]["max_perspective"], deep["target_minutes"]) == (5, 12)
    assert fast["params"]["max_tokens"] == deep["params"]["max_tokens"]  # the model's budget, not the level's


def test_an_unknown_level_is_refused(admin, browser, configured):
    user = make_user(admin, browser)
    r = user.post("/api/sessions", json={"topic": "Songkran", "language": "th", "depth": "extreme"})
    assert r.status_code == 422


def test_the_administrator_sets_what_a_level_means(admin, browser, configured, db):
    limits = admin.get("/api/admin/limits").json()
    assert set(limits["depth_levels"]) == {"fast", "standard", "deep"}
    limits["depth_levels"]["fast"] = {"target_minutes": 1, "storm": {"max_perspective": 1, "max_conv_turn": 1}}
    assert admin.put("/api/admin/limits", json=limits).status_code == 200

    user = make_user(admin, browser)
    options = user.get("/api/options").json()
    assert [(d["id"], d["target_minutes"]) for d in options["depth_levels"]] == [
        ("fast", 1), ("standard", 5), ("deep", 12)
    ]
    config = stored(db, start(user, depth="fast"))
    assert config["params"]["max_perspective"] == 1 and config["target_minutes"] == 1


def test_a_run_keeps_its_level_when_the_level_changes_or_it_is_retried(admin, browser, configured, db):
    user = make_user(admin, browser)
    run = start(user, depth="deep")
    limits = admin.get("/api/admin/limits").json()
    limits["depth_levels"]["deep"]["storm"]["max_perspective"] = 9
    admin.put("/api/admin/limits", json=limits)
    assert stored(db, run)["params"]["max_perspective"] == 5  # started with 5

    user.post(f"/api/runs/{run['id']}/cancel")
    again = user.post(f"/api/runs/{run['id']}/retry").json()
    assert again["depth"] == "deep"
    assert stored(db, again)["params"]["max_perspective"] == 9  # today's deep
