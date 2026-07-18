"""SQLite persistence for owner-managed model candidate credentials."""
import hashlib
import json
import secrets
import time

from app.prompts import db


VALIDATION_TTL_SECONDS = 10 * 60


class ValidationTicketError(ValueError):
    pass


class ValidationConfigChangedError(ValidationTicketError):
    pass


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _config_digest(candidate_id: str, config: dict[str, str]) -> str:
    canonical = json.dumps(
        {
            "candidate_id": candidate_id,
            "base_url": config["base_url"],
            "api_key": config["api_key"],
            "model": config["model"],
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def get_config(candidate_id: str) -> dict | None:
    db.run_migrations()
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM model_candidate_configs WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
    return dict(row) if row is not None else None


def get_route(scenario: str) -> dict | None:
    db.run_migrations()
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM model_routes WHERE scenario = ?", (scenario,),
        ).fetchone()
    return dict(row) if row is not None else None


def get_capabilities(candidate_id: str) -> dict | None:
    db.run_migrations()
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT capabilities_json FROM model_candidate_capabilities "
            "WHERE candidate_id = ?", (candidate_id,),
        ).fetchone()
    return json.loads(row["capabilities_json"]) if row is not None else None


def save_route(
    scenario: str,
    candidate_id: str,
    actor_user_id: str | None,
) -> dict:
    db.run_migrations()
    with db.get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO model_routes(scenario, candidate_id, updated_by) "
            "VALUES (?, ?, ?) ON CONFLICT(scenario) DO UPDATE SET "
            "candidate_id = excluded.candidate_id, "
            "updated_by = excluded.updated_by, updated_at = datetime('now')",
            (scenario, candidate_id, actor_user_id),
        )
        conn.execute(
            "INSERT INTO model_candidate_audit_events"
            "(action, candidate_id, actor_user_id, details_json) VALUES (?, ?, ?, ?)",
            (
                "route_saved", candidate_id, actor_user_id,
                json.dumps({"scenario": scenario}, ensure_ascii=False),
            ),
        )
        saved = conn.execute(
            "SELECT * FROM model_routes WHERE scenario = ?", (scenario,),
        ).fetchone()
    return dict(saved)


def record_key_reveal(candidate_id: str, actor_user_id: str | None) -> None:
    """Audit an explicit owner secret read without recording the secret."""
    db.run_migrations()
    with db.get_conn() as conn:
        conn.execute(
            "INSERT INTO model_candidate_audit_events"
            "(action, candidate_id, actor_user_id) VALUES (?, ?, ?)",
            ("key_revealed", candidate_id, actor_user_id),
        )


def issue_validation(
    candidate_id: str,
    config: dict[str, str],
    actor_user_id: str | None,
    capabilities: dict | None = None,
) -> dict[str, str]:
    db.run_migrations()
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    expires_at = now + VALIDATION_TTL_SECONDS
    with db.get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "DELETE FROM model_candidate_validation_capabilities WHERE token_hash IN ("
            "SELECT token_hash FROM model_candidate_validation_tickets "
            "WHERE expires_at <= ?)", (now,),
        )
        conn.execute(
            "DELETE FROM model_candidate_validation_tickets WHERE expires_at <= ?",
            (now,),
        )
        conn.execute(
            "INSERT INTO model_candidate_validation_tickets"
            "(token_hash, candidate_id, config_sha256, actor_user_id, expires_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                _token_digest(token), candidate_id,
                _config_digest(candidate_id, config), actor_user_id, expires_at,
            ),
        )
        created_at = conn.execute(
            "SELECT created_at FROM model_candidate_validation_tickets "
            "WHERE token_hash = ?", (_token_digest(token),),
        ).fetchone()["created_at"]
        conn.execute(
            "INSERT INTO model_candidate_validation_capabilities"
            "(token_hash, capabilities_json) VALUES (?, ?)",
            (
                _token_digest(token),
                json.dumps(capabilities or {}, ensure_ascii=False),
            ),
        )
        conn.execute(
            "INSERT INTO model_candidate_audit_events"
            "(action, candidate_id, actor_user_id, details_json) VALUES (?, ?, ?, ?)",
            (
                "validated", candidate_id, actor_user_id,
                json.dumps({"model": config["model"]}, ensure_ascii=False),
            ),
        )
    return {"token": token, "validated_at": created_at}


def save_validated(
    candidate_id: str,
    config: dict[str, str],
    validation_token: str,
    actor_user_id: str | None,
) -> dict:
    db.run_migrations()
    now = int(time.time())
    digest = _token_digest(validation_token)
    with db.get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM model_candidate_validation_tickets "
            "WHERE token_hash = ?", (digest,),
        ).fetchone()
        if row is None or row["expires_at"] <= now:
            conn.execute(
                "DELETE FROM model_candidate_validation_capabilities "
                "WHERE token_hash = ?", (digest,),
            )
            conn.execute(
                "DELETE FROM model_candidate_validation_tickets WHERE token_hash = ?",
                (digest,),
            )
            raise ValidationTicketError(
                "Validate this configuration successfully before saving it."
            )
        if row["candidate_id"] != candidate_id or row["actor_user_id"] != actor_user_id:
            raise ValidationTicketError(
                "Validate this configuration successfully before saving it."
            )
        if row["config_sha256"] != _config_digest(candidate_id, config):
            raise ValidationConfigChangedError(
                "The configuration changed after validation; validate it again."
            )
        capability_row = conn.execute(
            "SELECT capabilities_json FROM model_candidate_validation_capabilities "
            "WHERE token_hash = ?", (digest,),
        ).fetchone()

        conn.execute(
            "INSERT INTO model_candidate_configs"
            "(candidate_id, base_url, api_key, model, verified_at, updated_by) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(candidate_id) DO UPDATE SET "
            "base_url = excluded.base_url, api_key = excluded.api_key, "
            "model = excluded.model, verified_at = excluded.verified_at, "
            "updated_by = excluded.updated_by, updated_at = datetime('now')",
            (
                candidate_id, config["base_url"], config["api_key"],
                config["model"], row["created_at"], actor_user_id,
            ),
        )
        capabilities_json = (
            capability_row["capabilities_json"] if capability_row is not None else "{}"
        )
        conn.execute(
            "INSERT INTO model_candidate_capabilities"
            "(candidate_id, config_sha256, capabilities_json) VALUES (?, ?, ?) "
            "ON CONFLICT(candidate_id) DO UPDATE SET "
            "config_sha256 = excluded.config_sha256, "
            "capabilities_json = excluded.capabilities_json, "
            "verified_at = datetime('now')",
            (candidate_id, _config_digest(candidate_id, config), capabilities_json),
        )
        conn.execute(
            "DELETE FROM model_candidate_validation_capabilities WHERE token_hash = ?",
            (digest,),
        )
        conn.execute(
            "DELETE FROM model_candidate_validation_tickets WHERE token_hash = ?",
            (digest,),
        )
        conn.execute(
            "INSERT INTO model_candidate_audit_events"
            "(action, candidate_id, actor_user_id, details_json) VALUES (?, ?, ?, ?)",
            (
                "saved", candidate_id, actor_user_id,
                json.dumps(
                    {
                        "base_url": config["base_url"],
                        "model": config["model"],
                    },
                    ensure_ascii=False,
                ),
            ),
        )
        saved = conn.execute(
            "SELECT * FROM model_candidate_configs WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
    return dict(saved)
