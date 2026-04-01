"""
Maneuver API — POST /api/maneuver/schedule, GET /api/maneuver/log
Schedule ∆v burns and retrieve maneuver history.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from utils.security import get_api_key
from core.simulation_state import SimulationState, ManeuverBurn

logger = logging.getLogger("aether-x.api.maneuver")
router = APIRouter()


# ── Request Schemas ───────────────────────────────────────────────────────────

class DvVector(BaseModel):
    x: float
    y: float
    z: float

    def to_np(self) -> np.ndarray:
        return np.array([self.x, self.y, self.z])


class BurnRequest(BaseModel):
    satellite_id: str
    burn_id: Optional[str] = None
    dv_x_km_s: float = Field(description="Delta-V x component in km/s (ECI)")
    dv_y_km_s: float = Field(description="Delta-V y component in km/s (ECI)")
    dv_z_km_s: float = Field(description="Delta-V z component in km/s (ECI)")
    offset_seconds: float = Field(default=15.0, ge=10,
                                   description="Seconds from now to execute burn")


class ManeuverPlan(BaseModel):
    burns: List[BurnRequest]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/maneuver/schedule")
async def schedule_maneuver(plan: ManeuverPlan, api_key: str = Depends(get_api_key)):
    """
    Schedule one or more thruster burns. Burns are inserted into the
    satellite's maneuver queue and executed during simulation steps.
    Enforces 10-second communication latency and thruster cooldown.
    """
    sim = SimulationState.get_instance()
    scheduled = []
    errors = []

    for burn_req in plan.burns:
        sat_id = burn_req.satellite_id
        sat = sim.satellites.get(sat_id)

        if sat is None:
            errors.append({"satellite_id": sat_id, "error": "satellite not found"})
            continue

        if sat.status == "EOL":
            errors.append({"satellite_id": sat_id, "error": "satellite is EOL"})
            continue

        # Enforce cooldown
        if sat.last_burn_time is not None:
            from core.simulation_state import COOLDOWN
            elapsed = (sim.current_time - sat.last_burn_time).total_seconds()
            if elapsed < COOLDOWN:
                errors.append({
                    "satellite_id": sat_id,
                    "error": f"thruster cooldown: {COOLDOWN - elapsed:.0f}s remaining"
                })
                continue

        dv = np.array([burn_req.dv_x_km_s, burn_req.dv_y_km_s, burn_req.dv_z_km_s])
        dv_mag = float(np.linalg.norm(dv))

        if dv_mag > 0.1:
            errors.append({"satellite_id": sat_id, "error": "∆v too large (>100 m/s)"})
            continue

        burn_time = sim.current_time + timedelta(seconds=burn_req.offset_seconds)
        burn_id = burn_req.burn_id or f"MAN_{sat_id}_{sim.step_count}"

        burn = ManeuverBurn(
            burn_id=burn_id,
            burn_time=burn_time,
            dv_vector=dv,
        )
        sat.maneuver_queue.append(burn)
        sat.maneuver_queue.sort(key=lambda b: b.burn_time)

        scheduled.append({
            "satellite_id": sat_id,
            "burn_id": burn_id,
            "burn_time": burn_time.isoformat(),
            "dv_km_s": round(dv_mag, 6),
            "dv_m_s": round(dv_mag * 1000, 3),
        })
        logger.info(f"Manual burn scheduled: {burn_id} on {sat_id} @ {burn_time.isoformat()}")

    return {
        "scheduled": scheduled,
        "errors": errors,
        "total_scheduled": len(scheduled),
    }


@router.get("/maneuver/log")
async def get_maneuver_log(limit: int = Query(default=100, le=500)):
    """Return recent maneuver execution log."""
    sim = SimulationState.get_instance()
    log = sim.maneuver_log[-limit:]
    return {
        "log": list(reversed(log)),
        "total": len(sim.maneuver_log),
    }


@router.get("/maneuver/pending")
async def get_pending_burns():
    """Return all pending (unexecuted) burns across the fleet."""
    sim = SimulationState.get_instance()
    pending = []
    for sat_id, sat in sim.satellites.items():
        for burn in sat.maneuver_queue:
            if not burn.executed:
                dv_mag = float(np.linalg.norm(burn.dv_vector))
                pending.append({
                    "satellite_id": sat_id,
                    "burn_id": burn.burn_id,
                    "burn_time": burn.burn_time.isoformat(),
                    "dv_km_s": round(dv_mag, 6),
                    "dv_m_s": round(dv_mag * 1000, 3),
                    "seconds_until": round(
                        (burn.burn_time - sim.current_time).total_seconds(), 1
                    ),
                })
    pending.sort(key=lambda b: b["burn_time"])
    return {"pending": pending, "count": len(pending)}
