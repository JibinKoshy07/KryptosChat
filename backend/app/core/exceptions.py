"""Application-level exceptions mapped to structured HTTP error responses."""
from fastapi import HTTPException, status


class AppError(Exception):
    """Base application error; converted to a JSON error body by the API layer."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"
    detail: str = "Internal error"

    def __init__(self, detail: str | None = None):
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    detail = "Resource not found"


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"
    detail = "Forbidden"


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"
    detail = "Unauthorized"


class BadRequestError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "bad_request"
    detail = "Bad request"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"
    detail = "Conflict"


class RateLimitError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"
    detail = "Too many requests"


def http_400(detail: str = "Bad request"):
    return HTTPException(status_code=400, detail=detail)


def http_403(detail: str = "Forbidden"):
    return HTTPException(status_code=403, detail=detail)


def http_404(detail: str = "Not found"):
    return HTTPException(status_code=404, detail=detail)


def http_409(detail: str = "Conflict"):
    return HTTPException(status_code=409, detail=detail)
