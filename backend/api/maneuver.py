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
    burn_id: Optional[str] = None
    burnTime: str
    deltaV_vector: DvVector

class ManeuverPlan(BaseModel):
    satelliteId: str
    maneuver_sequence: List[BurnRequest]


# ── Endpoints ─────────────────────────────────────────────────────────────────

from dateutil.parser import isoparse

@router.post("/maneuver/schedule")
async def schedule_maneuver(plan: ManeuverPlan, api_key: str = Depends(get_api_key)):
    """
    Schedule one or more thruster burns. Burns are inserted into the
    satellite's maneuver queue and executed during simulation steps.
    """
    sim = SimulationState.get_instance()
    sat_id = plan.satelliteId
    sat = sim.satellites.get(sat_id)

    if sat is None:
        raise HTTPException(status_code=404, detail="satellite not found")

    if sat.status == "EOL":
        raise HTTPException(status_code=400, detail="satellite is EOL")

    has_los = sat.has_ground_contact()
    
    # Validation logic
    total_dv = 0.0
    for burn_req in plan.maneuver_sequence:
        dv = burn_req.deltaV_vector.to_np()
        dv_mag = float(np.linalg.norm(dv))

        # Spec: Maximum Thrust Limit: |Δv| ≤ 15.0 m/s per individual burn command
        MAX_DV_KM_S = 0.015
        if dv_mag > MAX_DV_KM_S:
            raise HTTPException(status_code=400, detail="∆v exceeds 15 m/s per-burn limit")
            
        total_dv += dv_mag

    from engine.physics import MU  # Need some way to roughly check fuel, or just basic check
    
    # Calculate approx fuel usage
    from core.simulation_state import ISP
    g0 = 9.80665 / 1000.0  # km/s^2
    total_mass = sat.mass_dry + sat.mass_fuel
    # delta_m = m0 * (1 - e^(-dv / (Isp * g0)))
    mass_ratio = np.exp(total_dv / (ISP * g0))
    proj_fuel = sat.mass_fuel - (total_mass - total_mass / mass_ratio)

    has_fuel = proj_fuel >= 0

    if has_fuel and has_los:
        for burn_req in plan.maneuver_sequence:
            dv = burn_req.deltaV_vector.to_np()
            burn_time = isoparse(burn_req.burnTime)
            burn_id = burn_req.burn_id or f"MAN_{sat_id}_{sim.step_count}"

            burn = ManeuverBurn(
                burn_id=burn_id,
                burn_time=burn_time,
                dv_vector=dv,
            )
            sat.maneuver_queue.append(burn)
            sat.maneuver_queue.sort(key=lambda b: b.burn_time)

            logger.info(f"Manual burn scheduled: {burn_id} on {sat_id} @ {burn_time.isoformat()}")

    return {
        "status": "SCHEDULED" if (has_fuel and has_los) else "REJECTED",
        "validation": {
            "ground_station_los": has_los,
            "sufficient_fuel": has_fuel,
            "projected_mass_remaining_kg": round(sat.mass_dry + max(0, proj_fuel), 2)
        }
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
