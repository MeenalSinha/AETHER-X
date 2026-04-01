"""
Telemetry API — POST /api/telemetry
Accepts real-time satellite & debris state vectors (ECI frame).
"""

import logging
from typing import List, Optional

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.simulation_state import SimulationState, SatelliteState, DebrisState

logger = logging.getLogger("aether-x.api.telemetry")
router = APIRouter()


# ── Request Schemas ───────────────────────────────────────────────────────────

class VectorSpec(BaseModel):
    x: float
    y: float
    z: float

    def to_np(self) -> np.ndarray:
        return np.array([self.x, self.y, self.z])

class TelemetryObject(BaseModel):
    id: str
    type: str  # "SATELLITE" or "DEBRIS"
    r: VectorSpec
    v: VectorSpec
    # Additional generic fields for satellites (to retain logic if supplied)
    mass_dry_kg: float = Field(default=500.0, gt=0)
    mass_fuel_kg: float = Field(default=50.0, ge=0)
    status: Optional[str] = "NOMINAL"
    rcs_m2: float = Field(default=0.01, gt=0)  # For debris

class TelemetryPayload(BaseModel):
    timestamp: str
    objects: List[TelemetryObject]


# ── Endpoint ──────────────────────────────────────────────────────────────────

from utils.security import get_api_key
from fastapi import Depends

@router.post("/telemetry")
async def ingest_telemetry(payload: TelemetryPayload, api_key: str = Depends(get_api_key)):
    """
    Ingest real-time state vectors for satellites and debris in the spec schema.
    Returns ACK status with processed count.
    """
    sim = SimulationState.get_instance()
    
    # Process objects
    processed_count = 0
    for obj in payload.objects:
        r_np = obj.r.to_np()
        v_np = obj.v.to_np()
        
        if obj.type.upper() == "SATELLITE":
            if obj.id in sim.satellites:
                sat = sim.satellites[obj.id]
                sat.r = r_np
                sat.v = v_np
                sat.status = obj.status or sat.status
            else:
                sat = SatelliteState(
                    id=obj.id, r=r_np, v=v_np,
                    mass_dry=obj.mass_dry_kg,
                    mass_fuel=obj.mass_fuel_kg,
                    status=obj.status or "NOMINAL",
                    nominal_r=r_np.copy(),
                    nominal_v=v_np.copy(),
                )
                sim.satellites[obj.id] = sat
        elif obj.type.upper() == "DEBRIS":
            sim.debris[obj.id] = DebrisState(id=obj.id, r=r_np, v=v_np, rcs=obj.rcs_m2)
        
        processed_count += 1

    active_warnings = sum(len(sat.conjunctions) for sat in sim.satellites.values())

    logger.info(f"Telemetry ingested: {processed_count} objects at {payload.timestamp}")
    return {
        "status": "ACK",
        "processed_count": processed_count,
        "active_cdm_warnings": active_warnings
    }
