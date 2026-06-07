"""Facts eval: run the real facts job over a conversation with planted facts,
then measure fact-recall by normalized containment (an expected fact counts as
recalled if its lowercased text appears within any captured fact, or vice-versa)."""
import json
from pathlib import Path

from app.model_loop import facts as facts_job
from app.store import memory, model

_DATA = Path(__file__).parent / "data" / "facts_cases.json"


def fact_recall(expected: list[str], actual: list[str]) -> dict:
    al = [a.lower() for a in actual]
    matched = [e for e in expected
               if any(e.lower() in a or a in e.lower() for a in al)]
    return {"recall": (len(matched) / len(expected)) if expected else 1.0,
            "matched": matched, "missed": [e for e in expected if e not in matched]}


async def run_case(case: dict) -> dict:
    end = -1
    for line in case["conversation"]:
        end = memory.append_message("user", line)["turn"]
    await facts_job.run(0, end)
    actual = [f["text"] for f in model.active_facts()]
    return {"name": case.get("name", "?"), **fact_recall(case["expect_facts"], actual),
            "actual": actual}


def load_cases() -> list[dict]:
    return json.loads(_DATA.read_text())
