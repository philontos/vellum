-- Memory layer: global ordered stream
CREATE TABLE IF NOT EXISTS messages (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  turn        INTEGER NOT NULL UNIQUE,
  role        TEXT    NOT NULL CHECK (role IN ('user','assistant')),
  content     TEXT    NOT NULL,
  created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS summaries (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  start_turn  INTEGER NOT NULL,
  end_turn    INTEGER NOT NULL,
  content     TEXT    NOT NULL,
  created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS vector_refs (
  label       INTEGER PRIMARY KEY AUTOINCREMENT,
  ref_type    TEXT    NOT NULL CHECK (ref_type IN ('message','summary')),
  ref_id      INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS cursors (
  concern       TEXT PRIMARY KEY CHECK (concern IN ('facts','trait','summary','dossier')),
  through_turn  INTEGER NOT NULL DEFAULT -1,
  updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
INSERT OR IGNORE INTO cursors(concern) VALUES ('facts'),('trait'),('summary'),('dossier');

-- Personal-model layer
CREATE TABLE IF NOT EXISTS dossier (
  id          INTEGER PRIMARY KEY CHECK (id = 1),
  content     TEXT    NOT NULL DEFAULT '',
  updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
INSERT OR IGNORE INTO dossier(id, content) VALUES (1, '');

CREATE TABLE IF NOT EXISTS trait_current (
  dimension     TEXT PRIMARY KEY,
  content_json  TEXT    NOT NULL,
  sample_count  INTEGER NOT NULL DEFAULT 0,
  updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS trait_history (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  dimension     TEXT    NOT NULL,
  content_json  TEXT    NOT NULL,
  taken_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_trait_history_dim ON trait_history(dimension, taken_at);

CREATE TABLE IF NOT EXISTS facts (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  text        TEXT    NOT NULL,
  status      TEXT    NOT NULL DEFAULT 'active' CHECK (status IN ('active','superseded')),
  source_turn INTEGER,
  created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
  updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_facts_status ON facts(status);

-- Observability layer
CREATE TABLE IF NOT EXISTS traces (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  turn               INTEGER,
  stage              TEXT    NOT NULL,
  model              TEXT,
  params             TEXT,
  prompt             TEXT,
  output             TEXT,
  prompt_tokens      INTEGER,
  completion_tokens  INTEGER,
  duration_ms        INTEGER,
  pinned             INTEGER NOT NULL DEFAULT 0,
  created_at         TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_traces_created ON traces(created_at);
