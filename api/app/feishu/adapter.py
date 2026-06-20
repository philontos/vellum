"""Feishu (Lark) long-connection adapter.

Receives Feishu **private-chat** messages over a WebSocket long connection and
answers with vellum's brain (`chat.converse.reply`). Runs as a background task in
the API process — deliberately in-process, since that process is the single owner
of the SQLite store and vector index; a second process would contend on both.

Why the indirection: Feishu's long-connection callback is **synchronous and must
return within ~3 seconds**, else the platform retries and the user gets duplicate
answers. An LLM turn takes far longer, so the callback only acks — it hands the
slow work to the app's event loop and returns immediately. The reply is then
pushed back as a *new* message via the send API, not as the callback's return.

This module is SDK glue; its logic seams (`parse.extract_text` / `text_content`,
`converse.reply`) are unit-tested, but the lark-oapi wiring is verified by a live
smoke test against a real Feishu app — see the Feishu setup steps in
api/.env.example.
"""
import asyncio
import traceback

import lark_oapi as lark
from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody

from app import config
from app.chat import converse
from app.feishu.parse import extract_text, text_content

_send_client: lark.Client | None = None


def _client() -> lark.Client:
    """Lazy singleton client for outbound sends (token caching lives here)."""
    global _send_client
    if _send_client is None:
        _send_client = (lark.Client.builder()
                        .app_id(config.feishu_app_id())
                        .app_secret(config.feishu_app_secret())
                        .build())
    return _send_client


def _send(chat_id: str, text: str) -> None:
    """Send a text message to a chat. Synchronous (lark HTTP call); the caller
    runs it off the event loop via asyncio.to_thread."""
    req = (CreateMessageRequest.builder()
           .receive_id_type("chat_id")
           .request_body(CreateMessageRequestBody.builder()
                         .receive_id(chat_id)
                         .msg_type("text")
                         .content(text_content(text))
                         .build())
           .build())
    resp = _client().im.v1.message.create(req)
    if not resp.success():
        print(f"[feishu] send failed: code={resp.code} msg={resp.msg} "
              f"log_id={resp.get_log_id()}")


async def _handle(message_type: str, content: str, chat_id: str) -> None:
    """Answer one message: parse → vellum → send. Never raises (a bad turn must
    not tear down the long connection); failures are reported back in-chat."""
    text = extract_text(message_type, content)
    if not text:
        return
    try:
        answer = await converse.reply(text)
    except Exception as exc:
        traceback.print_exc()
        answer = f"⚠️ {exc.__class__.__name__}: {exc}"
    await asyncio.to_thread(_send, chat_id, answer or "…")


def _make_handler(loop: asyncio.AbstractEventLoop) -> lark.EventDispatcherHandler:
    def on_message(data: lark.im.v1.P2ImMessageReceiveV1) -> None:
        # Runs on the SDK's thread and MUST return within ~3s. Ack fast: schedule
        # the slow turn on the app loop and return; the reply is pushed later.
        msg = data.event.message
        if getattr(msg, "chat_type", "p2p") != "p2p":
            return  # private chats only — no group replies (privacy + no spam)
        asyncio.run_coroutine_threadsafe(
            _handle(msg.message_type, msg.content, msg.chat_id), loop)

    return (lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(on_message)
            .build())


async def run() -> None:
    """Open the long connection and serve until cancelled. Launched as a
    background task from the app lifespan when `config.feishu_enabled()`."""
    loop = asyncio.get_running_loop()
    cli = lark.ws.Client(
        config.feishu_app_id(),
        config.feishu_app_secret(),
        event_handler=_make_handler(loop),
        log_level=lark.LogLevel.INFO,
    )
    # cli.start() runs its own blocking connection loop — keep it off the event
    # loop so the app stays responsive.
    await asyncio.to_thread(cli.start)
