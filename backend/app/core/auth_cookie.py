"""Reading the refresh token from the HttpOnly cookie."""
from fastapi import Request

from app.core.config import settings

COOKIE_NAME = settings.cookie_name


def read_refresh_cookie(request: Request) -> str | None:
    return request.cookies.get(COOKIE_NAME)