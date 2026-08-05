import pandas as pd
import numpy as np
from typing import Dict, Any, List

def check_status(val: float, limit_min: float, limit_max: float) -> str:
    """Returns ✅, ⚠️, or ❌ based on value against limits."""
    if pd.isna(val) or val is None:
        return "—"
    span = limit_max - limit_min
    warning_margin = span * 0.1
    if val < limit_min or val > limit_max:
        return "❌"
    elif (val < limit_min + warning_margin) or (val > limit_max - warning_margin):
        return "⚠️"
    else:
        return "✅"

def generate_stage_summary(
    sim_results: Dict[str, Any], 
    inputs: Dict[str, Any],
    limits: Dict[str, Any],
    optimized: Dict[str, Any] = None
) -> pd.DataFrame:
    rows = []
    
    # Check if we have phase data
    if 'phase' in sim_results and len(sim_results['phase']) == len(sim_results.get('time_s', sim_results.get('time', []))):
        phases = sim_results['phase']
        unique_phases, indices = np.unique(phases, return_index=True)
        # Sort by first appearance
        sorted_phases = [phases[i] for i in sorted(indices)]
        
        for i, phase in enumerate(sorted_phases):
            mask = phases == phase
            t_exh = sim_results.get('T_exhaust', sim_results.get('T_exhaust_pred', np.array([])))[mask]
            rh_exh = sim_results.get('RH_exhaust', sim_results.get('RH_exhaust_pred', np.array([])))[mask]
            wi = sim_results.get('WI', sim_results.get('WI_pred', np.array([])))[mask]
            
            if len(t_exh) == 0: continue
            
            val_t_exh = float(np.mean(t_exh))
            val_rh_exh = float(np.mean(rh_exh))
            val_wi = float(np.max(wi))
            
            rows.append([f"Stage {i+1}: {phase}", "T_exhaust", "—", "°C", f"{val_t_exh:.1f}", check_status(val_t_exh, limits.get('T_exh_min', 35), limits.get('T_exh_max', 50))])
            rows.append([f"Stage {i+1}: {phase}", "RH_exhaust", "—", "Frac", f"{val_rh_exh:.2f}", check_status(val_rh_exh, limits.get('RH_exh_min', 0.1), limits.get('RH_exh_max', 0.8))])
            rows.append([f"Stage {i+1}: {phase}", "EE Factor (Peak WI)", "—", "Ratio", f"{val_wi:.2f}", check_status(val_wi, limits.get('WI_min', 0.1), limits.get('WI_max', 1.0))])
    else:
        # Fallback to single row summary if no phases
        t_exh = sim_results.get('T_exhaust', sim_results.get('T_exhaust_pred', [0]))
        rh_exh = sim_results.get('RH_exhaust', sim_results.get('RH_exhaust_pred', [0]))
        wi = sim_results.get('WI', sim_results.get('WI_pred', [0]))
        
        val_t_exh = float(t_exh[-1]) if isinstance(t_exh, (list, np.ndarray)) else float(t_exh)
        val_rh_exh = float(rh_exh[-1]) if isinstance(rh_exh, (list, np.ndarray)) else float(rh_exh)
        val_wi = float(wi[-1]) if isinstance(wi, (list, np.ndarray)) else float(wi)
        
        rows.append(["Overall", "T_exhaust", inputs.get('T_inlet', '—'), "°C", f"{val_t_exh:.1f}", check_status(val_t_exh, limits.get('T_exh_min', 35), limits.get('T_exh_max', 50))])
        rows.append(["Overall", "RH_exhaust", inputs.get('air_cfm', '—'), "CFM", f"{val_rh_exh:.2f}", check_status(val_rh_exh, limits.get('RH_exh_min', 0.1), limits.get('RH_exh_max', 0.8))])
        rows.append(["Overall", "EE Factor (Peak WI)", inputs.get('spray_rate_g_min_gun', '—'), "g/min", f"{val_wi:.2f}", check_status(val_wi, limits.get('WI_min', 0.1), limits.get('WI_max', 1.0))])

    # Global variables
    hlf = inputs.get('HLF_kW_K', 0.1)
    rows.append(["Global", "Alpha (HLF)", "—", "kW/K", f"{hlf:.3f}", "✅"])
    
    wg = sim_results.get('weight_gain_pct', '—')
    if isinstance(wg, (list, np.ndarray)): wg = float(wg[-1])
    rows.append(["Global", "Weight Gain", "—", "%", f"{wg:.1f}" if isinstance(wg, float) else "—", "✅"])
    
    df = pd.DataFrame(rows, columns=["Stage/Category", "Parameter", "Current Input", "Unit", "Predicted Output", "Status"])
    return df
