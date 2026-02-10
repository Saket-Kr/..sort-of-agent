"""FastAPI application factory."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..config import Settings, get_settings
from ..observability.logger import get_logger, setup_logging
from .dependencies import Dependencies
from .rest.router import router as rest_router
from .websocket.router import init_websocket
from .websocket.router import router as websocket_router

# Path to web client directory
WEB_CLIENT_DIR = Path(__file__).parent.parent.parent.parent / "web_client"

logger = get_logger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """
    Create and configure FastAPI application.

    Args:
        settings: Optional settings override

    Returns:
        Configured FastAPI application
    """
    if settings is None:
        settings = get_settings()

    # Setup logging
    setup_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Application lifespan handler."""
        logger.info("Starting Reasoning Engine Pro...")

        # Initialize dependencies
        deps = Dependencies.get_instance(settings)

        # Initialize storage connection
        try:
            await deps.get_storage()
            logger.info("Storage connected")
        except Exception as e:
            logger.error("Failed to connect storage", error=str(e))

        # Initialize WebSocket
        init_websocket(deps, settings.max_concurrent_connections)
        logger.info(
            "WebSocket initialized",
            max_connections=settings.max_concurrent_connections,
        )

        logger.info(
            "Reasoning Engine Pro started",
            llm_provider=settings.llm_provider,
            llm_model=settings.llm_model_name,
        )

        yield

        # Cleanup
        logger.info("Shutting down...")
        await deps.cleanup()
        logger.info("Shutdown complete")

    # Create app
    app = FastAPI(
        title="Reasoning Engine Pro",
        description="Production-grade agentic workflow planning system",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(rest_router)
    app.include_router(websocket_router)

    # Serve web client static files
    if WEB_CLIENT_DIR.exists():
        # Mount static directories
        app.mount("/css", StaticFiles(directory=WEB_CLIENT_DIR / "css"), name="css")
        app.mount("/js", StaticFiles(directory=WEB_CLIENT_DIR / "js"), name="js")

        # Serve index.html at /app
        @app.get("/app", include_in_schema=False)
        async def serve_web_client():
            """Serve the web client application."""
            return FileResponse(WEB_CLIENT_DIR / "index.html")

        # Also serve at /app/ with trailing slash
        @app.get("/app/", include_in_schema=False)
        async def serve_web_client_trailing():
            """Serve the web client application (trailing slash)."""
            return FileResponse(WEB_CLIENT_DIR / "index.html")

        logger.info("Web client mounted at /app", path=str(WEB_CLIENT_DIR))
    else:
        logger.warning("Web client directory not found", path=str(WEB_CLIENT_DIR))

    return app


# Default app instance for uvicorn
app = create_app()
