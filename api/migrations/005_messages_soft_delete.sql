-- Manual soft-delete of stray history turns (failed retries, debug noise). A
-- deleted message keeps its row and turn (so turns never reuse and ordering is
-- preserved) but is filtered out of every model-facing read path — recent tail,
-- scroll-up window, turn-range hydration, and single-message resolve. Its vector
-- is left intact so a delete is reversible (UPDATE ... SET deleted_at = NULL);
-- retrieval skips it for free because the resolve step now returns NULL.
ALTER TABLE messages ADD COLUMN deleted_at TEXT;
