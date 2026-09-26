"""PC-friendly launcher.

Run this from the project root with:
    python run.py
"""
from __future__ import annotations

import uvicorn

from config import settings

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.environment == "development")
