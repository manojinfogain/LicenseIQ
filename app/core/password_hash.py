"""Password hashing for application login accounts (stdlib only)."""

from __future__ import annotations

import hashlib
import secrets

_PBKDF2_ITERATIONS = 100_000


def hash_password(password: str) -> str:
    """Return stored form: ``{salt}${hex_digest}``."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        _PBKDF2_ITERATIONS,
    )
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    if not password or not stored_hash or "$" not in stored_hash:
        return False
    salt, expected_hex = stored_hash.split("$", 1)
    if not salt or not expected_hex:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        _PBKDF2_ITERATIONS,
    )
    return secrets.compare_digest(digest.hex(), expected_hex)
