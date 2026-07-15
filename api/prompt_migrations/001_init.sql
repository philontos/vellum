-- Deployment-wide Prompt control plane. Drafts are mutable working state;
-- releases and their complete item snapshots are append-only.
CREATE TABLE IF NOT EXISTS prompt_releases (
  id                     INTEGER PRIMARY KEY AUTOINCREMENT,
  version                INTEGER NOT NULL UNIQUE,
  note                   TEXT NOT NULL DEFAULT '',
  rollback_of_release_id INTEGER,
  published_by           TEXT,
  published_at           TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (rollback_of_release_id) REFERENCES prompt_releases(id)
);

CREATE TABLE IF NOT EXISTS prompt_release_items (
  release_id     INTEGER NOT NULL,
  prompt_key     TEXT NOT NULL,
  content        TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  PRIMARY KEY (release_id, prompt_key),
  FOREIGN KEY (release_id) REFERENCES prompt_releases(id)
);
CREATE INDEX IF NOT EXISTS idx_prompt_release_items_key
  ON prompt_release_items(prompt_key, release_id);

CREATE TABLE IF NOT EXISTS prompt_workspace (
  id                      INTEGER PRIMARY KEY CHECK (id = 1),
  active_release_id       INTEGER,
  draft_source_release_id INTEGER,
  revision                INTEGER NOT NULL DEFAULT 0,
  updated_at              TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (active_release_id) REFERENCES prompt_releases(id),
  FOREIGN KEY (draft_source_release_id) REFERENCES prompt_releases(id)
);
INSERT OR IGNORE INTO prompt_workspace(id) VALUES (1);

CREATE TABLE IF NOT EXISTS prompt_drafts (
  prompt_key TEXT PRIMARY KEY,
  content    TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS prompt_audit_events (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  action        TEXT NOT NULL CHECK (
                  action IN ('draft_saved', 'published', 'release_loaded')
                ),
  actor_user_id TEXT,
  prompt_key    TEXT,
  release_id    INTEGER,
  details_json  TEXT NOT NULL DEFAULT '{}',
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (release_id) REFERENCES prompt_releases(id)
);
CREATE INDEX IF NOT EXISTS idx_prompt_audit_created
  ON prompt_audit_events(created_at, id);
