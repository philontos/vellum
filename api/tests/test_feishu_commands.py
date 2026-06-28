"""Feishu slash-command control (mode switching from mobile). `commands.handle`
is pure: it maps an inbound text + the current/available modes to either an
Outcome (a reply to send, optionally a new mode to remember) or None when the
text is ordinary chat to forward to the brain."""

from app.feishu import commands

AVAILABLE = {"neutral", "freud"}


def test_plain_text_is_not_a_command():
    assert commands.handle("我最近总是焦虑", current="neutral",
                           available=AVAILABLE, default="neutral") is None


def test_slash_mode_shows_status_without_switching():
    out = commands.handle("/mode", current="neutral",
                          available=AVAILABLE, default="neutral")
    assert out is not None
    assert out.new_mode is None                 # status query never switches
    assert "neutral" in out.reply and "freud" in out.reply   # lists available


def test_help_shows_status():
    out = commands.handle("/help", current="freud",
                          available=AVAILABLE, default="neutral")
    assert out is not None and out.new_mode is None
    assert "neutral" in out.reply and "freud" in out.reply


def test_slash_mode_with_valid_target_switches():
    out = commands.handle("/mode freud", current="neutral",
                          available=AVAILABLE, default="neutral")
    assert out is not None
    assert out.new_mode == "freud"
    assert "freud" in out.reply


def test_shortcut_switches():
    out = commands.handle("/freud", current="neutral",
                          available=AVAILABLE, default="neutral")
    assert out is not None and out.new_mode == "freud"


def test_neutral_shortcut_switches_back():
    out = commands.handle("/neutral", current="freud",
                          available=AVAILABLE, default="neutral")
    assert out is not None and out.new_mode == "neutral"


def test_invalid_mode_reports_error_and_does_not_switch():
    out = commands.handle("/mode zorro", current="neutral",
                          available=AVAILABLE, default="neutral")
    assert out is not None
    assert out.new_mode is None                 # stays put
    assert "zorro" in out.reply                 # echoes the bad name
    assert "freud" in out.reply                 # offers the valid ones


def test_unknown_slash_command_returns_help():
    out = commands.handle("/wat", current="neutral",
                          available=AVAILABLE, default="neutral")
    assert out is not None
    assert out.new_mode is None
    assert "neutral" in out.reply and "freud" in out.reply


def test_shortcut_is_case_insensitive():
    out = commands.handle("/FREUD", current="neutral",
                          available=AVAILABLE, default="neutral")
    assert out is not None and out.new_mode == "freud"


def test_mode_target_is_case_insensitive():
    out = commands.handle("/mode FREUD", current="neutral",
                          available=AVAILABLE, default="neutral")
    assert out is not None and out.new_mode == "freud"


def test_bare_mode_with_trailing_space_is_status_not_error():
    out = commands.handle("/mode   ", current="neutral",
                          available=AVAILABLE, default="neutral")
    assert out is not None and out.new_mode is None
    assert "neutral" in out.reply
