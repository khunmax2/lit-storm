"""The database connection, shared by the API and the Worker."""

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from litstorm import settings

# Connections a process may hold: the API's requests (admitted up to this
# many at once, api/deps.py) or the Worker's thread per Run. Postgres allows
# 200 (stack/compose.yml): the Worker and up to 4 API processes.
POOL_SIZE = 10
MAX_OVERFLOW = 20
POOL_TIMEOUT = 30


def capacity():
    return POOL_SIZE + MAX_OVERFLOW


@lru_cache
def engine():
    return create_engine(
        settings.get().database_url,
        pool_pre_ping=True,
        pool_size=POOL_SIZE,
        max_overflow=MAX_OVERFLOW,
        pool_timeout=POOL_TIMEOUT,
    )


@lru_cache
def sessions():
    return sessionmaker(engine(), expire_on_commit=False)
