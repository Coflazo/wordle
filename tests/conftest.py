"""Shared fixtures. Every test runs against a throwaway database."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# Point the app at a temp database before anything imports app.config.
_TMP_DB = Path(tempfile.mkdtemp(prefix="wordle-test-")) / "test.db"
os.environ["WORDLE_DB_URL"] = f"sqlite:///{_TMP_DB}"
# Never reach for the sidecar in tests; the in-process path is what CI has.
os.environ.setdefault("WORDLE_SOLVERD_SOCKET", str(_TMP_DB.parent / "absent.sock"))

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine, init_db  # noqa: E402
from app.main import app  # noqa: E402

# Build the schema now, so tests that never touch the client fixture (and so
# never run the app's lifespan) still have tables for the cleanup fixture.
init_db()


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_tables():
    """Truncate between tests so counts and streaks start from zero."""
    yield
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.exec_driver_sql(f"DELETE FROM {table.name}")


@pytest.fixture
def profile(client):
    response = client.post(
        "/api/profiles",
        json={"name": "Test", "preferred_language": "en", "avatar_config": {}},
    )
    assert response.status_code == 201, response.text
    return response.json()
