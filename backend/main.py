"""
AETHER-X: Autonomous Constellation Manager
Main FastAPI application entry point
"""

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware

from api.telemetry import router as telemetry_router
from utils.static import mount_frontend
from api.maneuver import router as maneuver_router
from api.simulate import router as simulate_router
from api.visualization import router as visualization_router
from core.simulation_state import SimulationState
from utils.security import get_api_key

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("aether-x")


# ── Rate Limiting (Production Hardening) ────────────────────────────────────
_rate_limit_db = {}  # {ip: [timestamp, count]}

async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "0.0.0.0"
    now = time.time()
    # 100 requests per minute
    if client_ip in _rate_limit_db:
        last_reset, count = _rate_limit_db[client_ip]
        if now - last_reset > 60:
            _rate_limit_db[client_ip] = [now, 1]
        else:
            if count >= 100:
                raise HTTPException(status_code=429, detail="Too many requests")
            _rate_limit_db[client_ip][1] += 1
    else:
        _rate_limit_db[client_ip] = [now, 1]
    return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize simulation on startup and persist on shutdown."""
    logger.info("Initializing AETHER-X Simulation Engine...")
    state = SimulationState.get_instance()
    await state.initialize()
    # RESTORE PERSISTED STATE (OVERWRITE WITH LATEST TELEMETRY)
    state.load_from_disk()
    logger.info(f"Initialized {len(state.satellites)} satellites and {len(state.debris)} debris objects.")
    
    yield
    
    logger.info("Shutting down AETHER-X. Persisting state...")
    state.save_to_disk()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="AETHER-X: Autonomous Constellation Manager",
    description="Orbital Debris Avoidance & Constellation Management System",
    version="1.0.0",
    lifespan=lifespan,
)

app.middleware("http")(rate_limit_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(telemetry_router, prefix="/api", tags=["Telemetry"])
app.include_router(maneuver_router, prefix="/api", tags=["Maneuver"])
app.include_router(simulate_router, prefix="/api", tags=["Simulation"])
app.include_router(visualization_router, prefix="/api", tags=["Visualization"])


# ── Health Check (Monitoring) ───────────────────────────────────────────────
@app.get("/health", tags=["Infrastructure"])
async def health():
    state = SimulationState.get_instance()
    return {
        "status": "operational",
        "satellites": len(state.satellites),
        "debris": len(state.debris),
        "sim_time": state.current_time.isoformat(),
    }


# Mount built frontend (must be last)
mount_frontend(app)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False, workers=1)
