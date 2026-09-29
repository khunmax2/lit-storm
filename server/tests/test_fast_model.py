"""The fast model (ADR-0006): set once by the Administrator, kept with each
Run, handed to the Run's process with its own key, priced as itself; a Run
whose fast model was turned off uses its main model."""

from decimal import Decimal

import pytest

from conftest import make_user
from test_api_runs import configured  # noqa: F401  (fixture)

pytestmark = pytest.mark.db


def _fast(admin, **extra):
    admin.put("/api/admin/llm-credentials/gemini", json={"api_key": "gm-test-5555"})
    return admin.post("/api/admin/llm-models", json={
        "label": "Fast", "provider": "gemini", "model": "gemini-lite", "max_tokens": {"conversation": 700},
        "price_in_per_mtok": "0.1", "price_out_per_mtok": "0.4", **extra,
    }).json()


def _claim():
    from litstorm import db as db_mod
    from litstorm.worker import queue

    with db_mod.sessions()() as s:
        return queue.claim(s)


def test_a_run_keeps_the_fast_model_and_gets_its_key(admin, browser, configured, db):
    from litstorm.db.models import Run

    fast = _fast(admin)
    assert admin.put("/api/admin/model-roles", json={"fast_model_id": fast["id"]}).json() == {
        "fast_model_id": fast["id"]
    }
    user = make_user(admin, browser)
    run = user.post("/api/sessions", json={"topic": "Songkran", "language": "th"}).json()["runs"][0]
    db.expire_all()
    kept = db.get(Run, run["id"]).config["fast_llm"]
    assert (kept["provider"], kept["model"], kept["max_tokens"]) == ("gemini", "gemini-lite", {"conversation": 700})
    assert "gm-test" not in str(kept)

    claim = _claim()
    assert claim.config.fast_llm["model"] == "gemini-lite"
    assert claim.secrets.fast_llm_api_key == "gm-test-5555"
    assert claim.secrets.llm_api_key == "sk-test-0000"  # the main model's own
    # The main model has no price of its own set, so only the fast one is listed.
    assert claim.prices == {"gemini/gemini-lite": (Decimal("0.1000"), Decimal("0.4000"))}


def test_a_fast_model_turned_off_leaves_the_main_model(admin, browser, configured):
    fast = _fast(admin)
    admin.put("/api/admin/model-roles", json={"fast_model_id": fast["id"]})
    user = make_user(admin, browser)
    user.post("/api/sessions", json={"topic": "Songkran", "language": "th"})
    admin.put(f"/api/admin/llm-models/{fast['id']}", json={**fast, "enabled": False})
    claim = _claim()
    assert claim is not None and claim.config.fast_llm == {} and claim.secrets.fast_llm_api_key == ""


def test_the_setting_takes_only_a_model_that_is_on(admin, configured):
    fast = _fast(admin, enabled=False)
    r = admin.put("/api/admin/model-roles", json={"fast_model_id": fast["id"]})
    assert r.status_code == 422 and r.json()["detail"] == "model_disabled"
    assert admin.put("/api/admin/model-roles", json={"fast_model_id": None}).json() == {"fast_model_id": None}


def test_the_same_model_as_fast_and_main_is_one_model(admin, browser, configured, db):
    from litstorm.db.models import Run

    model, _ = configured
    admin.put("/api/admin/model-roles", json={"fast_model_id": model["id"]})
    user = make_user(admin, browser)
    run = user.post("/api/sessions", json={"topic": "Songkran", "language": "th"}).json()["runs"][0]
    db.expire_all()
    assert "fast_llm" not in db.get(Run, run["id"]).config


def test_each_model_is_priced_as_itself():
    from litstorm import cost

    by_model = {"gemini/gemini-lite": [1_000_000, 0], "openrouter/a/b": [0, 1_000_000]}
    prices = {"gemini/gemini-lite": (Decimal("0.1"), Decimal("0.4")), "openrouter/a/b": (Decimal("1"), Decimal("2"))}
    assert cost.estimate(by_model, prices=prices) == Decimal("2.100000")
