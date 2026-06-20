import json

from app.feishu import parse


def test_extract_text_returns_text_payload():
    assert parse.extract_text("text", '{"text":"hello"}') == "hello"


def test_extract_text_strips_whitespace():
    assert parse.extract_text("text", '{"text":"  hi there  "}') == "hi there"


def test_extract_text_none_for_blank_text():
    assert parse.extract_text("text", '{"text":"   "}') is None


def test_extract_text_none_for_non_text_message():
    assert parse.extract_text("image", '{"image_key":"img_v2_x"}') is None


def test_extract_text_none_for_malformed_content():
    assert parse.extract_text("text", "not json at all") is None


def test_text_content_is_feishu_text_json_preserving_unicode():
    out = parse.text_content("你好 vellum")
    assert json.loads(out) == {"text": "你好 vellum"}
    assert "你好" in out                      # not \u-escaped
