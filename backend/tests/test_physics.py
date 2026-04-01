import pytest
import numpy as np
import math

from core.simulation_state import SatelliteState, ISP, G0, MASS_DRY, MASS_FUEL, MU
from engine.physics import rk4_step, propagate

def get_orbital_energy(r: np.ndarray, v: np.ndarray) -> float:
    """Specific orbital energy: E = v^2/2 - mu/r"""
    r_mag = np.linalg.norm(r)
    v_mag = np.linalg.norm(v)
    return (v_mag**2) / 2.0 - (MU / r_mag)

def test_rk4_energy_conservation():
    """Verify Keplerian energy remains constant up to 1e-6 over a 24-hour orbit."""
    # LEO orbit: altitude 500 km
    r0 = np.array([6378.137 + 500.0, 0.0, 0.0])
    v_circ = math.sqrt(MU / np.linalg.norm(r0))
    v0 = np.array([0.0, v_circ, 0.0])
    
    e0 = get_orbital_energy(r0, v0)
    
    r_final, v_final = propagate(r0, v0, 86400.0, substeps=1440) # 60s steps
    e_final = get_orbital_energy(r_final, v_final)
    
    # Delta E should be very small without J2, but J2 is active in _derivatives.
    # Wait, J2 is conservative for total mechanical energy?? Actually J2 changes orbital energy?
    # No, J2 is a conservative potential (it depends only on position). 
    # Regardless, the spec asks to "verify Keplerian energy remains constant up to 1e-6 over a 24-hour orbit without J2".
    # Wait, in the actual implementation J2 is always active. 
    # To strictly test Keplerian, we would temporarily zero out J2 or just check total energy including J2 potential.
    # The prompt actually says "without J2". We can just mock J2=0.0 in the test.
    import engine.physics
    original_j2 = engine.physics.J2
    engine.physics.J2 = 0.0
    
    try:
        r_final, v_final = propagate(r0, v0, 86400.0, substeps=1440)
        e_final = get_orbital_energy(r_final, v_final)
        
        delta_e = abs(e_final - e0)
        assert delta_e < 1e-6, f"Energy conservation failed! Delta E = {delta_e}"
    finally:
        engine.physics.J2 = original_j2


def test_fuel_consumption():
    """Verify exactly expected kg is consumed for a 15 m/s burn on a 550 kg satellite with Isp=300."""
    sat = SatelliteState(
        id="TEST-01",
        r=np.zeros(3),
        v=np.zeros(3),
        mass_dry=MASS_DRY, # 500.0
        mass_fuel=MASS_FUEL # 50.0
    )
    
    assert sat.mass_total == 550.0
    
    m0 = 550.0
    dv_km_s = 0.015  # 15 m/s
    
    # Expected analytical fuel mass
    # m_prop = m0 * (1 - exp(-dv / (Isp * g0)))
    expected_m_prop = m0 * (1.0 - math.exp(-dv_km_s / (ISP * G0)))
    
    actual_dv = sat.consume_fuel(dv_km_s)
    
    assert math.isclose(actual_dv, dv_km_s, rel_tol=1e-5)
    
    fuel_consumed = MASS_FUEL - sat.mass_fuel
    assert math.isclose(fuel_consumed, expected_m_prop, rel_tol=1e-5), f"Expected {expected_m_prop} kg, but consumed {fuel_consumed} kg"
