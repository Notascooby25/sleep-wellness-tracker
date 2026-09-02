from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from decimal import Decimal

# -------------------------
# MOOD SCHEMAS
# -------------------------

class MoodActivityDetailInput(BaseModel):
    activity_id: int
    position: Optional[str] = None
    severity: Optional[int] = None
    quantity_numeric: Optional[Decimal] = None
    quantity_unit: Optional[str] = None


class MoodBase(BaseModel):
    mood_score: Optional[int] = None  # Optional to support categories that don't require rating
    notes: Optional[str] = None
    image_url: Optional[str] = None
    image_urls: Optional[List[str]] = None
    timestamp: datetime
    activity_ids: Optional[List[int]] = Field(default_factory=list)
    # None means "do not touch existing details"; an empty list means "clear them".
    activity_details: Optional[List[MoodActivityDetailInput]] = None
    subjective_sleep_rating: Optional[int] = None

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
    require_rating: int = 1
    rating_label: Optional[str] = None

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
    name: str
    category_id: Optional[int] = None
    is_archived: Optional[bool] = False  # New field to indicate if the activity is archived
    deprecated_at: Optional[datetime] = None

class ActivityCreate(ActivityBase):
    pass


class ActivityUpdate(BaseModel):
    name: Optional[str] = None
    category_id: Optional[int] = None
    is_archived: Optional[bool] = None  # Allow updating the archived status
    deprecated_at: Optional[datetime] = None

class ActivityResponse(ActivityBase):
    id: int

    class Config:
        from_attributes = True
