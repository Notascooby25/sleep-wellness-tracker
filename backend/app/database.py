# File: backend/app/database.py
import os
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from .models import Base

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/postgres")

# create engine with pool_pre_ping to help with dropped connections
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# wait for DB to be available with retries
def wait_for_db(max_retries: int = 20, delay_seconds: int = 2):
    retries = 0
    while retries < max_retries:
        try:
            # attempt a real connection
            with engine.connect() as conn:
                return True
        except OperationalError:
            retries += 1
            time.sleep(delay_seconds)
    # final attempt to raise the last error if DB never became available
    with engine.connect() as conn:
        return True

# ensure DB is ready before creating sessions / tables
wait_for_db()

# create tables if they don't exist
Base.metadata.create_all(bind=engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# FastAPI dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
