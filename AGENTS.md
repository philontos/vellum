# Vellum — repo rules for AI coding agents

- Single-user, local, data-isolated. No multi-user / accounts / SaaS.
- Text lives only in SQLite. The HNSW index holds embeddings + integer labels only.
- Canonical enums are English (`role`, `status`, `ref_type`, `concern`, dimension keys).
- Prompts default to English and instruct "match the user's language"; never pin output language.
- Migrations are forward-only and idempotent; never edit a committed migration, add a new one.
- TDD: write the failing test first. Small files, single responsibility.
- Design source of truth: `docs/specs/2026-06-06-vellum-design.md`.
