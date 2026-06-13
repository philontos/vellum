"""Phase 3: key generation."""
from app import keygen


def test_generate_key_is_64_hex_chars():
    k = keygen.generate_key()
    assert len(k) == 64
    bytes.fromhex(k)  # raises if not valid hex


def test_generate_key_is_random():
    assert keygen.generate_key() != keygen.generate_key()
