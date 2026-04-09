from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime

from sqlalchemy.orm import declarative_base
Base = declarative_base()


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    activities = relationship("Activity", back_populates="category", cascade="all, delete")


class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    category = relationship("Category", back_populates="activities")

    __table_args__ = (UniqueConstraint("category_id", "name"),)


class MoodEntry(Base):
    __tablename__ = "mood_entries"

    id = Column(Integer, primary_key=True, index=True)
    mood_score = Column(Integer, nullable=False)
    note = Column(Text)
    timestamp = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    activities = relationship(
        "MoodEntryActivity",
        back_populates="entry",
        cascade="all, delete"
    )


class MoodEntryActivity(Base):
    __tablename__ = "mood_entry_activities"

    entry_id = Column(Integer, ForeignKey("mood_entries.id", ondelete="CASCADE"), primary_key=True)
    activity_id = Column(Integer, ForeignKey("activities.id", ondelete="CASCADE"), primary_key=True)

    entry = relationship("MoodEntry", back_populates="activities")
