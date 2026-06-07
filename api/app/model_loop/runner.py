"""Background modeling runner. Called after each chat turn. Each concern has its
own cursor and cadence, decoupled from window eviction (spec §8):
  facts   — eager, every call (catch up to max_turn)
  trait   — when (max_turn - cursor) >= K
  summary — when (max_turn - cursor) >= S
  dossier — when (max_turn - cursor) >= M
Each job is isolated (one failure doesn't block others); a cursor advances only
after its job succeeds, so a re-run is idempotent."""
from app import config
from app.model_loop import dossier, facts, summary, traits
from app.store import memory


async def _run_concern(concern: str, job, gap_threshold: int, max_turn: int) -> None:
    cursor = memory.get_cursor(concern)
    if max_turn - cursor < gap_threshold:
        return
    try:
        await job(cursor + 1, max_turn)
        memory.advance_cursor(concern, max_turn)
    except Exception:
        pass        # isolated: leave cursor unadvanced; re-runs next time


async def run_pending() -> None:
    max_turn = memory.max_turn()
    if max_turn < 0:
        return
    # facts: eager (threshold 1 = run whenever there's anything new)
    await _run_concern("facts", facts.run, 1, max_turn)
    await _run_concern("trait", traits.run, config.trait_batch_k(), max_turn)
    await _run_concern("summary", summary.run, config.summary_span_s(), max_turn)
    await _run_concern("dossier", dossier.run, config.dossier_batch_m(), max_turn)
