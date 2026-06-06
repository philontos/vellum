"""Personal-model DAO: dossier (one row), trait_current (live, overwritten) +
trait_history (append-only snapshot), and facts (pin board with lifecycle).

Note: trait snapshotting is 'archive-on-create' — set_trait writes the live row
AND immediately appends the same value to history, so the latest value is never
lost even if no further update ever happens."""
import json

from app.store.db import get_conn


def get_dossier() -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT content FROM dossier WHERE id = 1").fetchone()
    return row["content"] if row else ""


def set_dossier(content: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE dossier SET content = ?, updated_at = datetime('now') WHERE id = 1",
            (content,),
        )


def set_trait(dimension: str, content: dict, sample_count: int) -> None:
    blob = json.dumps(content, ensure_ascii=False)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO trait_current(dimension, content_json, sample_count) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(dimension) DO UPDATE SET "
            "content_json = excluded.content_json, "
            "sample_count = excluded.sample_count, updated_at = datetime('now')",
            (dimension, blob, sample_count),
        )
        # archive-on-create: freeze a snapshot the moment this value becomes current
        conn.execute(
            "INSERT INTO trait_history(dimension, content_json) VALUES (?, ?)",
            (dimension, blob),
        )


def get_trait(dimension: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM trait_current WHERE dimension = ?", (dimension,)
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["content_json"] = json.loads(d["content_json"])
    return d


def get_trait_history(dimension: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM trait_history WHERE dimension = ? ORDER BY id", (dimension,)
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["content_json"] = json.loads(d["content_json"])
        out.append(d)
    return out


def add_fact(text: str, source_turn: int | None = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO facts(text, source_turn) VALUES (?, ?)", (text, source_turn)
        )
        return cur.lastrowid


def active_facts() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM facts WHERE status = 'active' ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


def supersede_fact(fact_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE facts SET status = 'superseded', updated_at = datetime('now') "
            "WHERE id = ?",
            (fact_id,),
        )
