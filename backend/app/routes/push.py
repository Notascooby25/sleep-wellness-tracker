import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/push", tags=["push"])
logger = logging.getLogger("app.push")

DEFAULT_REMINDER_MESSAGE = "Update your tracker"
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "").strip()


@router.get("/public-key")
def get_public_key():
    if not VAPID_PUBLIC_KEY:
        raise HTTPException(status_code=503, detail="Push notifications are not configured (VAPID_PUBLIC_KEY unset)")
    return {"public_key": VAPID_PUBLIC_KEY}


@router.get("/subscriptions", response_model=list[schemas.PushSubscriptionResponse])
def list_subscriptions(db: Session = Depends(get_db)):
    return db.query(models.PushSubscription).order_by(models.PushSubscription.created_at.asc()).all()


@router.post("/subscribe", response_model=schemas.PushSubscriptionResponse)
def subscribe(payload: schemas.PushSubscriptionCreate, db: Session = Depends(get_db)):
    existing = db.query(models.PushSubscription).filter(models.PushSubscription.endpoint == payload.endpoint).first()
    if existing:
        existing.p256dh_key = payload.keys.p256dh
        existing.auth_key = payload.keys.auth
        if payload.device_label:
            existing.device_label = payload.device_label
        db.commit()
        db.refresh(existing)
        return existing

    subscription = models.PushSubscription(
        endpoint=payload.endpoint,
        p256dh_key=payload.keys.p256dh,
        auth_key=payload.keys.auth,
        device_label=payload.device_label,
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


@router.delete("/subscriptions/{subscription_id}", status_code=204)
def unsubscribe(subscription_id: int, db: Session = Depends(get_db)):
    subscription = db.query(models.PushSubscription).filter(models.PushSubscription.id == subscription_id).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    db.delete(subscription)
    db.commit()
    return


@router.get("/reminders", response_model=list[schemas.ReminderScheduleResponse])
def list_reminders(db: Session = Depends(get_db)):
    return db.query(models.ReminderSchedule).order_by(models.ReminderSchedule.time_of_day.asc()).all()


@router.post("/reminders", response_model=schemas.ReminderScheduleResponse)
def create_reminder(payload: schemas.ReminderScheduleCreate, db: Session = Depends(get_db)):
    reminder = models.ReminderSchedule(
        time_of_day=payload.time_of_day,
        message=(payload.message or "").strip() or None,
        enabled=payload.enabled,
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


@router.put("/reminders/{reminder_id}", response_model=schemas.ReminderScheduleResponse)
def update_reminder(reminder_id: int, payload: schemas.ReminderScheduleUpdate, db: Session = Depends(get_db)):
    reminder = db.query(models.ReminderSchedule).filter(models.ReminderSchedule.id == reminder_id).first()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    if payload.time_of_day is not None:
        reminder.time_of_day = payload.time_of_day
    if payload.message is not None:
        reminder.message = payload.message.strip() or None
    if payload.enabled is not None:
        reminder.enabled = payload.enabled
    db.commit()
    db.refresh(reminder)
    return reminder


@router.delete("/reminders/{reminder_id}", status_code=204)
def delete_reminder(reminder_id: int, db: Session = Depends(get_db)):
    reminder = db.query(models.ReminderSchedule).filter(models.ReminderSchedule.id == reminder_id).first()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    db.delete(reminder)
    db.commit()
    return
