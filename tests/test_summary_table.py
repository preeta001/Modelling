import pytest
from coating_model.summary_table import generate_stage_summary

def test_generate_stage_summary():
    sim_results = {
        'T_exhaust': [40.0, 42.0, 45.0],
        'RH_exhaust': [0.1, 0.5, 0.6],
        'WI': [0.0, 0.8, 0.9],
        'EWI': 0.0,
        'weight_gain_pct': [0.0, 1.5, 3.0]
    }
    
    inputs = {
        'T_inlet': 60.0,
        'air_cfm': 1200.0,
        'spray_rate_g_min_gun': 50.0
    }
    
    limits = {
        'T_exh_min': 40, 'T_exh_max': 50,
        'RH_exh_min': 0.1, 'RH_exh_max': 0.7,
        'WI_min': 0.1, 'WI_max': 0.95
    }
    
    df = generate_stage_summary(sim_results, inputs, limits)
    
    assert len(df) >= 4
    assert list(df.columns) == ["Stage/Category", "Parameter", "Current Input", "Unit", "Predicted Output", "Status"]
    
    # Check that T_exhaust picked the last value
    t_exh_row = df[df['Parameter'] == 'T_exhaust'].iloc[0]
    assert t_exh_row['Predicted Output'] == "45.0"
    assert t_exh_row['Status'] == "✅"
