"""Health check endpoints."""

import time
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends

from ...dependencies import Dependencies, get_dependencies
from ...websocket.router import get_connection_manager

router = APIRouter()

# Track server start time
_start_time = time.time()


@router.get("/")
async def root() -> dict[str, str]:
    """Server root endpoint."""
    return {
        "name": "Reasoning Engine Pro",
        "version": "1.0.0",
        "status": "running",
    }


@router.get("/health")
async def health_check(
    deps: Dependencies = Depends(get_dependencies),
) -> dict[str, Any]:
    """
    Health check endpoint.

    Returns service health status including storage connectivity.
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "checks": {},
    }

    # Check storage connectivity
    try:
        storage = await deps.get_storage()
        # Try a simple operation
        exists = await storage.exists("__health_check__")
        health_status["checks"]["storage"] = {
            "status": "healthy",
            "type": type(storage).__name__,
        }
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["checks"]["storage"] = {
            "status": "unhealthy",
            "error": str(e),
        }

    return health_status


@router.get("/info")
async def server_info(deps: Dependencies = Depends(get_dependencies)) -> dict[str, Any]:
    """
    Server information endpoint.

    Returns server stats and configuration.
    """
    uptime_seconds = time.time() - _start_time

    # Get connection stats

    try:
        manager = get_connection_manager()
        ws_stats = {
            "active_connections": manager.active_count,
            "max_connections": manager.max_connections,
        }
    except RuntimeError:
        ws_stats = {
            "active_connections": 0,
            "max_connections": deps.settings.max_concurrent_connections,
        }

    return {
        "name": "Reasoning Engine Pro",
        "version": "1.0.0",
        "uptime_seconds": round(uptime_seconds, 2),
        "uptime_human": _format_uptime(uptime_seconds),
        "started_at": datetime.fromtimestamp(_start_time).isoformat(),
        "websocket": ws_stats,
        "configuration": {
            "llm_provider": deps.settings.llm_provider,
            "llm_model": deps.settings.llm_model_name,
            "redis_configured": bool(deps.settings.redis_url),
        },
    }


def _format_uptime(seconds: float) -> str:
    """Format uptime in human-readable format."""
    days, remainder = divmod(int(seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")

    return " ".join(parts)
