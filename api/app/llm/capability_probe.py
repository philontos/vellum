"""Small live probes for scenario-relevant OpenAI-compatible capabilities."""
import asyncio
import json
import time

import httpx

from app.llm.client import _looks_like_json_format_rejection


_TIMEOUT_SECONDS = 30.0


def _result(status: str, started: float) -> dict:
    return {
        "status": status,
        "latency_ms": int((time.monotonic() - started) * 1000),
    }


def _headers(config: dict[str, str]) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }


def _content(response: httpx.Response) -> str:
    try:
        return response.json()["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError, ValueError):
        return ""


def _parse_object(text: str) -> bool:
    try:
        return isinstance(json.loads(text), dict)
    except (TypeError, json.JSONDecodeError):
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            return False
        try:
            return isinstance(json.loads(text[start:end + 1]), dict)
        except json.JSONDecodeError:
            return False


async def _structured(config: dict[str, str]) -> dict:
    started = time.monotonic()
    payload = {
        "model": config["model"],
        "stream": False,
        "messages": [{
            "role": "user",
            "content": 'Return exactly one JSON object: {"ok": true}',
        }],
        "response_format": {"type": "json_object"},
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{config['base_url']}/chat/completions",
                headers=_headers(config), json=payload,
            )
            if _looks_like_json_format_rejection(
                response.status_code, response.text,
            ):
                # Prompt-only JSON is a supported compatibility path in Vellum.
                payload.pop("response_format", None)
                response = await client.post(
                    f"{config['base_url']}/chat/completions",
                    headers=_headers(config), json=payload,
                )
        passed = response.status_code < 400 and _parse_object(_content(response))
        return _result("passed" if passed else "failed", started)
    except Exception:
        return _result("failed", started)


async def _tools(config: dict[str, str]) -> dict:
    started = time.monotonic()
    payload = {
        "model": config["model"],
        "stream": False,
        "messages": [{"role": "user", "content": "Reply with OK."}],
        "tools": [{
            "type": "function",
            "function": {
                "name": "capability_check",
                "description": "A no-op capability check.",
                "parameters": {"type": "object", "properties": {}},
            },
        }],
        "tool_choice": "auto",
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{config['base_url']}/chat/completions",
                headers=_headers(config), json=payload,
            )
        return _result("passed" if response.status_code < 400 else "failed", started)
    except Exception:
        return _result("failed", started)


async def _streaming(config: dict[str, str]) -> dict:
    started = time.monotonic()
    payload = {
        "model": config["model"],
        "stream": True,
        "messages": [{"role": "user", "content": "Reply with OK only."}],
        "max_tokens": 2,
    }
    try:
        saw_data = False
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            async with client.stream(
                "POST", f"{config['base_url']}/chat/completions",
                headers=_headers(config), json=payload,
            ) as response:
                if response.status_code >= 400:
                    return _result("failed", started)
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        saw_data = True
                    if line.strip() == "data: [DONE]":
                        break
        return _result("passed" if saw_data else "failed", started)
    except Exception:
        return _result("failed", started)


async def run(config: dict[str, str], *, basic_latency_ms: int) -> dict:
    structured, streaming, tools = await asyncio.gather(
        _structured(config), _streaming(config), _tools(config),
    )
    return {
        "basic": {"status": "passed", "latency_ms": basic_latency_ms},
        "structured_json": structured,
        "streaming": streaming,
        "tools": tools,
    }
