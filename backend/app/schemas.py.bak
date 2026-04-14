# backend/app/schemas.py
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

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
