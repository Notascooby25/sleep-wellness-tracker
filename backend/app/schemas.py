# backend/app/schemas.py
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime

# Use Pydantic v2 style: model_config with from_attributes True
class CategoryBase(BaseModel):
    name: str

class CategoryCreate(CategoryBase):
    pass

class CategoryResponse(BaseModel):
    id: int
    name: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ActivityBase(BaseModel):
    name: str
    category_id: int

class ActivityCreate(ActivityBase):
    pass

class ActivityResponse(BaseModel):
    id: int
    name: str
    category_id: int
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class MoodEntryCreate(BaseModel):
    mood_score: int = Field(..., ge=1, le=5)
    note: Optional[str] = None
    timestamp: datetime
    activity_ids: List[int] = Field(default_factory=list)


class MoodEntry(BaseModel):
    id: int
    mood_score: int
    note: Optional[str]
    timestamp: datetime
    created_at: datetime
    activity_ids: List[int]

    model_config = {"from_attributes": True}


class MoodEntryActivityResponse(BaseModel):
    activity_id: int

    model_config = {"from_attributes": True}


class MoodEntryResponse(BaseModel):
    id: int
    mood_score: int
    note: Optional[str]
    timestamp: datetime
    created_at: datetime
    activities: List[MoodEntryActivityResponse]

    model_config = {"from_attributes": True}

# Compatibility aliases expected by routes
Category = CategoryResponse
Activity = ActivityResponse
