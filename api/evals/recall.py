"""Recall eval: seed a corpus into a fresh stream, run the real retrieval for a
query, and check the expected turn(s) fall within the recalled windows."""
import json
from pathlib import Path

from app.chat import ingest, retrieval

_DATA = Path(__file__).parent / "data" / "recall_cases.json"


async def _seed(corpus: list[dict]) -> None:
    for m in corpus:
        if m["role"] == "user":
            await ingest.persist_user(m["content"])
        else:
            ingest.persist_assistant(m["content"])


async def run_case(case: dict, k: int, min_sim: float) -> dict:
    await _seed(case["corpus"])
    snippets = await retrieval.retrieve(case["query"], k=k, min_sim=min_sim)
    covered = set()
    for s in snippets:
        covered.update(range(s["start"], s["end"] + 1))
    expected = set(case["expect_turns"])
    found = expected & covered
    return {
        "name": case.get("name", "?"),
        "hit": expected.issubset(covered),
        "recall": (len(found) / len(expected)) if expected else 1.0,
    }


def load_cases() -> list[dict]:
    return json.loads(_DATA.read_text())
