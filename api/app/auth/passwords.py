"""Password policy and Argon2id hashing."""
from pwdlib import PasswordHash


MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 1024
_hasher = PasswordHash.recommended()
_dummy_hash: str | None = None


def validate(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"password must contain at least {MIN_PASSWORD_LENGTH} characters"
        )
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError("password is too long")


def hash_password(password: str) -> str:
    validate(password)
    return _hasher.hash(password)


def verify(password: str, password_hash: str) -> bool:
    if len(password) > MAX_PASSWORD_LENGTH:
        return False
    try:
        return _hasher.verify(password, password_hash)
    except (TypeError, ValueError):
        return False


def dummy_hash() -> str:
    """A real hash used to equalize work when a login username does not exist."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = _hasher.hash("vellum timing equalizer")
    return _dummy_hash
