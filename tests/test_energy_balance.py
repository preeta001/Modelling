import pytest
import numpy as np
from coating_model.dynamic_model import run_dynamic_simulation

def test_adiabatic_cooling():
    inputs = {
        'batch_load_kg': 100.0,
        'cp_core_kJ_kgK': 1.1,
        'A_bed_m2': 2.0,
        'h_conv_W_m2K': 50.0,
        'HLF_kW_K': 0.0, # Zero heat loss
        'T_inlet': 60.0,
        'air_cfm': 1500.0, 
        'R_h_inlet': 0.05,
        'spray_rate_g_min_gun': 20.0, # Spraying to cause evaporative cooling
        'no_of_guns': 4,
        'solids_fraction': 0.10,
    }
    
    initial_state = np.array([60.0, 0.0, 0.0, 60.0, 0.0, 0.0])
    time_span = (0.0, 300.0)
    
    res = run_dynamic_simulation(time_span, initial_state, inputs)
    
    # Because there is evaporation, bed temp must drop below 60C (evaporative cooling)
    assert res['T_bed'][-1] < 60.0
