import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Local development: SQLite
DATABASE_URL = "sqlite:///./local.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

from . import models  # noqa: E402

models.Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

        
