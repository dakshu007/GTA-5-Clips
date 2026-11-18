"""Single-owner authentication.

* One password, hashed with scrypt, stored in the settings table.
* First run: the server prints a one-time setup code to its console. The password
  can only be created by someone who can see that console (or via the CLI), so a
  stranger who reaches the URL first cannot claim the install.
* Sessions are signed, HttpOnly cookies. Changing the password bumps a session
  version, which signs out every other device.
* Repeated failed logins from one IP lock that IP out for 15 minutes.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from . import config, db

COOKIE_NAME = "gtaclips_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 14  # 14 days
MIN_PASSWORD_LEN = 8
MAX_FAILS = 5
LOCKOUT_SECONDS = 15 * 60

_setup_code: str | None = None
_fails: dict[str, deque] = defaultdict(deque)
_fails_lock = threading.Lock()


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(config.secret_key(), salt="gtaclips-session")


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if algo != "scrypt":
        return False
    candidate = hash_password(password, bytes.fromhex(salt_hex)).split("$")[2]
    return hmac.compare_digest(candidate, digest_hex)


def is_configured() -> bool:
    return bool(db.get_kv("auth.password_hash"))


def setup_code() -> str:
    """One-time code that must accompany the first password set from the browser."""
    global _setup_code
    if _setup_code is None:
        _setup_code = "-".join(secrets.token_hex(2).upper() for _ in range(3))
    return _setup_code


def set_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LEN:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LEN} characters")
    db.set_kv("auth.password_hash", hash_password(password))
    db.set_kv("auth.session_version", int(db.get_kv("auth.session_version", 0)) + 1)


def check_password(password: str) -> bool:
    stored = db.get_kv("auth.password_hash")
    return bool(stored) and verify_password(password, stored)


def make_session_token() -> str:
    return _serializer().dumps({"v": int(db.get_kv("auth.session_version", 0)), "n": secrets.token_hex(8)})


def validate_session_token(token: str | None) -> bool:
    if not token:
        return False
    try:
        data = _serializer().loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return False
    return int(data.get("v", -1)) == int(db.get_kv("auth.session_version", 0))


def revoke_all_sessions() -> None:
    db.set_kv("auth.session_version", int(db.get_kv("auth.session_version", 0)) + 1)


# ---------------------------------------------------------------- brute-force guard

def locked_out(ip: str) -> int:
    """Seconds remaining in lockout for this IP (0 if not locked)."""
    now = time.time()
    with _fails_lock:
        q = _fails[ip]
        while q and now - q[0] > LOCKOUT_SECONDS:
            q.popleft()
        if len(q) >= MAX_FAILS:
            return int(LOCKOUT_SECONDS - (now - q[0])) + 1
    return 0


def record_failure(ip: str) -> None:
    with _fails_lock:
        _fails[ip].append(time.time())


def clear_failures(ip: str) -> None:
    with _fails_lock:
        _fails.pop(ip, None)


# ---------------------------------------------------------------- signed media links

def _media_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(config.secret_key(), salt="gtaclips-media")


def sign_media(clip_id: int) -> str:
    return _media_serializer().dumps({"clip": clip_id})


def verify_media(token: str, max_age: int = 6 * 3600) -> int | None:
    try:
        return int(_media_serializer().loads(token, max_age=max_age)["clip"])
    except (BadSignature, SignatureExpired, KeyError, ValueError, TypeError):
        return None


def sign_state(data: dict) -> str:
    return URLSafeTimedSerializer(config.secret_key(), salt="gtaclips-oauth").dumps(data)


def verify_state(token: str, max_age: int = 900) -> dict | None:
    try:
        return URLSafeTimedSerializer(config.secret_key(), salt="gtaclips-oauth").loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
