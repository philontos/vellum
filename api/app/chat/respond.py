"""Stream one assistant reply. Hybrid recall: A retrieval is already baked into
the assembled `messages` (system reference). B = the recall_memory tool offered
here; if the provider does not support tools it will 400 and auto-degrade to
plain text (A-only). Yields {"type":"delta","text":...} events during the
stream and one {"type":"final","content":...} at the end."""
import json

from app import config
from app.chat.tools import recall, registry
from app.llm import client as llm


def _build_registry() -> registry.ToolRegistry:
    reg = registry.ToolRegistry()
    recall.register_into(reg)
    return reg


async def stream(messages: list[dict]):
    reg = _build_registry()
    tools = reg.schemas()
    convo = list(messages)
    content_parts: list[str] = []

    for _hop in range(config.recall_max_hops() + 1):
        assistant_msg = None
        finish = "stop"
        async for ev in llm.chat_with_tools_stream(messages=convo, tools=tools, stage="chat"):
            if ev["type"] == "content_delta":
                content_parts.append(ev["delta"])
                yield {"type": "delta", "text": ev["delta"]}
            elif ev["type"] == "done":
                assistant_msg = ev["message"]
                finish = ev["finish_reason"]

        if assistant_msg is not None:
            convo.append(assistant_msg)
        if finish != "tool_calls" or not reg:
            break

        # run each requested tool, append results, loop for another model round
        for tc in assistant_msg.get("tool_calls") or []:
            fn = tc["function"]
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            result = await reg.adispatch(fn["name"], args)
            convo.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

    yield {"type": "final", "content": "".join(content_parts)}
