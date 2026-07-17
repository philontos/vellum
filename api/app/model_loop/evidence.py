"""Shared deterministic validation for model-proposed USER evidence."""

CHANGE_BASES = {"explicit", "confirmed", "inferred"}
WEAK_CONFIRMATIONS = {
    "yes", "yeah", "right", "correct", "maybe", "perhaps", "i guess",
    "对", "是的", "嗯", "可能", "可能吧", "也许",
}


def _normalized(value: str) -> str:
    return " ".join(value.split()).casefold()


def validated_refs(item: dict, user_evidence: dict[int, str],
                   allowed_bases: set[str]) -> list[dict] | None:
    """Return cleaned USER refs, or None when any provenance rule fails."""
    if not isinstance(item, dict) or item.get("basis") not in allowed_bases:
        return None
    refs = item.get("evidence")
    if not isinstance(refs, list) or not refs:
        return None
    cleaned = []
    normalized_quotes = []
    for ref in refs:
        if not isinstance(ref, dict):
            return None
        turn = ref.get("turn")
        quote = ref.get("quote")
        if type(turn) is not int or turn not in user_evidence:
            return None
        if not isinstance(quote, str) or not quote.strip():
            return None
        normalized_quote = _normalized(quote)
        if normalized_quote not in _normalized(user_evidence[turn]):
            return None
        cleaned.append({"turn": turn, "quote": quote.strip()})
        normalized_quotes.append(normalized_quote)
    if item.get("basis") == "inferred" and len({ref["turn"] for ref in cleaned}) < 2:
        return None
    if item.get("basis") == "confirmed" and all(
        quote in WEAK_CONFIRMATIONS for quote in normalized_quotes
    ):
        return None
    return cleaned


def source_turn(item: dict, user_evidence: dict[int, str],
                allowed_bases: set[str]) -> int | None:
    refs = validated_refs(item, user_evidence, allowed_bases)
    if refs is None:
        return None
    return max(ref["turn"] for ref in refs)
