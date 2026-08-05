import pytest
from coating_model.data_loader import generate_synthetic_batch
from coating_model.batch_runner import run_batch_from_csv

def test_batch_runner_with_synthetic_data():
    df = generate_synthetic_batch(duration_min=30)
    
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
    
    res = run_batch_from_csv(df, inputs_base)
    
    assert len(res['time_s']) == len(df)
    assert 'T_exhaust_pred' in res
    assert 'T_exhaust_meas' in res
    assert len(res['T_exhaust_pred']) == len(res['T_exhaust_meas'])
    
    # T_exhaust_pred should respond to spray (cooling)
    # Spray starts at t=15 min
    assert res['T_exhaust_pred'][20] < res['T_exhaust_pred'][10]
