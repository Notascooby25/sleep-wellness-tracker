from pydantic import BaseModel, Field
from typing import List, Optional, Union
from datetime import datetime
from decimal import Decimal

# -------------------------
# MOOD SCHEMAS
# -------------------------

class MoodActivityDetailInput(BaseModel):
    activity_id: int
    position: Optional[Union[str, List[str]]] = None
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
    supports_position: bool = False

class CategoryResponse(CategoryBase):
    id: int
    require_rating: int
    rating_label: Optional[str] = None
    supports_position: bool

    class Config:
        from_attributes = True


class PositionOptionCreate(BaseModel):
    label: str

class PositionOptionResponse(BaseModel):
    id: int
    label: str

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
    supports_position: Optional[bool] = False

class ActivityCreate(ActivityBase):
    pass


class ActivityUpdate(BaseModel):
    name: Optional[str] = None
    category_id: Optional[int] = None
    is_archived: Optional[bool] = None  # Allow updating the archived status
    deprecated_at: Optional[datetime] = None
    supports_position: Optional[bool] = None

class ActivityResponse(ActivityBase):
    id: int

    class Config:
        from_attributes = True


# -------------------------
# PUSH NOTIFICATION SCHEMAS
# -------------------------

class PushSubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionCreate(BaseModel):
    endpoint: str
    keys: PushSubscriptionKeys
    device_label: Optional[str] = None


class PushSubscriptionResponse(BaseModel):
    id: int
    endpoint: str
    device_label: Optional[str] = None
    created_at: datetime
    last_seen_at: datetime

    class Config:
        from_attributes = True


class ReminderScheduleBase(BaseModel):
    time_of_day: str = Field(..., pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    message: Optional[str] = None
    enabled: bool = True


class ReminderScheduleCreate(ReminderScheduleBase):
    pass


class ReminderScheduleUpdate(BaseModel):
    time_of_day: Optional[str] = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    message: Optional[str] = None
    enabled: Optional[bool] = None


class ReminderScheduleResponse(ReminderScheduleBase):
    id: int

    class Config:
        from_attributes = True
