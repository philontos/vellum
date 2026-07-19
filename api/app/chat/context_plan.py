"""Resolve the Controller's responder-context request with deterministic rails."""
import re

from app.inquiry.contracts import InquiryDecision


_LOW_INFORMATION = {
    "hello", "hi", "hey", "hello there", "hi there",
    "你好", "您好", "嗨", "哈喽", "在吗",
}


def _normalized(text: str) -> str:
    value = re.sub(r"\s+", " ", text.strip().casefold())
    return value.strip(".!?。！？,，~～ ")


def effective_mode(decision: InquiryDecision, user_text: str) -> str:
    """Keep greetings lean and make the grounded Ledger primary in synthesis."""
    if decision.route == "synthesize":
        return "recent"
    if decision.route == "direct" and _normalized(user_text) in _LOW_INFORMATION:
        return "minimal"
    return decision.context_mode
