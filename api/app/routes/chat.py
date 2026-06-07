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


class ChatIn(BaseModel):
    message: str


@router.post("/chat")
async def chat(body: ChatIn):
    await ingest.persist_user(body.message)
    messages = await assemble.build_messages(query=body.message)
    cfg = resolve_structured_llm_config()

    async def gen():
        final = ""
        async for ev in respond.stream(messages):
            if ev["type"] == "delta":
                yield f"data: {json.dumps({'delta': ev['text']}, ensure_ascii=False)}\n\n"
            elif ev["type"] == "final":
                final = ev["content"]
        ingest.persist_assistant(final)
        traces.record(
            turn=None, stage="chat", model=cfg.get("model"),
            params={"provider": cfg.get("provider")},
            prompt=json.dumps(messages, ensure_ascii=False), output=final,
            prompt_tokens=None, completion_tokens=None, duration_ms=None,
        )
        asyncio.create_task(runner.run_pending())  # background, non-blocking
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
