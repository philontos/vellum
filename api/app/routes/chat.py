"""POST /chat — adapt orchestrator events to the existing SSE contract."""
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.chat import orchestrator


router = APIRouter()


class ChatIn(BaseModel):
    message: str
    persona: str | None = None


@router.post("/chat")
async def chat(body: ChatIn):
    async def gen():
        try:
            async for event in orchestrator.turn_events(
                body.message, persona_name=body.persona,
            ):
                kind = event["type"]
                if kind == "delta":
                    payload = {"delta": event["text"]}
                elif kind == "reasoning":
                    payload = {"reasoning": event["text"]}
                elif kind == "tool_start":
                    payload = {"tool": {
                        "phase": "start", "name": event["name"],
                        "query": event.get("query", ""),
                    }}
                elif kind == "tool_end":
                    payload = {"tool": {
                        "phase": "end", "name": event["name"],
                        "ok": event.get("ok", True),
                    }}
                else:
                    continue
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        except Exception as exc:
            payload = {"error": str(exc) or exc.__class__.__name__}
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
