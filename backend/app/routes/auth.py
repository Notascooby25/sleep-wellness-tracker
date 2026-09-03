from fastapi import APIRouter, HTTPException, Request, Response

from .. import auth

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/status")
def status(request: Request):
    token = request.cookies.get(auth.SESSION_COOKIE_NAME)
    return {
        "auth_required": auth.AUTH_ENABLED,
        "authenticated": (not auth.AUTH_ENABLED) or auth.verify_session_token(token),
    }


@router.post("/login")
def login(payload: dict, response: Response):
    password = str(payload.get("password") or "")
    if not auth.AUTH_ENABLED:
        return {"ok": True}
    if not auth.check_password(password):
        raise HTTPException(status_code=401, detail="Incorrect password")
    token = auth.create_session_token()
    response.set_cookie(
        key=auth.SESSION_COOKIE_NAME,
        value=token,
        max_age=auth.SESSION_MAX_AGE_SECONDS,
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
