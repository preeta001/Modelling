import numpy as np
from typing import Dict

def calculate_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Calculate standard validation metrics."""
    # Ensure they are numpy arrays and same shape
    y_t = np.asarray(y_true)
    y_p = np.asarray(y_pred)
    
    # Drop NaNs if any
    mask = ~np.isnan(y_t) & ~np.isnan(y_p)
    y_t = y_t[mask]
    y_p = y_p[mask]
    
    if len(y_t) == 0:
        return {'rmse': 0.0, 'mae': 0.0, 'bias': 0.0, 'r2': 0.0}

    err = y_p - y_t
    rmse = np.sqrt(np.mean(err**2))
    mae = np.mean(np.abs(err))
    bias = np.mean(err)
    
    ss_res = np.sum(err**2)
    ss_tot = np.sum((y_t - np.mean(y_t))**2)
    r2 = 1.0 - (ss_res / max(1e-9, ss_tot))
    
    return {
        'rmse': float(rmse),
        'mae': float(mae),
        'bias': float(bias),
        'r2': float(r2)
    }
