import pytest
import numpy as np
from coating_model.cqa import (
    predict_weight_gain, predict_film_thickness_distribution,
    calculate_thermal_exposure_integral
)

def test_weight_gain():
    wg = predict_weight_gain(10.0, 100.0)
    assert np.isclose(wg, 0.1)

def test_film_thickness():
    m_coat_i = np.array([0.0001, 0.0002]) # 0.1g, 0.2g
    a_tablet = 0.0001 # m2
    rho = 1000.0 # kg/m3
    
    thickness_um = predict_film_thickness_distribution(m_coat_i, a_tablet, rho)
    
    assert len(thickness_um) == 2
    assert thickness_um[0] == pytest.approx(1000.0) # 0.0001 / (1000 * 0.0001) = 0.001m = 1000um
    assert thickness_um[1] == pytest.approx(2000.0)

def test_thermal_exposure():
    t_bed = np.array([30.0, 40.0, 50.0, 60.0])
    time = np.array([0.0, 10.0, 20.0, 30.0])
    
    # max(0, t - 40) => [0, 0, 10, 20]
    # trapz: dt = 10. 
    # intervals: (0+0)/2*10 = 0
    # (0+10)/2*10 = 50
    # (10+20)/2*10 = 150
    # total = 200
    
    ht = calculate_thermal_exposure_integral(t_bed, time, t_ref_C=40.0)
    assert np.isclose(ht, 200.0)
