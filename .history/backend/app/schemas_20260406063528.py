from typing import Optional, List
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List


class CategoryBase(BaseModel):
    name: str


class CategoryCreate(CategoryBase):
    pass


class Category(CategoryBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


class ActivityBase(BaseModel):
    name: str
    category_id: int


class ActivityCreate(ActivityBase):
    pass


class Activity(ActivityBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


class MoodEntryBase(BaseModel):
    mood_score: int
    note: Optional[str] = None
    timestamp: datetime
    activity_ids: List[int]



class MoodEntryCreate(BaseModel):
    mood_score: int = Field(..., ge=1, le=5)
    note: str | None = None
    timestamp: datetime
    activity_ids: List[int] = []


class MoodEntry(BaseModel):
    id: int
    mood_score: int
    note: Optional[str]
    timestamp: datetime
    created_at: datetime
    activity_ids: List[int]

    class Config:
        orm_mode = True

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

class CategoryResponse(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class ActivityResponse(BaseModel):
    id: int
    name: str
    category_id: int

    model_config = {"from_attributes": True}

class CategoryCreate(BaseModel):
    name: str


class ActivityCreate(BaseModel):
    name: str
    category_id: int
class CategoryCreate(BaseModel):
    name: str


class ActivityCreate(BaseModel):
    name: str
    category_id: int
