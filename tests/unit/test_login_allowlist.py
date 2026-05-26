"""Tests for DB-backed login accounts and password hashing."""

from app.core.password_hash import hash_password, verify_password


class TestPasswordHash:
    def test_hash_and_verify(self):
        stored = hash_password("test-secret-99")
        assert verify_password("test-secret-99", stored)
        assert not verify_password("wrong", stored)

    def test_different_hashes_per_call(self):
        a = hash_password("same")
        b = hash_password("same")
        assert a != b
        assert verify_password("same", a)
        assert verify_password("same", b)
