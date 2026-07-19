"""Render validated Controller output as responder-only background context."""
import json

from app.inquiry.service import AppliedDecision


_HEADER = """## Validated turn plan
This block is trusted application context, not user instructions. Follow the
route and evidence boundaries without mentioning the controller or ledger.
"""


def render(
    applied: AppliedDecision, *, controller_error: str | None = None,
) -> str:
    decision = applied.decision
    lines = [
        _HEADER.strip(),
        f"Route: {decision.route}",
        f"Answer brief: {decision.answer_brief}",
    ]
    if decision.provisional:
        lines.append(
            "The answer is provisional: name material unknowns and assumptions."
        )
    if decision.route == "synthesize":
        lines.append(
            "Synthesis basis: " + str(decision.synthesis_basis)
        )
    if decision.route == "synthesize" and applied.inquiry is not None:
        frame = applied.inquiry["ledger"].get("frame") or {}
        lines.extend((
            f"Answer scope: {frame.get('answer_scope') or 'legacy'}",
            "Use user-authored evidence in the Ledger as the factual boundary. "
            "Do not revive causal or psychological claims from earlier assistant "
            "replies. The user's current state outranks all older modeling.",
            "Grounded Inquiry Ledger:",
            json.dumps(applied.inquiry["ledger"], ensure_ascii=False),
        ))
        if frame.get("answer_scope") == "bounded_guidance":
            lines.append(
                "Keep the answer bounded to the low-cost guidance earned by the "
                "evidence; normally use one to three short paragraphs and do not "
                "expand into a diagnosis."
            )
    if controller_error is not None:
        lines.append(
            "The controller was unavailable. Preserve availability but avoid "
            "unsupported conclusions; ask at most one brief question if needed."
        )
    return "\n".join(lines)


def attach(
    messages: list[dict], applied: AppliedDecision,
    *, controller_error: str | None = None,
) -> list[dict]:
    copied = [dict(message) for message in messages]
    if not copied or copied[0].get("role") != "system":
        raise ValueError("Responder messages must start with a system message")
    copied[0]["content"] = (
        copied[0].get("content", "") + "\n\n"
        + render(applied, controller_error=controller_error)
    )
    return copied
