import numpy as np

def calculate_wetness_index(m_water_spray: np.ndarray, m_evap_cap: np.ndarray) -> np.ndarray:
    """
    Calculate Wetness Index WI(t) = m_solvent_applied / m_evap_capacity
    """
    # Protect against divide by zero
    cap_safe = np.where(m_evap_cap > 1e-9, m_evap_cap, 1e-9)
    wi = m_water_spray / cap_safe
    # When both are zero (e.g. preheating), WI is 0
    wi[m_water_spray <= 1e-9] = 0.0
    return wi

def calculate_ewi(wi: np.ndarray, time_s: np.ndarray, wi_crit: float = 1.05) -> float:
    """
    Calculate Cumulative Excess Wetness Integral EWI = integral(max(0, WI - WI_crit))dt
    """
    excess = np.maximum(0.0, wi - wi_crit)
    # Numerical integration (trapezoidal rule)
    ewi = np.trapezoid(excess, x=time_s)
    return float(ewi)
