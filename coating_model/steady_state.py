import math
from typing import Dict, Any, Optional
import numpy as np

from .constants import Cp_air, T_amb_default, h_fg_i_water, CFM_TO_M3_S
from .solvent_properties import get_solvent, Solvent
from . import psychrometrics as psy

def mass_flow_dry_air(air_cfm: float, density: float) -> float:
    return air_cfm * CFM_TO_M3_S * density

def calculate_steady_state(
    T_inlet: float,
    air_cfm: float,
    R_h_inlet: float,
    spray_rate_g_min_gun: float,
    no_of_guns: int,
    solids_fraction: float,
    P_total: float = 101.325,
    solvent_name: str = "water",
    alpha_hlf: float = -100.0,
    T_exhaust_expected: Optional[float] = None
) -> Dict[str, Any]:
    """
    Calculate the steady-state thermodynamics for the coating pan.
    Reimplements the legacy EE model.
    """
    solvent = get_solvent(solvent_name)
    
    # 1. Inlet Air State
    p_sat_i = solvent.saturation_pressure(T_inlet)
    p_v_i = psy.vapor_pressure_from_rh(p_sat_i, R_h_inlet)
    w_inlet = psy.humidity_ratio(P_total, p_v_i, solvent)
    rho_air_i = psy.air_density(T_inlet, P_total, p_v_i, w_inlet, solvent)
    h_v_i = solvent.latent_heat(T_inlet)
    
    m_a = mass_flow_dry_air(air_cfm, rho_air_i)
    
    # 2. Spray & Evaporation
    spray_rate_total_g_min = spray_rate_g_min_gun * no_of_guns
    solvent_fraction = 1.0 - solids_fraction
    m_w = (spray_rate_total_g_min * solvent_fraction) / 60000.0 # kg/s
    
    # 3. Exhaust Humidity
    m_a_dry = m_a / (1 + w_inlet)
    w_exhaust = (m_w / m_a_dry) + w_inlet
    
    # 4. Exhaust Temperature (Energy Balance)
    def calc_T_exhaust(alpha: float) -> float:
        # T_exhaust = (T_inlet * (Cp_air + enthalpy_A * w_inlet + alpha/2) + ((w_exhaust - w_inlet) * (h_fg_i - enthalpy_B)) - (alpha * T_amb)) / (Cp_air + enthalpy_A * w_exhaust + alpha/2)
        # Using legacy formulation for exact match
        num = T_inlet * (Cp_air + solvent.enthalpy_A * w_inlet + alpha/2) + \
              ((w_exhaust - w_inlet) * (h_fg_i_water - solvent.enthalpy_B)) - (alpha * T_amb_default)
        den = Cp_air + solvent.enthalpy_A * w_exhaust + alpha/2
        return num / den

    if T_exhaust_expected is not None and T_exhaust_expected > 0:
        from scipy.optimize import differential_evolution
        def residual_alpha(alpha_arr):
            alpha_local = float(alpha_arr[0])
            T_exh = calc_T_exhaust(alpha_local)
            return abs(T_exh - T_exhaust_expected)
        
        bounds_alpha = [(-100.0, 1000.0)]
        sol_alpha = differential_evolution(residual_alpha, bounds=bounds_alpha, tol=1e-6, maxiter=1000, polish=True, disp=False)
        alpha_used = float(sol_alpha.x[0])
        T_exhaust = calc_T_exhaust(alpha_used)
    else:
        alpha_used = alpha_hlf
        T_exhaust = calc_T_exhaust(alpha_used)
        
    # 5. Exhaust State & EE
    p_sat_o = solvent.saturation_pressure(T_exhaust)
    h_v_o = solvent.latent_heat(T_exhaust)
    p_v_o = psy.vapor_pressure_from_humidity_ratio(P_total, w_exhaust, solvent)
    R_h_exhaust_raw = psy.relative_humidity(p_v_o, p_sat_o)
    R_h_exhaust = max(0.0, min(R_h_exhaust_raw, 0.99))
    
    T_wbt_i = psy.get_wet_bulb_temperature(T_inlet, R_h_inlet, P_total, solvent)
    rho_air_o = psy.air_density(T_exhaust, P_total, p_v_o, w_exhaust, solvent)
    p_w_i = solvent.saturation_pressure(T_wbt_i)
    
    # EE factor
    Num1 = (p_w_i * 1000) / (solvent.R_v * (T_wbt_i + 273.15))
    Num2 = (p_v_i * 1000) / (solvent.R_v * (T_inlet + 273.15))
    Num = Num1 - Num2
    Dnm1 = (rho_air_i + rho_air_o) / 2
    Dnm2 = Cp_air * 1000
    Dnm3 = T_inlet - T_exhaust
    Dnm4 = (h_v_o - h_fg_i_water) * 1000
    ee_factor = Num / max(1e-9, (Dnm1 * Dnm2 * Dnm3 / max(1e-9, Dnm4)))
    
    return {
        'T_exhaust': T_exhaust,
        'w_exhaust': w_exhaust,
        'RH_exhaust': R_h_exhaust,
        'RH_exhaust_raw': R_h_exhaust_raw,
        'ee_factor': ee_factor,
        'alpha_used': alpha_used,
        'T_wbt_i': T_wbt_i,
        'm_w': m_w,
        'm_a_dry': m_a_dry
    }
