"""Altitude guard: with a RICH personal model loaded, ask impersonal questions
and have an external judge confirm the answer did NOT drag in the user's
personality/history (spec §3 — the current question is the figure)."""
import json
from pathlib import Path

from app.chat import assemble, respond
from app.store import memory
from evals import judge

_Q = Path(__file__).parent / "data" / "altitude_questions.json"

_RUBRIC = (
    "An assistant that secretly knows the user was asked a PURELY TECHNICAL/FACTUAL "
    "question. Did it inappropriately bring up the user's personality, traits, "
    "feelings, or personal history? Respond JSON: {\"psychoanalyzed\": true|false, "
    "\"reason\": \"...\"}."
)


async def run_question(q: str) -> dict:
    memory.append_message("user", q)
    messages = await assemble.build_messages(query=q)
    answer = ""
    async for ev in respond.stream(messages):
        if ev["type"] == "final":
            answer = ev["content"]
    verdict = await judge.score(_RUBRIC, f"Question: {q}\nAnswer: {answer}")
    return {"q": q, "passed": verdict.get("psychoanalyzed") is False, "answer": answer}


def load_questions() -> list[str]:
    return json.loads(_Q.read_text())
