from app.store import db


def test_migrations_create_all_tables(migrated_db):
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    names = {r["name"] for r in rows}
    expected = {
        "messages", "summaries", "vector_refs", "cursors",
        "dossier", "portrait_claims", "trait_current", "trait_history", "trait_evidence",
        "facts", "traces",
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


def test_portrait_claim_migration_rewinds_dossier_for_grounded_backfill(migrated_db):
    with db.get_conn() as conn:
        conn.execute(
            "UPDATE cursors SET through_turn = 99 WHERE concern = 'dossier'"
        )
        conn.execute(
            "DELETE FROM schema_migrations WHERE name = '007_portrait_claims.sql'"
        )

    db.run_migrations()

    with db.get_conn() as conn:
        cursor = conn.execute(
            "SELECT through_turn FROM cursors WHERE concern = 'dossier'"
        ).fetchone()["through_turn"]
    assert cursor == -1
