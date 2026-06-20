"""Stream one assistant reply. Hybrid recall: A retrieval is already baked into
the assembled `messages` (system reference). B = the recall_memory tool offered
here; if the provider does not support tools it will 400 and auto-degrade to
plain text (A-only). Yields {"type":"delta","text":...} events during the
stream and one {"type":"final","content":...} at the end."""
import json

from app import config
from app.chat.tools import recall, registry, websearch
from app.llm import client as llm


def _build_registry() -> registry.ToolRegistry:
    reg = registry.ToolRegistry()
    recall.register_into(reg)
    if config.web_search_enabled():
        websearch.register_into(reg)
    return reg


def _max_hops() -> int:
    """Tool-loop ceiling. Web search needs more rounds to search → cross-check →
    answer, so it lifts the recall-only default when enabled."""
    hops = config.recall_max_hops()
    if config.web_search_enabled():
        hops = max(hops, config.web_search_max_hops())
    return hops


async def stream(messages: list[dict]):
    reg = _build_registry()
    tools = reg.schemas()
    convo = list(messages)
    content_parts: list[str] = []
    reasoning_parts: list[str] = []
    # Accumulate usage/latency across tool-loop hops so the chat trace reflects
    # the whole turn (every round-trip), not just the last one.
    prompt_tokens = completion_tokens = duration_ms = 0

    for _hop in range(_max_hops() + 1):
        assistant_msg = None
        finish = "stop"
        async for ev in llm.chat_with_tools_stream(messages=convo, tools=tools, stage="chat"):
            if ev["type"] == "content_delta":
                content_parts.append(ev["delta"])
                yield {"type": "delta", "text": ev["delta"]}
            elif ev["type"] == "reasoning_delta":
                # Surface the model's thinking live (the trace keeps the full copy
                # via the done event below).
                yield {"type": "reasoning", "text": ev["delta"]}
            elif ev["type"] == "done":
                assistant_msg = ev["message"]
                finish = ev["finish_reason"]
                usage = ev.get("usage") or {}
                prompt_tokens += int(usage.get("prompt_tokens") or 0)
                completion_tokens += int(usage.get("completion_tokens") or 0)
                duration_ms += int(ev.get("duration_ms") or 0)
                if ev.get("reasoning"):
                    reasoning_parts.append(ev["reasoning"])

        if assistant_msg is not None:
            convo.append(assistant_msg)
        if finish != "tool_calls" or not reg:
            break

        # run each requested tool, append results, loop for another model round.
        # tool_start/tool_end bracket each call so the UI can show the activity.
        for tc in assistant_msg.get("tool_calls") or []:
            fn = tc["function"]
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            query = args.get("query") if isinstance(args, dict) else None
            yield {"type": "tool_start", "name": fn["name"], "query": query or ""}
            result = await reg.adispatch(fn["name"], args)
            ok = not (isinstance(result, str) and result.startswith("ERROR"))
            yield {"type": "tool_end", "name": fn["name"], "ok": ok}
            convo.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

    # `or None` keeps "unknown" semantics for providers that don't report usage
    # (the trace card renders None as `?`); duration is always measured.
    yield {
        "type": "final",
        "content": "".join(content_parts),
        "reasoning": "\n\n".join(reasoning_parts) or None,
        "prompt_tokens": prompt_tokens or None,
        "completion_tokens": completion_tokens or None,
        "duration_ms": duration_ms or None,
    }
