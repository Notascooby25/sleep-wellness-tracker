import json
import logging
import os

from sqlalchemy.orm import Session

from .. import models

logger = logging.getLogger("app.push_sender")

VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "").strip()
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "").strip()
VAPID_CLAIMS_SUB = os.environ.get("VAPID_CLAIMS_SUB", "").strip()
DEFAULT_REMINDER_MESSAGE = "Update your tracker"

PUSH_CONFIGURED = bool(VAPID_PRIVATE_KEY and VAPID_PUBLIC_KEY and VAPID_CLAIMS_SUB)


def send_reminder_push(db: Session, message: str | None) -> None:
    """Send a Web Push notification to every registered device. Prunes stale/revoked subscriptions."""
    if not PUSH_CONFIGURED:
        logger.warning("Skipping reminder push: VAPID_PRIVATE_KEY/PUBLIC_KEY/CLAIMS_SUB not fully configured")
        return

    from pywebpush import webpush, WebPushException

    subscriptions = db.query(models.PushSubscription).all()
    if not subscriptions:
        logger.info("Reminder push skipped: no registered devices")
        return

    payload = json.dumps({"title": "Sleep Wellness Tracker", "body": message or DEFAULT_REMINDER_MESSAGE})
    stale_ids: list[int] = []

    for subscription in subscriptions:
        subscription_info = {
            "endpoint": subscription.endpoint,
            "keys": {"p256dh": subscription.p256dh_key, "auth": subscription.auth_key},
        }
        try:
            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": VAPID_CLAIMS_SUB},
            )
        except WebPushException as exc:
            status_code = getattr(exc.response, "status_code", None)
            if status_code in (404, 410):
                logger.info("Pruning stale push subscription id=%s (status=%s)", subscription.id, status_code)
                stale_ids.append(subscription.id)
            else:
                logger.warning("Push send failed for subscription id=%s: %s", subscription.id, exc)
        except Exception:
            logger.exception("Unexpected error sending push for subscription id=%s", subscription.id)

    if stale_ids:
        db.query(models.PushSubscription).filter(models.PushSubscription.id.in_(stale_ids)).delete(
            synchronize_session=False
        )
        db.commit()
