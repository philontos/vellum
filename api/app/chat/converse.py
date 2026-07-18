"""Collected adapter over the same orchestrated chat pipeline used by HTTP."""
from app.chat import orchestrator


async def reply(text: str, persona_name: str | None = None) -> str:
    final = ""
    async for event in orchestrator.turn_events(text, persona_name=persona_name):
        if event["type"] == "final":
            final = event["content"]
    return final
