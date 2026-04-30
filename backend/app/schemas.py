from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

# -------------------------
# MOOD SCHEMAS
# -------------------------

class MoodBase(BaseModel):
    mood_score: Optional[int] = None  # Optional to support categories that don't require rating
    notes: Optional[str] = Field(default=None, max_length=5000)
    timestamp: datetime
    activity_ids: Optional[List[int]] = Field(default_factory=list)

    class Config:
        populate_by_name = True





class MoodCreate(MoodBase):
    pass


class MoodUpdate(MoodBase):
    pass


class MoodRead(MoodBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        populate_by_name = True




# -------------------------
# CATEGORY SCHEMAS
# -------------------------

class CategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)

class CategoryCreate(CategoryBase):
    require_rating: int = 1
    rating_label: Optional[str] = Field(default=None, max_length=80)

class CategoryResponse(CategoryBase):
    id: int
    require_rating: int
    rating_label: Optional[str] = None

    class Config:
        from_attributes = True


# -------------------------
# ACTIVITY SCHEMAS
# -------------------------

class ActivityBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    category_id: Optional[int] = None

class ActivityCreate(ActivityBase):
    pass


class ActivityUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    category_id: Optional[int] = None

class ActivityResponse(ActivityBase):
    id: int

    class Config:
        from_attributes = True
