"""Entry point for the application."""

import uvicorn

from .config import get_settings


def main() -> None:
    """Run the application."""
    settings = get_settings()

    uvicorn.run(
        "reasoning_engine_pro.api.app:app",
        host=settings.ws_host,
        port=settings.ws_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
