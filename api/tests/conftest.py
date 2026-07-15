import pytest

from app.store import db
from app.prompts import db as prompt_db


@pytest.fixture
def migrated_db(tmp_path, monkeypatch):
    """Point VELLUM_DATA_DIR at a tmp dir and run migrations. Yields nothing —
    DAOs open their own short-lived connections via config paths."""
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))
    db.run_migrations()
    prompt_db.run_migrations()
    yield tmp_path
