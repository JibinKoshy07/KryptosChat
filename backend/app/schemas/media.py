"""Media upload/download schemas."""
from datetime import datetime

from pydantic import BaseModel


class AttachmentOut(BaseModel):
    id: int
    message_id: int
    original_filename: str
    mime_type: str
    size: int
    created_at: datetime


class UploadResponse(BaseModel):
    attachment_id: int
    storage_key: str