"""CLI: python -m evals.run <recall|traits|facts|altitude|consultant|all>

Real eval runner. Requires LLM_* (system under test) and EVAL_GEN_* (external
evaluator, distinct model). Each case runs against a fresh temp data dir so cases
don't contaminate each other or your real data."""
import asyncio
import os
import sys
import tempfile

from evals import config as ec


def _fresh_data_dir():
    d = tempfile.mkdtemp(prefix="vellum-eval-")
    os.environ["VELLUM_DATA_DIR"] = d
    from app.store import db
    db.run_migrations()


async def _recall():
    from evals import recall
    out = []
    for case in recall.load_cases():
        _fresh_data_dir()
        out.append(await recall.run_case(case, k=6, min_sim=0.35))
    return out


async def _traits():
    from evals import traits
    out = []
    for case in traits.load_cases():
        _fresh_data_dir()
        out.append(await traits.run_case(case))
    return out


async def _facts():
    from evals import facts
    out = []
    for case in facts.load_cases():
        _fresh_data_dir()
        out.append(await facts.run_case(case))
    return out


async def _altitude():
    from evals import altitude
    ec.enforce_distinct_model()
    out = []
    for q in altitude.load_questions():
        _fresh_data_dir()
        out.append(await altitude.run_question(q))
    return out


async def _consultant():
    from evals import consultant
    ec.enforce_distinct_model()
    out = []
    for probe in consultant.load_probes():
        out.append(await consultant.run_probe(probe))
    if out:
        avg = {k: round(sum((r[k] or 0) for r in out) / len(out), 2)
               for k in ("honesty", "depth", "growth")}
        print(f"AVG over {len(out)} probes: {avg}")
    return out


_EVALS = {"recall": _recall, "traits": _traits, "facts": _facts,
          "altitude": _altitude, "consultant": _consultant}


async def _main(which: str):
    names = list(_EVALS) if which == "all" else [which]
    for name in names:
        results = await _EVALS[name]()
        print(f"\n=== {name} ===")
        for r in results:
            print(r)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which != "all" and which not in _EVALS:
        sys.exit(f"Unknown eval {which!r}. Choose from: {', '.join(_EVALS)} or all")
    asyncio.run(_main(which))
