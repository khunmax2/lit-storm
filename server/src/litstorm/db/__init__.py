"""The database connection, shared by the API and the Worker."""

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from litstorm import settings


@lru_cache
def engine():
    return create_engine(settings.get().database_url, pool_pre_ping=True)


@lru_cache
def sessions():
    return sessionmaker(engine(), expire_on_commit=False)
