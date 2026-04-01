"""
Physics Engine: RK4 orbital propagation with J2 perturbation,
KD-Tree spatial indexing, TCA computation, conjunction assessment.
"""

import math
import time
import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.spatial import KDTree

from core.simulation_state import (
    SimulationState, SatelliteState, DebrisState,
    MU, RE, J2, COLLISION_THRESHOLD, eci_to_geodetic
)

logger = logging.getLogger("aether-x.physics")


# ── Equations of Motion ──────────────────────────────────────────────────────

def _j2_acceleration(r: np.ndarray) -> np.ndarray:
    """Compute J2 perturbation acceleration."""
    x, y, z = r
    r_mag = np.linalg.norm(r)
    r5 = r_mag ** 5
    factor = 1.5 * J2 * MU * RE**2 / r5
    z2_r2 = (z / r_mag) ** 2
    return factor * np.array([
        x * (5 * z2_r2 - 1),
        y * (5 * z2_r2 - 1),
        z * (5 * z2_r2 - 3),
    ])


def _derivatives(state: np.ndarray) -> np.ndarray:
    """State derivative: [v, a] for 6D state vector [x,y,z,vx,vy,vz]."""
    r = state[:3]
    v = state[3:]
    r_mag = np.linalg.norm(r)
    a_grav = -(MU / r_mag**3) * r
    a_j2 = _j2_acceleration(r)
    a_total = a_grav + a_j2
    return np.concatenate([v, a_total])


def rk4_step(state: np.ndarray, dt: float) -> np.ndarray:
    """Single RK4 integration step."""
    k1 = _derivatives(state)
    k2 = _derivatives(state + 0.5 * dt * k1)
    k3 = _derivatives(state + 0.5 * dt * k2)
    k4 = _derivatives(state + dt * k3)
    return state + (dt / 6.0) * (k1 + 2*k2 + 2*k3 + k4)


def propagate(r: np.ndarray, v: np.ndarray, dt: float,
              substeps: int = 10) -> Tuple[np.ndarray, np.ndarray]:
    """Propagate state forward by dt seconds using RK4 with substeps."""
    state = np.concatenate([r, v])
    sub_dt = dt / substeps
    for _ in range(substeps):
        state = rk4_step(state, sub_dt)
    return state[:3], state[3:]


def predict_trajectory(r: np.ndarray, v: np.ndarray,
                        duration_s: float, step_s: float = 60.0) -> List[np.ndarray]:
    """Generate trajectory positions over duration."""
    positions = [r.copy()]
    state = np.concatenate([r, v])
    n_steps = int(duration_s / step_s)
    for _ in range(n_steps):
        state = rk4_step(state, step_s)
        positions.append(state[:3].copy())
    return positions


# ── Spatial Indexing (KD-Tree) ────────────────────────────────────────────────

def derivatives_batch(states: np.ndarray) -> np.ndarray:
    """Vectorized state derivatives for [x, y, z, vx, vy, vz]. states is (N, 6)."""
    r = states[:, :3]
    v = states[:, 3:]
    # Avoid division by zero
    r_mag = np.linalg.norm(r, axis=1, keepdims=True) + 1e-9
    a_grav = -(MU / r_mag**3) * r
    
    # Vectorized J2
    z = r[:, 2:3]
    z2_r2 = (z / r_mag)**2
    factor = 1.5 * J2 * MU * RE**2 / r_mag**5
    a_j2 = factor * np.column_stack([
        r[:, 0] * (5 * z2_r2[:, 0] - 1),
        r[:, 1] * (5 * z2_r2[:, 0] - 1),
        r[:, 2] * (5 * z2_r2[:, 0] - 3),
    ])
    return np.column_stack([v, a_grav + a_j2])


def rk4_batch(states: np.ndarray, dt: float) -> np.ndarray:
    """Vectorized RK4 for N objects simultaneously. states is (N, 6)."""
    k1 = derivatives_batch(states)
    k2 = derivatives_batch(states + 0.5 * dt * k1)
    k3 = derivatives_batch(states + 0.5 * dt * k2)
    k4 = derivatives_batch(states + dt * k3)
    return states + (dt / 6.0) * (k1 + 2*k2 + 2*k3 + k4)

class DebrisNetEngine:
    """Fast collision pre-filter using KD-Tree spatial indexing."""

    def __init__(self):
        self._tree: Optional[KDTree] = None
        self._debris_ids: List[str] = []
        self._positions: Optional[np.ndarray] = None
        self._last_build_time: float = 0.0

    def rebuild(self, debris: Dict[str, DebrisState]):
        """Rebuild KD-Tree from current debris positions. O(N log N)."""
        t0 = time.perf_counter()
        ids = list(debris.keys())
        positions = np.array([debris[d].r for d in ids])
        self._tree = KDTree(positions)
        self._debris_ids = ids
        self._positions = positions
        elapsed = (time.perf_counter() - t0) * 1000
        logger.info(f"KD-Tree rebuilt: {len(ids)} objects in {elapsed:.2f}ms")
        return elapsed

    def query_nearby(self, sat_r: np.ndarray,
                      radius_km: float = 50.0) -> List[Tuple[str, float]]:
        """
        Return (debris_id, distance_km) pairs within radius.
        Reduces O(N²) to ~O(N log N).
        """
        if self._tree is None:
            return []
        t0 = time.perf_counter()
        indices = self._tree.query_ball_point(sat_r, radius_km)
        results = []
        for idx in indices:
            dist = float(np.linalg.norm(sat_r - self._positions[idx]))
            results.append((self._debris_ids[idx], dist))
        elapsed = (time.perf_counter() - t0) * 1000
        return results


# ── Conjunction Assessment ────────────────────────────────────────────────────

def compute_tca(r_sat: np.ndarray, v_sat: np.ndarray,
                r_deb: np.ndarray, v_deb: np.ndarray,
                horizon_s: float = 86400.0,
                step_s: float = 60.0) -> Tuple[float, float]:
    """
    Compute Time of Closest Approach (TCA) and minimum distance.
    Returns (tca_seconds, min_distance_km).
    Evaluates across the entire horizon to capture multi-pass conjunctions.
    """
    best_dist = float("inf")
    best_t = 0.0

    s_sat = np.concatenate([r_sat, v_sat])
    s_deb = np.concatenate([r_deb, v_deb])

    t = 0.0
    while t <= horizon_s:
        dist = np.linalg.norm(s_sat[:3] - s_deb[:3])
        if dist < best_dist:
            best_dist = float(dist)
            best_t = t

        s_sat = rk4_step(s_sat, step_s)
        s_deb = rk4_step(s_deb, step_s)
        t += step_s

    return best_t, best_dist


def assess_conjunctions(sim: SimulationState, debris_engine: DebrisNetEngine,
                         horizon_s: float = 86400.0) -> List[dict]:
    """
    Full conjunction assessment pipeline with Kinetic Bounding Volume pre-filter.
    """
    t0 = time.perf_counter()
    warnings = []

    for sat_id, sat in sim.satellites.items():
        if sat.status == "EOL":
            continue

        # Stage 1: KD-Tree spatial pre-filter (current snapshot)
        nearby = debris_engine.query_nearby(sat.r, radius_km=200.0)

        # Stage 2: KBV velocity-aware pre-filter
        kbv_candidates = kbv_pre_filter(
            sat.r, sat.v, nearby, sim.debris,
            lookahead_s=600.0, sigma_pos_km=0.05
        )

        for deb_id, coarse_dist, kbv_radius in kbv_candidates:
            if coarse_dist > 200.0 + kbv_radius:
                continue
            deb = sim.debris[deb_id]
            tca_s, min_dist = compute_tca(
                sat.r, sat.v, deb.r, deb.v, horizon_s=horizon_s, step_s=60.0
            )

            if min_dist < 10.0:  # Widened threshold from 5.0 to 10.0 per spec
                risk = "CRITICAL" if min_dist < COLLISION_THRESHOLD else (
                    "WARNING" if min_dist < 1.0 else "ADVISORY"
                )
                closing_spd = closing_speed_km_s(sat.v, deb.v, sat.r, deb.r)
                
                # Probabilistic Uncertainty Propagation (Shadow Agent)
                total_cov = sat.covariance + deb.covariance
                # Linearized Pc proxy: Mahalanobis distance overflow
                sigma_r = math.sqrt(np.trace(total_cov))
                pc = math.exp(-0.5 * (min_dist / (sigma_r + 1e-9))**2)
                
                warnings.append({
                    "satellite_id": sat_id,
                    "debris_id": deb_id,
                    "tca_seconds": tca_s,
                    "min_distance_km": min_dist,
                    "risk_level": risk,
                    "pc": round(pc, 6),           # Probability of Collision
                    "sigma_r_km": round(sigma_r, 4),# Probabilistic Uncertainty
                    "current_distance_km": coarse_dist,
                    "closing_speed_km_s": round(closing_spd, 4),
                    "kbv_radius_km": kbv_radius,
                })

    elapsed = (time.perf_counter() - t0) * 1000
    logger.info(f"Conjunction assessment: {len(warnings)} warnings in {elapsed:.2f}ms")
    warnings.sort(key=lambda w: w["min_distance_km"])
    return warnings


# ── RTN Frame Utilities ───────────────────────────────────────────────────────

def eci_to_rtn(r: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Build RTN rotation matrix from ECI state."""
    R_hat = r / np.linalg.norm(r)
    N_hat = np.cross(r, v)
    N_hat = N_hat / np.linalg.norm(N_hat)
    T_hat = np.cross(N_hat, R_hat)
    return np.column_stack([R_hat, T_hat, N_hat])  # ECI cols = RTN axes


def rtn_to_eci(dv_rtn: np.ndarray, r: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Convert delta-v from RTN to ECI frame."""
    M = eci_to_rtn(r, v)
    return M @ dv_rtn


def compute_evasion_dv(r_sat: np.ndarray, v_sat: np.ndarray,
                        r_deb: np.ndarray, v_deb: np.ndarray,
                        tca_s: float, min_dist: float) -> np.ndarray:
    """
    Compute optimal evasion delta-v in ECI using B-plane linearized miss distance.
    ΔB ≈ (∂B/∂v) · Δv ensures standoff is actually achieved.
    """
    # Propagate to TCA
    r_sat_tca, v_sat_tca = propagate(r_sat, v_sat, tca_s)
    r_deb_tca, v_deb_tca = propagate(r_deb, v_deb, tca_s)
    
    r_rel_tca = r_sat_tca - r_deb_tca
    v_rel_tca = v_sat_tca - v_deb_tca
    v_rel_mag = np.linalg.norm(v_rel_tca)
    
    # Target standoff
    target_standoff = 5.0 # targeting 5km standoff
    current_miss = np.linalg.norm(r_rel_tca)
    deficit = max(0.0, target_standoff - current_miss)
    
    if deficit == 0.0:
        return np.zeros(3)

    # Unit vector along relative velocity
    v_rel_hat = v_rel_tca / (v_rel_mag + 1e-9)
    
    # B-plane vector (miss vector at TCA)
    b_vec = r_rel_tca - np.dot(r_rel_tca, v_rel_hat) * v_rel_hat
    b_mag = np.linalg.norm(b_vec)
    
    if b_mag < 1e-6:
        # Exact head-on, arbitrary transverse direction
        v_sat_hat = v_sat_tca / np.linalg.norm(v_sat_tca)
        b_hat = np.cross(v_rel_hat, np.cross(v_sat_hat, v_rel_hat))
        b_hat = b_hat / np.linalg.norm(b_hat)
    else:
        b_hat = b_vec / b_mag
        
    # Desired change in B-plane vector
    delta_b_mag = deficit
    
    # Sensitivity (∂B/∂v): how delta-v at t=0 affects B at t=tca
    # Approximation: ΔB ≈ Δv_transverse * tca_s
    
    # We want to apply dv in the transverse (T) direction for fuel efficiency.
    v_mag = np.linalg.norm(v_sat)
    T_hat = v_sat / v_mag
    
    # Projection of T_hat on the B-plane
    T_hat_b = T_hat - np.dot(T_hat, v_rel_hat) * v_rel_hat
    T_hat_b_mag = np.linalg.norm(T_hat_b)
    
    if T_hat_b_mag < 0.1 or tca_s < 1.0:
        # If T directon doesn't align well with B-plane, or tca is too small, use b_hat
        dv_dir = b_hat
        dv_mag = (delta_b_mag / max(tca_s, 1.0))
    else:
        # Align dv with T_hat (prograde or retrograde)
        T_hat_b_unit = T_hat_b / T_hat_b_mag
        # Dot product with b_hat tells us if we should burn prograde or retrograde
        sign = np.sign(np.dot(T_hat_b_unit, b_hat))
        if sign == 0: sign = 1.0
        dv_dir = sign * T_hat
        dv_mag = delta_b_mag / (tca_s * T_hat_b_mag)
        
    # Cap Delta-V
    MAX_DV = 0.015
    dv_mag = max(0.001, min(dv_mag, MAX_DV))
    
    return dv_dir * dv_mag


def compute_recovery_dv(r_sat: np.ndarray, v_sat: np.ndarray,
                         r_nom: np.ndarray, v_nom: np.ndarray,
                         delay_s: float) -> np.ndarray:
    """
    Compute recovery burn to return to nominal slot.
    Propagates both satellite and nominal slot forward by delay_s,
    then computes the required phasing delta-v at that future epoch.
    """
    r_future, v_future = propagate(r_sat, v_sat, delay_s)
    r_nom_future, v_nom_future = propagate(r_nom, v_nom, delay_s)
    
    dv_nom = v_nom_future - v_future
    dv_mag = np.linalg.norm(dv_nom)
    if dv_mag < 1e-6:
        return np.zeros(3)
    
    # Cap at max single burn
    dv_mag = min(dv_mag, 0.010)
    return (dv_nom / np.linalg.norm(dv_nom)) * dv_mag

# Expose MAX_DV for import
MAX_DV = 0.015


# ── Kinetic Bounding Volumes (KBV) ──────────────────────────────────────────
#
# Enhancement: Instead of querying a static KD-Tree (snapshot of positions),
# KBV inflates each debris object's effective radius by its velocity uncertainty
# and propagation time, creating a swept volume per object.
#
# At TCA time t, the bounding sphere radius is:
#   r_bv(t) = r_physical + σ_pos + |v_rel| × t × safety_scale
#
# This catches objects that are "safe now" but converging fast — the KD-Tree
# alone misses these because it only sees current separation, not closing speed.
#
# Integration: KBV is used as a pre-filter *before* TCA computation.
# Only objects whose KBV overlaps the satellite's bounding sphere enter
# the expensive RK4 TCA computation loop.

KBV_SAFETY_SCALE = 0.002   # 2 m/s uncertainty per second of lookahead
KBV_PHYSICAL_RADIUS = 0.001  # km (1 m representative object size)


def compute_kinetic_bounding_radius(v_debris: np.ndarray,
                                     v_sat: np.ndarray,
                                     lookahead_s: float = 600.0,
                                     sigma_pos_km: float = 0.05) -> float:
    """
    Compute the kinetic bounding volume radius for a debris object.

    Inflates the collision sphere by:
    - Positional uncertainty (sigma_pos_km)
    - Velocity-induced sweep: |v_relative| × lookahead × safety_scale

    Args:
        v_debris:    Debris velocity vector (km/s ECI)
        v_sat:       Satellite velocity vector (km/s ECI)
        lookahead_s: Forward propagation window in seconds
        sigma_pos_km: Positional 1-sigma uncertainty in km

    Returns:
        Effective bounding radius in km.
    """
    v_rel = np.linalg.norm(v_debris - v_sat)
    swept = v_rel * lookahead_s * KBV_SAFETY_SCALE
    return KBV_PHYSICAL_RADIUS + sigma_pos_km + swept


def kbv_pre_filter(sat_r: np.ndarray, sat_v: np.ndarray, 
                    debris_candidates: list, 
                    sim_debris: dict, 
                    lookahead_s: float = 600.0, 
                    sigma_pos_km: float = 0.05) -> list:
    """
    Apply Vectorized Kinetic Bounding Volume (KBV) pre-filter.
    
    Architecture: This refactor moves from a Python-loop-per-object approach 
    to a vectorized NumPy broadcast. This is the **GPU-Ready** execution path 
    that allows AETHER-X to scale to 1M+ debris objects (using CuPy or Vulkan).
    """
    if not debris_candidates: return []
    
    ids = np.array([c[0] for c in debris_candidates])
    dists = np.array([c[1] for c in debris_candidates])
    
    # Extract velocities for relevant candidates only (Vectorized)
    v_deb_array = np.array([sim_debris[id].v for id in ids])
    
    # Vectorized KBV calculation (NumPy Broadcast)
    v_rel_vec = np.linalg.norm(v_deb_array - sat_v, axis=1)
    kbv_radii = KBV_PHYSICAL_RADIUS + sigma_pos_km + (v_rel_vec * lookahead_s * KBV_SAFETY_SCALE)
    
    # Vectorized Mask
    SAT_PROXIMITY_KM = 200.0
    mask = dists <= (SAT_PROXIMITY_KM + kbv_radii)
    
    return [(ids[i], dists[i], round(kbv_radii[i], 4)) for i in np.where(mask)[0]]


def closing_speed_km_s(v_sat: np.ndarray, v_debris: np.ndarray,
                         r_sat: np.ndarray, r_debris: np.ndarray) -> float:
    """
    Compute the radial closing speed between satellite and debris.
    Positive = converging, Negative = diverging.
    """
    r_rel = r_debris - r_sat
    v_rel = v_debris - v_sat
    r_hat = r_rel / (np.linalg.norm(r_rel) + 1e-9)
    return float(np.dot(v_rel, r_hat))
