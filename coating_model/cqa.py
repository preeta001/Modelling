import numpy as np
from typing import Dict, Any

def predict_weight_gain(m_coat_total_kg: float, m_core_total_kg: float) -> float:
    return m_coat_total_kg / max(1e-9, m_core_total_kg)

def predict_film_thickness_distribution(m_coat_i: np.ndarray, a_tablet_m2: float, rho_film_kg_m3: float = 1300.0) -> np.ndarray:
    """Returns thickness in micrometers."""
    delta_i_m = m_coat_i / (rho_film_kg_m3 * a_tablet_m2)
    return delta_i_m * 1e6

def predict_assay_distribution(m_coat_i: np.ndarray, x_api_coat: float) -> np.ndarray:
    """Returns mass of API per tablet."""
    return m_coat_i * x_api_coat

def calculate_thermal_exposure_integral(t_bed_series: np.ndarray, time_s_series: np.ndarray, t_ref_C: float = 40.0) -> float:
    """H_T = integral(max(0, T_bed - T_ref)) dt"""
    excess_T = np.maximum(0.0, t_bed_series - t_ref_C)
    return float(np.trapezoid(excess_T, x=time_s_series))

def calculate_moisture_exposure_integral(a_w_series: np.ndarray, time_s_series: np.ndarray) -> float:
    """H_M = integral(a_w) dt"""
    return float(np.trapezoid(a_w_series, x=time_s_series))
