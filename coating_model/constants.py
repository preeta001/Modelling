# Physical Constants

# Air
Cp_air = 1.005  # kJ/kg-K, specific heat capacity of dry air
R_d = 287.058   # J/(kg-K), gas constant for dry air

# Water Vapor
Cp_v_water = 1.86 # kJ/kg-K, specific heat capacity of water vapor
R_v_water = 461.495 # J/(kg-K), gas constant for water vapor
h_fg_0_water = 2501.0 # kJ/kg, latent heat of vaporization of water at 0 C
h_fg_i_water = 104.7598 # kJ/kg, generic enthalpy of water entering at 25 C (from legacy)

# General
g = 9.81 # m/s^2, gravitational acceleration
T_amb_default = 25.0 # Ambient temperature in room (C)

# Conversion Factors
CFM_TO_M3_S = 0.00047194745
M3_S_TO_CFM = 1.0 / CFM_TO_M3_S
G_MIN_TO_KG_S = 1.0 / (1000.0 * 60.0)
KG_S_TO_G_MIN = 1000.0 * 60.0
TORR_TO_KPA = 0.133322
KPA_TO_TORR = 1.0 / TORR_TO_KPA

def celsius_to_kelvin(c):
    return c + 273.15

def kelvin_to_celsius(k):
    return k - 273.15
