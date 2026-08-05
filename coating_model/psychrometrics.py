import math
from .constants import R_d, celsius_to_kelvin
from .solvent_properties import Solvent, get_solvent

def humidity_ratio(p_total_kpa: float, p_v_kpa: float, solvent: Solvent) -> float:
    """Calculate humidity ratio (kg solvent / kg dry air)."""
    # w = (Rd/Rv) * pv / (P - pv)
    p_d = max(1e-9, p_total_kpa - p_v_kpa)
    return (R_d / solvent.R_v) * p_v_kpa / p_d

def vapor_pressure_from_humidity_ratio(p_total_kpa: float, w: float, solvent: Solvent) -> float:
    """Calculate vapor pressure (kPa) from humidity ratio."""
    return w * p_total_kpa / ((R_d / solvent.R_v) + w)

def vapor_pressure_from_rh(p_sat_kpa: float, rh_fraction: float) -> float:
    """Calculate vapor pressure from saturation pressure and relative humidity."""
    return p_sat_kpa * max(0.0, min(1.0, rh_fraction))

def relative_humidity(p_v_kpa: float, p_sat_kpa: float) -> float:
    """Calculate relative humidity (fraction)."""
    return p_v_kpa / max(1e-9, p_sat_kpa)

def air_density(T_celsius: float, p_total_kpa: float, p_v_kpa: float, w: float, solvent: Solvent) -> float:
    """Calculate moist air density in kg/m^3."""
    p_d_kpa = p_total_kpa - p_v_kpa
    T_kelvin = celsius_to_kelvin(T_celsius)
    # rho = (P_d / (Rd*T)) * (1 + w) / (1 + w*(Rv/Rd))  <-- From legacy
    rho_dry = (p_d_kpa * 1000) / (R_d * T_kelvin)
    return rho_dry * ((1 + w) / (1 + w * (solvent.R_v / R_d)))

def get_wet_bulb_temperature(T_db_celsius: float, rh_fraction: float, p_total_kpa: float, solvent: Solvent, tol=1e-4, max_iter=200) -> float:
    """Calculate wet bulb temperature iteratively."""
    rh_fraction = max(0.0, min(1.0, rh_fraction))
    p_sat_db = solvent.saturation_pressure(T_db_celsius)
    p_v_in = p_sat_db * rh_fraction
    w_in = humidity_ratio(p_total_kpa, p_v_in, solvent)
    
    T_low = solvent.inverse_saturation_pressure(p_v_in)
    T_high = T_db_celsius
    T_star = 0.5 * (T_low + T_high)
    
    Cp_air = 1.005 # kJ/kg-K
    
    it = 0
    while (T_high - T_low) > tol and it < max_iter:
        p_sat_star = solvent.saturation_pressure(T_star)
        w_star = humidity_ratio(p_total_kpa, p_sat_star, solvent)
        h_fg_star = solvent.latent_heat(T_star)
        
        # Energy balance for adiabatic saturation / wet-bulb
        num = (h_fg_star - solvent.Cp_L * T_star) * w_star - Cp_air * (T_db_celsius - T_star)
        den = h_fg_star + solvent.Cp_V * T_db_celsius - solvent.Cp_L * T_star
        w_calc = max(0.0, num / max(1e-9, den))
        
        if w_calc > w_in:
            T_high = T_star
        else:
            T_low = T_star
        T_star = 0.5 * (T_low + T_high)
        it += 1
        
    if it >= max_iter:
        raise RuntimeError("Convergence not reached in get_wet_bulb_temperature.")
    return T_star
