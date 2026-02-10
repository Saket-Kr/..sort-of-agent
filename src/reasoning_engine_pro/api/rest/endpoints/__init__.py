"""REST API endpoints."""

from .analysis import router as analysis_router
from .health import router as health_router

__all__ = [
    "health_router",
    "analysis_router",
]
