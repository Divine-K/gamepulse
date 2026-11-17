from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import (
    JWT_ALGORITHM,
    api_key_matches,
    create_access_token,
    decode_access_token,
    generate_api_key,
    hash_password,
    parse_api_key_prefix,
    verify_password,
)


def test_password_hash_is_argon2_and_verifies() -> None:
    hashed = hash_password("s3cret-pass")
    assert hashed.startswith("$argon2id$")
    assert verify_password("s3cret-pass", hashed)
    assert not verify_password("wrong", hashed)


def test_access_token_round_trip() -> None:
    token, expires_in = create_access_token("user-1", "developer")
    claims = decode_access_token(token)
    assert claims["sub"] == "user-1"
    assert claims["role"] == "developer"
    assert expires_in == get_settings().access_token_expire_minutes * 60


def test_expired_token_is_rejected() -> None:
    expired = jwt.encode(
        {"sub": "u", "exp": datetime.now(UTC) - timedelta(seconds=5)},
        get_settings().secret_key,
        algorithm=JWT_ALGORITHM,
    )
    with pytest.raises(AppError) as exc:
        decode_access_token(expired)
    assert exc.value.status_code == 401


def test_token_signed_with_other_key_is_rejected() -> None:
    forged = jwt.encode(
        {"sub": "u", "exp": datetime.now(UTC) + timedelta(hours=1)},
        "x" * 40,
        algorithm=JWT_ALGORITHM,
    )
    with pytest.raises(AppError):
        decode_access_token(forged)


def test_unsigned_token_is_rejected() -> None:
    unsigned = jwt.encode({"sub": "u", "exp": 9999999999}, key=None, algorithm="none")
    with pytest.raises(AppError):
        decode_access_token(unsigned)


def test_api_key_format_hash_and_match() -> None:
    full_key, prefix, key_hash = generate_api_key()
    assert full_key.startswith(f"gp_{prefix}_")
    assert parse_api_key_prefix(full_key) == prefix
    assert key_hash != full_key
    assert api_key_matches(full_key, key_hash)
    assert not api_key_matches(full_key + "0", key_hash)


@pytest.mark.parametrize(
    "bad", ["", "gp_", "nope", "gp_abc_def", "GP_" + "a" * 12 + "_" + "b" * 64]
)
def test_malformed_api_keys_have_no_prefix(bad: str) -> None:
    assert parse_api_key_prefix(bad) is None
