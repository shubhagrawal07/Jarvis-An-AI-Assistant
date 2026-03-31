from app.core.security import hash_password, verify_password


def test_hash_and_verify_roundtrip():
    h = hash_password("password12")
    assert h.startswith("$2")
    assert verify_password("password12", h)
    assert not verify_password("wrong", h)


def test_verify_rejects_empty_hash():
    assert not verify_password("x", "")
