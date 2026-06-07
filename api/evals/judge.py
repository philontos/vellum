"""LLM-as-judge using the external evaluator model (EVAL_GEN_*). Returns a parsed
verdict dict (expects a JSON object with at least a numeric `score`)."""
import json

import httpx

from evals.config import eval_gen_config


async def _eval_chat(prompt: str) -> str:
    cfg = eval_gen_config()
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{cfg['base_url']}/chat/completions",
            headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
            json={"model": cfg["model"], "stream": False,
                  "messages": [{"role": "user", "content": prompt}]},
        )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        s, e = text.find("{"), text.rfind("}")
        if s != -1 and e != -1 and e > s:
            return json.loads(text[s:e + 1])
        raise


async def score(rubric: str, subject: str) -> dict:
    prompt = f"{rubric}\n\n## Subject to evaluate\n{subject}\n\nRespond with a single JSON object."
    return _extract_json(await _eval_chat(prompt))
