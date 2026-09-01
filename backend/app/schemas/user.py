"""User management schemas."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import ROLE_ADMIN, ROLE_USER


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    display_name: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=8, max_length=256)
    role: str = Field(default=ROLE_USER, pattern=f"^{ROLE_ADMIN}$|^{ROLE_USER}$")


class UserUpdate(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    password: Optional[str] = Field(default=None, min_length=8, max_length=256)
    role: Optional[str] = Field(default=None, pattern=f"^{ROLE_ADMIN}$|^{ROLE_USER}$")
    is_active: Optional[bool] = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    role: str
    is_active: bool
    last_seen_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    role: str
    is_active: bool
    created_at: datetime