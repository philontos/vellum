"""as-of date for a span: the calendar date of its most recent message. Facts
extraction uses it to ground relative time ("今年", "年底") against a real date so
the model never has to invent a year."""
from app.model_loop._span import span_asof_date, span_text
from app.store import memory
from app.store.db import get_conn


def test_span_asof_date_is_latest_message_date(migrated_db):
    memory.append_message("user", "hi")
    memory.append_message("assistant", "hello")
    rows = memory.messages_in_turn_range(0, 1)
    assert span_asof_date(0, 1) == rows[-1]["created_at"][:10]   # YYYY-MM-DD


def test_span_asof_date_none_when_span_empty(migrated_db):
    assert span_asof_date(5, 9) is None


def test_modeling_span_adds_local_time_to_each_user_turn(migrated_db, monkeypatch):
    monkeypatch.setenv("VELLUM_TIMEZONE", "Asia/Shanghai")
    first = memory.append_message("user", "上午想到一件事")
    memory.append_message("assistant", "你说")
    second = memory.append_message("user", "下午继续")
    with get_conn() as conn:
        conn.execute(
            "UPDATE messages SET created_at = ? WHERE id = ?",
            ("2026-07-14 01:15:00", first["id"]),
        )
        conn.execute(
            "UPDATE messages SET created_at = ? WHERE id = ?",
            ("2026-07-14 05:45:00", second["id"]),
        )

    span = span_text(0, 2)

    assert "application-generated" in span
    assert 'datetime="2026-07-14T09:15:00+08:00"' in span
    assert 'period="morning"' in span
    assert 'period="afternoon"' in span
    assert 'elapsed_since_previous_user="4h 30m"' in span
    assert "[turn=0 role=user use=evidence]" in span
    assert "[turn=1 role=assistant use=context_only]" in span
    assert "[turn=2 role=user use=evidence]" in span
    assert "你说" in span


def test_span_asof_date_uses_configured_local_calendar(migrated_db, monkeypatch):
    monkeypatch.setenv("VELLUM_TIMEZONE", "Asia/Shanghai")
    msg = memory.append_message("user", "close to midnight")
    with get_conn() as conn:
        conn.execute(
            "UPDATE messages SET created_at = ? WHERE id = ?",
            ("2026-07-13 17:30:00", msg["id"]),
        )

    assert span_asof_date(0, 0) == "2026-07-14"
