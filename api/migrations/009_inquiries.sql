-- Durable Inquiry state. Current state and its append-only event history live in
-- the account-scoped vellum.db; raw text never leaves SQLite.
CREATE TABLE IF NOT EXISTS inquiries (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  stream            TEXT    NOT NULL,
  status            TEXT    NOT NULL CHECK (
                      status IN ('exploring','reviewing','paused','closed')
                    ),
  revision          INTEGER NOT NULL DEFAULT 1,
  goal              TEXT    NOT NULL DEFAULT '',
  ledger_json       TEXT    NOT NULL,
  opened_turn       INTEGER NOT NULL,
  last_turn         INTEGER NOT NULL,
  closed_turn       INTEGER,
  parent_inquiry_id INTEGER,
  created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
  updated_at        TEXT    NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (parent_inquiry_id) REFERENCES inquiries(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_inquiries_one_current_stream
  ON inquiries(stream) WHERE status IN ('exploring','reviewing');
CREATE INDEX IF NOT EXISTS idx_inquiries_stream_updated
  ON inquiries(stream, updated_at, id);

CREATE TABLE IF NOT EXISTS inquiry_events (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  inquiry_id      INTEGER NOT NULL,
  run_id          TEXT,
  user_turn       INTEGER NOT NULL,
  action          TEXT    NOT NULL CHECK (
                    action IN ('open','inquire','synthesize','resume','pause','close')
                  ),
  revision_before INTEGER NOT NULL,
  revision_after  INTEGER NOT NULL,
  status_after    TEXT    NOT NULL CHECK (
                    status_after IN ('exploring','reviewing','paused','closed')
                  ),
  ledger_json     TEXT    NOT NULL,
  decision_json   TEXT    NOT NULL,
  created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (inquiry_id) REFERENCES inquiries(id),
  UNIQUE (inquiry_id, revision_after)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_inquiry_events_run
  ON inquiry_events(run_id) WHERE run_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_inquiry_events_inquiry
  ON inquiry_events(inquiry_id, revision_after);
