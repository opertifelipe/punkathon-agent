from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt

AUTH_SECRET_ENV_VAR = "PUNKAGENT_AUTH_SECRET"
AUTH_SECRET_FALLBACK = "punkagent-dev-secret-change-me-32bytes-minimum"
AUTH_TOKEN_LIFETIME_DAYS = 30
PASSWORD_HASH_ITERATIONS = 600_000


def normalize_email(value: str) -> str:
    return value.strip().casefold()


def _auth_secret() -> str:
    return os.getenv(AUTH_SECRET_ENV_VAR, AUTH_SECRET_FALLBACK)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_HASH_ITERATIONS,
    )
    digest = base64.b64encode(derived).decode("ascii")
    return f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}${salt}${digest}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_raw, salt, expected_digest = password_hash.split("$", 3)
    except ValueError:
        return False

    if algorithm != "pbkdf2_sha256":
        return False

    try:
        iterations = int(iterations_raw)
    except ValueError:
        return False

    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    actual_digest = base64.b64encode(derived).decode("ascii")
    return hmac.compare_digest(actual_digest, expected_digest)


def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=AUTH_TOKEN_LIFETIME_DAYS)).timestamp()),
    }
    return jwt.encode(payload, _auth_secret(), algorithm="HS256")


def decode_access_token(token: str) -> int:
    payload = jwt.decode(token, _auth_secret(), algorithms=["HS256"])
    raw_sub = payload.get("sub")
    if raw_sub is None:
        raise jwt.InvalidTokenError("Missing token subject.")
    return int(raw_sub)


__all__ = [
    "AUTH_TOKEN_LIFETIME_DAYS",
    "create_access_token",
    "decode_access_token",
    "hash_password",
    "normalize_email",
    "verify_password",
]
