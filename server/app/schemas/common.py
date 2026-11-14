from typing import Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic envelope for paginated list responses."""
    items: list[T]
    total: int = Field(..., description="Total number of items matching filters")
    page: int = Field(..., ge=1, description="Current page number (1-based)")
    size: int = Field(..., ge=1, description="Page size limit")
    pages: int = Field(..., ge=0, description="Total number of pages")

