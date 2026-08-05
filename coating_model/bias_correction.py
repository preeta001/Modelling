import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple

def apply_bias_correction(
    aligned_res: Dict[str, Any], 
    strategy: str = 'constant'
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Applies Track B style hybrid residual correction to the mechanistic model outputs.
    Returns the corrected T_exhaust and RH_exhaust arrays.
    """
    
    time_s = aligned_res['time_s']
    T_exh_pred = aligned_res['T_exhaust_pred']
    RH_exh_pred = aligned_res['RH_exhaust_pred']
    
    # If no measurements, we can't calculate bias; just return predictions
    if 'T_exhaust_meas' not in aligned_res or 'RH_exhaust_meas' not in aligned_res:
        return T_exh_pred, RH_exh_pred
        
    T_exh_meas = aligned_res['T_exhaust_meas']
    RH_exh_meas = aligned_res['RH_exhaust_meas']
    
    T_exh_corr = np.copy(T_exh_pred)
    RH_exh_corr = np.copy(RH_exh_pred)
    
    if strategy == 'constant':
        # Calculate mean error across the entire batch
        T_bias = np.mean(T_exh_meas - T_exh_pred)
        RH_bias = np.mean(RH_exh_meas - RH_exh_pred)
        
        T_exh_corr += T_bias
        RH_exh_corr += RH_bias
        
    elif strategy == 'phase_dependent':
        # Identify phases based on spray rate (if available in aligned_res)
        # For simplicity, if spray > 0, it's 'spray', else 'non-spray'
        # We need the spray rate used during the batch. We can infer it from m_evap or WI if needed.
        # But for robustness, we'll assume the dataframe has a 'spray_rate_g_min_gun' callable,
        # or we just fall back to a linear model if phases aren't strictly defined in the dict.
        # A simple proxy: if T_exh_pred is dropping rapidly, it's spraying.
        # Let's use a robust linear fallback for now.
        pass
        
    elif strategy == 'linear':
        # Fit a simple linear model: y_meas = a * y_pred + b
        # T_exhaust
        A = np.vstack([T_exh_pred, np.ones(len(T_exh_pred))]).T
        m_t, c_t = np.linalg.lstsq(A, T_exh_meas, rcond=None)[0]
        T_exh_corr = m_t * T_exh_pred + c_t
        
        # RH_exhaust
        A = np.vstack([RH_exh_pred, np.ones(len(RH_exh_pred))]).T
        m_rh, c_rh = np.linalg.lstsq(A, RH_exh_meas, rcond=None)[0]
        RH_exh_corr = m_rh * RH_exh_pred + c_rh
        
    return T_exh_corr, RH_exh_corr

def calculate_metrics(y_true, y_pred) -> Dict[str, float]:
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    rmse = np.sqrt(np.mean((y_true - y_pred)**2))
    mae = np.mean(np.abs(y_true - y_pred))
    bias = np.mean(y_true - y_pred)
    
    # R2
    ss_res = np.sum((y_true - y_pred)**2)
    ss_tot = np.sum((y_true - np.mean(y_true))**2)
    r2 = 1 - (ss_res / max(1e-9, ss_tot))
    
    return {
        'RMSE': rmse,
        'MAE': mae,
        'Bias': bias,
        'R2': r2
    }
