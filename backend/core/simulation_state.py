"""
Core simulation state: shared data model, constants, and initialization.
Single-instance SimulationState holds all satellites, debris, and runtime data.
"""

import os
import json
import math
import random
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path

import numpy as np

logger = logging.getLogger("aether-x.state")

# ── Physical Constants ────────────────────────────────────────────────────────
MU = 398600.4418       # km³/s² — Earth gravitational parameter
RE = 6378.137          # km — Earth equatorial radius
J2 = 1.08262668e-3     # J2 oblateness coefficient
G0 = 9.80665e-3        # km/s² — standard gravity
ISP = 220.0            # s — thruster specific impulse (hydrazine)
COLLISION_THRESHOLD = 0.1   # km — hard collision distance
COOLDOWN = 600              # s — thruster cooldown after burn
FUEL_EOL_THRESHOLD = 0.05   # fraction — trigger graveyard orbit

# ── Ground Station Locations (lat, lon, elevation mask deg) ───────────────────
GROUND_STATIONS: List[Tuple[float, float, float]] = [
    (40.7, -74.0,  5.0),   # New York
    (51.5,  -0.1,  5.0),   # London
    (35.7, 139.7,  5.0),   # Tokyo
    (-33.9,  18.4, 5.0),   # Cape Town
    (28.6,   77.2, 5.0),   # New Delhi
    (55.8,   37.6, 5.0),   # Moscow
    (-34.6, -58.4, 5.0),   # Buenos Aires
]


# ── Coordinate Utilities ──────────────────────────────────────────────────────

def eci_to_geodetic(r: np.ndarray, epoch: datetime) -> Tuple[float, float, float]:
    """Convert ECI position to (lat_deg, lon_deg, alt_km)."""
    x, y, z = r
    r_mag = math.sqrt(x*x + y*y + z*z)

    # Greenwich sidereal angle (simplified)
    j2000 = (epoch - datetime(2000, 1, 1, 12, tzinfo=timezone.utc)).total_seconds() / 86400.0
    theta_gmst = math.fmod(280.46061837 + 360.98564736629 * j2000, 360.0)
    theta_rad = math.radians(theta_gmst)

    # Rotate ECI → ECEF
    lon_eci = math.atan2(y, x)
    lon_ecef = lon_eci - theta_rad
    lon_deg = math.degrees(lon_ecef)
    lon_deg = ((lon_deg + 180) % 360) - 180

    lat_deg = math.degrees(math.asin(z / r_mag))
    alt_km = r_mag - RE
    return lat_deg, lon_deg, alt_km


def has_ground_contact(r: np.ndarray) -> bool:
    """Check if satellite has line-of-sight to any ground station."""
    r_mag = float(np.linalg.norm(r))
    for lat_gs, lon_gs, elev_mask in GROUND_STATIONS:
        lat_r = math.radians(lat_gs)
        lon_r = math.radians(lon_gs)
        r_gs = np.array([
            RE * math.cos(lat_r) * math.cos(lon_r),
            RE * math.cos(lat_r) * math.sin(lon_r),
            RE * math.sin(lat_r),
        ])
        diff = r - r_gs
        dist = float(np.linalg.norm(diff))
        # elevation mask: dot product check
        r_gs_hat = r_gs / np.linalg.norm(r_gs)
        diff_hat = diff / dist
        elev_rad = math.radians(elev_mask)
        # Nadir angle from ground station
        cos_nadir = float(np.dot(r_gs_hat, diff_hat))
        if cos_nadir > math.sin(elev_rad):
            return True
    return False


# ── Data Classes ──────────────────────────────────────────────────────────────

@dataclass
class ManeuverBurn:
    burn_id: str
    burn_time: datetime
    dv_vector: np.ndarray    # km/s ECI
    executed: bool = False


@dataclass
class SatelliteState:
    id: str
    r: np.ndarray            # ECI position km
    v: np.ndarray            # ECI velocity km/s
    mass_dry: float          # kg
    mass_fuel: float         # kg
    status: str = "NOMINAL"  # NOMINAL | EVADING | RECOVERING | EOL
    risk: str = "NOMINAL"    # NOMINAL | ADVISORY | WARNING | CRITICAL
    nominal_r: Optional[np.ndarray] = None
    nominal_v: Optional[np.ndarray] = None
    last_burn_time: Optional[datetime] = None
    maneuver_queue: List[ManeuverBurn] = field(default_factory=list)
    total_dv: float = 0.0    # km/s cumulative
    uptime_seconds: float = 0.0
    history: List[Tuple[float, float]] = field(default_factory=list)  # (lat, lon) trail
    covariance: np.ndarray = field(default_factory=lambda: np.eye(3) * 0.01) # Position covariance (km²)

    @property
    def mass_total(self) -> float:
        return self.mass_dry + self.mass_fuel

    @property
    def fuel_fraction(self) -> float:
        total_propellant = self.mass_dry * 0.15  # 15% dry mass as propellant capacity
        return max(0.0, min(1.0, self.mass_fuel / total_propellant))

    def consume_fuel(self, dv_km_s: float) -> float:
        """Apply Tsiolkovsky equation, return actual dv achieved."""
        if dv_km_s <= 0:
            return 0.0
        # m_prop = m_total * (1 - exp(-dv / (Isp * g0)))
        m_prop = self.mass_total * (1.0 - math.exp(-dv_km_s / (ISP * G0)))
        actual_prop = min(m_prop, self.mass_fuel)
        self.mass_fuel -= actual_prop
        # Actual dv from prop consumed
        if self.mass_total > 0:
            actual_dv = ISP * G0 * math.log((self.mass_total + actual_prop) / self.mass_total)
        else:
            actual_dv = 0.0
        self.total_dv += actual_dv
        return actual_dv

    def in_station_keeping(self) -> bool:
        """Check if within 10 km station-keeping box."""
        if self.nominal_r is None:
            return True
        dist = float(np.linalg.norm(self.r - self.nominal_r))
        return dist < 10.0

    def update_history(self, epoch: datetime):
        lat, lon, _ = eci_to_geodetic(self.r, epoch)
        self.history.append((lat, lon))
        if len(self.history) > 30:
            self.history = self.history[-30:]


@dataclass
class DebrisState:
    id: str
    r: np.ndarray
    v: np.ndarray
    rcs: float = 0.01   # m² radar cross section
    covariance: np.ndarray = field(default_factory=lambda: np.eye(3) * 0.1) # Position covariance (km²)


# ── SimulationState Singleton ─────────────────────────────────────────────────

class SimulationState:
    _instance: Optional["SimulationState"] = None

    def __init__(self):
        self.satellites: Dict[str, SatelliteState] = {}
        self.debris: Dict[str, DebrisState] = {}
        self.current_time: datetime = datetime.now(timezone.utc)
        self.step_count: int = 0
        self.maneuver_log: List[dict] = []
        self.performance_log: List[dict] = []
        self.total_collisions_avoided: int = 0

    @classmethod
    def get_instance(cls) -> "SimulationState":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def save_to_disk(self, filename: str = "infra/state.json"):
        """Serialize current state to disk for persistence."""
        try:
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            data = {
                "current_time": self.current_time.isoformat(),
                "step_count": self.step_count,
                "total_collisions_avoided": self.total_collisions_avoided,
                "satellites": {
                    sid: {
                        "r": sat.r.tolist(),
                        "v": sat.v.tolist(),
                        "mass_fuel": sat.mass_fuel,
                        "status": sat.status,
                        "risk": sat.risk,
                        "total_dv": sat.total_dv,
                        "history": list(sat.history),
                        "covariance": sat.covariance.tolist()
                    } for sid, sat in self.satellites.items()
                },
                "debris": {
                    did: {
                        "r": deb.r.tolist(),
                        "v": deb.v.tolist(),
                        "covariance": deb.covariance.tolist()
                    } for did, deb in self.debris.items()
                }
            }
            with open(filename, "w") as f:
                json.dump(data, f)
            logger.info(f"State persisted to {filename}")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def load_from_disk(self, filename: str = "infra/state.json"):
        """Load state from disk if exists."""
        if not os.path.exists(filename):
            return
        try:
            with open(filename, "r") as f:
                data = json.load(f)
            self.current_time = datetime.fromisoformat(data["current_time"])
            self.step_count = data["step_count"]
            self.total_collisions_avoided = data["total_collisions_avoided"]
            
            # Map back to satellite states (partial recovery of positions)
            for sid, sdata in data["satellites"].items():
                if sid in self.satellites:
                    sat = self.satellites[sid]
                    sat.r = np.array(sdata["r"])
                    sat.v = np.array(sdata["v"])
                    sat.mass_fuel = sdata["mass_fuel"]
                    sat.status = sdata["status"]
                    sat.risk = sdata["risk"]
                    sat.total_dv = sdata["total_dv"]
                    sat.history = [tuple(h) for h in sdata["history"]]
                    if "covariance" in sdata:
                        sat.covariance = np.array(sdata["covariance"])
            
            # Restore debris states if present
            if "debris" in data:
                for did, ddata in data["debris"].items():
                    if did in self.debris:
                        deb = self.debris[did]
                        deb.r = np.array(ddata["r"])
                        deb.v = np.array(ddata["v"])
                        if "covariance" in ddata:
                            deb.covariance = np.array(ddata["covariance"])

            logger.info(f"State restored from {filename}")
        except Exception as e:
            logger.error(f"Failed to load state: {e}")

    async def initialize(self, n_satellites: int = 50, n_debris: int = 10000):
        """Populate initial constellation and debris field."""
        random.seed(42)
        np.random.seed(42)

        if self.satellites:
            logger.info("Simulation already initialized. Skipping populate.")
            return

        # ── Generate satellite constellation ──────────────────────────────────
        # Walker Delta constellation: 5 orbital planes × 10 sats each
        n_planes = 5
        sats_per_plane = n_satellites // n_planes
        inclination = math.radians(53.0)   # ISS-like
        alt_km = 550.0

        a = RE + alt_km
        n_orb = math.sqrt(MU / a**3)   # mean motion rad/s

        for plane in range(n_planes):
            raan = math.radians(plane * 360.0 / n_planes)
            for s in range(sats_per_plane):
                mean_anomaly = math.radians(s * 360.0 / sats_per_plane +
                                            plane * 360.0 / n_planes / n_satellites * 180)
                r, v = _keplerian_to_eci(a, 0.001, inclination, raan,
                                         math.radians(5.0 * plane), mean_anomaly)
                # Add small dispersion
                r += np.random.randn(3) * 0.5
                v += np.random.randn(3) * 0.0001

                sat_id = f"SAT-{plane+1}{s+1:02d}"
                mass_dry = 250.0 + random.uniform(-20, 20)
                mass_fuel = mass_dry * 0.15 * random.uniform(0.7, 1.0)

                sat = SatelliteState(
                    id=sat_id, r=r, v=v,
                    mass_dry=mass_dry, mass_fuel=mass_fuel,
                    nominal_r=r.copy(), nominal_v=v.copy(),
                )
                sat.update_history(self.current_time)
                self.satellites[sat_id] = sat

        # ── Generate debris field ─────────────────────────────────────────────
        # Mix of altitudes (LEO range 300–2000 km), varied inclinations
        debris_alts = np.random.uniform(400, 800, n_debris)
        debris_incs = np.concatenate([
            np.random.uniform(0, 10, n_debris // 4),       # equatorial
            np.random.uniform(45, 60, n_debris // 4),      # mid-inclination
            np.random.uniform(85, 100, n_debris // 4),     # polar/sun-sync
            np.random.uniform(0, 180, n_debris // 4),      # random
        ])[:n_debris]
        debris_raans = np.random.uniform(0, 360, n_debris)
        debris_mas = np.random.uniform(0, 360, n_debris)

        for i in range(n_debris):
            a_d = RE + debris_alts[i]
            inc_d = math.radians(debris_incs[i])
            raan_d = math.radians(debris_raans[i])
            ma_d = math.radians(debris_mas[i])
            ecc_d = random.uniform(0, 0.01)

            r_d, v_d = _keplerian_to_eci(a_d, ecc_d, inc_d, raan_d, 0.0, ma_d)

            deb_id = f"DEB-{i+1:05d}"
            self.debris[deb_id] = DebrisState(
                id=deb_id, r=r_d, v=v_d,
                rcs=random.uniform(0.001, 1.0),
            )

        logger.info(f"Initialized {len(self.satellites)} satellites, {len(self.debris)} debris objects")

    def log_performance(self, event: str, elapsed_ms: float, extra: dict = None):
        entry = {
            "time": self.current_time.isoformat(),
            "event": event,
            "elapsed_ms": round(elapsed_ms, 3),
            **(extra or {}),
        }
        self.performance_log.append(entry)
        if len(self.performance_log) > 200:
            self.performance_log = self.performance_log[-200:]


# ── Orbital Mechanics Helper ──────────────────────────────────────────────────

def _keplerian_to_eci(a: float, ecc: float, inc: float, raan: float,
                       argp: float, ma: float) -> Tuple[np.ndarray, np.ndarray]:
    """Convert Keplerian elements to ECI position/velocity."""
    # Solve Kepler's equation (Newton-Raphson)
    E = ma
    for _ in range(50):
        dE = (ma - E + ecc * math.sin(E)) / (1 - ecc * math.cos(E))
        E += dE
        if abs(dE) < 1e-12:
            break

    # True anomaly
    nu = 2.0 * math.atan2(
        math.sqrt(1 + ecc) * math.sin(E / 2),
        math.sqrt(1 - ecc) * math.cos(E / 2)
    )

    # Distance and velocity in perifocal frame
    p = a * (1 - ecc**2)
    r_pqw = p / (1 + ecc * math.cos(nu))
    r_vec_pqw = np.array([r_pqw * math.cos(nu), r_pqw * math.sin(nu), 0.0])
    v_scale = math.sqrt(MU / p)
    v_vec_pqw = np.array([-v_scale * math.sin(nu), v_scale * (ecc + math.cos(nu)), 0.0])

    # Rotation matrix PQW → ECI
    R = _rot_pqw_eci(inc, raan, argp)
    return R @ r_vec_pqw, R @ v_vec_pqw


def _rot_pqw_eci(inc: float, raan: float, argp: float) -> np.ndarray:
    """Build PQW→ECI rotation matrix."""
    ci, si = math.cos(inc), math.sin(inc)
    cr, sr = math.cos(raan), math.sin(raan)
    cw, sw = math.cos(argp), math.sin(argp)
    return np.array([
        [cr*cw - sr*sw*ci,  -cr*sw - sr*cw*ci,  sr*si],
        [sr*cw + cr*sw*ci,  -sr*sw + cr*cw*ci, -cr*si],
        [sw*si,              cw*si,              ci   ],
    ])
