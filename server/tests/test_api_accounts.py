"""First-run setup, signing in, set-password links, and who may see what."""

import pytest

from conftest import make_user

pytestmark = pytest.mark.db


def test_setup_needs_the_installers_code(browser, bootstrap_code):
    b = browser()
    assert b.get("/api/setup").json() == {"needed": True, "code_configured": True}
    r = b.post("/api/setup", json={"code": "wrong", "email": "a@b.org", "name": "A", "password": "long enough 1"})
    assert r.status_code == 403
    r = b.post("/api/setup", json={"code": bootstrap_code, "email": "a@b.org", "name": "A", "password": "long enough 1"})
    assert r.status_code == 200 and r.json()["role"] == "admin"
    assert b.get("/api/setup").json()["needed"] is False


def test_setup_happens_once(admin, browser, bootstrap_code):
    r = browser().post(
        "/api/setup", json={"code": bootstrap_code, "email": "x@b.org", "name": "X", "password": "long enough 1"}
    )
    assert r.status_code == 409


def test_setup_is_closed_without_a_code(browser, db):
    r = browser().post("/api/setup", json={"code": "", "email": "a@b.org", "name": "A", "password": "long enough 1"})
    assert r.status_code == 409


def test_changes_need_the_csrf_header(admin):
    r = admin.client.post("/api/projects", json={"name": "P"})  # no header
    assert r.status_code == 403
    assert admin.post("/api/projects", json={"name": "P"}).status_code == 201


def test_login_failures_all_look_alike(admin, browser):
    make_user(admin, browser)
    wrong_password = browser().post("/api/auth/login", json={"email": "user@example.org", "password": "nope nope nope"})
    no_account = browser().post("/api/auth/login", json={"email": "ghost@example.org", "password": "nope nope nope"})
    assert wrong_password.status_code == no_account.status_code == 401
    assert wrong_password.json() == no_account.json()


def test_a_new_account_signs_in_through_its_link(admin, browser):
    link = admin.post("/api/admin/users", json={"email": "New@Example.org", "name": "N"}).json()["link"]
    token = link.split("#", 1)[1]
    b = browser()
    # No password yet, so no way in but the link.
    assert b.post("/api/auth/login", json={"email": "new@example.org", "password": "anything at all"}).status_code == 401
    assert b.post("/api/auth/password-link", json={"token": token, "password": ""}).json()["valid"] is True
    assert b.post("/api/auth/password", json={"token": token, "password": "short"}).status_code == 422
    assert b.post("/api/auth/password", json={"token": token, "password": "a fine password"}).status_code == 200
    assert b.get("/api/me").json()["email"] == "new@example.org"
    # Used once.
    assert browser().post("/api/auth/password", json={"token": token, "password": "another password"}).status_code == 410


def test_a_new_link_replaces_the_old_one(admin, browser):
    created = admin.post("/api/admin/users", json={"email": "n@e.org", "name": "N"}).json()
    first = created["link"].split("#", 1)[1]
    second = admin.post(f"/api/admin/users/{created['user']['id']}/link").json()["link"].split("#", 1)[1]
    assert browser().post("/api/auth/password", json={"token": first, "password": "a fine password"}).status_code == 410
    assert browser().post("/api/auth/password", json={"token": second, "password": "a fine password"}).status_code == 200


def test_reset_stops_the_old_password_and_signs_out(admin, browser):
    user = make_user(admin, browser)
    uid = user.get("/api/me").json()["id"]
    link = admin.post(f"/api/admin/users/{uid}/link").json()["link"]
    assert user.get("/api/me").status_code == 401  # signed out everywhere
    old = browser().post("/api/auth/login", json={"email": "user@example.org", "password": "user password 1"})
    assert old.status_code == 401
    b = browser()
    assert b.post("/api/auth/password", json={"token": link.split("#", 1)[1], "password": "brand new password"}).status_code == 200


def test_users_cannot_reach_admin_pages(admin, browser):
    user = make_user(admin, browser)
    assert user.get("/api/admin/users").status_code == 403


def test_one_user_cannot_see_anothers_work(admin, browser):
    alice = make_user(admin, browser, "alice@example.org")
    bob = make_user(admin, browser, "bob@example.org")
    project = alice.post("/api/projects", json={"name": "Alice's"}).json()
    assert bob.get(f"/api/projects/{project['id']}").status_code == 404
    assert bob.get("/api/projects").json() == []


def test_an_admin_does_not_read_users_research(admin, browser):
    alice = make_user(admin, browser, "alice@example.org")
    project = alice.post("/api/projects", json={"name": "Private"}).json()
    assert admin.get(f"/api/projects/{project['id']}").status_code == 404


def test_stored_keys_are_encrypted_and_only_hinted(admin, db):
    from litstorm.db.models import LlmCredential

    r = admin.put("/api/admin/llm-credentials/openrouter", json={"api_key": "sk-or-secret-1b1b"})
    assert r.json()["key_hint"] == "…1b1b"
    listed = admin.get("/api/admin/llm-credentials").json()
    assert "sk-or-secret-1b1b" not in str(listed)
    stored = db.get(LlmCredential, "openrouter").api_key_ciphertext
    assert "sk-or-secret" not in stored


def test_only_one_default_model(admin):
    a = admin.post("/api/admin/llm-models", json={"label": "A", "provider": "openrouter", "model": "a/a", "is_default": True}).json()
    b = admin.post("/api/admin/llm-models", json={"label": "B", "provider": "openrouter", "model": "b/b", "is_default": True}).json()
    defaults = [m["id"] for m in admin.get("/api/admin/llm-models").json() if m["is_default"]]
    assert defaults == [b["id"]] and a["id"] != b["id"]
