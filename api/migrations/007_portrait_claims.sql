-- Grounded, lifecycle-managed evidence for the narrative dossier. The prose
-- dossier is now a derived view over active portrait claims plus durable facts;
-- raw assistant replies never flow into the render step.
CREATE TABLE IF NOT EXISTS portrait_claims (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  claim_type    TEXT    NOT NULL CHECK (
                  claim_type IN (
                    'value', 'pattern', 'decision_style', 'current_state', 'self_concept'
                  )
                ),
  text          TEXT    NOT NULL,
  basis         TEXT    NOT NULL CHECK (basis IN ('explicit', 'confirmed', 'inferred')),
  evidence_json TEXT    NOT NULL DEFAULT '[]',
  status        TEXT    NOT NULL DEFAULT 'active' CHECK (status IN ('active','superseded')),
  source_turn   INTEGER,
  created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
  updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_portrait_claims_status
  ON portrait_claims(status);

-- Existing installations have a prose dossier but no grounded claim ledger.
-- Rewind once so the next dossier pass backfills claims from the user history
-- before replacing that prose with the new evidence-derived rendering.
UPDATE cursors SET through_turn = -1 WHERE concern = 'dossier';
