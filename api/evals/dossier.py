"""Dossier eval (holistic): the system builds a dossier from a persona's
conversation; an external judge scores 0-10 how well it captures the persona."""
import json
from pathlib import Path

from app.store import model
from evals import judge

_DATA = Path(__file__).parent / "data" / "personas"

_RUBRIC = (
    "You are grading how well an AI's portrait of a user matches the TRUE persona. "
    "Score 0-10 (10 = captures the persona's values/patterns with no contradictions). "
    "Penalize contradictions and generic filler. Respond JSON: {\"score\": <0-10>, \"reason\": \"...\"}.\n\n"
    "## True persona\n{persona}"
)


async def run_persona(name: str) -> dict:
    spec = json.loads((_DATA / f"{name}.json").read_text())
    dossier_text = model.get_dossier()
    rubric = _RUBRIC.replace("{persona}", json.dumps(spec, ensure_ascii=False))
    verdict = await judge.score(rubric, dossier_text or "(empty dossier)")
    return {"persona": name, "score": verdict.get("score"), "reason": verdict.get("reason")}
