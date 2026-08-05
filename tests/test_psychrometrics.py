import pytest
import math
from coating_model.solvent_properties import get_solvent
from coating_model.psychrometrics import (
    humidity_ratio, vapor_pressure_from_humidity_ratio, vapor_pressure_from_rh,
    relative_humidity, air_density, get_wet_bulb_temperature
)

def test_water_properties():
    water = get_solvent("water")
    p_sat = water.saturation_pressure(100.0)
    assert math.isclose(p_sat, 101.325, rel_tol=0.05) # Water boils at 100C at 1 atm

def test_humidity_ratio():
    water = get_solvent("water")
    w = humidity_ratio(101.325, 2.339, water) # ~20C saturated
    assert w > 0.01

def test_wet_bulb_bounds():
    water = get_solvent("water")
    T_db = 25.0
    RH = 0.5
    T_wb = get_wet_bulb_temperature(T_db, RH, 101.325, water)
    assert T_wb <= T_db
    
    # 100% RH -> T_wb == T_db
    T_wb_100 = get_wet_bulb_temperature(T_db, 1.0, 101.325, water)
    assert math.isclose(T_wb_100, T_db, abs_tol=0.1)
