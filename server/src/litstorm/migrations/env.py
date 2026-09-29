"""Alembic's entry point: migrate the database named in the settings."""

from alembic import context

from litstorm import db
from litstorm.db.models import Base

target_metadata = Base.metadata


def run_migrations_online():
    with db.engine().connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
