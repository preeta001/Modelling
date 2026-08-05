import pytest
import numpy as np
from coating_model.dynamic_model import run_dynamic_simulation

def test_dynamic_preheat_no_spray():
    # If no spray, bed should warm up towards inlet temp and moisture should be zero
    inputs = {
        'batch_load_kg': 100.0,
        'cp_core_kJ_kgK': 1.1,
        'A_bed_m2': 2.0,
        'h_conv_W_m2K': 50.0,
        'HLF_kW_K': 0.1,
        'T_inlet': 60.0,
        'air_cfm': 1200.0,
        'R_h_inlet': 0.1,
        'spray_rate_g_min_gun': 0.0, # Zero spray
        'no_of_guns': 4,
        'solids_fraction': 0.15,
    }
    
    initial_state = np.array([25.0, 0.0, 0.0, 25.0, 0.0, 0.0])
    time_span = (0.0, 600.0) # 10 mins
    
    res = run_dynamic_simulation(time_span, initial_state, inputs)
    
    # Bed should heat up
    assert res['T_bed'][-1] > 25.0
    # No water accumulation
    assert np.allclose(res['M_water'], 0.0)
    # No coat accumulation
    assert np.allclose(res['M_coat'], 0.0)

def test_dynamic_spray_accumulates_coat():
    inputs = {
        'batch_load_kg': 100.0,
        'cp_core_kJ_kgK': 1.1,
        'A_bed_m2': 2.0,
        'h_conv_W_m2K': 50.0,
        'HLF_kW_K': 0.1,
        'T_inlet': 60.0,
        'air_cfm': 1200.0,
        'R_h_inlet': 0.1,
        'spray_rate_g_min_gun': 50.0, # Spraying!
        'no_of_guns': 4,
        'solids_fraction': 0.15,
        'eta_dep': 0.95
    }
    
    initial_state = np.array([45.0, 0.0, 0.0, 45.0, 0.0, 0.0]) 
    time_span = (0.0, 60.0) # 1 min
    
    res = run_dynamic_simulation(time_span, initial_state, inputs)
    
    # Coat should accumulate
    assert res['M_coat'][-1] > 0.0
    # Expected mass: 50 g/min/gun * 4 guns = 200 g/min = 0.2 kg/min = 0.2 kg in 1 min. 
    # Solids fraction = 0.15 -> 0.03 kg solid.
    # Eta dep = 0.95 -> 0.0285 kg
    expected_coat = 0.2 * 0.15 * 0.95
    assert np.isclose(res['M_coat'][-1], expected_coat, rtol=0.01)

def test_thermal_equilibration_two_zones():
    # Test internal circulation thermodynamics.
    # Spray zone = 20C, Drying zone = 60C. 
    # f_s = 0.2, f_d = 0.8
    # With no external heat transfer, they must equilibrate exactly to:
    # 0.2 * 20 + 0.8 * 60 = 4 + 48 = 52C.
    inputs = {
        'batch_load_kg': 100.0,
        'cp_core_kJ_kgK': 1.1,
        'A_bed_m2': 2.0,
        'h_conv_W_m2K': 0.0,
        'HLF_kW_K': 0.0,
        'T_inlet': 60.0,
        'air_cfm': 0.0, # NO AIRFLOW
        'R_h_inlet': 0.1,
        'spray_rate_g_min_gun': 0.0, # NO SPRAY
        'pan_rpm': 10.0
    }
    
    initial_state = np.array([20.0, 0.0, 0.0, 60.0, 0.0, 0.0])
    time_span = (0.0, 600.0) 
    
    res = run_dynamic_simulation(time_span, initial_state, inputs)
    
    # Global energy must be conserved perfectly
    assert np.isclose(res['T_bed'][-1], 52.0, atol=0.1)

def test_extreme_circulation():
    # If RPM is extremely high (e.g. 100 RPM), the bed is perfectly mixed instantly.
    inputs = {
        'batch_load_kg': 100.0,
        'cp_core_kJ_kgK': 1.1,
        'A_bed_m2': 2.0,
        'h_conv_W_m2K': 0.0,
        'HLF_kW_K': 0.0,
        'T_inlet': 60.0,
        'air_cfm': 0.0,
        'R_h_inlet': 0.1,
        'spray_rate_g_min_gun': 0.0,
        'pan_rpm': 1000.0 # Extreme RPM
    }
    
    initial_state = np.array([20.0, 0.0, 0.0, 60.0, 0.0, 0.0])
    res = run_dynamic_simulation((0.0, 60.0), initial_state, inputs)
    
    # Even after 1 minute, T_bed must remain at the exact conserved average of 52.0
    assert np.isclose(res['T_bed'][-1], 52.0, atol=0.1)

def test_evaporative_cooling():
    # Massive spray rate with low inlet temp/airflow should result in significant cooling.
    inputs = {
        'batch_load_kg': 100.0,
        'cp_core_kJ_kgK': 1.1,
        'A_bed_m2': 2.0,
        'h_conv_W_m2K': 50.0,
        'HLF_kW_K': 0.1,
        'T_inlet': 30.0, # Low inlet heat
        'air_cfm': 500.0,
        'R_h_inlet': 0.1,
        'spray_rate_g_min_gun': 200.0, # Massive spray (800 g/min total)
        'no_of_guns': 4,
        'solids_fraction': 0.15,
        'pan_rpm': 10.0
    }
    
    # Start bed at 50C
    initial_state = np.array([50.0, 0.0, 0.0, 50.0, 0.0, 0.0])
    res = run_dynamic_simulation((0.0, 300.0), initial_state, inputs)
    
    # Bed temp should plummet due to massive evaporation taking latent heat
    assert res['T_bed'][-1] < 35.0
    # And moisture should heavily accumulate since evaporation capacity is low
    assert res['M_water'][-1] > 0.5
