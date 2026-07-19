"""One bounded structured LLM call that decides the next dialogue route."""
import json

from pydantic import ValidationError

from app.inquiry.contracts import InquiryDecision
from app.llm import client as llm
from app.prompts import runtime


class InquiryControllerError(RuntimeError):
    pass


_PROMPT = """You are the Inquiry Controller for a careful thinking partner.

Decide whether this turn should be answered directly, should ask one focused
question, or has enough grounded evidence to synthesize. Do not accept a user's
interpretation as an observation merely because it is stated confidently or
emotionally. Preserve multiple plausible hypotheses and seek both supporting and
disconfirming evidence when that distinction could materially change the answer.

Use inquiry only when missing user-specific information would materially change
the judgment. Do not interrogate simple factual, creative, operational, or fully
specified requests. When asking, ask exactly one high-information question and
keep the user-facing text brief. Never repeat an asked question. Obey the supplied
question policy; when its remaining budget is zero, synthesize with explicit
uncertainty or pause instead of asking again. Match the user's language in
next_question and answer_brief.

Choose the final responder's context deliberately. Use `context_mode=minimal`
for greetings and self-contained factual, writing, translation, or operational
requests; `recent` when the nearby exchange is sufficient; and `personal` only
when durable user knowledge or semantic recall materially improves the answer.
For personal mode, provide a focused `recall_query` when the current wording is
too vague to retrieve well. Otherwise use null.

When the goal has been answered and no blocking unknown remains, close the
Inquiry as part of synthesis. When the user suspends or changes away from the
topic, answer the new request directly and pause the active Inquiry in the same
decision (`route=direct`, `operation=pause`, empty patch). When a paused Inquiry
returns with enough evidence, it may use `route=synthesize`, `operation=resume`.
An already-paused Inquiry does not block opening a clearly different new topic.
Never synthesize an active Inquiry with `operation=none`; advance its revision.
These are semantic episode boundaries for downstream modeling.

`paused_inquiries` contains bounded summaries of older paused topics. When no
Inquiry is exploring/reviewing, you may select any matching paused topic with
`operation=resume` and its exact id/revision; code will load its full Ledger. The
summary itself is routing context, not evidence. If another Inquiry is active,
pause it first rather than trying to resume two topics in one operation.

Evidence citations must quote exact text from an application-provided user turn.
Never cite assistant text. A closed inquiry is immutable; revisiting it opens a
new linked inquiry. When resolving a blocking unknown, preserve what resolved it
as a grounded observation, interpretation, or hypothesis evidence update in the
same patch. Return only an object matching the supplied JSON schema.

patch must always be a JSON object. Use `{}` when there is no Ledger update.
Never return null for patch.
"""

_REPAIR_PROMPT = """Repair an invalid InquiryDecision.

Return one JSON object matching the schema exactly. Preserve the intended meaning
where possible, but remove unsupported fields and fix inconsistent routing,
operations, revisions, questions, and answer briefs. Match the user's language
for user-facing text. Do not add prose or markdown.
"""


def _input(
    context: dict, *, invalid: object | None = None, errors: str | None = None,
) -> str:
    payload = {
        "decision_schema": InquiryDecision.model_json_schema(),
        "context": context,
    }
    if invalid is not None:
        payload["invalid_decision"] = invalid
    if errors is not None:
        payload["validation_errors"] = errors
    return json.dumps(payload, ensure_ascii=False)


def _validate(raw: object) -> InquiryDecision:
    normalized_fields: list[str] = []
    candidate = raw
    if isinstance(raw, dict) and raw.get("patch") is None:
        candidate = {**raw, "patch": {}}
        normalized_fields.append("patch")
    decision = InquiryDecision.model_validate(candidate)
    decision.note_normalized_fields(normalized_fields)
    return decision


async def decide(context: dict) -> InquiryDecision:
    with runtime.ensure_snapshot():
        try:
            raw = await llm.chat_json(
                system_prompt=runtime.resolve("inquiry.controller", _PROMPT),
                user_prompt=_input(context),
                stage="inquiry.decide",
                scenario="inquiry",
                context={"stream": context.get("stream", "")},
            )
            try:
                return _validate(raw)
            except ValidationError as error:
                invalid: object | None = raw
                first_error: Exception = error
        except llm.StructuredResponseParseError as error:
            invalid = None
            first_error = error

        try:
            repaired = await llm.chat_json(
                system_prompt=runtime.resolve("inquiry.repair", _REPAIR_PROMPT),
                user_prompt=_input(
                    context, invalid=invalid, errors=str(first_error),
                ),
                stage="inquiry.repair",
                scenario="inquiry",
                context={"stream": context.get("stream", "")},
            )
            return _validate(repaired)
        except (ValidationError, llm.StructuredResponseParseError) as final_error:
            raise InquiryControllerError(
                "Inquiry Controller returned invalid decisions twice"
            ) from final_error
