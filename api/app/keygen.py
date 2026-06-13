"""Generate a fresh 256-bit database key.

    python -m app.keygen

The key is printed ONCE to stdout and never persisted. Store it in a password
manager or a key file kept OUTSIDE your data dir, and supply it at runtime via
VELLUM_DB_KEY. There is no backdoor: lose the key and the encrypted data is
unrecoverable.
"""
import secrets
import sys


def generate_key() -> str:
    """A random 256-bit key as 64 hex chars, suitable for VELLUM_DB_KEY."""
    return secrets.token_hex(32)


def main() -> None:
    key = generate_key()
    print(key)  # stdout: just the key, so it can be captured/piped
    print(
        "\n  ^ Your 256-bit VELLUM_DB_KEY — NOT saved anywhere.\n"
        "  Store it in a password manager or a key file OUTSIDE the data dir.\n"
        "  Use it at runtime:   export VELLUM_DB_KEY=<key>\n"
        "  No backdoor: lose it and the data is gone forever.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
