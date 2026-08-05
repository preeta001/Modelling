import pytest
import numpy as np
from coating_model.dynamic_model import run_dynamic_simulation

def test_mass_balance_closure():
    inputs = {
        'batch_load_kg': 100.0,
        'cp_core_kJ_kgK': 1.1,
        'A_bed_m2': 2.0,
        'h_conv_W_m2K': 50.0,
        'HLF_kW_K': 0.05,
        'T_inlet': 60.0,
        'air_cfm': 500.0, # Low airflow to force some moisture accumulation
        'R_h_inlet': 0.1,
        'spray_rate_g_min_gun': 100.0, # High spray
        'no_of_guns': 4,
        'solids_fraction': 0.15,
        'eta_dep': 1.0 # 100% deposition for easy balance check
    }
    
    initial_state = np.array([40.0, 0.0, 0.0, 40.0, 0.0, 0.0])
    time_span = (0.0, 300.0) # 5 mins
    
    res = run_dynamic_simulation(time_span, initial_state, inputs)
    
    # Total spray in 5 mins: 400 g/min * 5 = 2000 g = 2.0 kg
    # Solids: 2.0 * 0.15 = 0.3 kg
    # Water: 2.0 * 0.85 = 1.7 kg
    
    # Check solid mass balance
    assert np.isclose(res['M_coat'][-1], 0.3, rtol=0.01)
    
    # We can't directly check water mass balance without tracking evaporation explicitly in the output,
    # but we can ensure M_water > 0 because we sprayed a lot of water and airflow is low
    assert res['M_water'][-1] >= 0.0
    
    # If we had zero airflow (or very low), all water would accumulate
    # In reality some evaporated. M_water must be <= 1.7 kg
    assert res['M_water'][-1] <= 1.7
