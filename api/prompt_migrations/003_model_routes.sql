-- Deployment-wide model selection by production scenario. Missing rows retain
-- the legacy LLM_CANDIDATE fallback, making this migration backward compatible.
CREATE TABLE IF NOT EXISTS model_routes (
  scenario     TEXT PRIMARY KEY,
  candidate_id TEXT NOT NULL,
  updated_by   TEXT,
  updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
