import asyncio

import httpx
import pytest

from app.llm import capability_probe


def _response(status: int, body: dict) -> httpx.Response:
    request = httpx.Request("POST", "https://model.test/v1/chat/completions")
    return httpx.Response(status, json=body, request=request)


@pytest.mark.asyncio
async def test_structured_probe_retries_only_explicit_json_mode_rejection(monkeypatch):
    calls = []

    async def post(self, url, *, headers, json):
        calls.append(json.copy())
        if len(calls) == 1:
            return _response(400, {"error": "response_format is unsupported"})
        return _response(200, {
            "choices": [{"message": {"content": '{"ok": true}'}}],
        })

    monkeypatch.setattr(httpx.AsyncClient, "post", post)

    result = await capability_probe._structured({
        "base_url": "https://model.test/v1",
        "api_key": "secret",
        "model": "model",
    })

    assert result["status"] == "passed"
    assert len(calls) == 2
    assert "response_format" not in calls[1]


@pytest.mark.asyncio
async def test_structured_probe_does_not_mask_unrelated_bad_request(monkeypatch):
    calls = []

    async def post(self, url, *, headers, json):
        calls.append(json.copy())
        return _response(400, {"error": "invalid model identifier"})

    monkeypatch.setattr(httpx.AsyncClient, "post", post)

    result = await capability_probe._structured({
        "base_url": "https://model.test/v1",
        "api_key": "secret",
        "model": "model",
    })

    assert result["status"] == "failed"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_capability_probes_run_concurrently(monkeypatch):
    started = set()
    all_started = asyncio.Event()

    def probe(name):
        async def run(config):
            started.add(name)
            if len(started) == 3:
                all_started.set()
            await asyncio.wait_for(all_started.wait(), timeout=0.2)
            return {"status": "passed", "latency_ms": 1}
        return run

    monkeypatch.setattr(capability_probe, "_structured", probe("structured"))
    monkeypatch.setattr(capability_probe, "_streaming", probe("streaming"))
    monkeypatch.setattr(capability_probe, "_tools", probe("tools"))

    result = await capability_probe.run({}, basic_latency_ms=7)

    assert started == {"structured", "streaming", "tools"}
    assert result["basic"] == {"status": "passed", "latency_ms": 7}
