"""Slash-command control for the Feishu adapter — the mobile equivalent of the
web's mode picker. Pure and SDK-free (operates on plain strings + the known mode
set) so the command grammar is unit-tested without lark-oapi or the store.

Grammar (a leading '/' marks command intent; everything else is ordinary chat):
  /mode            → show the current mode and the available ones
  /mode <name>     → switch to <name> (or report it as unknown, listing valid ones)
  /<name>          → shortcut switch, e.g. /freud, /neutral
  /help            → same as bare /mode
  /<anything else> → help (so a typo'd command never leaks to the brain as chat)
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Outcome:
    reply: str            # text to send back to the chat
    new_mode: str | None  # when set, the adapter remembers it as the active mode


def _status(current: str, available: set[str]) -> str:
    return (f"当前模式: {current}\n"
            f"可用: {', '.join(sorted(available))}\n"
            f"切换: /<模式名> 或 /mode <模式名>")


def _switched(name: str) -> str:
    return f"已切换到 {name} 模式"


def handle(text: str, *, current: str, available: set[str],
           default: str) -> Outcome | None:
    """Classify one inbound message. Returns None for ordinary chat (the adapter
    forwards it to the brain under `current`), or an Outcome describing the reply
    and any mode change for a command."""
    text = text.strip()
    if not text.startswith("/"):
        return None

    parts = text[1:].split()
    cmd = parts[0].lower() if parts else ""
    arg = parts[1].lower() if len(parts) > 1 else None

    if cmd in ("mode", "help", ""):
        if arg is None:
            return Outcome(reply=_status(current, available), new_mode=None)
        if arg in available:
            return Outcome(reply=_switched(arg), new_mode=arg)
        return Outcome(reply=f"未知模式: {arg}\n{_status(current, available)}",
                       new_mode=None)

    if cmd in available:                         # /freud, /neutral shortcuts
        return Outcome(reply=_switched(cmd), new_mode=cmd)

    return Outcome(reply=f"未知命令: /{cmd}\n{_status(current, available)}",
                   new_mode=None)
