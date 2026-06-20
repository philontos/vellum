"""POST /chat — SSE stream. Persists the user turn, assembles context (A recall
baked in), streams the reply (B tool available), persists the assistant turn,
records one diagnostic trace."""
import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.chat import assemble, ingest, respond
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


@router.post("/chat")
async def chat(body: ChatIn):
    await ingest.persist_user(body.message)
    messages = await assemble.build_messages(query=body.message)
    cfg = resolve_structured_llm_config()

    async def gen():
        final = ""
        reasoning = None
        prompt_tokens = completion_tokens = duration_ms = None
        try:
            async for ev in respond.stream(messages):
                if ev["type"] == "delta":
                    yield f"data: {json.dumps({'delta': ev['text']}, ensure_ascii=False)}\n\n"
                elif ev["type"] == "final":
                    final = ev["content"]
                    reasoning = ev.get("reasoning")
                    prompt_tokens = ev.get("prompt_tokens")
                    completion_tokens = ev.get("completion_tokens")
                    duration_ms = ev.get("duration_ms")
            ingest.persist_assistant(final)
            traces.record(
                turn=None, stage="chat", model=cfg.get("model"),
                params={"provider": cfg.get("provider")},
                prompt=json.dumps(messages, ensure_ascii=False), output=final,
                reasoning=reasoning,
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
