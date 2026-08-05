import pytest
from coating_model.validity import check_validity_envelope
from coating_model.recommendations import generate_recommendations

def test_validity_envelope():
    limits = {'T_inlet': (20, 80)}
    val_ranges = {'spray_rate': (30, 60)}
    
    inputs_valid = {'T_inlet': 50, 'spray_rate': 45}
    res_v = check_validity_envelope(inputs_valid, limits, val_ranges)
    assert res_v['status'] == 'VALID'
    
    inputs_extrap = {'T_inlet': 50, 'spray_rate': 70}
    res_e = check_validity_envelope(inputs_extrap, limits, val_ranges)
    assert res_e['status'] == 'EXTRAPOLATION'
    
    inputs_bad = {'T_inlet': 100, 'spray_rate': 45}
    res_b = check_validity_envelope(inputs_bad, limits, val_ranges)
    assert res_b['status'] == 'ABSTAIN'

def test_recommendations():
    current = {'WI_peak': 1.1, 'T_bed_peak': 50.0, 'spray_rate_g_min_gun': 60.0}
    optimal = {'spray_rate_g_min_gun': 40.0}
    limits = {'WI_crit': 1.05, 'T_dcmp_C': 60.0}
    
    rec = generate_recommendations(current, optimal, limits)
    
    assert rec['current_assessment'] == 'High Risk'
    assert len(rec['recommendations']) == 2
    assert rec['recommendations'][0]['type'] == 'CRITICAL'
