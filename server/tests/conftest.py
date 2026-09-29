"""A real Postgres for the tests that need one, migrated to head.

Started once per test session (testcontainers, so Docker must be running);
each test gets empty tables.
"""

import os

import pytest


@pytest.fixture(scope="session")
def database_url(tmp_path_factory):
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:17-alpine", driver="psycopg") as pg:
        url = pg.get_connection_url()
        data_dir = tmp_path_factory.mktemp("data")
        from cryptography.fernet import Fernet

        os.environ.update(
            {
                "LITSTORM_DATABASE_URL": url,
                "LITSTORM_DATA_DIR": str(data_dir),
                "LITSTORM_SECRET_KEY": Fernet.generate_key().decode(),
                "LITSTORM_PUBLIC_URL": "http://test.local",
            }
        )
        _reset_caches()

        from alembic import command
        from alembic.config import Config

        config = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
        command.upgrade(config, "head")
        yield url


def _reset_caches():
    from litstorm import db, settings

    settings.get.cache_clear()
    db.engine.cache_clear()
    db.sessions.cache_clear()


@pytest.fixture
def db(database_url):
    from sqlalchemy import text

    from litstorm import db as db_mod
    from litstorm.db.models import Base

    with db_mod.engine().begin() as conn:
        names = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
        conn.execute(text(f"TRUNCATE {names} CASCADE"))
    with db_mod.sessions()() as session:
        yield session


@pytest.fixture
def bootstrap_code(tmp_path, database_url):
    path = tmp_path / "code"
    path.write_text("open-sesame-123\n")
    os.environ["LITSTORM_BOOTSTRAP_CODE_FILE"] = str(path)
    _reset_settings_only()
    yield "open-sesame-123"
    os.environ.pop("LITSTORM_BOOTSTRAP_CODE_FILE", None)
    _reset_settings_only()


def _reset_settings_only():
    from litstorm import settings

    settings.get.cache_clear()


class Browser:
    """A TestClient that sends the CSRF header the way the web app does."""

    def __init__(self, client):
        self.client = client

    def _headers(self):
        token = self.client.cookies.get("litstorm_csrf")
        return {"X-CSRF-Token": token} if token else {}

    def get(self, url, **kw):
        return self.client.get(url, **kw)

    def post(self, url, **kw):
        return self.client.post(url, headers=self._headers(), **kw)

    def put(self, url, **kw):
        return self.client.put(url, headers=self._headers(), **kw)

    def patch(self, url, **kw):
        return self.client.patch(url, headers=self._headers(), **kw)

    def delete(self, url, **kw):
        return self.client.delete(url, headers=self._headers(), **kw)


@pytest.fixture
def browser(db):
    from fastapi.testclient import TestClient

    from litstorm.api import create_app

    def make():
        return Browser(TestClient(create_app()))

    return make


@pytest.fixture
def admin(browser, bootstrap_code):
    b = browser()
    r = b.post(
        "/api/setup",
        json={"code": bootstrap_code, "email": "Admin@Example.org", "name": "Admin", "password": "correct horse"},
    )
    assert r.status_code == 200, r.text
    return b


def make_user(admin, browser, email="user@example.org", password="user password 1"):
    link = admin.post("/api/admin/users", json={"email": email, "name": "U"}).json()["link"]
    b = browser()
    r = b.post("/api/auth/password", json={"token": link.split("#", 1)[1], "password": password})
    assert r.status_code == 200, r.text
    return b
