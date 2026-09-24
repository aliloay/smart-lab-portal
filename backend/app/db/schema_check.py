"""
Startup schema guard.

A database managed by Alembic must be migrated by Alembic. If the code is
newer than the database, `Base.metadata.create_all` would create the new
tables but not the new columns on existing ones - and would then make the
real migration fail with "table already exists". So when an alembic_version
table is present, startup compares it with the migration head and refuses to
run against an out-of-date schema, naming the command that fixes it.

A database with no alembic_version table (the test suite, a throwaway
quickstart) keeps the create_all convenience.
"""
from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

ALEMBIC_DIR = Path(__file__).resolve().parents[2] / "alembic"


class SchemaOutOfDate(RuntimeError):
    pass


def is_alembic_managed(engine: Engine) -> bool:
    return inspect(engine).has_table("alembic_version")


def check_schema(engine: Engine) -> None:
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    script = ScriptDirectory(str(ALEMBIC_DIR))
    heads = set(script.get_heads())
    with engine.connect() as conn:
        current = set(MigrationContext.configure(conn).get_current_heads())
    if current != heads:
        raise SchemaOutOfDate(
            f"Database schema is at {sorted(current) or 'nothing'} but the code "
            f"expects {sorted(heads)}. Run `alembic upgrade head` in backend/ "
            f"before starting the API.")
