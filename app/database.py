"""SQLite engine, session factory, and a small forward-only migrator."""

from __future__ import annotations

import logging

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app import config

log = logging.getLogger("wordle.db")

engine = create_engine(
    config.DB_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _configure_sqlite(dbapi_connection, _record) -> None:
    """Pragmas SQLAlchemy does not set for us.

    Foreign keys are off by default in SQLite, which meant every ForeignKey in
    the schema was decorative: a meaning lookup with an invented profile_id
    happily created an orphan progress row. WAL lets a read proceed while a
    write is in flight, which matters because the guess handler and the stats
    dashboard run on different threads of the same process.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("PRAGMA journal_mode = WAL")
    cursor.execute("PRAGMA synchronous = NORMAL")
    cursor.execute("PRAGMA busy_timeout = 5000")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency for a request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Columns added after the first release, with the DDL to add them. `create_all`
# only creates missing *tables*, so without this an existing database keeps its
# old shape and every query naming a new column fails at runtime.
_ADDED_COLUMNS: dict[str, dict[str, str]] = {
    "profiles": {
        "theme": "ALTER TABLE profiles ADD COLUMN theme VARCHAR(24) NOT NULL DEFAULT 'system'",
    },
    "games": {
        "resigned": "ALTER TABLE games ADD COLUMN resigned INTEGER NOT NULL DEFAULT 0",
        "hints_used": "ALTER TABLE games ADD COLUMN hints_used INTEGER NOT NULL DEFAULT 0",
    },
    "guesses": {
        "turn": "ALTER TABLE guesses ADD COLUMN turn INTEGER NOT NULL DEFAULT 0",
        "result": "ALTER TABLE guesses ADD COLUMN result VARCHAR(16) NOT NULL DEFAULT ''",
    },
    "dictionary_cache": {
        "found": "ALTER TABLE dictionary_cache ADD COLUMN found INTEGER NOT NULL DEFAULT 1",
    },
}


# Columns the model no longer has. They must be dropped rather than ignored:
# each is NOT NULL with no database-side default, so once the model stops
# supplying a value every INSERT fails with a constraint error.
#   games.meaning_opened  never read or written by any code path
#   guesses.result_json   superseded by the packed `result` column, backfilled
#                         from it before the drop below
_DROPPED_COLUMNS: dict[str, tuple[str, ...]] = {
    "games": ("meaning_opened",),
    "guesses": ("result_json",),
}


def _drop_legacy_columns(connection) -> None:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    for table, columns in _DROPPED_COLUMNS.items():
        if table not in tables:
            continue
        existing = {col["name"] for col in inspector.get_columns(table)}
        for name in columns:
            if name not in existing:
                continue
            try:
                connection.execute(text(f"ALTER TABLE {table} DROP COLUMN {name}"))
                log.info("migrating: dropped %s.%s", table, name)
            except Exception as exc:
                raise RuntimeError(
                    f"cannot drop the obsolete column {table}.{name}: {exc}\n"
                    "DROP COLUMN needs SQLite 3.35 (2021) or newer. Upgrade Python, "
                    "or move oflaz_wordle.db aside to start from a fresh database."
                ) from exc


def _migrate(connection) -> None:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())

    for table, columns in _ADDED_COLUMNS.items():
        if table not in tables:
            continue  # create_all will build it with the right shape
        existing = {col["name"] for col in inspector.get_columns(table)}
        for name, ddl in columns.items():
            if name not in existing:
                log.info("migrating: adding %s.%s", table, name)
                connection.execute(text(ddl))

    if "guesses" not in tables:
        return

    columns = {col["name"] for col in inspect(connection).get_columns("guesses")}

    # Backfill the packed result from the old JSON blob, then the turn number
    # from insertion order. Rows written before this release have turn 0.
    if "result_json" in columns:
        rows = connection.execute(
            text("SELECT id, result_json FROM guesses WHERE result = '' OR result IS NULL")
        ).fetchall()
        for row_id, blob in rows:
            packed = _pack_legacy_result(blob)
            if packed:
                connection.execute(
                    text("UPDATE guesses SET result = :r WHERE id = :i"),
                    {"r": packed, "i": row_id},
                )
        if rows:
            log.info("migrating: packed %d legacy guess results", len(rows))

    stale = connection.execute(text("SELECT COUNT(*) FROM guesses WHERE turn = 0")).scalar()
    if stale:
        connection.execute(
            text(
                """
                UPDATE guesses SET turn = (
                    SELECT COUNT(*) FROM guesses AS earlier
                    WHERE earlier.game_id = guesses.game_id AND earlier.id <= guesses.id
                ) WHERE turn = 0
                """
            )
        )
        log.info("migrating: numbered %d legacy guess turns", stale)

    # Only now that everything has been read out of them.
    _drop_legacy_columns(connection)


def _pack_legacy_result(blob: str | None) -> str:
    import json

    if not blob:
        return ""
    try:
        marks = json.loads(blob)
    except (ValueError, TypeError):
        return ""
    digits = {"gray": "0", "grey": "0", "yellow": "1", "green": "2"}
    return "".join(digits.get(mark, "0") for mark in marks) if isinstance(marks, list) else ""


def init_db() -> None:
    """Create missing tables, then bring existing ones up to date. Idempotent."""
    from app import models  # noqa: F401  (populates Base.metadata)

    with engine.begin() as connection:
        _migrate(connection)
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        _migrate(connection)
