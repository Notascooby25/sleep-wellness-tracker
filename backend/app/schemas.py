# backend/app/schemas.py
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# Mood schemas
class MoodBase(BaseModel):
    mood_score: int
    note: Optional[str] = None
    timestamp: datetime
    activity_ids: Optional[List[int]] = []

class MoodCreate(MoodBase):
    pass

class MoodRead(MoodBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Category schemas
class CategoryBase(BaseModel):
    name: str

class CategoryCreate(CategoryBase):
    pass

class CategoryResponse(CategoryBase):
    id: int

    class Config:
        from_attributes = True

# Activity schemas
class ActivityBase(BaseModel):
    name: str
    category_id: int

class ActivityCreate(ActivityBase):
    pass

class ActivityResponse(ActivityBase):
    id: int

    class Config:
        from_attributes = True
