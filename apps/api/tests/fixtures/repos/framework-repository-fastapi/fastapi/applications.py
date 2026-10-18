"""FastAPI application module."""

from starlette.applications import Starlette

from fastapi.routing import APIRouter


class FastAPI(Starlette):
    """A simple, fast, high-performance web framework for building APIs with Python."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.router = APIRouter()
