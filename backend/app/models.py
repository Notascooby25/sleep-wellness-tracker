# models.py
from sqlalchemy import Table, Column, Integer, ForeignKey, DateTime, String, func
from sqlalchemy.orm import relationship
from .database import Base  # adjust import to your project

mood_activities = Table(
    "mood_activities",
    Base.metadata,
    Column("mood_id", Integer, ForeignKey("moods.id"), primary_key=True),
    Column("activity_id", Integer, ForeignKey("activities.id"), primary_key=True),
)

class Mood(Base):
    __tablename__ = "moods"
    id = Column(Integer, primary_key=True, index=True)
    mood_score = Column(Integer, nullable=False)
    note = Column(String, nullable=True)
    timestamp = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    activities = relationship("Activity", secondary=mood_activities, back_populates="moods")

class Activity(Base):
    __tablename__ = "activities"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"))
    moods = relationship("Mood", secondary=mood_activities, back_populates="activities")
