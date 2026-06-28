"""One chat turn, collected into a string — the same brain as POST /chat
(persist the user turn, assemble context with recall baked in, stream the reply
through the tool loop, persist the assistant turn, record one diagnostic trace,
kick off background modeling) for callers that cannot consume an SSE stream,
such as the Feishu adapter."""
import asyncio
import json

from app import config
from app.chat import assemble, ingest, persona, respond
from app.llm.client import resolve_structured_llm_config
from app.model_loop import runner
from app.store import traces

_background_tasks: set[asyncio.Task] = set()


def _track(task: asyncio.Task) -> None:
    """Keep a strong ref so a fired-and-forgotten task isn't GC'd mid-flight, and
    surface its failure instead of swallowing it (mirrors routes/chat.py)."""
    _background_tasks.add(task)

    def _done(t: asyncio.Task) -> None:
        _background_tasks.discard(t)
        if not t.cancelled() and t.exception() is not None:
            import traceback
            traceback.print_exception(t.exception())

    task.add_done_callback(_done)


async def reply(text: str, persona_name: str | None = None) -> str:
    """Run `text` through the chat pipeline and return the assistant's reply.
    `persona_name` selects the prompt-side mode (the Feishu adapter passes the
    mode the user picked via a slash command); unknown/None falls back to the
    default, mirroring POST /chat. The mode name is also the context stream, so
    both turns persist into it — switching modes on mobile keeps the same per-mode
    partitioning the web has. Records one chat trace and schedules background
    modeling — the same observability + learning POST /chat performs, sans SSE."""
    pname = persona_name if persona_name in persona.available() else config.persona_name()
    await ingest.persist_user(text, stream=pname)
    messages = await assemble.build_messages(query=text, persona_name=pname)
    cfg = resolve_structured_llm_config()

    final = ""
    reasoning = None
    tool_calls = None
    prompt_tokens = completion_tokens = duration_ms = None
    async for ev in respond.stream(messages, stream=pname):
        if ev["type"] == "final":
            final = ev["content"]
            reasoning = ev.get("reasoning")
            tool_calls = ev.get("tool_calls")
            prompt_tokens = ev.get("prompt_tokens")
            completion_tokens = ev.get("completion_tokens")
            duration_ms = ev.get("duration_ms")

    assistant = ingest.persist_assistant(final, stream=pname)
    traces.record(
        turn=assistant["turn"], stage="chat", model=cfg.get("model"),
        params={"provider": cfg.get("provider"), "persona": pname},
        prompt=json.dumps(messages, ensure_ascii=False), output=final,
        reasoning=reasoning, tool_calls=tool_calls,
        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
        duration_ms=duration_ms,
    )
    _track(asyncio.create_task(runner.run_pending()))  # background, non-blocking
    return final
