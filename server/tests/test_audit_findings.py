"""Findings of the 2026-10-24 audit (docs/reports/audit-2026-10-24/security.md).

Each test asserts the SAFE behaviour, so it fails today and is marked
xfail(strict=True): once the finding is fixed the test passes, strict turns
that into a failure, and whoever fixed it removes the mark. Nothing here
calls a real model or search service; outbound calls are captured.
"""

import asyncio
import http.server
import re
import ssl
import threading
from pathlib import Path

import pytest

from conftest import make_user


def finding(code):
    return pytest.mark.xfail(strict=True, raises=AssertionError, reason=code)


# --- SEC-02: Agent Research fetches internal addresses ----------------------------


class _Internal(http.server.BaseHTTPRequestHandler):
    """Stands in for a service only the Worker can reach (SearXNG, MRA, the host)."""

    def do_GET(self):  # noqa: N802 - http.server's name
        body = b"<html><body><p>internal-service-secret-sec02</p></body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def internal_service():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Internal)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/"
    finally:
        server.shutdown()
        server.server_close()


@finding("SEC-02")
def test_sec02_agent_research_does_not_fetch_internal_addresses(internal_service):
    """The pages a search result (or the crawl agent, from what the model
    asks) points at are fetched with no check of where they are: a loopback,
    private or link-local address comes back as text for the report."""
    from deep_researcher.tools.web_search import WebpageSnippet, scrape_urls

    results = asyncio.run(scrape_urls([WebpageSnippet(url=internal_service, title="", description="")]))
    assert not any("internal-service-secret-sec02" in (r.text or "") for r in results)


# --- SEC-03 and SEC-08: signing in -----------------------------------------------------


@finding("SEC-03")
@pytest.mark.db
def test_sec03_repeated_wrong_passwords_are_slowed_down(admin, browser):
    make_user(admin, browser, "audit-victim@example.org", "the right password 1")
    stranger = browser()
    codes = [
        stranger.post("/api/auth/login", json={"email": "audit-victim@example.org", "password": f"guess {i:04d}"}).status_code
        for i in range(50)
    ]
    # 429 Too Many Requests, 423 Locked or 503 with Retry-After: any of them is a throttle.
    assert THROTTLED & set(codes), f"50 wrong passwords in a row, all answered {set(codes)}"


THROTTLED = {423, 429, 503}


@finding("SEC-08")
@pytest.mark.db
def test_sec08_login_does_the_same_work_for_an_unknown_address(admin, browser, monkeypatch):
    """An address with no account is refused before any password is
    checked, so it answers about 50 ms sooner (argon2) than a wrong password
    for a real account. Safe: the password is checked (against a dummy hash)
    whether or not the address has an account."""
    from litstorm import security

    calls = []
    real = security.verify_password

    def counted(password_hash, password):
        calls.append(password_hash)
        return real(password_hash, password)

    monkeypatch.setattr(security, "verify_password", counted)
    r = browser().post("/api/auth/login", json={"email": "audit-nobody@example.org", "password": "not the password"})
    assert r.status_code == 401
    assert calls, "no password was checked for an address without an account"


# --- SEC-05: a stored key goes to an address typed in the request -----------------

STORED_KEY = "sk-or-v1-audit-stored-key-0000000000"
ELSEWHERE = "http://attacker.invalid/v1"


@finding("SEC-05")
@pytest.mark.db
def test_sec05_testing_a_draft_model_does_not_send_the_stored_key_elsewhere(admin, monkeypatch):
    import litellm

    sent = []

    def capture(**kwargs):
        sent.append(kwargs)
        raise RuntimeError("captured, not sent")

    monkeypatch.setattr(litellm, "completion", capture)
    assert admin.put("/api/admin/llm-credentials/openrouter", json={"api_key": STORED_KEY}).status_code == 200
    r = admin.post("/api/admin/llm-models/check", json={"provider": "openrouter", "model": "any/model", "api_base": ELSEWHERE})
    assert r.status_code == 200
    leaked = [k for k in sent if k.get("api_key") == STORED_KEY and k.get("api_base") == ELSEWHERE]
    assert len(leaked) == 0, "the stored OpenRouter key was handed to an address the request named"


@finding("SEC-05")
@pytest.mark.db
def test_sec05_testing_an_embedding_does_not_send_the_stored_key_elsewhere(admin, monkeypatch):
    """embedding.key_for keeps the key from another address for
    "openai-compatible" only; the other providers take an api_base too."""
    from litstorm import embedding

    sent = []

    class Refused:
        status_code = 401
        text = "captured"

    def capture(url, json=None, headers=None, timeout=None):
        sent.append((url, headers or {}))
        return Refused()

    monkeypatch.setattr(embedding.requests, "post", capture)
    assert admin.put("/api/admin/llm-credentials/openrouter", json={"api_key": STORED_KEY}).status_code == 200
    r = admin.post("/api/admin/embedding/check", json={"provider": "openrouter", "model": "m", "api_base": ELSEWHERE})
    assert r.status_code == 200
    leaked = [u for u, h in sent if u.startswith(ELSEWHERE) and STORED_KEY in h.get("Authorization", "")]
    assert len(leaked) == 0, "the stored OpenRouter key was sent to an address the request named"


# --- SEC-06: Agent Research turns certificate checks off ---------------------------


@finding("SEC-06")
def test_sec06_agent_research_checks_certificates():
    """Its one TLS context serves the Tavily search (the key in the body),
    SearXNG and every page it reads."""
    from deep_researcher.tools import web_search

    assert web_search.ssl_context.verify_mode == ssl.CERT_REQUIRED
    assert web_search.ssl_context.check_hostname


# --- SEC-07: a reset leaves the account's API tokens working ---------------------


@finding("SEC-07")
@pytest.mark.db
def test_sec07_a_password_reset_stops_the_accounts_api_tokens(admin, browser):
    import json

    from fastapi.testclient import TestClient

    from litstorm.api import create_app

    user = make_user(admin, browser, "audit-reset@example.org")
    token = user.post("/api/me/tokens", json={"name": "t", "scopes": ["read"], "days": 30}).json()["token"]
    account = next(u for u in admin.get("/api/admin/users").json() if u["email"] == "audit-reset@example.org")
    # "the old password stops working and the User is signed out everywhere" (api/admin.reset_link)
    assert admin.post(f"/api/admin/users/{account['id']}/link").status_code == 200

    listing = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json, text/event-stream",
               "Content-Type": "application/json"}
    with TestClient(create_app()) as client:
        r = client.post("/api/mcp", headers=headers, content=json.dumps(listing))
    assert r.status_code in (401, 403), f"the token still opens the MCP server after the reset ({r.status_code})"


# --- SEC-09: security headers ------------------------------------------------------------

WEB = Path(__file__).resolve().parents[2] / "web"


@finding("SEC-09")
def test_sec09_the_web_app_is_served_with_a_csp_and_no_framing():
    # Directives only: a comment that names a header does not send it.
    lines = (WEB / "nginx.conf").read_text(encoding="utf-8").splitlines()
    conf = "\n".join(line.split("#", 1)[0] for line in lines)
    assert re.search(r"add_header\s+Content-Security-Policy\s", conf)
    assert re.search(r"add_header\s+Content-Security-Policy\s[^\n]*frame-ancestors", conf) or re.search(
        r"add_header\s+X-Frame-Options\s", conf
    )


# --- SEC-11: dependencies with fixes that reach our code ----------------------------


def _version(name):
    from importlib.metadata import version

    from packaging.version import Version

    return Version(version(name))


@finding("SEC-11")
def test_sec11_outbound_https_libraries_are_patched():
    from packaging.version import Version

    # certifi < 2026.10.19 trusts the emSign ECC Root CA - G3 (PYSEC-2026-4320).
    assert _version("certifi") >= Version("2026.10.19")
    # aiohttp 3.14.4: the client Agent Research reads pages with (GHSA-2g87-pp6c-29x5 and others).
    assert _version("aiohttp") >= Version("3.14.4")
