"""Single-shared-password session auth, gated by APP_PASSWORD.

Requires APP_PASSWORD to be set unless AUTH_DISABLED=true is explicitly passed
for local development, preventing accidental fail-open deployments.
"""
import base64
import hashlib
import hmac
import logging
import os
import time

logger = logging.getLogger("app.auth")

SESSION_COOKIE_NAME = "session"
SESSION_MAX_AGE_SECONDS = 90 * 24 * 60 * 60  # 90 days

APP_PASSWORD = os.environ.get("APP_PASSWORD", "").strip()
AUTH_DISABLED = os.environ.get("AUTH_DISABLED", "").strip().lower() in {"1", "true", "yes", "on"}
if not APP_PASSWORD and not AUTH_DISABLED:
    raise RuntimeError(
        "APP_PASSWORD is not set. Set APP_PASSWORD in .env, or set AUTH_DISABLED=true for local development."
    )
AUTH_ENABLED = bool(APP_PASSWORD)

_EXPLICIT_SESSION_SECRET = os.environ.get("APP_SESSION_SECRET", "").strip()
if AUTH_ENABLED and not _EXPLICIT_SESSION_SECRET:
    logger.warning("APP_SESSION_SECRET is not set; deriving session signing key from APP_PASSWORD")

# Falls back to a fixed derivation from APP_PASSWORD so a token stays valid across
# restarts even if APP_SESSION_SECRET isn't set — but setting it explicitly is preferred.
_SESSION_SECRET = _EXPLICIT_SESSION_SECRET or hashlib.sha256(
    f"sleep-wellness-tracker::{APP_PASSWORD}".encode()
).hexdigest()


def check_password(candidate: str) -> bool:
    return AUTH_ENABLED and hmac.compare_digest(candidate or "", APP_PASSWORD)


def _sign(payload: str) -> str:
    return hmac.new(_SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()


def create_session_token(max_age_seconds: int = SESSION_MAX_AGE_SECONDS) -> str:
    expires_at = int(time.time()) + max_age_seconds
    payload = str(expires_at)
    signature = _sign(payload)
    raw = f"{payload}.{signature}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def verify_session_token(token: str | None) -> bool:
    if not token or not AUTH_ENABLED:
        return False
    try:
        raw = base64.urlsafe_b64decode(token.encode()).decode()
        payload, signature = raw.rsplit(".", 1)
    except Exception:
        return False
    if not hmac.compare_digest(signature, _sign(payload)):
        return False
    try:
        expires_at = int(payload)
    except ValueError:
        return False
    return time.time() < expires_at
