"""Pricing a Run: LiteLLM's table under a router's model, and a Run that
could not be priced, said so rather than left a silent NULL."""

import uuid
from decimal import Decimal

import pytest

from conftest import make_user

# Gemini 3.1 Flash Lite's price, USD per token, as LiteLLM's table has it
# under the vendor's name only: it dropped every openrouter/ row on 2026-10-09.
TABLE = {"gemini-3.1-flash-lite": (Decimal("0.25") / 1_000_000, Decimal("1.5") / 1_000_000)}


@pytest.fixture
def table(monkeypatch):
    """LiteLLM's table, fixed, so no test depends on the one it fetches."""
    from litstorm import cost

    asked = []

    def lookup(name, prompt_tokens, completion_tokens):
        asked.append(name)
        if name not in TABLE:
            return None
        cost_in, cost_out = TABLE[name]
        return cost_in * prompt_tokens, cost_out * completion_tokens

    monkeypatch.setattr(cost, "_table_cost", lookup)
    return asked


def test_a_routers_model_is_asked_for_by_its_own_name_then_the_bare_one():
    from litstorm import cost

    assert cost.table_names("openrouter/google/gemini-3.1-flash-lite") == [
        "openrouter/google/gemini-3.1-flash-lite",
        "gemini-3.1-flash-lite",
    ]
    assert cost.table_names("gemini/gemini-3.1-flash-lite") == ["gemini/gemini-3.1-flash-lite"]


def test_a_routers_model_is_priced_by_the_vendors_name(table):
    from litstorm import cost

    # A fast Deep Research Run of 2026-10-06, priced then at $0.234831.
    priced = cost.price({"openrouter/google/gemini-3.1-flash-lite": [478_469, 76_809]})
    assert priced.usd == Decimal("0.234831")
    assert priced.unpriced == []
    assert priced.priced_as == {"openrouter/google/gemini-3.1-flash-lite": "gemini-3.1-flash-lite"}
    assert cost.estimate({"openrouter/google/gemini-3.1-flash-lite": [478_469, 76_809]}) == Decimal("0.234831")


def test_only_a_router_falls_back_to_the_bare_name(table):
    from litstorm import cost

    # groq's own model is not Google's, whatever it is called.
    assert cost.price({"groq/gemini-3.1-flash-lite": [1000, 1000]}).unpriced == ["groq/gemini-3.1-flash-lite"]


def test_a_model_found_under_its_own_name_is_not_marked(table):
    from litstorm import cost

    priced = cost.price({"gemini-3.1-flash-lite": [1_000_000, 0]})
    assert priced.usd == Decimal("0.250000") and priced.priced_as == {}


def test_every_model_without_a_price_is_named(table):
    from litstorm import cost

    priced = cost.price({"openrouter/google/gemini-3.1-flash-lite": [10, 10], "a/x": [1, 1], "b/y": [1, 1]})
    assert priced.usd is None
    assert priced.unpriced == ["a/x", "b/y"]


def test_the_admins_price_wins_over_the_table(table):
    from litstorm import cost

    prices = {"openrouter/google/gemini-3.1-flash-lite": (Decimal("1"), Decimal("2"))}
    priced = cost.price({"openrouter/google/gemini-3.1-flash-lite": [1_000_000, 1_000_000]}, prices=prices)
    assert priced.usd == Decimal("3.000000") and priced.priced_as == {}
    assert table == []  # the table was not asked


def test_table_rates_are_per_million_tokens(table):
    from litstorm import cost

    assert cost.table_rates("openrouter/google/gemini-3.1-flash-lite") == (
        Decimal("0.25"), Decimal("1.5"), "gemini-3.1-flash-lite"
    )
    assert cost.table_rates("nobody/unknown") is None


# --- in the Worker and Settings › Models ---------------------------------------------------------


@pytest.fixture
def unpriced(admin):
    """A model with no price of the Administrator's: the table decides."""
    admin.put("/api/admin/llm-credentials/openrouter", json={"api_key": "sk-test-0000"})
    model = admin.post(
        "/api/admin/llm-models",
        json={"label": "M", "provider": "openrouter", "model": "google/gemini-3.1-flash-lite", "is_default": True},
    ).json()
    admin.post("/api/admin/search-providers", json={"label": "arXiv", "kind": "arxiv", "is_default": True})
    return model


def run_fake(db, user):
    """A Run to its end with the fake engine, which reports its usage as
    "fake/model", as the Worker would."""
    from litstorm import db as db_mod
    from litstorm.db.models import Run
    from litstorm.worker import main, queue

    run = user.post("/api/sessions", json={"topic": "Songkran", "language": "th"}).json()["runs"][0]
    row = db.get(Run, uuid.UUID(run["id"]))
    row.engine = "fake"
    row.config = {**row.config, "params": {"script": [{"stage": "research"}]}}
    db.commit()
    with db_mod.sessions()() as s:
        claim = queue.claim(s)
    main.run_one(claim)
    db.expire_all()
    return db.get(Run, uuid.UUID(run["id"]))


@pytest.mark.db
def test_a_run_that_could_not_be_priced_says_so(admin, browser, unpriced, db, table, caplog):
    alice = make_user(admin, browser)
    with caplog.at_level("WARNING", logger="litstorm.worker"):
        stored = run_fake(db, alice)
    assert stored.status == "succeeded" and stored.tokens_in == 10
    assert stored.cost_usd is None
    assert stored.notes["cost"] == {"unpriced": ["fake/model"], "priced_as": {}}
    assert "no price for fake/model" in caplog.text

    assert "cost" not in alice.get(f"/api/runs/{stored.id}").json()["notes"]  # the Administrator's to know
    shown = admin.get("/api/admin/runs").json()[0]
    assert shown["cost_usd"] is None and shown["cost_unpriced"] == ["fake/model"]
    assert admin.get("/api/admin/usage").json()["rows"][0]["cost_incomplete"] is True


@pytest.mark.db
def test_a_priced_run_carries_no_cost_note(admin, browser, unpriced, db, monkeypatch, table):
    monkeypatch.setitem(TABLE, "fake/model", (Decimal("1") / 1_000_000, Decimal("2") / 1_000_000))
    alice = make_user(admin, browser)
    stored = run_fake(db, alice)
    assert stored.cost_usd == Decimal("0.000020")  # 10 × $1/M + 5 × $2/M
    assert "cost" not in stored.notes
    assert admin.get("/api/admin/runs").json()[0]["cost_unpriced"] == []


@pytest.mark.db
def test_settings_shows_the_tables_price_or_none(admin, unpriced, table):
    admin.post(
        "/api/admin/llm-models",
        json={"label": "N", "provider": "openrouter", "model": "nobody/unknown-xyz"},
    )
    admin.post(
        "/api/admin/llm-models",
        json={"label": "P", "provider": "openrouter", "model": "nobody/priced",
              "price_in_per_mtok": "1", "price_out_per_mtok": "2"},
    )
    listed = {m["label"]: m for m in admin.get("/api/admin/llm-models").json()}
    m = listed["M"]
    assert (Decimal(m["table_price_in"]), Decimal(m["table_price_out"])) == (Decimal("0.25"), Decimal("1.5"))
    assert m["table_name"] == "gemini-3.1-flash-lite" and m["price_in_per_mtok"] is None
    assert listed["N"]["table_price_in"] is None and listed["N"]["table_name"] is None
    assert Decimal(listed["P"]["price_in_per_mtok"]) == 1  # the Administrator's, beside no table price
