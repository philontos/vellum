"""Deterministically fit responder messages into a hard context budget."""
from dataclasses import dataclass, field

from app.token_budget import clip_text, estimate_tokens


_OMITTED = "\n[… omitted for responder budget …]\n"


@dataclass
class ContextBuilder:
    base_sections: list[str]
    extra_sections: list[str]
    current_message: dict | None
    max_tokens: int
    sections: list[str] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)
    current_message_truncated: bool = False

    def __post_init__(self) -> None:
        if self.current_message is not None:
            self.history = [dict(self.current_message)]
        self._fit_current()

    def _messages(
        self, *, sections: list[str] | None = None,
        history: list[dict] | None = None,
    ) -> list[dict]:
        rendered_sections = [
            *self.base_sections,
            *(self.sections if sections is None else sections),
            *self.extra_sections,
        ]
        messages = [{"role": "system", "content": "\n\n".join(rendered_sections)}]
        messages.extend(self.history if history is None else history)
        return messages

    def _fits(
        self, *, sections: list[str] | None = None,
        history: list[dict] | None = None,
    ) -> bool:
        return estimate_tokens(
            self._messages(sections=sections, history=history),
        ) <= self.max_tokens

    def _fit_current(self) -> None:
        if self._fits():
            return
        if not self.history:
            raise ValueError("Responder context budget is smaller than fixed system context")
        self.current_message_truncated = True
        original = self.history[0]["content"]
        low, high = 0, len(original)
        best: str | None = None
        while low <= high:
            retained = (low + high) // 2
            head = (retained + 1) // 2
            tail = retained // 2
            candidate = (
                original[:head] + _OMITTED
                + (original[-tail:] if tail else "")
            )
            self.history[0]["content"] = candidate
            if self._fits():
                best = candidate
                low = retained + 1
            else:
                high = retained - 1
        if best is None:
            self.history[0]["content"] = ""
            if not self._fits():
                raise ValueError(
                    "Responder context budget is smaller than fixed system context",
                )
        else:
            self.history[0]["content"] = best

    def add_history_suffix(self, annotated_tail: list[dict]) -> int:
        """Keep a contiguous recent suffix; the current message is never dropped."""
        if not annotated_tail:
            return 0
        kept = 1
        for count in range(2, len(annotated_tail) + 1):
            candidate = [dict(item) for item in annotated_tail[-count:]]
            candidate[-1] = self.history[-1]
            if not self._fits(history=candidate):
                break
            self.history = candidate
            kept = count
        return kept

    def add_text_section(
        self, heading: str, text: str, allocation: int,
    ) -> tuple[bool, bool]:
        clipped, truncated = clip_text(
            text.strip(), allocation, omission_marker=_OMITTED,
        )
        if not clipped:
            return False, truncated
        block = f"{heading}\n{clipped}"
        candidate = [*self.sections, block]
        if not self._fits(sections=candidate):
            return False, truncated
        self.sections = candidate
        return True, truncated

    def add_item_section(
        self, heading: str, items: list[str], allocation: int,
        *, separator: str = "\n",
    ) -> tuple[int, int]:
        kept: list[str] = []
        truncated = 0
        for item in items:
            used = estimate_tokens(separator.join(kept)) if kept else 0
            remaining = max(0, allocation - used)
            clipped, was_truncated = clip_text(
                item, remaining, omission_marker=_OMITTED,
            )
            if not clipped:
                break
            block = f"{heading}\n{separator.join([*kept, clipped])}"
            candidate = [*self.sections, block]
            if not self._fits(sections=candidate):
                break
            kept.append(clipped)
            truncated += int(was_truncated)
            if was_truncated:
                break
        if kept:
            self.sections.append(f"{heading}\n{separator.join(kept)}")
        return len(kept), truncated

    def build(self) -> list[dict]:
        messages = self._messages()
        if estimate_tokens(messages) > self.max_tokens:
            raise ValueError("Responder context exceeded its hard budget")
        return messages
