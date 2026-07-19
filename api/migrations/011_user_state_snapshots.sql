-- Append-only, user-grounded snapshots of time-sensitive state. These are kept
-- separate from durable facts and traits so a temporary feeling or intention is
-- never silently promoted into a permanent description of the user.
CREATE TABLE IF NOT EXISTS user_state_snapshots (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  stream      TEXT    NOT NULL,
  user_turn   INTEGER NOT NULL UNIQUE,
  inquiry_id  INTEGER,
  snapshot_json TEXT  NOT NULL,
  run_id      TEXT,
  created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (inquiry_id) REFERENCES inquiries(id)
);
CREATE INDEX IF NOT EXISTS idx_user_state_snapshots_turn
  ON user_state_snapshots(user_turn DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_user_state_snapshots_stream_turn
  ON user_state_snapshots(stream, user_turn DESC, id DESC);
