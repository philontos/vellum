"""Read-only inspection of the personal model + diagnostic traces (plus pin/note
on traces), and the eval panel endpoints (run via SSE + list/detail of past runs).
Not part of the chat hot path."""
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from app import config
from app.auth.dependencies import require_owner
from app.config.dimensions_loader import dimension_meta
from app.model_loop import schwartz
from app.evaluation import archive as conversation_archive
from app.evaluation import conversation as conversation_eval
from app.inquiry import store as inquiry_store
from app.llm import candidates as model_candidates
from app.llm.client import resolve_structured_llm_config
from app.store import (
    model, observability as obs, portrait_claims, traces, turn_runs, user_states,
)
from evals.config import eval_gen_config
from evals.suites import SUITES

router = APIRouter()

_API_DIR = Path(__file__).resolve().parents[2]   # api/ — where `app` and `evals` live


@router.get("/inspect/model")
def inspect_model():
    traits = model.all_traits()
    for t in traits:
        t["history"] = model.get_trait_history(t["dimension"])
        t["observations"] = model.list_trait_observations(t["dimension"], 50)
        t["meta"] = dimension_meta(t["dimension"])   # names + pole labels for the UI
        if t["dimension"] == "schwartz":
            t["profile"] = schwartz.profile_payload(
                t["content_json"],
                t["history"],
                model.get_trait_evidence("schwartz"),
            )
    return {
        "dossier": model.get_dossier(),
        "dossier_meta": model.get_dossier_row(),
        # Active only — consolidation retires merged/contradicted facts, and the
        # superseded tail would otherwise grow without bound on this page.
        "facts": model.active_facts(),
        "portrait_claims": portrait_claims.active(),
        "traits": traits,
        "current_states": user_states.recent(limit=20),
    }


@router.get("/inspect/traces")
def inspect_traces(limit: int = 100, stage: str | None = None):
    return {"traces": traces.list_summaries(limit=limit, stage=stage)}


@router.get("/inspect/traces/{trace_id}")
def inspect_trace(trace_id: int):
    trace = traces.get_by_id(trace_id)
    if trace is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return {"trace": trace}


@router.get("/inspect/turn-runs")
def inspect_turn_runs(limit: int = Query(default=100, ge=1, le=500)):
    return {"runs": turn_runs.list_recent(limit=limit)}


@router.get("/inspect/inquiries")
def inspect_inquiries(
    limit: int = Query(default=100, ge=1, le=500),
    stream: str | None = None,
):
    return {"inquiries": inquiry_store.list_recent(limit=limit, stream=stream)}


@router.get("/inspect/inquiries/{inquiry_id}")
def inspect_inquiry(inquiry_id: int):
    inquiry = inquiry_store.get(inquiry_id)
    if inquiry is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return {
        "inquiry": inquiry,
        "events": inquiry_store.list_events(inquiry_id),
    }


@router.get("/inspect/probe")
async def probe(q: str = "", stream: str = "neutral"):
    """Read-only recall inspector. For a query, return the scored retrieval
    breakdown (kept hits + below-threshold near-misses + snippets) scoped to
    `stream`, plus the always-in-context durable facts board. Persists nothing —
    purely diagnostic."""
    from app.chat import retrieval
    if q.strip():
        result = await retrieval.retrieve_explained(q, stream=stream)
    else:
        result = {"params": None, "hits": [], "snippets": []}
    return {"query": q, **result, "facts": model.active_facts()}


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


# --- conversation replay evals --------------------------------------------

class ConversationPromptVersionIn(BaseModel):
    name: str
    content: str


class ConversationReplayIn(BaseModel):
    assistant_turn: int
    prompt_kind: Literal["original", "release", "custom"]
    prompt_release_id: int | None = None
    prompt_version_id: int | None = None
    model_candidate: str | None = None


class ConversationModelCandidateIn(BaseModel):
    model_candidate: str | None = None


def _conversation_model_config(candidate_id: str | None) -> dict[str, str]:
    if candidate_id:
        return model_candidates.resolve(candidate_id)
    return model_candidates.resolve_for_scenario("evaluation")


def _conversation_eval_error(exc: Exception):
    if isinstance(exc, conversation_eval.ConversationRoundNotFoundError):
        raise HTTPException(status_code=404, detail="Conversation round not found") from exc
    if isinstance(exc, conversation_archive.ConversationEvalRecordNotFoundError):
        raise HTTPException(status_code=404, detail="Evaluation record not found") from exc
    if isinstance(exc, conversation_eval.ReplayValidationError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(exc, model_candidates.ModelCandidateError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    raise exc


@router.get("/inspect/conversation-evals")
def conversation_eval_workspace(
    limit: int = Query(default=50, ge=1, le=200),
    before: int | None = Query(default=None),
    _owner: dict | None = Depends(require_owner),
):
    return conversation_eval.workspace(limit=limit, before=before)


@router.get("/inspect/conversation-evals/rounds/{assistant_turn}")
def conversation_eval_round(
    assistant_turn: int,
    _owner: dict | None = Depends(require_owner),
):
    try:
        return conversation_eval.round_detail(assistant_turn)
    except Exception as exc:
        return _conversation_eval_error(exc)


@router.get("/inspect/conversation-evals/records")
def conversation_eval_records(
    limit: int = Query(default=50, ge=1, le=200),
    before: int | None = Query(default=None),
    _owner: dict | None = Depends(require_owner),
):
    return conversation_archive.list_records(limit=limit, before=before)


@router.get("/inspect/conversation-evals/records/{record_id}")
def conversation_eval_record(
    record_id: int,
    _owner: dict | None = Depends(require_owner),
):
    try:
        return conversation_archive.record_detail(record_id)
    except Exception as exc:
        return _conversation_eval_error(exc)


@router.post("/inspect/conversation-evals/records", status_code=201)
async def create_conversation_eval_record(
    body: ConversationReplayIn,
    _owner: dict | None = Depends(require_owner),
):
    try:
        return await conversation_archive.create_record(
            body.assistant_turn,
            body.prompt_kind,
            prompt_release_id=body.prompt_release_id,
            prompt_version_id=body.prompt_version_id,
        )
    except Exception as exc:
        return _conversation_eval_error(exc)


@router.post("/inspect/conversation-evals/prompt-versions", status_code=201)
def create_conversation_prompt_version(
    body: ConversationPromptVersionIn,
    _owner: dict | None = Depends(require_owner),
):
    try:
        return conversation_eval.create_prompt_version(body.name, body.content)
    except Exception as exc:
        return _conversation_eval_error(exc)


@router.post("/inspect/conversation-evals/run")
async def run_conversation_eval(
    body: ConversationReplayIn,
    _owner: dict | None = Depends(require_owner),
):
    try:
        llm_config = _conversation_model_config(body.model_candidate)
        record = await conversation_archive.create_record(
            body.assistant_turn,
            body.prompt_kind,
            prompt_release_id=body.prompt_release_id,
            prompt_version_id=body.prompt_version_id,
        )
        prepared = conversation_archive.prepared_for_record(record["id"])
        run = conversation_eval.start_run(
            prepared, record_id=record["id"], llm_config=llm_config,
        )
    except Exception as exc:
        return _conversation_eval_error(exc)

    return _conversation_run_stream(run, prepared, llm_config)


@router.post("/inspect/conversation-evals/records/{record_id}/runs")
async def run_conversation_eval_record(
    record_id: int,
    body: ConversationModelCandidateIn | None = Body(default=None),
    _owner: dict | None = Depends(require_owner),
):
    try:
        llm_config = _conversation_model_config(
            body.model_candidate if body is not None else None
        )
        prepared = conversation_archive.prepared_for_record(record_id)
        run = conversation_eval.start_run(
            prepared, record_id=record_id, llm_config=llm_config,
        )
    except Exception as exc:
        return _conversation_eval_error(exc)
    return _conversation_run_stream(run, prepared, llm_config)


def _conversation_run_stream(run: dict, prepared, llm_config: dict[str, str]):
    async def gen():
        yield _sse({"run": run})
        async for event in conversation_eval.run_events(
            run["id"], prepared, llm_config=llm_config,
        ):
            if event["type"] == "delta":
                yield _sse({"delta": {"text": event["text"]}})
            elif event["type"] == "activity":
                yield _sse({"activity": event["activity"]})
            elif event["type"] == "done":
                yield _sse({"done": event["run"]})
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


# --- eval panel ------------------------------------------------------------

@router.get("/inspect/evals")
def list_eval_runs(limit: int = 50, _owner: dict | None = Depends(require_owner)):
    suites = [{"key": k, "needs_eval_gen": s.needs_eval_gen} for k, s in SUITES.items()]
    return {"runs": obs.list_runs(limit=limit), "suites": suites}


@router.get("/inspect/evals/{run_id}")
def get_eval_run(run_id: int, _owner: dict | None = Depends(require_owner)):
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
    if config.auth_enabled():
        # The child process cannot inherit a ContextVar. Point it at the already
        # scoped owner directory and run it in legacy-path mode; eval scratch then
        # remains isolated without ever falling back to the deployment root DB.
        env["VELLUM_PROMPT_DB_PATH"] = str(config.prompt_db_path())
        env["VELLUM_DATA_DIR"] = str(config.data_dir())
        env["VELLUM_AUTH_ENABLED"] = "0"
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
async def run_eval(suite: str, _owner: dict | None = Depends(require_owner)):
    if suite not in SUITES:
        return JSONResponse(
            {"error": f"unknown suite {suite!r}; choose from {', '.join(SUITES)}"},
            status_code=422,
        )
    cfg = resolve_structured_llm_config(stage="eval")
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
