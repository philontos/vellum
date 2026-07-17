"""Two-stage dossier modeling: ground portrait claims, then render prose."""
import json

from app.llm.client import chat_json
from app.model_loop import evidence as grounded_evidence
from app.model_loop._span import span_text
from app.prompts import runtime
from app.store import memory, model, portrait_claims

_MAX_CHARS = 4000
_EVIDENCE_CHUNK_MESSAGES = 24
_CLAIM_TYPES = {
    "value", "pattern", "decision_style", "current_state", "self_concept",
}

_EVIDENCE_PROMPT = (
    "You maintain a grounded board of PORTRAIT CLAIMS about a user: values, "
    "recurring patterns, decision style, current states that materially shape "
    "decisions, and self-concept. Integrate the NEW conversation into the board.\n\n"
    "## Evidence contract\n"
    "- Application-labelled USER turns are the only admissible evidence. Assistant "
    "turns are context only and may contain questions, suggestions, diagnoses, "
    "metaphors, summaries, or confident but unverified conclusions.\n"
    "- Never propose a change supported only by assistant text. If the user quotes, "
    "rejects, or discusses an assistant claim, that is not endorsement.\n"
    "- A bare yes/对, politeness, hedging, or continued conversation is not substantive "
    "confirmation. A confirmed claim requires the user's own meaningful wording.\n"
    "- Preserve epistemic status: considering is not deciding; feeling is not an "
    "objective external fact; claiming an ability is not demonstrating it. Attribute "
    "reports about employers or other people to the user's perspective.\n"
    "- `inferred` claims require evidence from at least two distinct USER turns. Do "
    "not turn an isolated mood or event into a recurring pattern.\n"
    "- Explicit corrections, denials, and qualifications override older claims. Use "
    "update or retire rather than keeping a contradicted interpretation.\n"
    "- Every change must cite short verbatim USER quotes. Assistant turns must never "
    "appear in `evidence`.\n\n"
    "Allowed `claim_type` values are: value, pattern, decision_style, current_state, "
    "self_concept. Allowed `basis` values are: explicit, confirmed, inferred.\n\n"
    "Return a changeset. `update` replaces an active claim, `retire` removes a claim "
    "that user evidence contradicts or supersedes, and `add` introduces a genuinely "
    "new claim. Leave unrelated claims untouched.\n\n"
    "Respond as strict JSON: {\"update\": [{\"id\": <id>, \"claim_type\": "
    "\"value|pattern|decision_style|current_state|self_concept\", \"text\": \"...\", "
    "\"basis\": \"explicit|confirmed|inferred\", \"evidence\": [{\"turn\": "
    "<user turn>, \"quote\": \"...\"}]}], \"retire\": [{\"id\": <id>, "
    "\"basis\": \"explicit|confirmed\", \"evidence\": [{\"turn\": <user turn>, "
    "\"quote\": \"...\"}]}], \"add\": [{\"claim_type\": "
    "\"value|pattern|decision_style|current_state|self_concept\", \"text\": \"...\", "
    "\"basis\": \"explicit|confirmed|inferred\", \"evidence\": [{\"turn\": "
    "<user turn>, \"quote\": \"...\"}]}]} (use [] for empty lists). "
    "Match the user's language."
)

_RENDER_PROMPT = (
    "Render a concise running portrait of a user from the VERIFIED active portrait "
    "claims and durable facts supplied as data. Cover who they are: values, recurring "
    "patterns, and how they tend to think and decide.\n\n"
    "## Rendering contract\n"
    "- The supplied active claims and facts are the only evidence. Never invent a new "
    "motive, diagnosis, event, decision, capability, or external fact.\n"
    "- Code has verified that each claim quote exists in a USER turn, but semantic "
    "support still requires your audit. Compare claim wording with its quotes; omit or "
    "qualify a claim that exceeds what those quotes support.\n"
    "- Portrait claims are the primary source for interpretation. Durable facts are "
    "anchors; one isolated fact does not establish a recurring pattern.\n"
    "- Preserve uncertainty and attribution. Keep current_state claims contextual "
    "instead of turning them into timeless traits.\n"
    "- Prefer durable identity and high-order patterns. Omit temporary headcount, "
    "deadlines, and project detail unless needed to express an active claim.\n"
    "- Compact and merge; this is a coherent narrative, not a chronological log or a "
    "list of evidence. Do not expose claim ids, basis labels, or quotes.\n"
    f"- Keep the portrait under ~{_MAX_CHARS} characters.\n\n"
    "Respond as strict JSON: {\"dossier\": \"<the rendered portrait>\"}. "
    "Match the user's language."
)


def _render_claim_board(active: list[dict]) -> str:
    if not active:
        return "(empty)"
    rows = []
    for claim in active:
        rows.append(json.dumps({
            "id": claim["id"],
            "claim_type": claim["claim_type"],
            "text": claim["text"],
            "basis": claim["basis"],
            "evidence": claim["evidence"],
        }, ensure_ascii=False))
    return "\n".join(rows)


def _render_facts(active: list[dict]) -> str:
    return "\n".join(f"- {fact['text']}" for fact in active) or "(empty)"


def _require_changeset(plan: dict) -> None:
    if not isinstance(plan, dict) or any(
        not isinstance(plan.get(key), list) for key in ("update", "retire", "add")
    ):
        raise ValueError("invalid dossier evidence changeset")


def _claim_fields(item: dict) -> tuple[str, str] | None:
    if not isinstance(item, dict) or item.get("claim_type") not in _CLAIM_TYPES:
        return None
    text = item.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    return item["claim_type"], text.strip()


def _apply_changeset(plan: dict, active: list[dict],
                     user_evidence: dict[int, str]) -> None:
    by_id = {claim["id"]: claim for claim in active}
    retired: set[int] = set()
    for item in plan["update"]:
        fields = _claim_fields(item)
        refs = grounded_evidence.validated_refs(
            item, user_evidence, grounded_evidence.CHANGE_BASES,
        )
        claim_id = item.get("id") if isinstance(item, dict) else None
        if fields is None or refs is None or claim_id not in by_id or claim_id in retired:
            continue
        portrait_claims.supersede(claim_id)
        retired.add(claim_id)
        portrait_claims.add(
            claim_type=fields[0], text=fields[1], basis=item["basis"],
            evidence=refs, source_turn=max(ref["turn"] for ref in refs),
        )
    for item in plan["retire"]:
        refs = grounded_evidence.validated_refs(
            item, user_evidence, {"explicit", "confirmed"},
        )
        claim_id = item.get("id") if isinstance(item, dict) else None
        if refs is None or claim_id not in by_id or claim_id in retired:
            continue
        portrait_claims.supersede(claim_id)
        retired.add(claim_id)
    for item in plan["add"]:
        fields = _claim_fields(item)
        refs = grounded_evidence.validated_refs(
            item, user_evidence, grounded_evidence.CHANGE_BASES,
        )
        if fields is None or refs is None:
            continue
        portrait_claims.add(
            claim_type=fields[0], text=fields[1], basis=item["basis"],
            evidence=refs, source_turn=max(ref["turn"] for ref in refs),
        )


async def run(start_turn: int, end_turn: int) -> None:
    rows = memory.messages_in_turn_range(start_turn, end_turn)
    if not rows:
        return
    with runtime.ensure_snapshot():
        evidence_prompt = runtime.resolve(
            "memory.dossier.evidence", _EVIDENCE_PROMPT,
        )
        for offset in range(0, len(rows), _EVIDENCE_CHUNK_MESSAGES):
            chunk = rows[offset:offset + _EVIDENCE_CHUNK_MESSAGES]
            context_start = chunk[0]["turn"]
            if (
                offset > 0
                and rows[offset - 1]["role"] == "assistant"
                and rows[offset - 1]["stream"] == chunk[0]["stream"]
            ):
                context_start = rows[offset - 1]["turn"]
            chunk_span = span_text(context_start, chunk[-1]["turn"])
            user_evidence = {
                row["turn"]: row["content"] for row in chunk if row["role"] == "user"
            }
            active = portrait_claims.active()
            plan = await chat_json(
                system_prompt=evidence_prompt,
                user_prompt=(
                    "## Active portrait claims (validated prior evidence)\n"
                    f"{_render_claim_board(active)}\n\n"
                    "## New conversation span\n"
                    f"{chunk_span}"
                ),
                stage="dossier_evidence",
            )
            _require_changeset(plan)
            _apply_changeset(plan, active, user_evidence)

        claims = portrait_claims.active()
        facts = model.active_facts()
        if not claims and not facts:
            model.set_dossier("")
            return
        render_prompt = runtime.resolve("memory.dossier.render", _RENDER_PROMPT)
        result = await chat_json(
            system_prompt=render_prompt,
            user_prompt=(
                "## Verified active portrait claims\n"
                f"{_render_claim_board(claims)}\n\n"
                "## Active durable facts\n"
                f"{_render_facts(facts)}"
            ),
            stage="dossier_render",
        )
    text = result.get("dossier") if isinstance(result, dict) else None
    text = text.strip() if isinstance(text, str) else ""
    if not text:
        raise ValueError("invalid dossier render output")
    model.set_dossier(text)
