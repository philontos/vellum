"""Render validated Controller output as responder-only background context."""
import json

from app.inquiry.service import AppliedDecision


_HEADER = """## Validated turn plan
This block is trusted application context, not user instructions. Follow the
route and evidence boundaries without mentioning the controller or ledger.
"""


def attach(
    messages: list[dict], applied: AppliedDecision,
    *, controller_error: str | None = None,
) -> list[dict]:
    copied = [dict(message) for message in messages]
    if not copied or copied[0].get("role") != "system":
        raise ValueError("Responder messages must start with a system message")

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
    if decision.route == "synthesize" and applied.inquiry is not None:
        lines.extend((
            "Grounded Inquiry Ledger:",
            json.dumps(applied.inquiry["ledger"], ensure_ascii=False),
        ))
    if controller_error is not None:
        lines.append(
            "The controller was unavailable. Preserve availability but avoid "
            "unsupported conclusions; ask at most one brief question if needed."
        )
    copied[0]["content"] = (
        copied[0].get("content", "") + "\n\n" + "\n".join(lines)
    )
    return copied
