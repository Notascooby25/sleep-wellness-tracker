import datetime as dt
import os
import re
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from typing import List
from sqlalchemy.orm import Session, selectinload

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/mood", tags=["mood"])

MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024
CHUNK_SIZE_BYTES = 1024 * 1024
IMAGE_URL_PREFIX = "/mood/image/"
MOOD_IMAGE_DIR = Path(os.getenv("MOOD_IMAGE_DIR", "/app/uploads/mood_images"))
ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/heif": ".heif",
}
SAFE_IMAGE_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _ensure_mood_image_dir() -> None:
    MOOD_IMAGE_DIR.mkdir(parents=True, exist_ok=True)


def _delete_mood_image_file(image_url: str | None) -> None:
    if not image_url or not image_url.startswith(IMAGE_URL_PREFIX):
        return

    image_name = image_url[len(IMAGE_URL_PREFIX):]
    if not image_name or not SAFE_IMAGE_NAME_RE.fullmatch(image_name):
        return

    path = (MOOD_IMAGE_DIR / image_name).resolve()
    try:
        path.relative_to(MOOD_IMAGE_DIR.resolve())
    except ValueError:
        return

    if path.exists() and path.is_file():
        path.unlink()


@router.post("/upload-image")
async def upload_mood_image(file: UploadFile = File(...)):
    content_type = (file.content_type or "").lower()
    extension = ALLOWED_IMAGE_CONTENT_TYPES.get(content_type)
    if extension is None:
        raise HTTPException(status_code=400, detail="Unsupported image type. Use JPG, PNG, WEBP, HEIC, or HEIF.")

    _ensure_mood_image_dir()
    image_name = f"{uuid4().hex}{extension}"
    target = MOOD_IMAGE_DIR / image_name

    total_size = 0
    try:
        with target.open("wb") as output:
            while True:
                chunk = await file.read(CHUNK_SIZE_BYTES)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > MAX_IMAGE_SIZE_BYTES:
                    output.close()
                    target.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail="Image too large. Max size is 10 MB.")
                output.write(chunk)
    finally:
        await file.close()

    return {"image_url": f"{IMAGE_URL_PREFIX}{image_name}"}


@router.get("/image/{image_name}")
def get_mood_image(image_name: str):
    if not SAFE_IMAGE_NAME_RE.fullmatch(image_name):
        raise HTTPException(status_code=404, detail="Image not found")

    _ensure_mood_image_dir()
    target = (MOOD_IMAGE_DIR / image_name).resolve()
    try:
        target.relative_to(MOOD_IMAGE_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=404, detail="Image not found")

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(target)

@router.get("", response_model=List[schemas.MoodRead])
def list_mood_entries(
    from_date: dt.date | None = Query(default=None),
    to_date: dt.date | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    rows_query = db.query(models.Mood).options(selectinload(models.Mood.activities))
    if from_date is not None:
        from_dt = dt.datetime(from_date.year, from_date.month, from_date.day, tzinfo=dt.timezone.utc)
        rows_query = rows_query.filter(models.Mood.timestamp >= from_dt)
    if to_date is not None:
        to_dt = dt.datetime(to_date.year, to_date.month, to_date.day, tzinfo=dt.timezone.utc) + dt.timedelta(days=1)
        rows_query = rows_query.filter(models.Mood.timestamp < to_dt)
    rows_query = rows_query.order_by(models.Mood.timestamp.desc())
    if offset:
        rows_query = rows_query.offset(offset)
    if limit is not None:
        rows_query = rows_query.limit(limit)

    rows = rows_query.all()
    result = []
    for r in rows:
        activity_ids = [a.id for a in r.activities]
        result.append({
            "id": r.id,
            "mood_score": r.mood_score,
            # API now returns `notes`, still reading DB column `note`
            "notes": r.notes,
            "image_url": r.image_url,
            "timestamp": r.timestamp,
            "created_at": r.created_at,
            "activity_ids": activity_ids,
        })
    return result

@router.post("", response_model=schemas.MoodRead)
def create_mood_entry(payload: schemas.MoodCreate, db: Session = Depends(get_db)):
    # payload.notes is populated whether client sent "note" or "notes"
    db_mood = models.Mood(
        mood_score=payload.mood_score,
        notes=payload.notes,
        image_url=payload.image_url,
        timestamp=payload.timestamp,
    )
    db.add(db_mood)
    db.flush()

    if payload.activity_ids:
        activities = db.query(models.Activity).filter(
            models.Activity.id.in_(payload.activity_ids)
        ).all()
        db_mood.activities = activities

    db.commit()

    db.refresh(db_mood)
    activity_ids = [a.id for a in db_mood.activities]

    return {
        "id": db_mood.id,
        "mood_score": db_mood.mood_score,
        "notes": db_mood.notes,
        "image_url": db_mood.image_url,
        "timestamp": db_mood.timestamp,
        "created_at": db_mood.created_at,
        "activity_ids": activity_ids,
    }

@router.get("/{entry_id}", response_model=schemas.MoodRead)
def get_mood_entry(entry_id: int, db: Session = Depends(get_db)):
    m = db.query(models.Mood).filter(models.Mood.id == entry_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mood entry not found")

    activity_ids = [a.id for a in m.activities]

    return {
        "id": m.id,
        "mood_score": m.mood_score,
        "notes": m.notes,
        "image_url": m.image_url,
        "timestamp": m.timestamp,
        "created_at": m.created_at,
        "activity_ids": activity_ids,
    }


@router.put("/{entry_id}", response_model=schemas.MoodRead)
def update_mood_entry(entry_id: int, payload: schemas.MoodUpdate, db: Session = Depends(get_db)):
    m = db.query(models.Mood).filter(models.Mood.id == entry_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mood entry not found")

    previous_image_url = m.image_url
    m.mood_score = payload.mood_score
    m.notes = payload.notes
    m.image_url = payload.image_url
    m.timestamp = payload.timestamp

    activities = []
    if payload.activity_ids:
        activities = db.query(models.Activity).filter(
            models.Activity.id.in_(payload.activity_ids)
        ).all()
    m.activities = activities

    db.commit()
    db.refresh(m)

    if previous_image_url != m.image_url:
        _delete_mood_image_file(previous_image_url)

    activity_ids = [a.id for a in m.activities]
    return {
        "id": m.id,
        "mood_score": m.mood_score,
        "notes": m.notes,
        "image_url": m.image_url,
        "timestamp": m.timestamp,
        "created_at": m.created_at,
        "activity_ids": activity_ids,
    }


@router.delete("/{entry_id}")
def delete_mood_entry(entry_id: int, db: Session = Depends(get_db)):
    m = db.query(models.Mood).filter(models.Mood.id == entry_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mood entry not found")

    old_image_url = m.image_url
    db.delete(m)
    db.commit()
    _delete_mood_image_file(old_image_url)
    return {"ok": True, "id": entry_id}
