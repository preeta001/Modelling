import pytest
import numpy as np
from coating_model.exposure import simulate_monte_carlo_exposure

def test_monte_carlo_exposure():
    res = simulate_monte_carlo_exposure(
        n_tablets=500,
        t_coat_s=3600.0,
        mean_circulation_time_s=10.0,
        mean_residence_time_s=0.5,
        spray_flux_kg_m2_s=0.01,
        a_tablet_m2=0.0001,
        solids_fraction=0.15,
        eta_dep=0.95
    )
    
    assert res['cv_m'] > 0.0
    assert res['cv_m'] < 1.0 # Should be somewhat uniform
    assert len(res['m_coat_i']) == 500
    assert np.all(res['m_coat_i'] >= 0.0)
