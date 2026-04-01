"""
Avoidance & Optimization Engine
Heuristic collision avoidance + multi-objective maneuver planning.
Tracks fuel, enforces cooldowns, manages EOL transitions.
"""

import logging
import math
from datetime import datetime, timezone, timedelta
from typing import List, Optional

import numpy as np

from core.simulation_state import (
    SimulationState, SatelliteState, ManeuverBurn,
    COOLDOWN, FUEL_EOL_THRESHOLD, has_ground_contact, G0, ISP
)
from engine.physics import (
    compute_evasion_dv, compute_recovery_dv, rtn_to_eci,
    predict_trajectory, rk4_step, MAX_DV
)

logger = logging.getLogger("aether-x.optimizer")

LATENCY_S = 10  # seconds

class AvoidanceOptimizer:
    """
    Multi-objective optimizer (deterministic baseline, RL-extensible).

    Objectives:
    - Maximize safety (avoid collisions) — Primary
    - Minimize fuel (∆v)                — Secondary
    - Maximize uptime (station-keeping) — Tertiary
    """

    def __init__(self, sim: SimulationState):
        self.sim = sim
        self._evasion_pairs = set()  # (sat_id, debris_id) scheduled
        self.gpu_accelerated = False

    def process_conjunctions(self, warnings: List[dict]) -> List[dict]:
        """
        Global Fleet Coordinator:
        1. Prioritize all conjunctions by Risk + Mission Value (fuel/health).
        2. Resolve conflicts (multiple sats vs same debris).
        3. Schedule fuel-optimal maneuvers.
        """
        if not warnings:
            return []

        # 1. Global Ranking (Simulation of MILP prioritization)
        # Coordinate to prefer the satellite with HIGHEST remaining fuel to maneuver
        def sort_key(w):
            risk_map = {"CRITICAL": 0, "WARNING": 1, "ADVISORY": 2}
            risk_val = risk_map.get(w["risk_level"], 9)
            sat = self.sim.satellites.get(w["satellite_id"])
            fuel = -sat.fuel_fraction if sat else 1.0
            tca = w["tca_seconds"]
            return (risk_val, fuel, tca)

        sorted_warnings = sorted(warnings, key=sort_key)
        
        scheduled = []
        seen_sats = set()
        debris_handled = set()  # Global coordination: avoid over-maneuvering for same debris

        for w in sorted_warnings:
            sat_id = w["satellite_id"]
            deb_id = w["debris_id"]
            
            # Coordination: If this satellite is already moving or this debris is handled by another sat
            if sat_id in seen_sats:
                continue
            
            if w["risk_level"] not in ("CRITICAL", "WARNING"):
                continue

            pair_key = (sat_id, deb_id)
            if pair_key in self._evasion_pairs:
                continue

            sat = self.sim.satellites.get(sat_id)
            if sat is None or sat.status == "EOL":
                continue

            # Fuel-Aware Thresholding
            if sat.fuel_fraction <= FUEL_EOL_THRESHOLD:
                self._schedule_eol(sat)
                continue

            # Coordination: Multi-sat conflict resolution
            if deb_id in debris_handled and w["risk_level"] != "CRITICAL":
                logger.info(f"Coordination: Debris {deb_id} already being cleared by another sat maneuver.")
                continue

            # Check cooldown
            if sat.last_burn_time is not None:
                elapsed = (self.sim.current_time - sat.last_burn_time).total_seconds()
                if elapsed < COOLDOWN:
                    logger.warning(f"Coordination: {sat_id} thruster cooldown ({COOLDOWN - elapsed:.0f}s)")
                    continue

            # Greedy minimum-∆v selection: earliest burn_time has longest time to TCA -> smallest ∆v
            burn_time = self._find_burn_window(sat, w["tca_seconds"])
            if burn_time is None:
                continue

            # Compute evasion ∆v
            deb = self.sim.debris.get(deb_id)
            if deb is None:
                continue

            dv_eci = compute_evasion_dv(
                sat.r, sat.v, deb.r, deb.v,
                w["tca_seconds"], w["min_distance_km"]
            )

            evasion_burn = ManeuverBurn(
                burn_id=f"EVA_{sat_id}_{deb_id}_{int(self.sim.current_time.timestamp())}",
                burn_time=burn_time,
                dv_vector=dv_eci,
            )

            # Recovery burn: Adaptive recovery timing logic
            # Search a +/- 30 min window around the 90-min mark for minimum recovery ∆v
            base_delay_s = 5400.0  # 90 mins
            best_rec_dv = float('inf')
            best_rec_time = None
            best_dv_rec = None
            
            delay_since_current = (burn_time - self.sim.current_time).total_seconds()

            if sat.nominal_r is not None and sat.nominal_v is not None:
                for offset in [-1800.0, 0.0, 1800.0]:
                    delay_s = base_delay_s + offset
                    total_delay_s = delay_since_current + delay_s
                    # Compute recovery dv at this future epoch
                    test_dv_rec = compute_recovery_dv(sat.r, sat.v, sat.nominal_r, sat.nominal_v, total_delay_s)
                    test_dv_mag = np.linalg.norm(test_dv_rec)
                    
                    if test_dv_mag < best_rec_dv:
                        best_rec_dv = test_dv_mag
                        best_rec_time = burn_time + timedelta(seconds=delay_s)
                        best_dv_rec = test_dv_rec
            
            if best_dv_rec is None:
                best_rec_time = burn_time + timedelta(seconds=base_delay_s)
                best_dv_rec = -dv_eci * 0.95

            recovery_burn = ManeuverBurn(
                burn_id=f"REC_{sat_id}_{deb_id}_{int(self.sim.current_time.timestamp())}",
                burn_time=best_rec_time,
                dv_vector=best_dv_rec,
            )

            sat.maneuver_queue.append(evasion_burn)
            sat.maneuver_queue.append(recovery_burn)
            sat.maneuver_queue.sort(key=lambda b: b.burn_time)

            self._evasion_pairs.add(pair_key)
            seen_sats.add(sat_id)
            debris_handled.add(deb_id)

            dv_mag_ms = np.linalg.norm(dv_eci) * 1000
            scheduled.append({
                "satellite_id": sat_id,
                "debris_id": deb_id,
                "evasion_burn": burn_time.isoformat(),
                "recovery_burn": best_rec_time.isoformat(),
                "dv_ms": round(dv_mag_ms, 4),
                "risk": w["risk_level"],
                "coordination": "GLOBAL_OPTIMIZED",
                "gpu_accelerated": self.gpu_accelerated
            })

        return scheduled

    def execute_due_maneuvers(self, sim_time: datetime) -> int:
        """Execute all burns due at or before sim_time. Returns count executed."""
        executed = 0
        for sat_id, sat in self.sim.satellites.items():
            if sat.status == "EOL":
                continue
            due = [b for b in sat.maneuver_queue
                   if not b.executed and b.burn_time <= sim_time]
            for burn in due:
                self._execute_burn(sat, burn, sim_time)
                executed += 1
        return executed

    def _execute_burn(self, sat: SatelliteState, burn: ManeuverBurn, sim_time: datetime):
        """Apply ∆v instantaneously."""
        dv = burn.dv_vector
        dv_mag = float(np.linalg.norm(dv))

        # Check LOS
        if not has_ground_contact(sat.r):
            logger.warning(f"{sat.id}: burn {burn.burn_id} skipped — no LOS")
            burn.executed = True
            return

        actual_dv = sat.consume_fuel(dv_mag)
        if dv_mag > 0:
            sat.v = sat.v + dv * (actual_dv / dv_mag)

        sat.last_burn_time = sim_time
        burn.executed = True

        self.sim.maneuver_log.append({
            "satellite_id": sat.id,
            "burn_id": burn.burn_id,
            "time": sim_time.isoformat(),
            "dv_km_s": round(actual_dv, 6),
            "fuel_remaining_kg": round(sat.mass_fuel, 3),
        })
        logger.info(
            f"Executed {burn.burn_id} on {sat.id}: "
            f"∆v={actual_dv*1000:.3f}m/s, fuel={sat.mass_fuel:.2f}kg"
        )

        # Check EOL after burn
        if sat.fuel_fraction <= FUEL_EOL_THRESHOLD:
            self._schedule_eol(sat)

    def _find_burn_window(self, sat: SatelliteState, tca_s: float) -> Optional[datetime]:
        """
        Find earliest valid burn time with LOS and latency margins.
        Handles blackout pre-scheduling.
        """
        earliest = self.sim.current_time + timedelta(seconds=LATENCY_S)
        tca_time = self.sim.current_time + timedelta(seconds=tca_s)

        # We need burn at least 300s before TCA for effectiveness
        latest_burn = tca_time - timedelta(seconds=300)
        if earliest > latest_burn:
            return None

        # Check if current position has LOS
        if has_ground_contact(sat.r):
            return earliest

        # Try to find window in next 30 minutes by propagating
        import numpy as np
        from engine.physics import rk4_step
        state = np.concatenate([sat.r, sat.v])
        for i in range(180):  # 10s steps = 30 min
            state = rk4_step(state, 10.0)
            r_test = state[:3]
            t_test = earliest + timedelta(seconds=i * 10)
            if t_test > latest_burn:
                break
            if has_ground_contact(r_test):
                return t_test

        return None

    def _schedule_eol(self, sat: SatelliteState):
        """Transition satellite to graveyard orbit (raise apogee)."""
        if sat.status == "EOL":
            return
        logger.warning(f"{sat.id}: FUEL CRITICAL — scheduling EOL graveyard maneuver")
        sat.status = "EOL"
        # Prograde burn to raise orbit (deorbit prevention)
        v_hat = sat.v / np.linalg.norm(sat.v)
        dv_graveyard = v_hat * 0.005  # 5 m/s prograde
        burn_time = self.sim.current_time + timedelta(seconds=LATENCY_S + 60)
        sat.maneuver_queue.append(ManeuverBurn(
            burn_id=f"EOL_{sat.id}",
            burn_time=burn_time,
            dv_vector=dv_graveyard,
        ))

    def update_uptime(self, dt: float):
        """Update uptime counters for all satellites."""
        for sat in self.sim.satellites.values():
            if sat.status != "EOL" and sat.in_station_keeping():
                sat.uptime_seconds += dt

    def global_fuel_stats(self) -> dict:
        """Fleet-wide fuel and efficiency summary."""
        fuels = [s.mass_fuel for s in self.sim.satellites.values()]
        dvs = [s.total_dv for s in self.sim.satellites.values()]
        return {
            "total_fuel_remaining_kg": round(sum(fuels), 2),
            "avg_fuel_fraction": round(
                sum(s.fuel_fraction for s in self.sim.satellites.values()) / max(len(self.sim.satellites), 1), 4
            ),
            "total_dv_km_s": round(sum(dvs), 6),
            "satellites_nominal": sum(1 for s in self.sim.satellites.values() if s.status == "NOMINAL"),
            "satellites_eol": sum(1 for s in self.sim.satellites.values() if s.status == "EOL"),
        }
