"""API tokens and integration accounts (litstorm.tokens, api/tokens.py)."""

from datetime import datetime, timedelta, timezone

import pytest

from conftest import make_user
from test_api_runs import configured  # noqa: F401 - a fixture

pytestmark = pytest.mark.db


def _make(browser_user, **body):
    return browser_user.post("/api/me/tokens", json={"name": "Claude on my laptop", **body})


def test_a_user_makes_a_token_sees_it_once_and_revokes_it(admin, browser, db):
    from litstorm import tokens
    from litstorm.db.models import ApiToken

    user = make_user(admin, browser)
    made = _make(user, scopes=["read"], days=30)
    assert made.status_code == 201, made.text
    token, record = made.json()["token"], made.json()["record"]
    assert token.startswith("dlk_") and len(token) > 40
    assert record["prefix"] == token[:8] and record["scopes"] == ["read"] and record["state"] == "live"
    # Only the hash is kept; the list never shows the token again.
    assert token not in str(user.get("/api/me/tokens").json())
    stored = db.get(ApiToken, record["id"])
    assert stored.token_hash != token and token not in str(stored.__dict__)

    found, row = tokens.authenticate(db, f"Bearer {token}")
    assert found.email == "user@example.org" and str(row.id) == record["id"]
    tokens.require(row, "read")
    with pytest.raises(tokens.Refused) as no_scope:
        tokens.require(row, "research")
    assert no_scope.value.reason == "needs_research_scope"

    assert user.delete(f"/api/me/tokens/{record['id']}").status_code == 204
    assert user.get("/api/me/tokens").json()[0]["state"] == "revoked"
    db.expire_all()
    with pytest.raises(tokens.Refused) as revoked:
        tokens.authenticate(db, token)
    assert revoked.value.reason == "bad_token"


def test_tokens_that_must_not_work_do_not(admin, browser, db):
    from litstorm import tokens
    from litstorm.db.models import ApiToken, User

    user = make_user(admin, browser)
    token = _make(user, scopes=["read", "research"], days=90).json()["token"]
    for raw, reason in (("", "no_token"), ("Bearer abc", "no_token"), ("dlk_not-a-real-one", "bad_token")):
        with pytest.raises(tokens.Refused) as refused:
            tokens.authenticate(db, raw)
        assert refused.value.reason == reason

    row = db.query(ApiToken).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    with pytest.raises(tokens.Refused):
        tokens.authenticate(db, token)
    row.expires_at = None
    db.query(User).filter_by(email="user@example.org").one().is_active = False
    db.commit()
    with pytest.raises(tokens.Refused):
        tokens.authenticate(db, token)


def test_the_administrator_can_switch_the_server_and_token_making_off(admin, browser, db):
    from litstorm import tokens

    user = make_user(admin, browser)
    token = _make(user).json()["token"]
    assert admin.get("/api/admin/mcp").json() == {"enabled": True, "users_create_tokens": True}

    admin.put("/api/admin/mcp", json={"enabled": True, "users_create_tokens": False})
    assert _make(user).status_code == 403  # ordinary users may not
    assert _make(admin).status_code == 201  # an Administrator still may
    assert user.get("/api/me/connection").json()["may_create"] is False

    admin.put("/api/admin/mcp", json={"enabled": False, "users_create_tokens": True})
    db.expire_all()
    with pytest.raises(tokens.Refused) as off:
        tokens.authenticate(db, token)
    assert off.value.reason == "mcp_disabled"


def test_a_token_is_made_with_known_scopes_and_lifetimes(admin, browser):
    user = make_user(admin, browser)
    assert _make(user, scopes=["admin"]).json()["detail"] == "unknown_scope"
    assert _make(user, days=7).json()["detail"] == "unknown_lifetime"
    assert _make(user, days=None).json()["detail"] == "token_needs_expiry"
    connection = user.get("/api/me/connection").json()
    assert connection["url"].endswith("/api/mcp") and connection["lifetimes"] == [30, 90, 365]


def test_an_administrator_sees_and_revokes_every_token(admin, browser):
    user = make_user(admin, browser)
    mine = _make(user).json()["record"]
    listed = admin.get("/api/admin/tokens").json()
    assert [(t["id"], t["owner_name"], t["owner_kind"]) for t in listed] == [(mine["id"], "U", "person")]
    assert admin.delete(f"/api/admin/tokens/{mine['id']}").status_code == 204
    assert user.get("/api/me/tokens").json()[0]["state"] == "revoked"
    assert user.get("/api/admin/tokens").status_code == 403


def test_an_integration_account_holds_tokens_and_never_signs_in(admin, browser, db):
    from litstorm import tokens

    made = admin.post("/api/admin/integrations", json={
        "name": "DeepWitya", "monthly_run_quota": 50, "max_concurrent_runs": 2, "allowed_engines": ["storm", "agent"],
    })
    assert made.status_code == 201, made.text
    account = made.json()
    assert account["allowed_engines"] == ["storm", "agent"] and account["quota_limit"] == 50
    # Not among the people, and no link to set a password.
    assert "DeepWitya" not in str(admin.get("/api/admin/users").json())
    assert admin.post(f"/api/admin/users/{account['id']}/link").status_code == 404

    key = admin.post(f"/api/admin/integrations/{account['id']}/tokens", json={"name": "server", "days": None})
    assert key.status_code == 201 and key.json()["record"]["expires_at"] is None
    user, _ = tokens.authenticate(db, key.json()["token"])
    assert user.kind == "integration" and user.name == "DeepWitya"
    listed = admin.get("/api/admin/integrations").json()
    assert [len(a["tokens"]) for a in listed] == [1]

    assert admin.patch(f"/api/admin/integrations/{account['id']}", json={"allowed_engines": ["nope"]}).status_code == 422
    assert admin.patch(f"/api/admin/integrations/{account['id']}", json={"is_active": False}).json()["is_active"] is False
    assert browser().post("/api/auth/login", json={"email": user.email, "password": ""}).status_code in (401, 422)


def test_an_account_starts_only_the_modes_it_is_allowed(admin, browser, configured, db):  # noqa: F811
    from litstorm.db.models import User

    user = make_user(admin, browser)
    db.query(User).filter_by(email="user@example.org").one().allowed_engines = ["deep"]
    db.commit()
    r = user.post("/api/sessions", json={"topic": "Songkran", "language": "th", "engine": "storm"})
    assert r.status_code == 422 and r.json()["detail"] == "engine_not_allowed"


def test_the_setup_page_names_every_mcp_server_and_who_may_use_it(admin, browser):
    user = make_user(admin, browser)
    endpoints = {e["id"]: e for e in user.get("/api/me/connection").json()["endpoints"]}
    assert list(endpoints) == ["all", "storm", "deep", "agent", "medical"]
    assert [e["id"] for e in endpoints.values() if not e["allowed"]] == ["medical"]  # until MRA is set up
    assert endpoints["deep"]["path"] == "/api/mcp/deep" and endpoints["deep"]["name"] == "deeplit-deep"
    assert endpoints["deep"]["url"].endswith("/api/mcp/deep") and endpoints["deep"]["tool_prefix"] == "deep_research"
    admin.put("/api/admin/engines/agent", json={"enabled": False})
    assert not {e["id"]: e for e in user.get("/api/me/connection").json()["endpoints"]}["agent"]["allowed"]
    account = admin.post("/api/admin/integrations", json={"name": "DeepWitya", "allowed_engines": ["deep"]}).json()
    assert {e["id"] for e in account["endpoints"] if e["allowed"]} == {"all", "deep"}
