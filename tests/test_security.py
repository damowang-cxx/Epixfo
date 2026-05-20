from datetime import timedelta

from app.core.security import create_signed_token, decode_signed_token, hash_password, verify_password


def test_password_hash_round_trip() -> None:
    password_hash = hash_password("secret123")

    assert verify_password("secret123", password_hash)
    assert not verify_password("wrong", password_hash)


def test_signed_token_round_trip() -> None:
    token = create_signed_token("1", "access", timedelta(minutes=5), {"roles": ["admin"]})

    payload = decode_signed_token(token, "access")

    assert payload is not None
    assert payload["sub"] == "1"
    assert payload["roles"] == ["admin"]
    assert decode_signed_token(token, "refresh") is None
