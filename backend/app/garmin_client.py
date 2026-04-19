import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("app.garmin")

try:
    from garminconnect import Garmin
except Exception:  # pragma: no cover - optional dependency at runtime
    Garmin = None
    logger.exception("Garmin library import failed")


class GarminClientError(RuntimeError):
    pass


def _garmin_email() -> str:
    return os.getenv("GARMIN_EMAIL", "").strip()


def _garmin_password() -> str:
    return os.getenv("GARMIN_PASSWORD", "").strip()


def is_garmin_configured() -> bool:
    return bool(_garmin_email() and _garmin_password())


def _token_store_dir() -> str:
    return os.getenv("GARMIN_TOKEN_DIR", "/app/garmin_tokens")


def _token_store_path() -> str:
    token_dir = Path(_token_store_dir())
    token_dir.mkdir(parents=True, exist_ok=True)
    return str(token_dir / "garmin_tokens.json")


def get_garmin_client() -> Any:
    if Garmin is None:
        logger.error("Garmin client requested but garminconnect package is not installed")
        raise GarminClientError("garminconnect package is not installed")

    if not is_garmin_configured():
        logger.warning(
            "Garmin client requested without complete credentials; email_set=%s password_set=%s",
            bool(_garmin_email()),
            bool(_garmin_password()),
        )
        raise GarminClientError("GARMIN_EMAIL / GARMIN_PASSWORD are not configured")

    email = _garmin_email()
    password = _garmin_password()
    token_store = _token_store_path()

    logger.info(
        "Starting Garmin login; email=%s token_store=%s token_exists=%s",
        email,
        token_store,
        Path(token_store).exists(),
    )

    client = Garmin(email, password)
    try:
        # Reuses cached tokens when available; falls back to credential login.
        client.login(token_store)
        logger.info("Garmin login succeeded; token_store=%s", token_store)
    except Exception as exc:
        logger.exception("Garmin login failed for email=%s", email)
        raise GarminClientError(f"Garmin login failed: {exc}") from exc

    return client
