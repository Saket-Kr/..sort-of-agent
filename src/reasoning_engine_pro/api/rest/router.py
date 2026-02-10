"""REST API router."""

from fastapi import APIRouter

from .endpoints.analysis import router as analysis_router
from .endpoints.health import router as health_router

router = APIRouter()

# Include sub-routers
router.include_router(health_router, tags=["Health"])
router.include_router(analysis_router, tags=["Analysis"])
