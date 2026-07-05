"""Compatibility entrypoint for ASGI servers.

Run the application with:
    uvicorn backend.main:app --reload
"""

from backend.main import app

__all__ = ["app"]
