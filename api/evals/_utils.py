from app.store import memory


def seed_user_lines(lines: list[str]) -> int:
    """Append user lines to the stream; return the last turn (or -1 if none)."""
    end = -1
    for line in lines:
        end = memory.append_message("user", line)["turn"]
    return end
