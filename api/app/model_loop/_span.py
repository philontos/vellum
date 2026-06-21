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


def span_asof_date(start_turn: int, end_turn: int) -> str | None:
    """The calendar date (YYYY-MM-DD) of the most recent message in the span, or
    None when the span has no messages. Facts extraction passes this so the model
    can resolve relative time ("今年", "年底") against a real date instead of
    inventing a year. messages_in_turn_range returns rows oldest->newest, so the
    last row is the latest point in the span — the right 'as of' anchor."""
    rows = memory.messages_in_turn_range(start_turn, end_turn)
    if not rows:
        return None
    return rows[-1]["created_at"][:10]
