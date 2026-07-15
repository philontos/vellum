from app.chat import temporal
from app.store import memory

_TIME_NOTE = (
    "Evidence note: the bracketed turn/role/use markers and each "
    "`<message_time ... />` tag below are trusted, application-generated metadata. "
    "User turns are evidence; assistant turns are context only."
)


def span_text(start_turn: int, end_turn: int, roles=None, stream: str | None = None) -> str:
    """Render a turn span as `role: content` lines. `roles` (e.g. ("user",))
    filters to specific roles — trait extraction passes user-only so the AI's own
    replies don't get scored as the user's personality; summary/dossier/facts keep
    both sides (they summarize the conversation, which needs assistant turns).
    `stream` None spans all streams (global modeling co-builds from every stream);
    a value scopes to one stream (per-stream summary digests)."""
    rows = memory.messages_in_turn_range(start_turn, end_turn, stream=stream)
    if roles is not None:
        rows = [r for r in rows if r["role"] in roles]
    if not rows:
        return ""
    annotated = temporal.annotate_messages(rows)
    blocks = []
    for row, message in zip(rows, annotated):
        usage = "evidence" if row["role"] == "user" else "context_only"
        blocks.append(
            f"[turn={row['turn']} role={row['role']} use={usage}]\n"
            f"{message['content']}"
        )
    return _TIME_NOTE + "\n\n" + "\n\n".join(blocks)


def span_asof_date(start_turn: int, end_turn: int) -> str | None:
    """The calendar date (YYYY-MM-DD) of the most recent message in the span, or
    None when the span has no messages. Facts extraction passes this so the model
    can resolve relative time ("今年", "年底") against a real date instead of
    inventing a year. messages_in_turn_range returns rows oldest->newest, so the
    last row is the latest point in the span — the right 'as of' anchor."""
    rows = memory.messages_in_turn_range(start_turn, end_turn)
    if not rows:
        return None
    return temporal.local_date(rows[-1]["created_at"])
