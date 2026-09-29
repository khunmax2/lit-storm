"""What the API and the Worker read from their environment.

Secrets arrive as files (Docker secrets), never as plain environment values:
a value in the environment shows up in `docker inspect` and in every child
process. The Run's own process gets its credentials on stdin instead.
"""

import os
from dataclasses import dataclass
from functools import lru_cache


def _read_file(path):
    if not path:
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


@dataclass(frozen=True)
class Settings:
    database_url: str
    data_dir: str
    # Fernet key that encrypts provider credentials at rest (docs/adr/0002).
    secret_key: str
    # The one-time code the installer sets for creating the first
    # Administrator (docs/web-app-design.md, การสร้างผู้ดูแลคนแรก).
    bootstrap_code: str
    cookie_secure: bool
    # Where the web app is reached, for the set-password links admins copy.
    public_url: str

    @property
    def runs_dir(self):
        return os.path.join(self.data_dir, "runs")


@lru_cache
def get():
    return Settings(
        database_url=os.environ.get(
            "LITSTORM_DATABASE_URL", "postgresql+psycopg://litstorm:litstorm@localhost:5432/litstorm"
        ),
        data_dir=os.environ.get("LITSTORM_DATA_DIR", os.path.abspath("data")),
        secret_key=_read_file(os.environ.get("LITSTORM_SECRET_KEY_FILE"))
        or os.environ.get("LITSTORM_SECRET_KEY", ""),
        bootstrap_code=_read_file(os.environ.get("LITSTORM_BOOTSTRAP_CODE_FILE")),
        cookie_secure=os.environ.get("LITSTORM_COOKIE_SECURE", "false").lower() == "true",
        public_url=os.environ.get("LITSTORM_PUBLIC_URL", "http://localhost:8090").rstrip("/"),
    )
