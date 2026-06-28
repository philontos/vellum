"""The Feishu adapter's `_handle` seam: a command message switches the in-memory
mode and replies in-chat without bothering the brain; ordinary text is forwarded
to `converse.reply` under whatever mode is currently active. (The lark-oapi wiring
around this is covered by the live smoke test, not here.)"""
import json


def _text(s: str) -> str:
    return json.dumps({"text": s})


async def test_command_switches_mode_and_replies_without_calling_brain(monkeypatch):
    from app.feishu import adapter

    monkeypatch.setattr(adapter, "_mode", None)          # start at default

    called = {"brain": False}

    async def fake_reply(text, persona_name=None):
        called["brain"] = True
        return "should not happen"

    sent = {}

    def fake_send(chat_id, text):
        sent["chat_id"], sent["text"] = chat_id, text

    monkeypatch.setattr(adapter.converse, "reply", fake_reply)
    monkeypatch.setattr(adapter, "_send", fake_send)

    await adapter._handle("text", _text("/freud"), "chat1")

    assert called["brain"] is False                      # command never hits the brain
    assert sent["text"] == "已切换到 freud 模式"
    assert adapter._current() == "freud"                 # mode remembered


async def test_plain_text_is_forwarded_to_brain_under_current_mode(monkeypatch):
    from app.feishu import adapter

    monkeypatch.setattr(adapter, "_mode", "freud")       # already switched earlier

    seen = {}

    async def fake_reply(text, persona_name=None):
        seen["text"], seen["persona"] = text, persona_name
        return "答复"

    sent = {}

    def fake_send(chat_id, text):
        sent["text"] = text

    monkeypatch.setattr(adapter.converse, "reply", fake_reply)
    monkeypatch.setattr(adapter, "_send", fake_send)

    await adapter._handle("text", _text("我最近很焦虑"), "chat1")

    assert seen == {"text": "我最近很焦虑", "persona": "freud"}
    assert sent["text"] == "答复"


async def test_switch_then_chat_uses_the_switched_mode(monkeypatch):
    """End-to-end of the two seams: after a /freud command, the next ordinary
    message is answered in freud — the whole point of mobile mode switching."""
    from app.feishu import adapter

    monkeypatch.setattr(adapter, "_mode", None)

    seen = {}

    async def fake_reply(text, persona_name=None):
        seen["persona"] = persona_name
        return "ok"

    monkeypatch.setattr(adapter.converse, "reply", fake_reply)
    monkeypatch.setattr(adapter, "_send", lambda *a: None)

    await adapter._handle("text", _text("/freud"), "chat1")
    await adapter._handle("text", _text("继续聊"), "chat1")

    assert seen["persona"] == "freud"
