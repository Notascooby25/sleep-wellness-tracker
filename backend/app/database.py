import logging
import os
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from .models import Base

logger = logging.getLogger("app.database")

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is not set. "
        "Copy .env.example to .env and configure your database connection."
    )

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def wait_for_db(max_retries: int = 20, delay_seconds: int = 2):
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            with engine.connect():
                logger.info("Database connection established on attempt %d", attempt)
                return True
        except OperationalError as exc:
            last_exc = exc
            logger.warning(
                "Database not ready (attempt %d/%d), retrying in %ds...",
                attempt, max_retries, delay_seconds,
            )
            time.sleep(delay_seconds)
    raise RuntimeError(
        f"Database not available after {max_retries} attempts. Last error: {last_exc}"
    ) from last_exc


wait_for_db()

logger.info("Running create_all to ensure all tables exist...")
Base.metadata.create_all(bind=engine)
logger.info("Database tables verified.")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
