"""Provider-neutral conservative token estimates for bounded Inquiry state."""
import json


def estimate_tokens(value: object) -> int:
    """Estimate serialized JSON without depending on one model's tokenizer.

    ASCII-heavy text is usually near four characters per token, so three is a
    safety margin. Non-ASCII tokenization varies much more across providers;
    counting two tokens per code point deliberately leaves headroom for CJK,
    emoji, and less common scripts.
    """
    serialized = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"),
    )
    non_ascii = sum(ord(char) > 127 for char in serialized)
    ascii_chars = len(serialized) - non_ascii
    return max(1, (non_ascii * 2) + ((ascii_chars + 2) // 3))
