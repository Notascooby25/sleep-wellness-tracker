# File: backend/app/database.py
import logging
import os
import time
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from . import models
from .models import Base

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is not set. "
        "Copy .env.example to .env and configure your database connection."
    )

# create engine with pool_pre_ping to help with dropped connections
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# wait for DB to be available with retries
def wait_for_db(max_retries: int = 20, delay_seconds: int = 2):
    if max_retries < 1:
        raise ValueError("max_retries must be at least 1")
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            with engine.connect():
                return True
        except OperationalError as exc:
            last_exc = exc
            time.sleep(delay_seconds)
    raise RuntimeError(
        f"Database not available after {max_retries} attempts. Last error: {last_exc}"
    ) from last_exc

# ensure DB is ready before creating sessions / tables
wait_for_db()

logger.info("Running create_all to ensure all tables exist...")
Base.metadata.create_all(bind=engine)


def _ensure_legacy_schema_compatibility() -> None:
    """Patch older databases with columns introduced after initial deployment."""
    inspector = inspect(engine)
    dialect = engine.dialect.name

    if not inspector.has_table("categories"):
        return

    category_columns = {col["name"] for col in inspector.get_columns("categories")}
    activity_columns = {col["name"] for col in inspector.get_columns("activities")} if inspector.has_table("activities") else {}
    mood_columns = {col["name"]: col for col in inspector.get_columns("moods")} if inspector.has_table("moods") else {}

    with engine.begin() as conn:
        if "is_archived" not in activity_columns and inspector.has_table("activities"):
            logger.warning("Adding missing activities.is_archived column for legacy database")
            conn.execute(
                text("ALTER TABLE activities ADD COLUMN is_archived BOOLEAN NOT NULL DEFAULT FALSE")
            )

        if "require_rating" not in category_columns:
            logger.warning("Adding missing categories.require_rating column for legacy database")
            conn.execute(
                text("ALTER TABLE categories ADD COLUMN require_rating INTEGER NOT NULL DEFAULT 1")
            )

        if "rating_label" not in category_columns:
            logger.warning("Adding missing categories.rating_label column for legacy database")
            conn.execute(
                text("ALTER TABLE categories ADD COLUMN rating_label VARCHAR(80)")
            )

        if "image_url" not in mood_columns and inspector.has_table("moods"):
            logger.warning("Adding missing moods.image_url column for legacy database")
            conn.execute(
                text("ALTER TABLE moods ADD COLUMN image_url VARCHAR(1024)")
            )

        if "image_urls" not in mood_columns and inspector.has_table("moods"):
            logger.warning("Adding missing moods.image_urls column for legacy database")
            conn.execute(
                text("ALTER TABLE moods ADD COLUMN image_urls JSON")
            )

        mood_score_col = mood_columns.get("mood_score")
        if mood_score_col and mood_score_col.get("nullable") is False:
            if dialect == "postgresql":
                logger.warning("Dropping NOT NULL on moods.mood_score for optional ratings")
                conn.execute(text("ALTER TABLE moods ALTER COLUMN mood_score DROP NOT NULL"))
            else:
                logger.warning(
                    "moods.mood_score is NOT NULL, but automatic nullable migration is unsupported for dialect=%s",
                    dialect,
                )

    if inspector.has_table("moods"):
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("moods")}
        if "ix_moods_timestamp" not in existing_indexes:
            logger.warning("Adding missing moods.timestamp index for query performance")
            with engine.begin() as conn:
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_moods_timestamp ON moods (timestamp)"))


_ensure_legacy_schema_compatibility()
logger.info("Database tables verified.")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _backfill_mood_image_urls() -> None:
    db = SessionLocal()
    try:
        changed = False
        rows = db.query(models.Mood).all()
        for mood in rows:
            urls = []
            for url in mood.image_urls or []:
                cleaned = str(url).strip()
                if cleaned:
                    urls.append(cleaned)
            if not urls and mood.image_url:
                urls = [mood.image_url.strip()]
            primary = urls[0] if urls else None

            if mood.image_urls != (urls or None):
                mood.image_urls = urls or None
                changed = True
            if mood.image_url != primary:
                mood.image_url = primary
                changed = True

        if changed:
            db.commit()
    finally:
        db.close()


_backfill_mood_image_urls()

# FastAPI dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
