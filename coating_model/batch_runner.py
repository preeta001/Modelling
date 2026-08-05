import pandas as pd
import numpy as np
from scipy.interpolate import interp1d
from typing import Dict, Any

from coating_model.dynamic_model import run_dynamic_simulation

def create_interpolator(time_s: np.ndarray, values: np.ndarray):
    """Creates a callable function that returns the value at time t."""
    return interp1d(time_s, values, kind='linear', bounds_error=False, fill_value=(values[0], values[-1]))

def run_batch_from_csv(df: pd.DataFrame, inputs_base: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes the dynamic simulation using time-varying inputs from a dataframe.
    """
    time_s = df['time_s'].values
    
    # Required input columns (fallback to base if missing)
    interp_funcs = {}
    for col in ['T_inlet', 'airflow', 'spray_rate', 'RH_inlet']:
        if col in df.columns:
            # Map 'spray_rate' back to 'spray_rate_g_min_gun' conceptually
            key = 'spray_rate_g_min_gun' if col == 'spray_rate' else col
            if col == 'airflow':
                key = 'air_cfm' # Rename for compatibility with dynamic model
            if col == 'RH_inlet':
                key = 'R_h_inlet' # Rename for compatibility with dynamic model
            interp_funcs[key] = create_interpolator(time_s, df[col].values)
    
    # Merge callables into inputs
    sim_inputs = inputs_base.copy()
    for k, v in interp_funcs.items():
        sim_inputs[k] = v
        
    T0 = inputs_base.get('initial_T_bed', 40.0)
    initial_state = np.array([T0, 0.0, 0.0, T0, 0.0, 0.0])
    time_span = (time_s[0], time_s[-1])
    
    # Run the dynamic model
    res = run_dynamic_simulation(time_span, initial_state, sim_inputs, dt_eval_s=10.0)
    
    # Interpolate results to match the CSV timestamps for direct comparison
    aligned_res = {}
    for key in ['T_bed', 'M_water', 'M_coat', 'T_exhaust', 'RH_exhaust', 'w_exhaust', 'WI', 'm_evap', 'm_evap_cap']:
        if key in res:
            interpolator = create_interpolator(res['time_s'], res[key])
            aligned_res[f"{key}_pred"] = interpolator(time_s)
            
    # Copy measured outputs
    aligned_res['time_s'] = time_s
    if 'T_exhaust' in df.columns:
        aligned_res['T_exhaust_meas'] = df['T_exhaust'].values
    if 'RH_exhaust' in df.columns:
        aligned_res['RH_exhaust_meas'] = df['RH_exhaust'].values
    if 'T_bed' in df.columns:
        aligned_res['T_bed_meas'] = df['T_bed'].values
        
    aligned_res['EWI'] = res.get('EWI', 0.0)
    aligned_res['weight_gain_pct'] = res.get('weight_gain_pct', 0.0)
    
    return aligned_res
