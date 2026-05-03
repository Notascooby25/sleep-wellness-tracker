# File: backend/app/models.py
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Date,
    DateTime,
    JSON,
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
    require_rating = Column(Integer, nullable=False, default=1)  # 1=true (required), 0=false (optional)
    rating_label = Column(String(80), nullable=True)  # e.g., "Pain/Discomfort Level", "Mood"

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
    mood_score = Column(Integer, nullable=True)  # Nullable to support optional ratings
    notes = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    activities = relationship("Activity", secondary=mood_activities, back_populates="moods")


class GarminSleepDaily(Base):
    __tablename__ = "garmin_sleep_daily"

    id = Column(Integer, primary_key=True, index=True)
    sleep_date = Column(Date, unique=True, nullable=False, index=True)
    sleep_start = Column(DateTime(timezone=True), nullable=True)
    sleep_end = Column(DateTime(timezone=True), nullable=True)
    total_sleep_minutes = Column(Integer, nullable=True)
    deep_sleep_minutes = Column(Integer, nullable=True)
    light_sleep_minutes = Column(Integer, nullable=True)
    rem_sleep_minutes = Column(Integer, nullable=True)
    awake_minutes = Column(Integer, nullable=True)
    sleep_score = Column(Integer, nullable=True)
    body_battery_wakeup = Column(Integer, nullable=True)
    body_battery_bedtime = Column(Integer, nullable=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class GarminBodyBatteryDaily(Base):
    __tablename__ = "garmin_body_battery_daily"

    id = Column(Integer, primary_key=True, index=True)
    battery_date = Column(Date, unique=True, nullable=False, index=True)
    morning_value = Column(Integer, nullable=True)
    end_of_day_value = Column(Integer, nullable=True)
    peak_value = Column(Integer, nullable=True)
    low_value = Column(Integer, nullable=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class GarminHRVDaily(Base):
    __tablename__ = "garmin_hrv_daily"

    id = Column(Integer, primary_key=True, index=True)
    hrv_date = Column(Date, unique=True, nullable=False, index=True)
    weekly_avg = Column(Integer, nullable=True)
    baseline_low = Column(Integer, nullable=True)
    baseline_high = Column(Integer, nullable=True)
    status = Column(String(80), nullable=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class GarminRestingHeartRateDaily(Base):
    __tablename__ = "garmin_resting_heart_rate_daily"

    id = Column(Integer, primary_key=True, index=True)
    heart_rate_date = Column(Date, unique=True, nullable=False, index=True)
    resting_heart_rate = Column(Integer, nullable=True)
    min_heart_rate = Column(Integer, nullable=True)
    max_heart_rate = Column(Integer, nullable=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class GarminStressDaily(Base):
    __tablename__ = "garmin_stress_daily"

    id = Column(Integer, primary_key=True, index=True)
    stress_date = Column(Date, unique=True, nullable=False, index=True)
    overall_stress_level = Column(Integer, nullable=True)
    rest_stress_duration = Column(Integer, nullable=True)
    low_stress_duration = Column(Integer, nullable=True)
    medium_stress_duration = Column(Integer, nullable=True)
    high_stress_duration = Column(Integer, nullable=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class GarminHydrationDaily(Base):
    __tablename__ = "garmin_hydration_daily"

    id = Column(Integer, primary_key=True, index=True)
    hydration_date = Column(Date, unique=True, nullable=False, index=True)
    consumed_ml = Column(Integer, nullable=True)
    goal_ml = Column(Integer, nullable=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class GarminStepsDaily(Base):
    __tablename__ = "garmin_steps_daily"

    id = Column(Integer, primary_key=True, index=True)
    steps_date = Column(Date, unique=True, nullable=False, index=True)
    total_steps = Column(Integer, nullable=True)
    distance_meters = Column(Integer, nullable=True)
    calories_burned = Column(Integer, nullable=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class GarminActivity(Base):
    __tablename__ = "garmin_activities"

    id = Column(Integer, primary_key=True, index=True)
    garmin_activity_id = Column(String(80), unique=True, nullable=False, index=True)
    activity_date = Column(Date, nullable=False, index=True)
    start_time = Column(DateTime(timezone=True), nullable=True)
    activity_type = Column(String(80), nullable=True, index=True)
    activity_name = Column(String(255), nullable=True)
    distance_meters = Column(Integer, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    calories = Column(Integer, nullable=True)
    average_hr = Column(Integer, nullable=True)
    max_hr = Column(Integer, nullable=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class GarminSyncState(Base):
    __tablename__ = "garmin_sync_state"

    key = Column(String(80), primary_key=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    detail = Column(Text, nullable=True)
