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

class ECIVector(BaseModel):
    x: float
    y: float
    z: float

    def to_np(self) -> np.ndarray:
        return np.array([self.x, self.y, self.z])


class SatelliteTelemetry(BaseModel):
    id: str
    position_km: ECIVector
    velocity_km_s: ECIVector
    mass_dry_kg: float = Field(default=250.0, gt=0)
    mass_fuel_kg: float = Field(default=30.0, ge=0)
    status: Optional[str] = "NOMINAL"


class DebrisTelemetry(BaseModel):
    id: str
    position_km: ECIVector
    velocity_km_s: ECIVector
    rcs_m2: float = Field(default=0.01, gt=0)


class TelemetryPayload(BaseModel):
    satellites: List[SatelliteTelemetry] = []
    debris: List[DebrisTelemetry] = []
    replace: bool = False   # if True, replace existing; else upsert


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/telemetry")
async def ingest_telemetry(payload: TelemetryPayload):
    """
    Ingest real-time state vectors for satellites and debris.
    Upserts into simulation state. Use replace=true to reset the field.
    """
    sim = SimulationState.get_instance()

    if payload.replace:
        sim.satellites.clear()
        sim.debris.clear()

    sat_updated = 0
    for t in payload.satellites:
        r = t.position_km.to_np()
        v = t.velocity_km_s.to_np()
        if t.id in sim.satellites:
            sat = sim.satellites[t.id]
            sat.r = r
            sat.v = v
            sat.status = t.status or sat.status
        else:
            sat = SatelliteState(
                id=t.id, r=r, v=v,
                mass_dry=t.mass_dry_kg,
                mass_fuel=t.mass_fuel_kg,
                status=t.status or "NOMINAL",
                nominal_r=r.copy(),
                nominal_v=v.copy(),
            )
            sim.satellites[t.id] = sat
        sat_updated += 1

    deb_updated = 0
    for d in payload.debris:
        r = d.position_km.to_np()
        v = d.velocity_km_s.to_np()
        sim.debris[d.id] = DebrisState(id=d.id, r=r, v=v, rcs=d.rcs_m2)
        deb_updated += 1

    logger.info(f"Telemetry ingested: {sat_updated} satellites, {deb_updated} debris")
    return {
        "status": "ok",
        "satellites_updated": sat_updated,
        "debris_updated": deb_updated,
        "total_satellites": len(sim.satellites),
        "total_debris": len(sim.debris),
    }
