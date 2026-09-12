"""Password hashing and stateless cookie session helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import uuid


_ITERATIONS = 120_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    encoded = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _ITERATIONS
    ).hex()
    salt_hex = salt.hex()
    return f"pbkdf2_sha256${_ITERATIONS}${salt_hex}${encoded}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt, encoded = password_hash.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt),
            int(iterations),
        ).hex()
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(candidate, encoded)


def create_access_token(username: str, secret: str, expires_hours: int) -> str:
    payload = json.dumps(
        {"sub": username, "exp": time.time() + expires_hours * 3600, "jti": uuid.uuid4().hex},
        separators=(",", ":"),
    ).encode("utf-8")
    header = b"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    body = base64.urlsafe_b64encode(payload).rstrip(b"=")
    signature = base64.urlsafe_b64encode(
        hmac.new(secret.encode("utf-8"), header + b"." + body, hashlib.sha256).digest()
    ).rstrip(b"=")
    return ".".join(part.decode("ascii") for part in (header, body, signature))


def read_access_token(token: str, secret: str) -> dict[str, object] | None:
    try:
        header, body, signature = token.split(".")
        expected = base64.urlsafe_b64encode(
            hmac.new(
                secret.encode("utf-8"),
                header.encode("ascii") + b"." + body.encode("ascii"),
                hashlib.sha256,
            ).digest()
        ).rstrip(b"=")
        if not hmac.compare_digest(signature.encode("ascii"), expected):
            return None
        padding = "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(body + padding))
    except (KeyError, ValueError, UnicodeDecodeError):
        return None
    if payload.get("exp", 0) < time.time() or not isinstance(payload.get("sub"), str):
        return None
    return payload
