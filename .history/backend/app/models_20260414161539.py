# File: backend/app/models.py
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Table,
    func,
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

# association table for many-to-many between Mood and Activity
mood_activities = Table(
    "mood_activities",
    Base.metadata,
    Column("mood_id", Integer, ForeignKey("moods.id", ondelete="CASCADE"), primary_key=True),
    Column("activity_id", Integer, ForeignKey("activities.id", ondelete="CASCADE"), primary_key=True),
)

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)

    activities = relationship("Activity", back_populates="category", cascade="all, delete-orphan")

class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)

    category = relationship("Category", back_populates="activities")
    moods = relationship("Mood", secondary=mood_activities, back_populates="activities")

class Mood(Base):
    __tablename__ = "moods"

    id = Column(Integer, primary_key=True, index=True)
    mood_score = Column(Integer, nullable=False)
    note = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    activities = relationship("Activity", secondary=mood_activities, back_populates="moods")
