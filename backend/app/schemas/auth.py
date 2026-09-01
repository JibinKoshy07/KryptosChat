"""Auth request/response schemas."""
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class RefreshRequest(BaseModel):
    refresh_token: str | None = Field(default=None, description="Optional refresh token body")


class UserSummary(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    is_active: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserSummary


class LogoutResponse(BaseModel):
    ok: bool = True