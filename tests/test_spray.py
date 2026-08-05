import pytest
import math
from coating_model.spray import calculate_droplet_size, classify_spray_regime, calculate_spray_flux

def test_droplet_size():
    # Higher pressure -> smaller droplet
    d_low_p = calculate_droplet_size(1.0, 50.0)
    d_high_p = calculate_droplet_size(4.0, 50.0)
    assert d_high_p < d_low_p

def test_spray_flux():
    flux = calculate_spray_flux(spray_rate_kg_s=0.1, n_guns=4, l_gun_bed_m=0.2, theta_deg=60.0)
    assert flux > 0.0

def test_spray_regime():
    assert classify_spray_regime(0.1, 1.0) == "SPRAY_DRYING"
    assert classify_spray_regime(1.0, 1.0) == "IDEAL"
    assert classify_spray_regime(3.0, 1.0) == "OVERWETTING"
