# File: backend/app/database.py
import logging
import os
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
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
            with engine.connect() as conn:
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
logger.info("Database tables verified.")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# FastAPI dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
