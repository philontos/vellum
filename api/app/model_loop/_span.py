from app.store import memory


def span_text(start_turn: int, end_turn: int, roles=None) -> str:
    """Render a turn span as `role: content` lines. `roles` (e.g. ("user",))
    filters to specific roles — trait extraction passes user-only so the AI's own
    replies don't get scored as the user's personality; summary/dossier/facts keep
    both sides (they summarize the conversation, which needs assistant turns)."""
    rows = memory.messages_in_turn_range(start_turn, end_turn)
    if roles is not None:
        rows = [r for r in rows if r["role"] in roles]
    return "\n".join(f"{r['role']}: {r['content']}" for r in rows)
