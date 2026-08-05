import math
from typing import Dict, Any

def scale_rpm_linear(N_ref: float, D_ref: float, D_target: float) -> float:
    """Rule 1: Constant Peripheral Speed"""
    return N_ref * (D_ref / D_target)

def scale_rpm_froude(N_ref: float, D_ref: float, D_target: float) -> float:
    """Rule 2: Constant Froude Number"""
    return N_ref * math.sqrt(D_ref / D_target)

def scale_up_equipment(source_equip: Any, target_equip: Any, source_rpm: float) -> Dict[str, float]:
    """
    Calculate target RPM using different rules and calculate divergence.
    """
    n_linear = scale_rpm_linear(source_rpm, source_equip.diameter_m, target_equip.diameter_m)
    n_froude = scale_rpm_froude(source_rpm, source_equip.diameter_m, target_equip.diameter_m)
    
    return {
        'target_rpm_linear': n_linear,
        'target_rpm_froude': n_froude,
        'divergence_pct': abs(n_linear - n_froude) / max(n_linear, 1e-9) * 100.0
    }
