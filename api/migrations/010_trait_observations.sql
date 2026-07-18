-- Personality extraction progress is independent for each dimension. Accepted
-- observations retain exact user evidence; aggregate scores remain in the
-- existing trait_current/history tables.
CREATE TABLE IF NOT EXISTS trait_cursors (
  dimension    TEXT PRIMARY KEY,
  through_turn INTEGER NOT NULL DEFAULT -1,
  updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS trait_batches (
  dimension     TEXT NOT NULL,
  start_turn    INTEGER NOT NULL,
  end_turn      INTEGER NOT NULL,
  accepted_count INTEGER NOT NULL DEFAULT 0,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (dimension, start_turn, end_turn)
);

CREATE TABLE IF NOT EXISTS trait_observations (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  dimension       TEXT NOT NULL,
  sub_dimension   TEXT NOT NULL,
  start_turn      INTEGER NOT NULL,
  end_turn        INTEGER NOT NULL,
  score           REAL NOT NULL CHECK (score >= 0 AND score <= 100),
  confidence      REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
  evidence_turn   INTEGER NOT NULL,
  evidence_quote  TEXT NOT NULL,
  created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_trait_observations_dimension
  ON trait_observations(dimension, id);
CREATE INDEX IF NOT EXISTS idx_trait_observations_turn
  ON trait_observations(evidence_turn, id);
