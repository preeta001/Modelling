import pytest
import numpy as np
from coating_model.data_loader import generate_synthetic_batch
from coating_model.calibration import calibrate_thermodynamics
from coating_model.bias_correction import apply_bias_correction, calculate_metrics
from coating_model.batch_runner import run_batch_from_csv

def test_calibration_and_bias_correction():
    df = generate_synthetic_batch(duration_min=10) # short for speed
    
    inputs_base = {
        'batch_load_kg': 100.0,
        'cp_core_kJ_kgK': 1.1,
        'A_bed_m2': 2.0,
        'h_conv_W_m2K': 50.0,
        'HLF_kW_K': 0.1,
        'no_of_guns': 4,
        'solids_fraction': 0.15,
        'eta_dep': 0.95,
        'initial_T_bed': 30.0
    }
    
    # 1. Calibrate
    cal_res = calibrate_thermodynamics(df, inputs_base)
    assert 'HLF_kW_K' in cal_res
    assert 'evap_efficiency' in cal_res
    
    # 2. Update inputs and run
    inputs_base['HLF_kW_K'] = cal_res['HLF_kW_K']
    inputs_base['evap_efficiency'] = cal_res['evap_efficiency']
    
    res = run_batch_from_csv(df, inputs_base)
    
    # 3. Apply Bias Correction
    T_corr_const, RH_corr_const = apply_bias_correction(res, strategy='constant')
    T_corr_lin, RH_corr_lin = apply_bias_correction(res, strategy='linear')
    
    # Metrics
    metrics_uncorr = calculate_metrics(res['T_exhaust_meas'], res['T_exhaust_pred'])
    metrics_corr_const = calculate_metrics(res['T_exhaust_meas'], T_corr_const)
    metrics_corr_lin = calculate_metrics(res['T_exhaust_meas'], T_corr_lin)
    
    # Constant correction should exactly zero the bias
    assert abs(metrics_corr_const['Bias']) < 1e-6
    
    # Linear should be at least as good as constant for RMSE
    assert metrics_corr_lin['RMSE'] <= metrics_corr_const['RMSE'] + 1e-6
