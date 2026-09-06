from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    error: dict[str, Any]


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int = 1
    page_size: int = 20
    cursor: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    postgres: str
    redis: str
