"""Generate a synthetic conversation that ENACTS a target (show, don't tell),
using the external evaluator model EVAL_GEN_*. Used to (re)author committed trait
conversation fixtures and persona conversations."""
import httpx

from evals.config import eval_gen_config, enforce_distinct_model


async def generate_conversation(instruction: str, n: int = 6) -> list[str]:
    enforce_distinct_model()
    cfg = eval_gen_config()
    prompt = (
        f"Produce exactly {n} first-person user messages (a person talking to an AI) "
        f"that AUTHENTICALLY ENACT the following, WITHOUT ever naming the trait or "
        f"stating it directly — show it through concrete situations, choices, and tone:\n\n"
        f"{instruction}\n\nRespond as strict JSON: {{\"messages\": [\"...\", ...]}}."
    )
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{cfg['base_url']}/chat/completions",
            headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
            json={"model": cfg["model"], "stream": False,
                  "messages": [{"role": "user", "content": prompt}]},
        )
    resp.raise_for_status()
    import json
    content = resp.json()["choices"][0]["message"]["content"]
    s, e = content.find("{"), content.rfind("}")
    return json.loads(content[s:e + 1])["messages"]
