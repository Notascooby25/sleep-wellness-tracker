from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

# -------------------------
# MOOD SCHEMAS
# -------------------------

class MoodBase(BaseModel):
    mood_score: int
    # Canonical field is `notes`, but accept incoming `note` as alias
    notes: Optional[str] = Field(None, alias="note")
    timestamp: datetime
    activity_ids: Optional[List[int]] = []

    class Config:
        # allow both "notes" and "note" in incoming JSON
        populate_by_name = True

class MoodCreate(MoodBase):
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
    name: str

class CategoryCreate(CategoryBase):
    pass

class CategoryResponse(CategoryBase):
    id: int

    class Config:
        from_attributes = True


# -------------------------
# ACTIVITY SCHEMAS
# -------------------------

class ActivityBase(BaseModel):
    name: str
    category_id: Optional[int] = None

class ActivityCreate(ActivityBase):
    pass

class ActivityResponse(ActivityBase):
    id: int

    class Config:
        from_attributes = True
