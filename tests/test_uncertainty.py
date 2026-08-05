import pytest
import numpy as np
from coating_model.uncertainty import run_monte_carlo_propagation, calculate_failure_probability

def dummy_sim_func(inputs):
    # Just a mock function returning inputs
    return {
        'T_bed': np.array([inputs['T_inlet'] - 10.0]),
        'M_water_final': 0.1,
        'WI_peak': 1.1 if inputs['spray_rate'] > 50 else 0.9
    }

def test_monte_carlo():
    base_inputs = {'T_inlet': 60.0, 'spray_rate': 40.0}
    input_dists = {
        'T_inlet': ('normal', 60.0, 2.0),
        'spray_rate': ('uniform', 30.0, 70.0)
    }
    
    res = run_monte_carlo_propagation(100, base_inputs, input_dists, dummy_sim_func)
    
    assert len(res['T_bed_final']) == 100
    assert len(res['WI_peak']) == 100
    
    # Check failure probability
    p_fail = calculate_failure_probability(res['WI_peak'], 1.0, '>')
    assert p_fail >= 0.0 and p_fail <= 1.0
