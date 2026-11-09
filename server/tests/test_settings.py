"""Where the secrets come from: a Docker secret file first, else the
environment (a host whose runner cannot bind files, deploy/aiforthai)."""

import pytest

from litstorm import settings


@pytest.fixture
def fresh(monkeypatch):
    for name in ("LITSTORM_SECRET_KEY_FILE", "LITSTORM_SECRET_KEY",
                 "LITSTORM_BOOTSTRAP_CODE_FILE", "LITSTORM_BOOTSTRAP_CODE"):
        monkeypatch.delenv(name, raising=False)
    settings.get.cache_clear()
    yield monkeypatch
    settings.get.cache_clear()


def test_the_bootstrap_code_can_come_from_the_environment(fresh):
    fresh.setenv("LITSTORM_BOOTSTRAP_CODE", "code-from-env")
    assert settings.get().bootstrap_code == "code-from-env"


def test_a_secret_file_wins_over_the_environment(fresh, tmp_path):
    path = tmp_path / "bootstrap_code"
    path.write_text("code-from-file\n", encoding="utf-8")
    fresh.setenv("LITSTORM_BOOTSTRAP_CODE_FILE", str(path))
    fresh.setenv("LITSTORM_BOOTSTRAP_CODE", "code-from-env")
    assert settings.get().bootstrap_code == "code-from-file"
