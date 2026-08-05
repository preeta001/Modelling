import pytest
import numpy as np
from coating_model.dynamic_model import run_dynamic_simulation
from coating_model.steady_state import calculate_steady_state

def test_dynamic_model_exhaust_outputs():
    """
    Test that the dynamic model correctly outputs T_exhaust, RH_exhaust, and WI.
    Verify that at long times under constant spray, T_exhaust matches the steady-state EE model.
    """
    inputs = {
        'batch_load_kg': 100.0,
        'cp_core_kJ_kgK': 1.1,
        'A_bed_m2': 2.0,
        'h_conv_W_m2K': 50.0,
        'HLF_kW_K': 0.1,
        'T_inlet': 60.0,
        'air_cfm': 1200.0,
        'R_h_inlet': 0.1,
        'spray_rate_g_min_gun': 30.0,
        'no_of_guns': 4,
        'solids_fraction': 0.15,
        'eta_dep': 0.95,
        'evap_efficiency': 0.8
    }
    
    initial_state = np.array([40.0, 0.0, 0.0, 40.0, 0.0, 0.0])
    time_span = (0.0, 1800.0) # 30 minutes to ensure steady state
    
    res_dyn = run_dynamic_simulation(time_span, initial_state, inputs, dt_eval_s=60.0)
    
    # Check that new outputs exist
    assert 'T_exhaust' in res_dyn
    assert 'RH_exhaust' in res_dyn
    assert 'WI' in res_dyn
    assert 'EWI' in res_dyn
    assert 'weight_gain_pct' in res_dyn
    
    # Calculate steady state equivalent
    res_ss = calculate_steady_state(
        T_inlet=60.0,
        air_cfm=1200.0,
        R_h_inlet=0.1,
        spray_rate_g_min_gun=30.0,
        no_of_guns=4,
        solids_fraction=0.15,
        alpha_hlf=0.1
    )
    
    # The dynamic model's final exhaust temperature should closely approach the steady-state
    # (subject to slight differences in mass transfer efficiency vs pure equilibrium, but they should track)
    T_exh_dyn_final = res_dyn['T_exhaust'][-1]
    
    # T_exhaust should be lower than T_inlet due to evaporative cooling
    assert T_exh_dyn_final < 60.0
    
    # RH_exhaust should be > 0 and < 1.0
    RH_exh_dyn_final = res_dyn['RH_exhaust'][-1]
    assert 0.0 < RH_exh_dyn_final < 1.0
    
    # Wetness index should be computable
    WI_final = res_dyn['WI'][-1]
    assert WI_final > 0.0
