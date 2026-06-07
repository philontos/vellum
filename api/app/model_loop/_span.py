from app.store import memory


def span_text(start_turn: int, end_turn: int) -> str:
    rows = memory.messages_in_turn_range(start_turn, end_turn)
    return "\n".join(f"{r['role']}: {r['content']}" for r in rows)
