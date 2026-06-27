-- Per-mode context streams. The LIVE conversation context (recent tail + recall)
-- is split per stream so switching modes (e.g. daily ↔ counseling) never drags one
-- mode's transcript into another. The distilled user model (facts / traits / dossier)
-- stays GLOBAL and is co-built from every stream. Summaries (the recall handle + the
-- diary timeline) are per-stream. The stream key is the persona name; all existing
-- rows belong to the original 'neutral' stream.
ALTER TABLE messages  ADD COLUMN stream TEXT NOT NULL DEFAULT 'neutral';
ALTER TABLE summaries ADD COLUMN stream TEXT NOT NULL DEFAULT 'neutral';

-- Per-stream tail / scroll-up / range scans all filter by stream then order by turn.
CREATE INDEX IF NOT EXISTS idx_messages_stream_turn ON messages(stream, turn);

-- Per-stream summary progress. The global `cursors` table has a CHECK on `concern`,
-- so per-stream summary cursors live in their own table. Seed the 'neutral' stream
-- from wherever the old global summary cursor had reached, so already-digested
-- history is not re-summarized.
CREATE TABLE IF NOT EXISTS summary_cursors (
  stream        TEXT PRIMARY KEY,
  through_turn  INTEGER NOT NULL DEFAULT -1,
  updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
INSERT OR IGNORE INTO summary_cursors(stream, through_turn)
  SELECT 'neutral', COALESCE((SELECT through_turn FROM cursors WHERE concern = 'summary'), -1);
