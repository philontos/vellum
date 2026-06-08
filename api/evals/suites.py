"""Unified suite registry — single source of truth for the 5 eval suites, consumed
by both the CLI (evals.run) and the streaming entrypoint (evals.stream).

Each Suite normalizes a heterogeneous eval module to a common shape:
  load()        -> list of cases (dicts, or bare strings for altitude)
  run(case)     -> result dict (async)
  name_of(c,i)  -> stable case label
  status_of(r)  -> pass|fail|scored
  aggregate(rs) -> run-level summary dict
  needs_eval_gen -> requires the external judge model (EVAL_GEN_*)
  needs_scratch  -> run() writes to the DB/vectors, so isolate it in memory scratch
"""
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from app import config
from evals import altitude, consultant, facts, recall, traits


@dataclass
class Suite:
    key: str
    load: Callable[[], list]
    run: Callable[[Any], Awaitable[dict]]
    name_of: Callable[[Any, int], str]
    status_of: Callable[[dict], str]
    aggregate: Callable[[list], dict]
    needs_eval_gen: bool
    needs_scratch: bool


def _mean(vals) -> float | None:
    nums = [v for v in vals if isinstance(v, (int, float))]
    return round(sum(nums) / len(nums), 2) if nums else None


# --- per-suite adapters ----------------------------------------------------

def _traits_name(case, i):
    t = case.get("target", {})
    return f"{case.get('dimension', '?')}_{t.get('sub', '?')}_{t.get('direction', '?')}"


def _traits_agg(rs):
    return {"pass": sum(1 for r in rs if r.get("direction_ok") and r.get("crosstalk_ok")),
            "total": len(rs),
            "mean_target_score": _mean([r.get("target_score") for r in rs])}


def _recall_agg(rs):
    return {"mean_recall": _mean([r.get("recall") for r in rs]),
            "hit": sum(1 for r in rs if r.get("hit")), "total": len(rs)}


def _facts_agg(rs):
    return {"mean_recall": _mean([r.get("recall") for r in rs]), "total": len(rs)}


def _altitude_agg(rs):
    return {"passed": sum(1 for r in rs if r.get("passed")), "total": len(rs)}


def _consultant_agg(rs):
    return {"honesty": _mean([r.get("honesty") for r in rs]),
            "depth": _mean([r.get("depth") for r in rs]),
            "growth": _mean([r.get("growth") for r in rs]),
            "total": len(rs)}


SUITES: dict[str, Suite] = {
    "traits": Suite(
        key="traits", load=traits.load_cases, run=traits.run_case,
        name_of=_traits_name,
        status_of=lambda r: "pass" if r.get("direction_ok") and r.get("crosstalk_ok") else "fail",
        aggregate=_traits_agg, needs_eval_gen=False, needs_scratch=False,
    ),
    "facts": Suite(
        key="facts", load=facts.load_cases, run=facts.run_case,
        name_of=lambda c, i: c.get("name", f"case_{i}"),
        status_of=lambda r: "pass" if (r.get("recall") or 0) >= 1.0 else "fail",
        aggregate=_facts_agg, needs_eval_gen=False, needs_scratch=False,
    ),
    "recall": Suite(
        key="recall", load=recall.load_cases,
        run=lambda c: recall.run_case(c, k=config.recall_k(), min_sim=config.recall_min_sim()),
        name_of=lambda c, i: c.get("name", f"case_{i}"),
        status_of=lambda r: "pass" if r.get("hit") else "fail",
        aggregate=_recall_agg, needs_eval_gen=False, needs_scratch=True,
    ),
    "altitude": Suite(
        key="altitude", load=altitude.load_questions, run=altitude.run_question,
        name_of=lambda c, i: (c[:48] if isinstance(c, str) else f"q_{i}"),
        status_of=lambda r: "pass" if r.get("passed") else "fail",
        aggregate=_altitude_agg, needs_eval_gen=True, needs_scratch=True,
    ),
    "consultant": Suite(
        key="consultant", load=consultant.load_probes, run=consultant.run_probe,
        name_of=lambda c, i: c.get("id", f"probe_{i}"),
        status_of=lambda r: "scored",
        aggregate=_consultant_agg, needs_eval_gen=True, needs_scratch=False,
    ),
}
