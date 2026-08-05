import pytest
import math
from coating_model.steady_state import calculate_steady_state

def test_steady_state_regression():
    # Known inputs that would match the legacy EE model
    inputs = {
        'T_inlet': 60.0,
        'air_cfm': 1200.0,
        'R_h_inlet': 0.1,
        'spray_rate_g_min_gun': 30.0,
        'no_of_guns': 4,
        'solids_fraction': 0.15,
        'P_total': 101.325,
        'solvent_name': "water",
        'T_exhaust_expected': 45.0
    }
    
    res = calculate_steady_state(**inputs)
    
    assert res['T_exhaust'] > 0
    assert res['ee_factor'] > 0
    
    # Just checking it runs without crashing and produces physical outputs
    assert res['RH_exhaust'] >= 0.0
    assert res['RH_exhaust'] <= 1.0
