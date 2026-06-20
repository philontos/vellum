"""Background modeling runner. Called after each chat turn. Each concern has its
own cursor and cadence, decoupled from window eviction (spec §8):
  facts   — eager, every call (catch up to max_turn)
  trait   — when (max_turn - cursor) >= K
  summary — when (max_turn - cursor) >= S
  dossier — when (max_turn - cursor) >= M
Each job is isolated (one failure doesn't block others); a cursor advances only
after its job succeeds, so a re-run is idempotent."""
import uuid

from app import config
from app.llm.client import capture_llm_calls
from app.model_loop import dossier, facts, summary, traits
from app.store import memory, traces


def _flush_traces(calls: list[dict], turn: int, start_turn: int | None = None,
                  batch: str | None = None) -> None:
    """Persist captured LLM calls (success or failure) as trace rows. `turn` is the
    end of the covered span (the trigger turn); `start_turn` its beginning. A pass
    covers a *range* of turns, not one round — record [from, to] in params so the
    Traces panel can label it 'turns from–to'. `batch` is a per-pass id stamped on
    every call of one invocation, so the pass is an unambiguous group (not merely
    inferred from (stage, turn)) — survives concurrency and alternate timelines."""
    for c in calls:
        prompt = (c.get("system_prompt") or "")
        if c.get("user_prompt"):
            prompt += "\n\n[user]\n" + c["user_prompt"]
        params = {"status": c.get("status"), "error": c.get("error")}
        if start_turn is not None:
            params["from"] = start_turn
            params["to"] = turn
        if batch is not None:
            params["batch"] = batch
        traces.record(
            turn=turn,
            stage=c.get("stage") or "?",
            model=c.get("model"),
            params=params,
            prompt=prompt,
            output=c.get("response") or "",
            reasoning=c.get("reasoning") or None,
            prompt_tokens=c.get("prompt_tokens"),
            completion_tokens=c.get("completion_tokens"),
            duration_ms=c.get("duration_ms"),
        )


async def _run_concern(concern: str, job, gap_threshold: int, max_turn: int) -> None:
    cursor = memory.get_cursor(concern)
    if max_turn - cursor < gap_threshold:
        return
    # One id per pass invocation: stage + trigger turn (eyeball-readable) plus a
    # short random suffix (unique even if two passes of a stage race).
    batch = f"{concern}:{max_turn}:{uuid.uuid4().hex[:8]}"
    calls: list[dict] = []
    try:
        with capture_llm_calls(calls):
            await job(cursor + 1, max_turn)
        memory.advance_cursor(concern, max_turn)
    except Exception as exc:
        import traceback
        print(f"[model_loop] {concern} job failed: {exc!r}", flush=True)
        traceback.print_exc()
    finally:
        _flush_traces(calls, max_turn, start_turn=cursor + 1, batch=batch)


async def run_pending() -> None:
    max_turn = memory.max_turn()
    if max_turn < 0:
        return
    # facts: eager (threshold 1 = run whenever there's anything new)
    await _run_concern("facts", facts.run, 1, max_turn)
    await _run_concern("trait", traits.run, config.trait_batch_k(), max_turn)
    await _run_concern("summary", summary.run, config.summary_span_s(), max_turn)
    await _run_concern("dossier", dossier.run, config.dossier_batch_m(), max_turn)
