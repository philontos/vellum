"""Personal-model DAO: dossier (one row), trait_current (live, overwritten) +
trait_history (append-only snapshot), and facts (pin board with lifecycle).

Note: trait snapshotting is 'archive-on-create' — set_trait writes the live row
AND immediately appends the same value to history, so the latest value is never
lost even if no further update ever happens."""
import json

from app.store.db import get_conn


class FactConflictError(ValueError):
    """A manual edit would duplicate another active Fact."""


def _normalized_fact(text: str) -> str:
    return " ".join(text.split()).casefold()


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


def replace_active_fact(fact_id: int, text: str) -> dict | None:
    """Atomically replace one active Fact while preserving its source turn.

    The old row stays as lifecycle history (`superseded`), matching automatic
    Fact updates and compaction. None means the requested row is no longer active.
    """
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        current = conn.execute(
            "SELECT * FROM facts WHERE id = ? AND status = 'active'",
            (fact_id,),
        ).fetchone()
        if current is None:
            return None
        normalized = _normalized_fact(text)
        others = conn.execute(
            "SELECT text FROM facts WHERE status = 'active' AND id <> ?",
            (fact_id,),
        ).fetchall()
        if any(_normalized_fact(row["text"]) == normalized for row in others):
            raise FactConflictError("an equivalent active Fact already exists")
        inserted = conn.execute(
            "INSERT INTO facts(text, source_turn) VALUES (?, ?)",
            (text, current["source_turn"]),
        )
        changed = conn.execute(
            "UPDATE facts SET status = 'superseded', updated_at = datetime('now') "
            "WHERE id = ? AND status = 'active'",
            (fact_id,),
        )
        if changed.rowcount != 1:
            raise RuntimeError("Fact changed during manual edit")
        row = conn.execute(
            "SELECT * FROM facts WHERE id = ?", (inserted.lastrowid,)
        ).fetchone()
        return dict(row)


def delete_active_fact(fact_id: int) -> bool:
    """Retire one active Fact; repeated or unknown deletes are safe no-ops."""
    with get_conn() as conn:
        changed = conn.execute(
            "UPDATE facts SET status = 'superseded', updated_at = datetime('now') "
            "WHERE id = ? AND status = 'active'",
            (fact_id,),
        )
        return changed.rowcount == 1


def all_facts() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM facts ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def all_traits() -> list[dict]:
    with get_conn() as conn:
        dims = [r["dimension"] for r in
                conn.execute("SELECT dimension FROM trait_current ORDER BY dimension")]
    return [get_trait(d) for d in dims]


def get_dossier_row() -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT content, updated_at FROM dossier WHERE id = 1").fetchone()
    return dict(row) if row else {"content": "", "updated_at": None}
