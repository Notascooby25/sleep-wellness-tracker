from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

# -------------------------
# MOOD SCHEMAS
# -------------------------

class MoodBase(BaseModel):
    mood_score: int
    notes: Optional[str] = None
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
