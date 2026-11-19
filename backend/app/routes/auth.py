import threading
import time
from collections import deque

from fastapi import APIRouter, HTTPException, Request, Response

from .. import auth

router = APIRouter(prefix="/auth", tags=["auth"])

_LOGIN_MAX_FAILURES = 5
_LOGIN_WINDOW_SECONDS = 60
_login_failures: dict[str, deque[float]] = {}
_login_lock = threading.Lock()


def _client_ip(request: Request) -> str:
    real_ip = (request.headers.get("x-real-ip") or "").strip()
    if real_ip:
        return real_ip
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    return request.client.host if request.client else "unknown"


def _prune_failures(attempts: deque[float], now: float) -> None:
    cutoff = now - _LOGIN_WINDOW_SECONDS
    while attempts and attempts[0] <= cutoff:
        attempts.popleft()


@router.get("/status")
def status(request: Request):
    token = request.cookies.get(auth.SESSION_COOKIE_NAME)
    return {
        "auth_required": auth.AUTH_ENABLED,
        "authenticated": (not auth.AUTH_ENABLED) or auth.verify_session_token(token),
    }


@router.post("/login")
def login(payload: dict, request: Request, response: Response):
    password = str(payload.get("password") or "")
    if not auth.AUTH_ENABLED:
        return {"ok": True}

    ip = _client_ip(request)
    now = time.monotonic()
    with _login_lock:
        attempts = _login_failures.get(ip)
        if attempts is not None:
            _prune_failures(attempts, now)
            if len(attempts) >= _LOGIN_MAX_FAILURES:
                retry_after = max(1, int(_LOGIN_WINDOW_SECONDS - (now - attempts[0])) + 1)
                raise HTTPException(
                    status_code=429,
                    detail="Too many login attempts. Please wait a minute and try again.",
                    headers={"Retry-After": str(retry_after)},
                )

    if not auth.check_password(password):
        with _login_lock:
            attempts = _login_failures.setdefault(ip, deque())
            _prune_failures(attempts, now)
            attempts.append(now)
        raise HTTPException(status_code=401, detail="Incorrect password")

    with _login_lock:
        _login_failures.pop(ip, None)

    token = auth.create_session_token()
    response.set_cookie(
        key=auth.SESSION_COOKIE_NAME,
        value=token,
        max_age=auth.SESSION_MAX_AGE_SECONDS,
        expires=auth.SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        # Not "secure": the app is reachable over both plain HTTP (LAN) and HTTPS
        # (Tailscale Funnel) — a Secure-only cookie would break LAN-only access.
        secure=False,
        path="/",
    )
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(auth.SESSION_COOKIE_NAME, path="/")
    return {"ok": True}
