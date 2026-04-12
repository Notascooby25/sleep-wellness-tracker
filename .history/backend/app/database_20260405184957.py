import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Use env var set in docker-compose; fallback to local postgres
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/sleepdb")

# SQLAlchemy engine and session factory
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Import models so metadata is available for create_all
from . import models  # noqa: E402

# Create tables if they don't exist (safe on startup)
models.Base.metadata.create_all(bind=engine)

# Dependency for FastAPI routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
