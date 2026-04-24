import uuid
from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel


class ImageUploadResponse(BaseModel):
    id: uuid.UUID
    url: str
    thumbnail_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    file_size: int

    class Config:
        from_attributes = True


class ImageItem(BaseModel):
    id: uuid.UUID
    record_date: date
    url: str
    thumbnail_url: Optional[str] = None
    ai_caption: Optional[str] = None
    ai_tags: Optional[List[str]] = None
    dominant_colors: Optional[List[str]] = None
    width: Optional[int] = None
    height: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ImageWithDateGroup(BaseModel):
    record_date: date
    images: List[ImageItem]
    dominant_emotion: Optional[str] = None


class HistoryImagesResponse(BaseModel):
    items: List[ImageWithDateGroup]
    total: int
    page: int
    page_size: int
    has_more: bool


class OnThisDayImagesResponse(BaseModel):
    month: int
    day: int
    items: List[ImageWithDateGroup]
