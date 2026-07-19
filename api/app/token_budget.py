"""Provider-neutral conservative token estimates for bounded model context."""
import json


def estimate_tokens(value: object) -> int:
    """Estimate serialized JSON without depending on one model tokenizer."""
    serialized = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"),
    )
    non_ascii = sum(ord(char) > 127 for char in serialized)
    ascii_chars = len(serialized) - non_ascii
    return max(1, (non_ascii * 2) + ((ascii_chars + 2) // 3))


def clip_text(
    text: str, max_tokens: int, *, omission_marker: str,
) -> tuple[str, bool]:
    """Fit text by keeping both ends, using the same conservative estimate."""
    if max_tokens <= 0:
        return "", bool(text)
    if estimate_tokens(text) <= max_tokens:
        return text, False
    low, high = 0, len(text)
    best = ""
    while low <= high:
        retained = (low + high) // 2
        head = (retained + 1) // 2
        tail = retained // 2
        candidate = (
            text[:head] + omission_marker + (text[-tail:] if tail else "")
        )
        if estimate_tokens(candidate) <= max_tokens:
            best = candidate
            low = retained + 1
        else:
            high = retained - 1
    return best, True
