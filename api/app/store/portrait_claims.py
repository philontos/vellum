"""Grounded portrait-claim ledger used to render the prose dossier."""
import json

from app.store.db import get_conn


def _normalized(text: str) -> str:
    return " ".join(text.split()).casefold()


def _row(value) -> dict:
    item = dict(value)
    try:
        evidence = json.loads(item.pop("evidence_json"))
    except (TypeError, json.JSONDecodeError):
        evidence = []
    item["evidence"] = evidence if isinstance(evidence, list) else []
    return item


def add(*, claim_type: str, text: str, basis: str, evidence: list[dict],
        source_turn: int | None) -> int:
    """Add one active claim, returning an equivalent active row when present."""
    cleaned = text.strip()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, text FROM portrait_claims "
            "WHERE status = 'active' AND claim_type = ?",
            (claim_type,),
        ).fetchall()
        normalized = _normalized(cleaned)
        for row in rows:
            if _normalized(row["text"]) == normalized:
                return row["id"]
        cursor = conn.execute(
            "INSERT INTO portrait_claims"
            "(claim_type, text, basis, evidence_json, source_turn) "
            "VALUES (?, ?, ?, ?, ?)",
            (claim_type, cleaned, basis,
             json.dumps(evidence, ensure_ascii=False), source_turn),
        )
        return cursor.lastrowid


def active() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM portrait_claims WHERE status = 'active' ORDER BY id"
        ).fetchall()
    return [_row(row) for row in rows]


def all() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM portrait_claims ORDER BY id").fetchall()
    return [_row(row) for row in rows]


def supersede(claim_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE portrait_claims SET status = 'superseded', "
            "updated_at = datetime('now') WHERE id = ? AND status = 'active'",
            (claim_id,),
        )
