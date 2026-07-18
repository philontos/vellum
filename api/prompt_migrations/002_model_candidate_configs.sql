-- Deployment-wide model credentials managed by an owner. Validation tickets
-- hold hashes only and expire quickly; raw API keys exist only in the final
-- configuration row (and follow the prompt database's SQLCipher-at-rest mode).
CREATE TABLE IF NOT EXISTS model_candidate_configs (
  candidate_id TEXT PRIMARY KEY,
  base_url     TEXT NOT NULL,
  api_key      TEXT NOT NULL,
  model        TEXT NOT NULL,
  verified_at  TEXT NOT NULL,
  updated_by   TEXT,
  updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS model_candidate_validation_tickets (
  token_hash    TEXT PRIMARY KEY,
  candidate_id  TEXT NOT NULL,
  config_sha256 TEXT NOT NULL,
  actor_user_id TEXT,
  expires_at    INTEGER NOT NULL,
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_model_candidate_tickets_expiry
  ON model_candidate_validation_tickets(expires_at);

CREATE TABLE IF NOT EXISTS model_candidate_audit_events (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  action        TEXT NOT NULL,
  candidate_id  TEXT NOT NULL,
  actor_user_id TEXT,
  details_json  TEXT NOT NULL DEFAULT '{}',
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_model_candidate_audit_created
  ON model_candidate_audit_events(created_at, id);
