"""
Static file server: mounts the Vite-built frontend under FastAPI.
Falls back gracefully if the build directory doesn't exist (dev mode).
"""

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

logger = logging.getLogger("aether-x.utils.static")

FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"


def mount_frontend(app: FastAPI):
    """Mount built React frontend. Serves index.html for all unknown routes (SPA)."""
    if not FRONTEND_DIST.exists():
        logger.warning(
            f"Frontend dist not found at {FRONTEND_DIST}. "
            "Run 'npm run build' inside frontend/ or build via Docker."
        )
        return

    # Serve static assets (JS, CSS, images)
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    # Catch-all: serve index.html for SPA routing
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        index = FRONTEND_DIST / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return {"error": "Frontend not built. Run npm run build."}

    logger.info(f"Frontend mounted from {FRONTEND_DIST}")
