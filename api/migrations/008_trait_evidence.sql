-- Durable, rebuildable evidence behind conversational trait projections.  Traces
-- are diagnostic and may be pruned; this ledger is part of the personal model.
-- Natural-language evidence remains in per-account SQLite, never in the vector
-- index.  episode_key makes a retried trait batch idempotent.
CREATE TABLE IF NOT EXISTS trait_evidence (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  dimension      TEXT    NOT NULL,
  subdimension   TEXT    NOT NULL,
  episode_key    TEXT    NOT NULL,
  direction      TEXT    NOT NULL CHECK (direction IN ('support','oppose','sacrifice')),
  strength       REAL    NOT NULL CHECK (strength >= 0 AND strength <= 1),
  confidence     REAL    NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
  basis          TEXT    NOT NULL CHECK (
                   basis IN (
                     'costly_choice','tradeoff','repeated_behavior','self_statement',
                     'aspiration','emotion','legacy'
                   )
                 ),
  episode        TEXT    NOT NULL,
  evidence       TEXT    NOT NULL,
  counterpart    TEXT,
  start_turn     INTEGER,
  end_turn       INTEGER,
  occurrences    INTEGER NOT NULL DEFAULT 1 CHECK (occurrences > 0),
  model_version  TEXT    NOT NULL DEFAULT 'schwartz-v2',
  observed_at    TEXT    NOT NULL DEFAULT (datetime('now')),
  created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_trait_evidence_episode
  ON trait_evidence(dimension, subdimension, episode_key);
CREATE INDEX IF NOT EXISTS idx_trait_evidence_dimension_time
  ON trait_evidence(dimension, observed_at, id);
