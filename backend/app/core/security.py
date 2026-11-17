"""Password hashing, JWT access tokens and game API keys."""

import hashlib
import hmac
import re
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings
from app.core.errors import AppError

_password_hasher = PasswordHash.recommended()  # Argon2id
# Verified against when the email is unknown, so login timing doesn't reveal valid emails.
DUMMY_PASSWORD_HASH = _password_hasher.hash("not-a-real-password")

JWT_ALGORITHM = "HS256"

API_KEY_PATTERN = re.compile(r"^gp_([0-9a-f]{12})_([0-9a-f]{64})$")


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hasher.verify(password, password_hash)


def create_access_token(subject: str, role: str) -> tuple[str, int]:
    """Return (token, expires_in_seconds)."""
    settings = get_settings()
    now = datetime.now(UTC)
    expires = timedelta(minutes=settings.access_token_expire_minutes)
    claims = {"sub": subject, "role": role, "iat": now, "exp": now + expires}
    return jwt.encode(claims, settings.secret_key, algorithm=JWT_ALGORITHM), int(
        expires.total_seconds()
    )


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            get_settings().secret_key,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise AppError(
            "invalid_token",
            "Invalid or expired token.",
            401,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def generate_api_key() -> tuple[str, str, str]:
    """Return (full_key, prefix, sha256_hash). The full key must be shown only once."""
    prefix = secrets.token_hex(6)
    secret = secrets.token_hex(32)
    full_key = f"gp_{prefix}_{secret}"
    return full_key, prefix, hash_api_key(full_key)


def hash_api_key(full_key: str) -> str:
    # 256-bit random keys don't need a slow hash; SHA-256 keeps per-request auth cheap.
    return hashlib.sha256(full_key.encode()).hexdigest()


def parse_api_key_prefix(full_key: str) -> str | None:
    match = API_KEY_PATTERN.match(full_key)
    return match.group(1) if match else None


def api_key_matches(full_key: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_api_key(full_key), stored_hash)
