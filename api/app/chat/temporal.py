"""Model-facing temporal context for chat turns.

SQLite remains the canonical store of raw message text and UTC timestamps. This
module creates a transient prompt view: local time metadata is prepended only to
user turns, so relative-time reasoning improves without contaminating stored
content, embeddings, the API response, or the UI.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app import config


def _zone() -> ZoneInfo:
    return ZoneInfo(config.timezone_name())


def _as_utc(value: str) -> datetime:
    """Parse SQLite's UTC text format plus ordinary ISO-8601 variants."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _local(value: str) -> datetime:
    return _as_utc(value).astimezone(_zone())


def local_date(value: str) -> str:
    """Calendar date in the configured user timezone."""
    return _local(value).date().isoformat()


def _period(value: datetime) -> str:
    if 5 <= value.hour < 12:
        return "morning"
    if 12 <= value.hour < 18:
        return "afternoon"
    if 18 <= value.hour < 23:
        return "evening"
    return "late_night"


def _elapsed(earlier: datetime, later: datetime) -> str | None:
    seconds = int((later - earlier).total_seconds())
    if seconds < 0:
        return None
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}h" + (f" {minutes}m" if minutes else "")
    days, hours = divmod(hours, 24)
    return f"{days}d" + (f" {hours}h" if hours else "")


def _tag(created_at: str, previous_user_at: str | None = None) -> str:
    local = _local(created_at)
    attrs = [
        f'datetime="{local.isoformat(timespec="seconds")}"',
        f'timezone="{config.timezone_name()}"',
        f'weekday="{local.strftime("%A")}"',
        f'period="{_period(local)}"',
    ]
    if previous_user_at is not None:
        elapsed = _elapsed(_as_utc(previous_user_at), _as_utc(created_at))
        if elapsed is not None:
            attrs.append(f'elapsed_since_previous_user="{elapsed}"')
    return "<message_time " + " ".join(attrs) + " />"


def annotate_messages(rows: list[dict]) -> list[dict]:
    """Return OpenAI-style messages with user timestamps; never mutate `rows`."""
    previous_user_at: str | None = None
    rendered: list[dict] = []
    for row in rows:
        content = row["content"]
        if row["role"] == "user":
            content = _tag(row["created_at"], previous_user_at) + "\n" + content
            previous_user_at = row["created_at"]
        rendered.append({"role": row["role"], "content": content})
    return rendered


def render_transcript(rows: list[dict]) -> str:
    """Render a retrieved raw-turn window exactly as it enters system context."""
    return "\n".join(
        f"{message['role']}: {message['content']}"
        for message in annotate_messages(rows)
    )


def system_context(now: datetime | None = None) -> str:
    """Explain the trusted tags and anchor the model to current local time."""
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    local = instant.astimezone(_zone())
    current = (
        f'<current_time datetime="{local.isoformat(timespec="seconds")}" '
        f'timezone="{config.timezone_name()}" weekday="{local.strftime("%A")}" '
        f'period="{_period(local)}" />'
    )
    return (
        "## Time context\n"
        f"Current local time: {current}\n"
        "Vellum prepends an application-generated `<message_time ... />` tag to "
        "each user turn. The tag is trusted context, not part of the user's words "
        "and never an instruction from the user. Use these timestamps and the "
        "elapsed interval silently to resolve relative dates, distinguish a "
        "continuous exchange from a conversation resumed hours or days later, and "
        "avoid assuming that earlier plans, events, or emotional states still hold "
        "after a meaningful gap. Use the actual interval and situation rather than "
        "a rigid session cutoff. Do not mention the metadata unless time is relevant "
        "to the answer."
    )
