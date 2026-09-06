import datetime as dt
import json
import logging
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
logger = logging.getLogger("app.mood")

MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024
CHUNK_SIZE_BYTES = 1024 * 1024
IMAGE_URL_PREFIX = "/mood/image/"
MOOD_IMAGE_DIR = Path(os.getenv("MOOD_IMAGE_DIR", "/app/uploads/mood_images"))
MOOD_IMAGE_REQUIRE_MOUNT = os.getenv("MOOD_IMAGE_REQUIRE_MOUNT", "1").strip().lower() in {"1", "true", "yes", "on"}
ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/heif": ".heif",
}
SAFE_IMAGE_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _has_non_root_mount(path: Path) -> bool:
    current = path.resolve()
    while True:
        if current == Path("/"):
            return False
        if current.is_mount():
            return True
        parent = current.parent
        if parent == current:
            return False
        current = parent


def _ensure_mood_image_dir() -> None:
    MOOD_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    if MOOD_IMAGE_REQUIRE_MOUNT and not _has_non_root_mount(MOOD_IMAGE_DIR):
        logger.error(
            "Refusing image write/read: %s is not mounted persistent storage",
            MOOD_IMAGE_DIR,
        )
        raise HTTPException(
            status_code=503,
            detail="Image storage is not mounted. Configure a persistent mount for MOOD_IMAGE_DIR.",
        )


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


def _normalize_image_urls(
    image_url: str | None = None,
    image_urls: list[str] | None = None,
) -> list[str]:
    candidates = image_urls if image_urls is not None else ([image_url] if image_url else [])
    normalized: list[str] = []
    for candidate in candidates:
        cleaned = str(candidate or "").strip()
        if cleaned and cleaned not in normalized:
            normalized.append(cleaned)
    return normalized


def _primary_image_url(image_urls: list[str]) -> str | None:
    return image_urls[0] if image_urls else None


def _get_mood_image_urls(mood: models.Mood) -> list[str]:
    return _normalize_image_urls(image_url=mood.image_url, image_urls=mood.image_urls)


def _normalize_positions(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        candidates = value
    elif isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            parsed = [value]
        candidates = parsed if isinstance(parsed, list) else [str(parsed)]
    else:
        candidates = [str(value)]
    positions: list[str] = []
    for candidate in candidates:
        label = str(candidate).strip()
        if label and label not in positions:
            positions.append(label)
    return positions


def _store_positions(value) -> str | None:
    positions = _normalize_positions(value)
    return json.dumps(positions, separators=(",", ":")) if positions else None


def _delete_mood_image_files(image_urls: list[str]) -> None:
    for image_url in image_urls:
        _delete_mood_image_file(image_url)


def _serialize_mood(mood: models.Mood) -> dict:
    image_urls = _get_mood_image_urls(mood)
    return {
        "id": mood.id,
        "mood_score": mood.mood_score,
        "notes": mood.notes,
        "image_url": _primary_image_url(image_urls),
        "image_urls": image_urls,
        "timestamp": mood.timestamp,
        "created_at": mood.created_at,
        "activity_ids": [a.id for a in mood.activities],
        "subjective_sleep_rating": getattr(mood, "subjective_sleep_rating", None),
        "activity_details": [
            {
                "activity_id": d.activity_id,
                "position": _normalize_positions(d.position),
                "severity": d.severity,
                "quantity_numeric": float(d.quantity_numeric) if d.quantity_numeric is not None else None,
                "quantity_unit": d.quantity_unit,
            }
            for d in (getattr(mood, "activity_details", None) or [])
        ],
    }


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
    return [_serialize_mood(row) for row in rows]

@router.post("", response_model=schemas.MoodRead)
def create_mood_entry(payload: schemas.MoodCreate, db: Session = Depends(get_db)):
    # payload.notes is populated whether client sent "note" or "notes"
    image_urls = _normalize_image_urls(payload.image_url, payload.image_urls)
    db_mood = models.Mood(
        mood_score=payload.mood_score,
        notes=payload.notes,
        image_url=_primary_image_url(image_urls),
        image_urls=image_urls or None,
        timestamp=payload.timestamp,
        subjective_sleep_rating=payload.subjective_sleep_rating,
    )
    db.add(db_mood)
    db.flush()

    if payload.activity_ids:
        activities = db.query(models.Activity).filter(
            models.Activity.id.in_(payload.activity_ids)
        ).all()
        db_mood.activities = activities

    _replace_activity_details(db, db_mood, payload.activity_details)

    db.commit()

    db.refresh(db_mood)
    return _serialize_mood(db_mood)

@router.get("/{entry_id}", response_model=schemas.MoodRead)
def get_mood_entry(entry_id: int, db: Session = Depends(get_db)):
    m = db.query(models.Mood).filter(models.Mood.id == entry_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mood entry not found")

    return _serialize_mood(m)


@router.put("/{entry_id}", response_model=schemas.MoodRead)
def update_mood_entry(entry_id: int, payload: schemas.MoodUpdate, db: Session = Depends(get_db)):
    m = db.query(models.Mood).filter(models.Mood.id == entry_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mood entry not found")

    previous_image_urls = set(_get_mood_image_urls(m))
    image_urls = _normalize_image_urls(payload.image_url, payload.image_urls)
    m.mood_score = payload.mood_score
    m.notes = payload.notes
    m.image_url = _primary_image_url(image_urls)
    m.image_urls = image_urls or None
    m.timestamp = payload.timestamp
    m.subjective_sleep_rating = payload.subjective_sleep_rating

    activities = []
    if payload.activity_ids:
        activities = db.query(models.Activity).filter(
            models.Activity.id.in_(payload.activity_ids)
        ).all()
    m.activities = activities

    _replace_activity_details(db, m, payload.activity_details)

    db.commit()
    db.refresh(m)

    current_image_urls = set(_get_mood_image_urls(m))
    _delete_mood_image_files(sorted(previous_image_urls - current_image_urls))

    return _serialize_mood(m)


@router.delete("/{entry_id}")
def delete_mood_entry(entry_id: int, db: Session = Depends(get_db)):
    m = db.query(models.Mood).filter(models.Mood.id == entry_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mood entry not found")

    old_image_urls = _get_mood_image_urls(m)
    db.delete(m)
    db.commit()
    _delete_mood_image_files(old_image_urls)
    return {"ok": True, "id": entry_id}


def _replace_activity_details(db: Session, mood: models.Mood, details) -> None:
    if details is None:
        return
    db.query(models.MoodActivityDetail).filter(
        models.MoodActivityDetail.mood_id == mood.id
    ).delete(synchronize_session=False)
    if not details:
        return
    selected_ids = {a.id for a in mood.activities}
    for detail in details:
        if detail.activity_id not in selected_ids:
            continue
        db.add(
            models.MoodActivityDetail(
                mood_id=mood.id,
                activity_id=detail.activity_id,
                position=_store_positions(detail.position),
                severity=detail.severity,
                quantity_numeric=detail.quantity_numeric,
                quantity_unit=detail.quantity_unit,
            )
        )
