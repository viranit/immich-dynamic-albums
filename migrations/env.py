"""Alembic env for Flask-Migrate."""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, create_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import the Flask app to get the metadata and the real DATABASE_URL.
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app, db as _db
_app = create_app()
target_metadata = _db.metadata

# Always use the URL from Flask config — never the alembic.ini placeholder.
_db_url = _app.config['SQLALCHEMY_DATABASE_URI']


def run_migrations_offline() -> None:
    context.configure(
        url=_db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(_db_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
