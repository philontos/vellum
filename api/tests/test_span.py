"""as-of date for a span: the calendar date of its most recent message. Facts
extraction uses it to ground relative time ("今年", "年底") against a real date so
the model never has to invent a year."""
from app.model_loop._span import span_asof_date
from app.store import memory


def test_span_asof_date_is_latest_message_date(migrated_db):
    memory.append_message("user", "hi")
    memory.append_message("assistant", "hello")
    rows = memory.messages_in_turn_range(0, 1)
    assert span_asof_date(0, 1) == rows[-1]["created_at"][:10]   # YYYY-MM-DD


def test_span_asof_date_none_when_span_empty(migrated_db):
    assert span_asof_date(5, 9) is None
