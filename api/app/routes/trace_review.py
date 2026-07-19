"""Read-only, OpenAPI-described endpoints for reviewing production trace runs."""
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel

from app import trace_review


router = APIRouter(prefix="/inspect/trace-review", tags=["trace-review"])

RunStatus = Literal["running", "done", "degraded", "error"]
RunRoute = Literal["direct", "inquire", "synthesize"]


class TraceSummary(BaseModel):
    trace_count: int
    stages: list[str]
    models: list[str]
    prompt_tokens: int
    completion_tokens: int
    total_duration_ms: int
    error_count: int
    retry_count: int
    pruned_trace_count: int


class RunRecord(BaseModel):
    id: str
    user_turn: int
    assistant_turn: int | None
    stream: str
    route: RunRoute | None
    status: RunStatus
    inquiry_id: int | None
    revision_before: int | None
    revision_after: int | None
    controller_model: str | None
    responder_model: str | None
    decision: dict[str, Any] | None
    context_meta: dict[str, Any]
    prompt_release_id: int | None
    prompt_release_version: int | None
    error: str | None
    started_at: str
    finished_at: str | None


class ReviewedRun(RunRecord):
    trace_summary: TraceSummary


class RunListResponse(BaseModel):
    runs: list[ReviewedRun]


class ReviewedTrace(BaseModel):
    id: int
    turn: int | None
    stage: str
    model: str | None
    params: Any
    prompt: Any
    output: str | None
    reasoning: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    duration_ms: int | None
    pinned: int
    note: str | None
    tool_calls: Any
    run_id: str
    scenario: str | None
    attempt: int | None
    created_at: str


class ReviewSignal(BaseModel):
    code: str
    severity: Literal["info", "warning", "error"]
    message: str
    evidence: dict[str, Any]


class RunDetailResponse(BaseModel):
    run: RunRecord
    trace_summary: TraceSummary
    traces: list[ReviewedTrace]
    signals: list[ReviewSignal]


class DurationStats(BaseModel):
    known_count: int
    total: int
    average: float | None
    p50: int | None
    p95: int | None
    max: int | None


class TraceGroupStats(BaseModel):
    key: str
    calls: int
    errors: int
    retries: int
    prompt_tokens: int
    completion_tokens: int
    duration_ms: DurationStats


class StatsWindow(BaseModel):
    limit: int
    run_count: int
    trace_count: int
    started_at_min: str | None
    started_at_max: str | None


class RunStats(BaseModel):
    by_status: dict[str, int]
    by_route: dict[str, int]


class TraceTotals(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    duration_ms: int
    trace_errors: int
    retries: int


class StatsResponse(BaseModel):
    window: StatsWindow
    runs: RunStats
    totals: TraceTotals
    by_stage: list[TraceGroupStats]
    by_model: list[TraceGroupStats]


def _sqlite_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value.isoformat(sep=" ", timespec="seconds")


def _filters(
    *,
    status: RunStatus | None,
    route: RunRoute | None,
    stream: str | None,
    user_turn: int | None,
    assistant_turn: int | None,
    started_after: datetime | None,
    started_before: datetime | None,
) -> dict:
    return {
        "status": status,
        "route": route,
        "stream": stream,
        "user_turn": user_turn,
        "assistant_turn": assistant_turn,
        "started_after": _sqlite_timestamp(started_after),
        "started_before": _sqlite_timestamp(started_before),
    }


@router.get(
    "/runs",
    response_model=RunListResponse,
    summary="List recent trace runs for review",
    description=(
        "Find account-scoped production turn runs and lightweight correlated-span "
        "summaries. Full prompts, outputs, reasoning, and tool results are omitted."
    ),
)
def list_trace_runs(
    limit: int = Query(default=20, ge=1, le=200),
    status: RunStatus | None = None,
    route: RunRoute | None = None,
    stream: str | None = Query(default=None, min_length=1, max_length=64),
    user_turn: int | None = Query(default=None, ge=0),
    assistant_turn: int | None = Query(default=None, ge=0),
    started_after: datetime | None = None,
    started_before: datetime | None = None,
):
    return {"runs": trace_review.list_runs(
        limit=limit,
        **_filters(
            status=status,
            route=route,
            stream=stream,
            user_turn=user_turn,
            assistant_turn=assistant_turn,
            started_after=started_after,
            started_before=started_before,
        ),
    )}


@router.get(
    "/runs/{run_id}",
    response_model=RunDetailResponse,
    summary="Review one complete trace run",
    description=(
        "Load one account-scoped turn root, every correlated LLM span in call "
        "order, decoded JSON bodies, totals, and deterministic diagnostic signals."
    ),
)
def get_trace_run(
    run_id: str = Path(min_length=1, max_length=128),
):
    review = trace_review.get_run(run_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Trace run not found")
    return review


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Aggregate a recent trace-review window",
    description=(
        "Aggregate bounded, account-scoped run metadata by status, route, stage, "
        "and model without loading prompt/output bodies."
    ),
)
def trace_review_stats(
    limit: int = Query(default=100, ge=1, le=500),
    status: RunStatus | None = None,
    route: RunRoute | None = None,
    stream: str | None = Query(default=None, min_length=1, max_length=64),
    user_turn: int | None = Query(default=None, ge=0),
    assistant_turn: int | None = Query(default=None, ge=0),
    started_after: datetime | None = None,
    started_before: datetime | None = None,
):
    return trace_review.stats(
        limit=limit,
        **_filters(
            status=status,
            route=route,
            stream=stream,
            user_turn=user_turn,
            assistant_turn=assistant_turn,
            started_after=started_after,
            started_before=started_before,
        ),
    )
