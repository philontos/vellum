"""Correlate one orchestrated turn with its LLM spans and Ledger revisions."""
import json
from contextlib import contextmanager
from dataclasses import dataclass, field

from app.llm.client import capture_llm_calls
from app.store import traces, turn_runs


def _context_meta(context: dict) -> dict:
    budget = context.get("budget") or {}
    policy = context.get("policy") or {}
    return {
        "estimated_tokens": budget.get("estimated_tokens"),
        "max_input_tokens": budget.get("max_input_tokens"),
        "dropped_recent_messages": budget.get("dropped_recent_messages", 0),
        "dropped_cited_evidence": budget.get("dropped_cited_evidence", 0),
        "dropped_paused_inquiries": budget.get(
            "dropped_paused_inquiries", 0,
        ),
        "current_user_turn_truncated": budget.get(
            "current_user_turn_truncated", False,
        ),
        "recent_message_count": len(context.get("recent_messages") or []),
        "cited_evidence_count": len(context.get("cited_evidence") or []),
        "paused_inquiry_count": len(context.get("paused_inquiries") or []),
        "had_active_inquiry": context.get("inquiry") is not None,
        "max_questions": policy.get("max_questions"),
        "questions_asked": policy.get("questions_asked"),
        "remaining_questions": policy.get("remaining_questions"),
    }


def _call_params(
    call: dict, *, pipeline_sequence: int,
    normalized_fields: tuple[str, ...] = (),
) -> dict:
    params = {
        "status": call.get("status"),
        "error": call.get("error"),
        "prompt_chars": call.get("prompt_chars"),
        "context": call.get("context") or {},
        "pipeline_sequence": pipeline_sequence,
    }
    if normalized_fields:
        params["normalized_fields"] = list(normalized_fields)
    return params


@dataclass
class TurnRunObserver:
    run_id: str
    user_turn: int
    inquiry_before_id: int | None
    revision_before: int | None
    configured_controller_model: str | None
    controller_calls: list[dict] = field(default_factory=list)
    controller_normalized_fields: tuple[str, ...] = ()
    response_context_meta: dict = field(default_factory=dict)
    controller_spans_persisted: bool = False
    finished: bool = False

    @classmethod
    def start(
        cls, *, run_id: str, user_turn: int, stream: str, context: dict,
        prompt_release_id: int | None, prompt_release_version: int | None,
        controller_model: str | None,
    ) -> "TurnRunObserver":
        inquiry = context.get("inquiry")
        revision_before = inquiry.get("revision") if inquiry is not None else None
        turn_runs.start(
            run_id=run_id,
            user_turn=user_turn,
            stream=stream,
            context_meta=_context_meta(context),
            prompt_release_id=prompt_release_id,
            prompt_release_version=prompt_release_version,
        )
        return cls(
            run_id=run_id,
            user_turn=user_turn,
            inquiry_before_id=(inquiry.get("id") if inquiry is not None else None),
            revision_before=revision_before,
            configured_controller_model=controller_model,
        )

    @contextmanager
    def capture_controller(self):
        with capture_llm_calls(self.controller_calls):
            yield

    def note_decision(self, decision) -> None:
        self.controller_normalized_fields = decision.normalized_fields

    def note_response_context(self, meta: dict | None) -> None:
        self.response_context_meta = dict(meta or {})

    def chat_pipeline_sequence(self) -> int:
        return len(self.controller_calls) + 1

    def _persist_controller_spans(self, turn: int) -> None:
        if self.controller_spans_persisted:
            return
        for attempt, call in enumerate(self.controller_calls, start=1):
            prompt = json.dumps({
                "system_prompt": call.get("system_prompt") or "",
                "user_prompt": call.get("user_prompt") or "",
            }, ensure_ascii=False)
            traces.record(
                turn=turn,
                stage=call.get("stage") or "inquiry.decide",
                model=call.get("model"),
                params=_call_params(
                    call,
                    pipeline_sequence=attempt,
                    normalized_fields=(
                        self.controller_normalized_fields
                        if attempt == len(self.controller_calls) else ()
                    ),
                ),
                prompt=prompt,
                output=call.get("response") or "",
                reasoning=call.get("reasoning"),
                prompt_tokens=call.get("prompt_tokens"),
                completion_tokens=call.get("completion_tokens"),
                duration_ms=call.get("duration_ms"),
                run_id=self.run_id,
                scenario="inquiry",
                attempt=attempt,
            )
        self.controller_spans_persisted = True

    def persist_controller_spans(self, turn: int) -> None:
        self._persist_controller_spans(turn)

    def complete(
        self, *, assistant_turn: int, applied, responder_model: str | None,
        controller_error: str | None,
    ) -> None:
        self._persist_controller_spans(assistant_turn)
        inquiry = applied.inquiry
        controller_model = (
            next((call.get("model") for call in reversed(self.controller_calls)
                  if call.get("model")), None)
            or self.configured_controller_model
        )
        selected_an_older_paused_inquiry = bool(
            self.inquiry_before_id is not None
            and inquiry is not None
            and inquiry["id"] != self.inquiry_before_id
            and applied.decision.expected_revision is not None
        )
        revision_before = (
            applied.decision.expected_revision
            if selected_an_older_paused_inquiry else self.revision_before
        )
        turn_runs.finish(
            run_id=self.run_id,
            assistant_turn=assistant_turn,
            route=applied.decision.route,
            status="degraded" if controller_error else "done",
            inquiry_id=inquiry["id"] if inquiry is not None else None,
            revision_before=revision_before,
            revision_after=inquiry["revision"] if inquiry is not None else None,
            controller_model=controller_model,
            responder_model=responder_model,
            decision=applied.decision.model_dump(mode="json"),
            error=controller_error,
            context_meta_update={
                "responder": self.response_context_meta,
                "controller_normalized_fields": list(
                    self.controller_normalized_fields,
                ),
            },
        )
        self.finished = True

    def fail(self, exc: Exception) -> None:
        if self.finished:
            return
        diagnostic_errors = []
        try:
            turn_runs.fail(
                self.run_id, f"{type(exc).__name__}: {exc}"[:2_000],
            )
        except Exception as diagnostic_error:
            diagnostic_errors.append(diagnostic_error)
        try:
            # A failed responder has no assistant turn. Anchor the already-run
            # controller spans to the triggering user turn so the failed path
            # remains inspectable and correlated by run_id.
            self._persist_controller_spans(self.user_turn)
        except Exception as diagnostic_error:
            diagnostic_errors.append(diagnostic_error)
        self.finished = True
        for diagnostic_error in diagnostic_errors:
            print(
                f"[turn_observer] failed to persist diagnostics: "
                f"{diagnostic_error!r}",
                flush=True,
            )
