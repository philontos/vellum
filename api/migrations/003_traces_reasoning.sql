-- Reasoning models (DeepSeek-reasoner, Claude thinking, ...) return their chain
-- of thought in a separate field (reasoning_content / reasoning), distinct from
-- the answer content. Capture it as part of the trace for inspection. NULL when
-- the model didn't reason or the provider hides it.
ALTER TABLE traces ADD COLUMN reasoning TEXT;
