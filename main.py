"""Application entry point and startup."""
from __future__ import annotations

import uvicorn

from app.api import create_app
from config import settings

app = create_app()


def cli() -> None:
    """Console-script entry point for editable installs."""
    # Bind to 0.0.0.0 for containers and live preview environments.
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.environment == "development")


if __name__ == "__main__":
    cli()
