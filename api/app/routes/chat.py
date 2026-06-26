"""POST /chat — SSE stream. Persists the user turn, assembles context (A recall
baked in), streams the reply (B tool available), persists the assistant turn,
records one diagnostic trace."""
import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app import config
from app.chat import assemble, ingest, persona, respond
from app.llm.client import resolve_structured_llm_config
from app.model_loop import runner
from app.store import traces

router = APIRouter()

_background_tasks: set[asyncio.Task] = set()


def _track(task: asyncio.Task) -> None:
    _background_tasks.add(task)

    def _done(t: asyncio.Task) -> None:
        _background_tasks.discard(t)
        if not t.cancelled() and t.exception() is not None:
            import traceback
            traceback.print_exception(t.exception())

    task.add_done_callback(_done)


class ChatIn(BaseModel):
    message: str
    persona: str | None = None  # prompt-side mode; unknown/None falls back to the default


@router.post("/chat")
async def chat(body: ChatIn):
    # Validate against the known modes; an unknown value quietly uses the default
    # so a stale client can never wedge the chat on a missing persona.
    pname = body.persona if body.persona in persona.available() else config.persona_name()
    await ingest.persist_user(body.message)
    messages = await assemble.build_messages(query=body.message, persona_name=pname)
    cfg = resolve_structured_llm_config()

    async def gen():
        final = ""
        reasoning = None
        tool_calls = None
        prompt_tokens = completion_tokens = duration_ms = None
        try:
            async for ev in respond.stream(messages):
                if ev["type"] == "delta":
                    yield f"data: {json.dumps({'delta': ev['text']}, ensure_ascii=False)}\n\n"
                elif ev["type"] == "reasoning":
                    yield f"data: {json.dumps({'reasoning': ev['text']}, ensure_ascii=False)}\n\n"
                elif ev["type"] == "tool_start":
                    tool = {"phase": "start", "name": ev["name"], "query": ev.get("query", "")}
                    yield f"data: {json.dumps({'tool': tool}, ensure_ascii=False)}\n\n"
                elif ev["type"] == "tool_end":
                    tool = {"phase": "end", "name": ev["name"], "ok": ev.get("ok", True)}
                    yield f"data: {json.dumps({'tool': tool}, ensure_ascii=False)}\n\n"
                elif ev["type"] == "final":
                    final = ev["content"]
                    reasoning = ev.get("reasoning")
                    tool_calls = ev.get("tool_calls")
                    prompt_tokens = ev.get("prompt_tokens")
                    completion_tokens = ev.get("completion_tokens")
                    duration_ms = ev.get("duration_ms")
            assistant = ingest.persist_assistant(final)
            traces.record(
                turn=assistant["turn"], stage="chat", model=cfg.get("model"),
                params={"provider": cfg.get("provider"), "persona": pname},
                prompt=json.dumps(messages, ensure_ascii=False), output=final,
                reasoning=reasoning, tool_calls=tool_calls,
                prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                duration_ms=duration_ms,
            )
            _track(asyncio.create_task(runner.run_pending()))  # background, non-blocking
        except Exception as exc:
            # Surface the failure as an SSE frame instead of letting the generator
            # raise: an uncaught raise sends no error and no [DONE], so the client's
            # stream reader hangs forever. The full error is already in traces.
            yield f"data: {json.dumps({'error': str(exc) or exc.__class__.__name__}, ensure_ascii=False)}\n\n"
        finally:
            # Always terminate the stream so the client can stop waiting.
            yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
