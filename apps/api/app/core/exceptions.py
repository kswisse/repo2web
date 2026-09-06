from typing import Any, Optional


class AppException(Exception):
    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: str,
        headers: Optional[dict[str, str]] = None,
    ):
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code
        self.headers = headers


class NotFoundException(AppException):
    def __init__(self, resource: str, resource_id: Any):
        super().__init__(
            status_code=404,
            detail=f"{resource} with id {resource_id} not found",
            error_code=f"{resource.upper()}_NOT_FOUND",
        )


class ValidationException(AppException):
    def __init__(self, detail: str):
        super().__init__(
            status_code=422,
            detail=detail,
            error_code="VALIDATION_ERROR",
        )


class ConflictException(AppException):
    def __init__(self, detail: str):
        super().__init__(
            status_code=409,
            detail=detail,
            error_code="CONFLICT",
        )


class RateLimitException(AppException):
    def __init__(self):
        super().__init__(
            status_code=429,
            detail="Rate limit exceeded",
            error_code="RATE_LIMIT_EXCEEDED",
            headers={"Retry-After": "60"},
        )


class ExternalServiceException(AppException):
    def __init__(self, service: str, detail: str):
        super().__init__(
            status_code=502,
            detail=f"External service error ({service}): {detail}",
            error_code="EXTERNAL_SERVICE_ERROR",
        )
