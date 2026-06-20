"""Read-only inspection of the personal model + diagnostic traces (plus pin/note
on traces), and the eval panel endpoints (run via SSE + list/detail of past runs).
Not part of the chat hot path."""
import asyncio
import json
import os
import sys
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from app.config.dimensions_loader import dimension_meta
from app.llm.client import resolve_structured_llm_config
from app.store import model, observability as obs, traces
from evals.config import eval_gen_config
from evals.suites import SUITES

router = APIRouter()

_API_DIR = Path(__file__).resolve().parents[2]   # api/ — where `app` and `evals` live


@router.get("/inspect/model")
def inspect_model():
    traits = model.all_traits()
    for t in traits:
        t["history"] = model.get_trait_history(t["dimension"])
        t["meta"] = dimension_meta(t["dimension"])   # names + pole labels for the UI
    return {
        "dossier": model.get_dossier(),
        "dossier_meta": model.get_dossier_row(),
        # Active only — consolidation retires merged/contradicted facts, and the
        # superseded tail would otherwise grow without bound on this page.
        "facts": model.active_facts(),
        "traits": traits,
    }


@router.get("/inspect/traces")
def inspect_traces(limit: int = 100, stage: str | None = None):
    return {"traces": traces.list_recent(limit=limit, stage=stage)}


class TracePatch(BaseModel):
    pinned: bool | None = None
    note: str | None = None


@router.post("/inspect/traces/{trace_id}")
def patch_trace(trace_id: int, body: TracePatch):
    if body.pinned is not None:
        traces.pin(trace_id, body.pinned)
    if body.note is not None:
        traces.set_note(trace_id, body.note)
    return {"ok": True}


# --- eval panel ------------------------------------------------------------

@router.get("/inspect/evals")
def list_eval_runs(limit: int = 50):
    suites = [{"key": k, "needs_eval_gen": s.needs_eval_gen} for k, s in SUITES.items()]
    return {"runs": obs.list_runs(limit=limit), "suites": suites}


@router.get("/inspect/evals/{run_id}")
def get_eval_run(run_id: int):
    run = obs.get_run(run_id)
    if run is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return {"run": run, "results": obs.results_for_run(run_id),
            "traces": obs.traces_for_run(run_id)}


async def _stream_lines(suite: str):
    """Spawn `python -m evals.stream <suite>` in a subprocess and yield its stdout
    lines. The subprocess isolates the in-memory scratch (process-global conn swap)
    from the server; the parent here does all durable observability.db writes."""
    env = {**os.environ, "PYTHONPATH": str(_API_DIR)}
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "evals.stream", suite,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        cwd=str(_API_DIR), env=env,
    )
    try:
        async for raw in proc.stdout:
            line = raw.decode("utf-8").strip()
            if line:
                yield line
    finally:
        await proc.wait()


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


@router.post("/inspect/evals/run")
async def run_eval(suite: str):
    if suite not in SUITES:
        return JSONResponse(
            {"error": f"unknown suite {suite!r}; choose from {', '.join(SUITES)}"},
            status_code=422,
        )
    cfg = resolve_structured_llm_config()
    eval_model = eval_gen_config().get("model") or None
    run_id = obs.create_run(suite, total=0, model=cfg.get("model") or None,
                            eval_model=eval_model)

    async def gen():
        aggregate = None
        status = "error"            # default if the stream dies before "done"
        try:
            async for line in _stream_lines(suite):
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue        # ignore non-JSON noise on stdout
                kind = ev.get("type")
                if kind == "run":
                    obs.set_total(run_id, ev.get("total", 0))
                    yield _sse({"run": {"id": run_id, "suite": suite,
                                        "total": ev.get("total", 0),
                                        "needs_eval_gen": ev.get("needs_eval_gen")}})
                elif kind == "trace":
                    traces.record(
                        turn=None, stage=ev.get("stage") or "eval",
                        model=ev.get("model"), params=ev.get("params") or {},
                        prompt=ev.get("prompt"), output=ev.get("output"),
                        reasoning=ev.get("reasoning"),
                        prompt_tokens=ev.get("prompt_tokens"),
                        completion_tokens=ev.get("completion_tokens"),
                        duration_ms=ev.get("duration_ms"),
                        eval_run_id=run_id, eval_case=ev.get("case"),
                    )
                elif kind == "case":
                    obs.add_result(run_id, ev["seq"], ev["case"], ev["status"],
                                   result=ev.get("result"), error=ev.get("error"))
                    obs.bump_completed(run_id)
                    yield _sse({"case": {"seq": ev["seq"], "case": ev["case"],
                                         "status": ev["status"],
                                         "result": ev.get("result"),
                                         "error": ev.get("error")}})
                elif kind == "done":
                    aggregate = ev.get("aggregate")
                    status = ev.get("status", "done")
                elif kind == "error":
                    status = "error"
                    aggregate = None
            obs.finish_run(run_id, status, aggregate=aggregate)
            yield _sse({"done": {"run_id": run_id, "status": status,
                                 "aggregate": aggregate}})
        except Exception as exc:
            obs.finish_run(run_id, "error", error=f"{type(exc).__name__}: {exc}")
            yield _sse({"done": {"run_id": run_id, "status": "error",
                                 "error": str(exc)}})
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
