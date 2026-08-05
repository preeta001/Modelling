from scipy.optimize import differential_evolution
import numpy as np
import pandas as pd
from typing import Dict, Any

from coating_model.batch_runner import run_batch_from_csv

def calibrate_thermodynamics(
    df_batch: pd.DataFrame,
    inputs_base: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Stage 1 Calibration: Fit HLF and evap_efficiency
    Minimizes the error between Predicted T_exhaust and Measured T_exhaust
    """
    def objective(params):
        hlf, eff = params
        sim_inputs = inputs_base.copy()
        sim_inputs['HLF_kW_K'] = hlf
        sim_inputs['evap_efficiency'] = eff
        
        # Run batch prediction
        res = run_batch_from_csv(df_batch, sim_inputs)
        
        # Calculate MSE for T_exhaust (primary target)
        if 'T_exhaust_meas' in res and 'T_exhaust_pred' in res:
            mse_t_exh = np.mean((res['T_exhaust_meas'] - res['T_exhaust_pred'])**2)
        else:
            mse_t_exh = 1e6
            
        # Optional: add penalty for RH_exhaust if available
        if 'RH_exhaust_meas' in res and 'RH_exhaust_pred' in res:
            mse_rh = np.mean((res['RH_exhaust_meas'] - res['RH_exhaust_pred'])**2)
            # Scale RH (0-1) to roughly match T (10-60) scale, e.g. weight by 1000
            total_mse = mse_t_exh + (mse_rh * 1000.0)
        else:
            total_mse = mse_t_exh
            
        return total_mse

    # Bounds for Heat Loss Factor (kW/K) and Evaporation Efficiency (0-1)
    bounds = [(0.0, 1.0), (0.1, 1.0)]
    
    # Differential evolution for robust global search
    sol = differential_evolution(
        objective, 
        bounds, 
        maxiter=15, 
        popsize=5, 
        tol=0.01, 
        polish=True, 
        disp=False
    )
    
    return {
        'HLF_kW_K': sol.x[0],
        'evap_efficiency': sol.x[1],
        'mse': sol.fun
    }
