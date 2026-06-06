from app.store import db


def test_migrations_create_all_tables(migrated_db):
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    names = {r["name"] for r in rows}
    expected = {
        "messages", "summaries", "vector_refs", "cursors",
        "dossier", "trait_current", "trait_history", "facts", "traces",
        "schema_migrations",
    }
    assert expected <= names


def test_migrations_idempotent(migrated_db):
    # Running again must not raise and must not duplicate applied rows.
    db.run_migrations()
    with db.get_conn() as conn:
        n = conn.execute(
            "SELECT COUNT(*) AS c FROM schema_migrations WHERE name='001_init.sql'"
        ).fetchone()["c"]
    assert n == 1


def test_cursors_seeded(migrated_db):
    with db.get_conn() as conn:
        rows = conn.execute("SELECT concern FROM cursors").fetchall()
    assert {r["concern"] for r in rows} == {"facts", "trait", "summary", "dossier"}
