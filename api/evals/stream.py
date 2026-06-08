"""python -m evals.stream <suite>

Run one suite's cases and emit one JSON line per event to stdout, for the API
route to relay as SSE and persist. Runs in a SUBPROCESS: the in-memory scratch
(needs_scratch suites) swaps a process-global DB connection target, so it must be
isolated from the server process — the subprocess gives that for free, and the
parent (which holds the real observability.db) does all durable writes.

Frames (one JSON object per line):
  {"type":"run",   "suite":..., "total":N, "needs_eval_gen":bool}
  {"type":"trace", "case":..., "stage":..., "prompt":..., "output":..., ...}
  {"type":"case",  "seq":i, "case":..., "status":"pass|fail|scored|error", "result":{...}|null, "error":...}
  {"type":"done",  "status":"done|error", "aggregate":{...}}
Each case's LLM calls are captured (even failures) and emitted as `trace` frames
before its `case` frame."""
import asyncio
import json
import sys

from app.llm.client import capture_llm_calls
from app.store import db, vectors
from evals import suites as S


def _emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _calls_to_traces(calls: list[dict], case_name: str) -> list[dict]:
    out = []
    for c in calls:
        prompt = c.get("system_prompt") or ""
        if c.get("user_prompt"):
            prompt += "\n\n[user]\n" + c["user_prompt"]
        out.append({
            "type": "trace", "case": case_name,
            "stage": c.get("stage") or "?", "model": c.get("model"),
            "params": {"status": c.get("status"), "error": c.get("error")},
            "prompt": prompt, "output": c.get("response") or "",
            "reasoning": c.get("reasoning") or None,
            "prompt_tokens": c.get("prompt_tokens"),
            "completion_tokens": c.get("completion_tokens"),
            "duration_ms": c.get("duration_ms"),
        })
    return out


async def _run_one(suite: S.Suite, case, seq: int) -> dict:
    name = suite.name_of(case, seq)
    calls: list[dict] = []
    try:
        with capture_llm_calls(calls):
            if suite.needs_scratch:
                with db.memory_scratch(f"eval_{suite.key}_{seq}"), vectors.memory_index():
                    result = await suite.run(case)
            else:
                result = await suite.run(case)
        return {"seq": seq, "case": name, "status": suite.status_of(result),
                "result": result, "_traces": _calls_to_traces(calls, name)}
    except Exception as exc:  # model unconfigured, judge missing, bad case — never fatal
        return {"seq": seq, "case": name, "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
                "_traces": _calls_to_traces(calls, name)}


async def main(which: str) -> None:
    suite = S.SUITES.get(which)
    if suite is None:
        _emit({"type": "error", "error": f"unknown suite {which!r}"})
        return
    cases = suite.load()
    _emit({"type": "run", "suite": which, "total": len(cases),
           "needs_eval_gen": suite.needs_eval_gen})

    results = []
    for seq, case in enumerate(cases):
        out = await _run_one(suite, case, seq)
        for tr in out.pop("_traces"):
            _emit(tr)
        _emit({"type": "case", "seq": out["seq"], "case": out["case"],
               "status": out["status"], "result": out.get("result"),
               "error": out.get("error")})
        if out["status"] != "error" and out.get("result") is not None:
            results.append(out["result"])

    status = "done" if (results or not cases) else "error"
    _emit({"type": "done", "status": status, "aggregate": suite.aggregate(results)})


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    asyncio.run(main(which))
