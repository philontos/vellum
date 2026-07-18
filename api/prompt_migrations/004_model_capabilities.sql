-- Capability results are bound to the exact validated configuration. They are
-- separate from credentials so the committed config migration stays immutable.
CREATE TABLE IF NOT EXISTS model_candidate_validation_capabilities (
  token_hash        TEXT PRIMARY KEY,
  capabilities_json TEXT NOT NULL,
  FOREIGN KEY (token_hash)
    REFERENCES model_candidate_validation_tickets(token_hash)
);
CREATE TABLE IF NOT EXISTS model_candidate_capabilities (
  candidate_id      TEXT PRIMARY KEY,
  config_sha256     TEXT NOT NULL,
  capabilities_json TEXT NOT NULL,
  verified_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
