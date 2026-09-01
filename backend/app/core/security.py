"""Security primitives: password hashing (argon2id), JWT creation/validation.

Encryption keys come from environment via settings — never from source code.
The authenticated encryption primitives (AES-256-GCM, HKDF) live in
``app.services.crypto`` and are used by the message/media services.
"""
import base64
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from jose import JWTError, jwt

from app.core.config import settings


# --------------------------------------------------------------------------- #
# Password hashing — Argon2id (memory-hard, resistant to GPU cracking).        #
# --------------------------------------------------------------------------- #
_ph = PasswordHasher(time_cost=2, memory_cost=19 * 1024, parallelism=1, hash_len=32)


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, plain)
    except (VerifyMismatchError, InvalidHashError):
        return False


# --------------------------------------------------------------------------- #
# JWT tokens (signed with ``jwt_secret``; refresh cookie uses session_secret) #
# --------------------------------------------------------------------------- #
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_token(subject: str, token_type: str, expires_delta: timedelta, extra: Optional[dict] = None) -> str:
    expire = _utcnow() + expires_delta
    payload: dict[str, Any] = {"sub": subject, "type": token_type, "exp": expire}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: int) -> str:
    return create_token(
        str(user_id),
        "access",
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user_id: int) -> str:
    return create_token(
        str(user_id),
        "refresh",
        timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str, expected_type: Optional[str] = None) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    if expected_type and payload.get("type") != expected_type:
        return None
    return payload


# --------------------------------------------------------------------------- #
# Key loading helpers                                                         #
# --------------------------------------------------------------------------- #
def load_key_b64(b64_key: str) -> bytes:
    """Decode a base64 (standard or urlsafe) 32-byte key.

    Placeholder/unset values are rejected so a misconfigured deployment fails
    loudly at startup rather than silently decrypting nothing.
    """
    if not b64_key or b64_key in {"CHANGE_ME_32_byte_base64_key", "CHANGE_ME_32_byte_base64_master_key"}:
        raise ValueError("Encryption key is not configured (placeholder value detected)")
    try:
        raw = base64.b64decode(b64_key.encode("ascii"), validate=False)
    except (ValueError, TypeError) as exc:
        raise ValueError("Encryption key is not valid base64") from exc
    if len(raw) != 32:
        raise ValueError("Encryption key must decode to exactly 32 bytes")
    return raw
