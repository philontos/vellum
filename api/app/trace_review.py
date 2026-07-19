"""Compose trace-review read models, deterministic signals, and metrics."""
from collections import Counter
import json
import math

from app.store import trace_reviews as review_store


def _params(span: dict) -> dict:
    value = span.get("params")
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    try:
        value = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _is_error(span: dict) -> bool:
    params = _params(span)
    status = params.get("status")
    return bool(params.get("error")) or status in {"error", "failed", "failure"}


def _summary(spans: list[dict]) -> dict:
    return {
        "trace_count": len(spans),
        "stages": list(dict.fromkeys(span["stage"] for span in spans)),
        "models": list(dict.fromkeys(
            span["model"] for span in spans if span.get("model")
        )),
        "prompt_tokens": sum(span.get("prompt_tokens") or 0 for span in spans),
        "completion_tokens": sum(
            span.get("completion_tokens") or 0 for span in spans
        ),
        "total_duration_ms": sum(span.get("duration_ms") or 0 for span in spans),
        "error_count": sum(_is_error(span) for span in spans),
        "retry_count": sum((span.get("attempt") or 0) > 1 for span in spans),
        "pruned_trace_count": sum(
            not span.get("has_prompt") or not span.get("has_output")
            for span in spans
        ),
    }


def list_runs(**filters) -> list[dict]:
    """List recent roots with lightweight correlated-span summaries."""
    runs, spans = review_store.load_window(**filters)
    by_run: dict[str, list[dict]] = {run["id"]: [] for run in runs}
    for span in spans:
        by_run[span["run_id"]].append(span)
    for run in runs:
        run["trace_summary"] = _summary(by_run[run["id"]])
    return runs


def _signal(
    code: str,
    severity: str,
    message: str,
    evidence: dict | None = None,
) -> dict:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "evidence": evidence or {},
    }


def _context_signals(context: dict) -> list[dict]:
    signals = []
    estimated = context.get("estimated_tokens")
    maximum = context.get("max_input_tokens")
    if (
        isinstance(estimated, (int, float))
        and isinstance(maximum, (int, float))
        and maximum > 0
        and estimated / maximum >= 0.9
    ):
        signals.append(_signal(
            "context.near_limit", "warning",
            "The controller context used at least 90% of its token budget.",
            {"estimated_tokens": estimated, "max_input_tokens": maximum},
        ))
    dropped = {
        key: context.get(key, 0)
        for key in (
            "dropped_recent_messages",
            "dropped_cited_evidence",
            "dropped_paused_inquiries",
        )
        if isinstance(context.get(key, 0), (int, float)) and context.get(key, 0) > 0
    }
    if dropped:
        signals.append(_signal(
            "context.items_dropped", "warning",
            "Some context items were dropped to fit the controller budget.",
            {**dropped, "total": sum(dropped.values())},
        ))
    if context.get("current_user_turn_truncated") is True:
        signals.append(_signal(
            "context.current_turn_truncated", "warning",
            "The triggering user turn was truncated in controller context.",
        ))
    return signals


def _signals(run: dict, spans: list[dict]) -> list[dict]:
    signals = []
    if run["status"] == "error":
        signals.append(_signal(
            "run.error", "error", "The turn pipeline ended with an error.",
            {"error": run.get("error")},
        ))
    elif run["status"] == "degraded":
        signals.append(_signal(
            "run.degraded", "warning",
            "The turn completed through a degraded fallback path.",
            {"error": run.get("error")},
        ))
    elif run["status"] == "running":
        signals.append(_signal(
            "run.incomplete", "info", "The turn is still marked as running.",
        ))
    signals.extend(_context_signals(run.get("context_meta") or {}))

    error_spans = [span for span in spans if _is_error(span)]
    if error_spans:
        signals.append(_signal(
            "trace.call_error", "error",
            "One or more correlated LLM calls recorded an error.",
            {"trace_ids": [span["id"] for span in error_spans]},
        ))
    retry_spans = [span for span in spans if (span.get("attempt") or 0) > 1]
    if retry_spans:
        signals.append(_signal(
            "trace.retry", "warning",
            "One or more pipeline stages required another attempt.",
            {"trace_ids": [span["id"] for span in retry_spans]},
        ))
    failed_tools = []
    for span in spans:
        calls = span.get("tool_calls")
        if not isinstance(calls, list):
            continue
        failed_tools.extend(
            {"trace_id": span["id"], "name": call.get("name") or "unknown"}
            for call in calls
            if isinstance(call, dict) and call.get("ok") is False
        )
    if failed_tools:
        signals.append(_signal(
            "tool.call_error", "warning",
            "One or more tools returned an unsuccessful result.",
            {"calls": failed_tools},
        ))
    pruned = [
        span["id"] for span in spans
        if span.get("prompt") is None or span.get("output") is None
    ]
    if pruned:
        signals.append(_signal(
            "trace.body_pruned", "info",
            "Some retained metadata no longer has a complete prompt/output body.",
            {"trace_ids": pruned},
        ))
    if not spans:
        signals.append(_signal(
            "trace.missing", "error", "No LLM spans are correlated to this run.",
        ))
    elif (
        run["status"] in {"done", "degraded"}
        and not any(span["stage"] == "chat" for span in spans)
    ):
        signals.append(_signal(
            "trace.chat_missing", "warning",
            "A completed turn has no correlated chat trace.",
        ))
    return signals


def get_run(run_id: str) -> dict | None:
    """Return one root, all full spans in call order, and objective signals."""
    loaded = review_store.get(run_id)
    if loaded is None:
        return None
    run, spans = loaded
    summary_rows = [
        {
            **span,
            "has_prompt": span["prompt"] is not None,
            "has_output": span["output"] is not None,
        }
        for span in spans
    ]
    return {
        "run": run,
        "trace_summary": _summary(summary_rows),
        "traces": spans,
        "signals": _signals(run, spans),
    }


def _percentile(values: list[int], percentile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def _duration(values: list[int]) -> dict:
    if not values:
        return {
            "known_count": 0, "total": 0, "average": None,
            "p50": None, "p95": None, "max": None,
        }
    total = sum(values)
    return {
        "known_count": len(values),
        "total": total,
        "average": round(total / len(values), 2),
        "p50": _percentile(values, 0.5),
        "p95": _percentile(values, 0.95),
        "max": max(values),
    }


def _group(spans: list[dict], field: str) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for span in spans:
        groups.setdefault(str(span.get(field) or "unknown"), []).append(span)
    result = [{
        "key": key,
        "calls": len(rows),
        "errors": sum(_is_error(row) for row in rows),
        "retries": sum((row.get("attempt") or 0) > 1 for row in rows),
        "prompt_tokens": sum(row.get("prompt_tokens") or 0 for row in rows),
        "completion_tokens": sum(row.get("completion_tokens") or 0 for row in rows),
        "duration_ms": _duration([
            row["duration_ms"] for row in rows
            if row.get("duration_ms") is not None
        ]),
    } for key, rows in groups.items()]
    return sorted(result, key=lambda row: (-row["calls"], row["key"]))


def stats(**filters) -> dict:
    """Aggregate a bounded recent run window without loading trace bodies."""
    runs, spans = review_store.load_window(**filters)
    statuses = Counter(run["status"] for run in runs)
    routes = Counter(run.get("route") or "unknown" for run in runs)
    started = [run["started_at"] for run in runs]
    return {
        "window": {
            "limit": filters["limit"],
            "run_count": len(runs),
            "trace_count": len(spans),
            "started_at_min": min(started) if started else None,
            "started_at_max": max(started) if started else None,
        },
        "runs": {
            "by_status": dict(sorted(statuses.items())),
            "by_route": dict(sorted(routes.items())),
        },
        "totals": {
            "prompt_tokens": sum(row.get("prompt_tokens") or 0 for row in spans),
            "completion_tokens": sum(
                row.get("completion_tokens") or 0 for row in spans
            ),
            "duration_ms": sum(row.get("duration_ms") or 0 for row in spans),
            "trace_errors": sum(_is_error(row) for row in spans),
            "retries": sum((row.get("attempt") or 0) > 1 for row in spans),
        },
        "by_stage": _group(spans, "stage"),
        "by_model": _group(spans, "model"),
    }
