"""Personal-model DAO: dossier (one row), trait_current (live, overwritten) +
trait_history (append-only snapshot), and facts (pin board with lifecycle).

Note: trait snapshotting is 'archive-on-create' — set_trait writes the live row
AND immediately appends the same value to history, so the latest value is never
lost even if no further update ever happens."""
import hashlib
import json

from app.store.db import get_conn


class FactConflictError(ValueError):
    """A manual edit would duplicate another active Fact."""


class TraitRebuildConflictError(RuntimeError):
    """A staged trait rebuild no longer matches its source/live projection."""


_TRAIT_EVIDENCE_BASIS_RANK = {
    "legacy": 0,
    "emotion": 1,
    "aspiration": 2,
    "self_statement": 3,
    "repeated_behavior": 4,
    "tradeoff": 5,
    "costly_choice": 6,
}


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


def add_trait_evidence(records: list[dict]) -> int:
    """Append canonical evidence; repeated discussion refines one episode.

    Return the number of genuinely new episodes.  A follow-up with the same
    semantic episode key may raise strength/confidence and refresh its quote, but
    never increments occurrences, so five clarifying turns do not become five
    independent samples.
    """
    if not records:
        return 0
    inserted = 0
    with get_conn() as conn:
        for record in records:
            current = conn.execute(
                "SELECT id, strength, confidence, basis FROM trait_evidence "
                "WHERE dimension = ? AND subdimension = ? AND episode_key = ?",
                (record["dimension"], record["subdimension"], record["episode_key"]),
            ).fetchone()
            if current is not None:
                stronger = (
                    _TRAIT_EVIDENCE_BASIS_RANK.get(record["basis"], -1),
                    float(record["confidence"]), float(record["strength"])
                ) >= (
                    _TRAIT_EVIDENCE_BASIS_RANK.get(current["basis"], -1),
                    float(current["confidence"]), float(current["strength"])
                )
                conn.execute(
                    "UPDATE trait_evidence SET "
                    "strength = MAX(strength, ?), confidence = MAX(confidence, ?), "
                    "direction = CASE WHEN ? THEN ? ELSE direction END, "
                    "basis = CASE WHEN ? THEN ? ELSE basis END, "
                    "evidence = CASE WHEN ? THEN ? ELSE evidence END, "
                    "counterpart = CASE WHEN ? THEN ? ELSE counterpart END, "
                    "start_turn = CASE WHEN ? IS NULL THEN start_turn "
                    "WHEN start_turn IS NULL THEN ? ELSE MIN(start_turn, ?) END, "
                    "end_turn = CASE WHEN ? IS NULL THEN end_turn "
                    "WHEN end_turn IS NULL THEN ? ELSE MAX(end_turn, ?) END, "
                    "model_version = CASE WHEN ? THEN ? ELSE model_version END, "
                    "observed_at = datetime('now') WHERE id = ?",
                    (
                        record["strength"], record["confidence"], stronger,
                        record["direction"], stronger, record["basis"], stronger,
                        record["evidence"], stronger, record.get("counterpart"),
                        record.get("start_turn"), record.get("start_turn"),
                        record.get("start_turn"), record.get("end_turn"),
                        record.get("end_turn"), record.get("end_turn"), stronger,
                        record.get("model_version", "schwartz-v2"), current["id"],
                    ),
                )
                continue
            conn.execute(
                "INSERT INTO trait_evidence("
                "dimension, subdimension, episode_key, direction, strength, confidence, "
                "basis, episode, evidence, counterpart, start_turn, end_turn, occurrences, "
                "model_version, observed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                "COALESCE(?, datetime('now')))",
                (
                    record["dimension"], record["subdimension"], record["episode_key"],
                    record["direction"], record["strength"], record["confidence"],
                    record["basis"], record.get("episode") or record["episode_key"],
                    record["evidence"], record.get("counterpart"),
                    record.get("start_turn"), record.get("end_turn"),
                    record.get("occurrences", 1), record.get("model_version", "schwartz-v2"),
                    record.get("observed_at"),
                ),
            )
            inserted += 1
    return inserted


def get_trait_evidence(dimension: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM trait_evidence WHERE dimension = ? ORDER BY id",
            (dimension,),
        ).fetchall()
    return [dict(row) for row in rows]


def _query_digest(conn, sql: str, args: tuple = ()) -> str:
    """Hash query rows without ever copying private text outside SQLite/process."""
    digest = hashlib.sha256()
    for row in conn.execute(sql, args):
        digest.update(b"\x1e")
        for value in row:
            if value is None:
                digest.update(b"N")
                continue
            encoded = str(value).encode("utf-8")
            digest.update(b"V")
            digest.update(len(encoded).to_bytes(8, "big"))
            digest.update(encoded)
    return digest.hexdigest()


def _trait_rebuild_guard(conn, dimension: str) -> dict[str, str]:
    """Fingerprint both immutable rebuild input and the live target state."""
    history = _query_digest(
        conn,
        "SELECT id, turn, role, content, created_at, deleted_at, stream "
        "FROM messages ORDER BY id",
    )
    target = hashlib.sha256()
    target.update(_query_digest(
        conn,
        "SELECT dimension, content_json, sample_count, updated_at "
        "FROM trait_current WHERE dimension = ?",
        (dimension,),
    ).encode("ascii"))
    target.update(_query_digest(
        conn,
        "SELECT id, dimension, content_json, taken_at "
        "FROM trait_history WHERE dimension = ? ORDER BY id",
        (dimension,),
    ).encode("ascii"))
    target.update(_query_digest(
        conn,
        "SELECT id, dimension, subdimension, episode_key, direction, strength, "
        "confidence, basis, episode, evidence, counterpart, start_turn, end_turn, "
        "occurrences, model_version, observed_at, created_at "
        "FROM trait_evidence WHERE dimension = ? ORDER BY id",
        (dimension,),
    ).encode("ascii"))
    return {"history": history, "trait": target.hexdigest()}


def trait_rebuild_guard(dimension: str) -> dict[str, str]:
    """Capture a consistent optimistic-lock token before expensive extraction."""
    with get_conn() as conn:
        conn.execute("BEGIN")
        return _trait_rebuild_guard(conn, dimension)


def replace_trait_projection(
    dimension: str,
    content: dict,
    sample_count: int,
    history: list[dict],
    evidence: list[dict],
    expected_guard: dict[str, str],
) -> None:
    """Atomically install a fully staged rebuild, or leave the old model intact.

    LLM work happens before this call.  The immediate transaction verifies that
    neither source messages nor this dimension changed while extraction ran, then
    replaces only the requested dimension's projection, snapshots, and ledger.
    """
    blob = json.dumps(content, ensure_ascii=False)
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        actual = _trait_rebuild_guard(conn, dimension)
        if actual["history"] != expected_guard.get("history"):
            raise TraitRebuildConflictError(
                "message history changed during trait rebuild; no changes were applied"
            )
        if actual["trait"] != expected_guard.get("trait"):
            raise TraitRebuildConflictError(
                f"{dimension} trait changed during rebuild; no changes were applied"
            )

        conn.execute("DELETE FROM trait_current WHERE dimension = ?", (dimension,))
        conn.execute("DELETE FROM trait_history WHERE dimension = ?", (dimension,))
        conn.execute("DELETE FROM trait_evidence WHERE dimension = ?", (dimension,))

        for record in evidence:
            conn.execute(
                "INSERT INTO trait_evidence("
                "dimension, subdimension, episode_key, direction, strength, confidence, "
                "basis, episode, evidence, counterpart, start_turn, end_turn, occurrences, "
                "model_version, observed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                "COALESCE(?, datetime('now')))",
                (
                    dimension, record["subdimension"], record["episode_key"],
                    record["direction"], record["strength"], record["confidence"],
                    record["basis"], record.get("episode") or record["episode_key"],
                    record["evidence"], record.get("counterpart"),
                    record.get("start_turn"), record.get("end_turn"),
                    record.get("occurrences", 1),
                    record.get("model_version", "schwartz-v2"),
                    record.get("observed_at"),
                ),
            )

        conn.execute(
            "INSERT INTO trait_current(dimension, content_json, sample_count) "
            "VALUES (?, ?, ?)",
            (dimension, blob, sample_count),
        )
        for snapshot in history:
            snapshot_blob = json.dumps(snapshot["content_json"], ensure_ascii=False)
            conn.execute(
                "INSERT INTO trait_history(dimension, content_json, taken_at) "
                "VALUES (?, ?, COALESCE(?, datetime('now')))",
                (dimension, snapshot_blob, snapshot.get("taken_at")),
            )


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
