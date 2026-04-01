"""
Visualization API — GET /api/visualization/snapshot, /fleet/health, trajectories.
Returns compressed, frontend-ready data for the Orbital Insight Dashboard.
"""

import math
import logging
from typing import Optional

import numpy as np
from fastapi import APIRouter, Query

from core.simulation_state import SimulationState, eci_to_geodetic, RE, GROUND_STATIONS
from engine.physics import predict_trajectory, DebrisNetEngine

logger = logging.getLogger("aether-x.api.visualization")
router = APIRouter()

# Shared debris engine (same instance as simulate.py via module-level state)
_local_debris_engine = DebrisNetEngine()


# ── Terminator Line ───────────────────────────────────────────────────────────

def _compute_terminator(epoch) -> list:
    """Compute approximate day/night terminator points."""
    from datetime import datetime, timezone
    import math

    # Solar declination (simplified)
    doy = epoch.timetuple().tm_yday
    decl = math.radians(-23.45 * math.cos(math.radians(360 / 365 * (doy + 10))))

    j2000 = (epoch - datetime(2000, 1, 1, 12, tzinfo=timezone.utc)).total_seconds() / 86400.0
    theta_gmst = math.fmod(280.46061837 + 360.98564736629 * j2000, 360.0)

    # Approximate subsolar longitude
    ha_sun = -theta_gmst  # rough
    subsolar_lon = ha_sun % 360.0
    if subsolar_lon > 180:
        subsolar_lon -= 360.0

    points = []
    for lat_deg in range(-89, 90, 2):
        lat_r = math.radians(lat_deg)
        # terminator longitude at this latitude
        cos_lon = -math.tan(lat_r) * math.tan(decl)
        if abs(cos_lon) > 1.0:
            continue
        lon_offset = math.degrees(math.acos(cos_lon))
        for side in (subsolar_lon + lon_offset - 90, subsolar_lon - lon_offset + 90):
            side_norm = ((side + 180) % 360) - 180
            points.append([side_norm, lat_deg])

    points.sort(key=lambda p: p[1])
    return points


# ── Snapshot Endpoint ─────────────────────────────────────────────────────────

@router.get("/visualization/snapshot")
async def get_snapshot():
    """
    Returns compressed snapshot for frontend rendering:
    - Satellite positions with geodetic coordinates + risk
    - Debris cloud (lat/lon/alt triplets, downsampled for performance)
    - Terminator line
    """
    sim = SimulationState.get_instance()
    epoch = sim.current_time

    # Satellites
    satellites_out = []
    for sat_id, sat in sim.satellites.items():
        lat, lon, alt = eci_to_geodetic(sat.r, epoch)

        # Pending burns summary
        pending = [
            {"burn_id": b.burn_id, "time": b.burn_time.isoformat()}
            for b in sat.maneuver_queue if not b.executed
        ]

        satellites_out.append({
            "id": sat_id,
            "lat": round(lat, 4),
            "lon": round(lon, 4),
            "alt_km": round(alt, 2),
            "fuel_fraction": round(sat.fuel_fraction, 4),
            "fuel_kg": round(sat.mass_fuel, 2),
            "status": sat.status,
            "risk": sat.risk,
            "total_dv_ms": round(sat.total_dv * 1000, 3),
            "uptime_h": round(sat.uptime_seconds / 3600, 2),
            "in_station_keeping": sat.in_station_keeping(),
            "pending_burns": pending,
            "history": sat.history[-20:],   # last 20 ground track points
        })

    # Debris cloud — downsample to 3000 points for rendering performance
    debris_list = list(sim.debris.values())
    step = max(1, len(debris_list) // 3000)
    debris_cloud = []
    for deb in debris_list[::step]:
        lat, lon, alt = eci_to_geodetic(deb.r, epoch)
        debris_cloud.append([round(alt, 1), round(lat, 2), round(lon, 2)])

    # Ground stations
    gs_out = []
    for lat, lon, _, _, _ in GROUND_STATIONS:
        gs_out.append({"lat": lat, "lon": lon})

    return {
        "sim_time": epoch.isoformat(),
        "step_count": sim.step_count,
        "satellites": satellites_out,
        "debris_cloud": debris_cloud,
        "debris_total": len(sim.debris),
        "terminator": _compute_terminator(epoch),
        "ground_stations": gs_out,
    }


# ── Satellite Trajectory ──────────────────────────────────────────────────────

@router.get("/visualization/satellite/{sat_id}/trajectory")
async def get_trajectory(sat_id: str, horizon_minutes: int = Query(default=90, le=1440)):
    """
    Predict trajectory for one satellite over the next N minutes.
    Returns list of (lat, lon, alt_km) waypoints.
    """
    sim = SimulationState.get_instance()
    sat = sim.satellites.get(sat_id)
    if sat is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Satellite {sat_id} not found")

    horizon_s = horizon_minutes * 60.0
    positions_eci = predict_trajectory(sat.r, sat.v, horizon_s, step_s=60.0)

    trajectory = []
    from datetime import timedelta
    for i, r_eci in enumerate(positions_eci):
        t = sim.current_time + timedelta(seconds=i * 60)
        lat, lon, alt = eci_to_geodetic(r_eci, t)
        trajectory.append({"lat": round(lat, 3), "lon": round(lon, 3), "alt_km": round(alt, 2)})

    return {
        "satellite_id": sat_id,
        "horizon_minutes": horizon_minutes,
        "points": len(trajectory),
        "trajectory": trajectory,
    }


# ── Fleet Health ──────────────────────────────────────────────────────────────

@router.get("/visualization/fleet/health")
async def get_fleet_health():
    """
    Returns per-satellite health metrics for the Fleet Health Dashboard.
    """
    sim = SimulationState.get_instance()

    fleet = []
    for sat_id, sat in sim.satellites.items():
        lat, lon, alt = eci_to_geodetic(sat.r, sim.current_time)

        # Pending burn count
        pending = sum(1 for b in sat.maneuver_queue if not b.executed)

        fleet.append({
            "id": sat_id,
            "lat": round(lat, 3),
            "lon": round(lon, 3),
            "alt_km": round(alt, 2),
            "fuel_fraction": round(sat.fuel_fraction, 4),
            "fuel_pct": round(sat.fuel_fraction * 100, 2),   # alias for FleetHealthPanel
            "fuel_kg": round(sat.mass_fuel, 2),
            "status": sat.status,
            "risk": sat.risk,
            "total_dv_ms": round(sat.total_dv * 1000, 3),
            "uptime_h": round(sat.uptime_seconds / 3600, 2),
            "in_station_keeping": sat.in_station_keeping(),
            "in_box": sat.in_station_keeping(),             # alias for FleetHealthPanel
            "pending_burns": pending,
            "mass_dry_kg": round(sat.mass_dry, 1),
        })

    # Sort: CRITICAL → WARNING → NOMINAL
    risk_order = {"CRITICAL": 0, "WARNING": 1, "ADVISORY": 2, "NOMINAL": 3, "EOL": 4}
    fleet.sort(key=lambda s: risk_order.get(s["risk"], 5))

    # Aggregate stats
    total_fuel = sum(s["fuel_kg"] for s in fleet)
    avg_fuel_frac = sum(s["fuel_fraction"] for s in fleet) / max(len(fleet), 1)
    n_eol = sum(1 for s in fleet if s["status"] == "EOL")
    n_nominal = sum(1 for s in fleet if s["status"] == "NOMINAL")

    return {
        "fleet": fleet,
        "summary": {
            "total_satellites": len(fleet),
            "nominal": n_nominal,
            "evading": sum(1 for s in fleet if s["status"] == "EVADING"),
            "recovering": sum(1 for s in fleet if s["status"] == "RECOVERING"),
            "eol": n_eol,
            "total_fuel_kg": round(total_fuel, 2),
            "avg_fuel_fraction": round(avg_fuel_frac, 4),
            "collisions_avoided": sim.total_collisions_avoided,
        }
    }


# ── Gaussian Probability Ellipsoid (Bonus) ────────────────────────────────────

@router.get("/visualization/conjunction/{sat_id}/ellipsoid")
async def get_collision_ellipsoid(sat_id: str, debris_id: str = Query(...)):
    """
    Compute Gaussian probability ellipsoid parameters for a conjunction.
    Returns semi-axes and probability of collision (Pc).
    """
    sim = SimulationState.get_instance()
    sat = sim.satellites.get(sat_id)
    deb = sim.debris.get(debris_id)

    if sat is None or deb is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Satellite or debris not found")

    # Position covariance (simplified 1-sigma position uncertainty)
    sigma_r_sat = 0.050  # km (50m)
    sigma_r_deb = 0.200  # km (200m — debris is less well-tracked)

    # Combined covariance in RTN frame
    sigma_combined = math.sqrt(sigma_r_sat**2 + sigma_r_deb**2)

    # Current separation
    sep = float(np.linalg.norm(sat.r - deb.r))

    # Mahalanobis distance
    mahal = sep / sigma_combined

    # Probability of collision (simplified: Gaussian CDF complement)
    import math
    pc = math.exp(-0.5 * mahal**2) if mahal < 10 else 0.0

    return {
        "satellite_id": sat_id,
        "debris_id": debris_id,
        "separation_km": round(sep, 4),
        "sigma_combined_km": round(sigma_combined, 4),
        "mahalanobis_distance": round(mahal, 3),
        "probability_of_collision": round(pc, 8),
        "risk_level": (
            "CRITICAL" if sep < 0.1 else
            "WARNING" if sep < 1.0 else
            "ADVISORY" if sep < 5.0 else "NOMINAL"
        ),
    }
