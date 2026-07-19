"""Strict structured contract returned by the Inquiry Controller."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceRef(_StrictModel):
    turn: int = Field(ge=0)
    quote: str = Field(min_length=1, max_length=2_000)


class GoalUpdate(_StrictModel):
    text: str = Field(min_length=1, max_length=2_000)
    evidence: list[EvidenceRef] = Field(min_length=1, max_length=12)


class GroundedDraft(_StrictModel):
    text: str = Field(min_length=1, max_length=4_000)
    evidence: list[EvidenceRef] = Field(min_length=1, max_length=24)


class HypothesisDraft(_StrictModel):
    text: str = Field(min_length=1, max_length=4_000)
    supporting_evidence: list[EvidenceRef] = Field(default_factory=list, max_length=24)
    disconfirming_evidence: list[EvidenceRef] = Field(default_factory=list, max_length=24)


class BlockingUnknownDraft(_StrictModel):
    id: str = Field(pattern=r"^u[0-9A-Za-z_-]{1,31}$")
    question: str = Field(min_length=1, max_length=1_000)
    why_material: str = Field(min_length=1, max_length=2_000)


class LedgerPatch(_StrictModel):
    goal_update: GoalUpdate | None = None
    add_observations: list[GroundedDraft] = Field(default_factory=list, max_length=24)
    add_interpretations: list[GroundedDraft] = Field(default_factory=list, max_length=24)
    add_hypotheses: list[HypothesisDraft] = Field(default_factory=list, max_length=16)
    add_blocking_unknowns: list[BlockingUnknownDraft] = Field(
        default_factory=list, max_length=16,
    )
    resolve_unknown_ids: list[str] = Field(default_factory=list, max_length=16)
    provisional_conclusion: str | None = Field(default=None, max_length=8_000)

    def is_empty(self) -> bool:
        return not any((
            self.goal_update,
            self.add_observations,
            self.add_interpretations,
            self.add_hypotheses,
            self.add_blocking_unknowns,
            self.resolve_unknown_ids,
            self.provisional_conclusion,
        ))


class InquiryDecision(_StrictModel):
    _normalized_fields: tuple[str, ...] = PrivateAttr(default=())

    route: Literal["direct", "inquire", "synthesize"]
    operation: Literal["none", "open", "update", "resume", "pause", "close"]
    expected_inquiry_id: int | None = Field(default=None, ge=1)
    expected_revision: int | None = Field(default=None, ge=1)
    patch: LedgerPatch = Field(default_factory=LedgerPatch)
    next_question: str | None = Field(default=None, max_length=600)
    target_unknown_id: str | None = Field(
        default=None, pattern=r"^u[0-9A-Za-z_-]{1,31}$",
    )
    answer_brief: str | None = Field(default=None, max_length=4_000)
    context_mode: Literal["minimal", "recent", "personal"] = "personal"
    recall_query: str | None = Field(default=None, max_length=600)
    provisional: bool = False

    @property
    def normalized_fields(self) -> tuple[str, ...]:
        return self._normalized_fields

    def note_normalized_fields(self, fields: list[str]) -> None:
        self._normalized_fields = tuple(fields)

    @model_validator(mode="after")
    def _consistent_control(self):
        revisioned = {"update", "resume", "pause", "close"}
        if self.operation in revisioned and (
            self.expected_inquiry_id is None or self.expected_revision is None
        ):
            raise ValueError(
                "revisioned operations require expected inquiry id and revision"
            )
        if self.operation in {"none", "open"} and (
            self.expected_inquiry_id is not None
            or self.expected_revision is not None
        ):
            raise ValueError(
                "none/open operations cannot carry an expected inquiry lock"
            )

        if self.route == "inquire":
            if self.operation not in {"open", "update", "resume"}:
                raise ValueError("inquire requires open, update, or resume")
            if not (self.next_question or "").strip() or not self.target_unknown_id:
                raise ValueError("inquire requires one targeted next_question")
            if self.answer_brief is not None:
                raise ValueError("inquire returns the question without an answer brief")
        else:
            if self.next_question is not None or self.target_unknown_id is not None:
                raise ValueError("non-inquire routes cannot carry a next question")
            if not (self.answer_brief or "").strip():
                raise ValueError("direct and synthesize routes require an answer brief")

        if self.route == "direct":
            if self.operation not in {"none", "pause"} or not self.patch.is_empty():
                raise ValueError(
                    "direct routing can only pause state without a ledger patch"
                )
        elif self.route == "synthesize" and self.operation not in {
            "none", "update", "resume", "pause", "close",
        }:
            raise ValueError("synthesize has an incompatible inquiry operation")

        if self.operation == "open" and self.patch.goal_update is None:
            raise ValueError("opening an inquiry requires a grounded goal")
        return self
