"""Translate between Feishu message payloads and plain text. Deliberately
SDK-free (operates on the raw `message_type` + `content` strings the event
carries) so the in/out shaping is unit-testable without lark-oapi installed."""
import json


def extract_text(message_type: str, content: str) -> str | None:
    """The plain user text from a Feishu message event, or None when it is not
    usable text — a non-text message type, an empty/whitespace body, or content
    that does not parse. The adapter ignores None (nothing to answer)."""
    if message_type != "text":
        return None
    try:
        text = json.loads(content).get("text", "")
    except (json.JSONDecodeError, TypeError, AttributeError):
        return None
    text = (text or "").strip()
    return text or None


def text_content(text: str) -> str:
    """The `content` JSON string for sending a Feishu text message. Keeps unicode
    literal (ensure_ascii=False) so Chinese is sent as-is, not \\uXXXX."""
    return json.dumps({"text": text}, ensure_ascii=False)
