import math

def calculate_droplet_size(p_atom_bar: float, spray_rate_g_min: float, nozzle_d_mm: float = 1.2) -> float:
    """
    Estimate Sauter mean droplet diameter d32 (um).
    Using a simplified empirical correlation typical for two-fluid nozzles.
    d32 = a * (Ms/Ma)^b * P_atom^c
    """
    # Simple heuristic if true parameters are unknown
    # Higher pressure -> smaller droplets
    # Higher spray rate -> larger droplets
    d32_base = 40.0 # um at 2 bar, 50 g/min
    p_factor = (2.0 / max(0.5, p_atom_bar)) ** 0.8
    m_factor = (max(1.0, spray_rate_g_min) / 50.0) ** 0.3
    
    return d32_base * p_factor * m_factor

def classify_spray_regime(t_dry: float, t_flight: float) -> str:
    """
    Classify based on Drying-vs-Flight dimensionless number.
    Pi = t_dry / t_flight
    """
    pi_flight = t_dry / max(1e-9, t_flight)
    if pi_flight < 0.5:
        return "SPRAY_DRYING"
    elif pi_flight > 2.0:
        return "OVERWETTING"
    return "IDEAL"

def calculate_spray_flux(spray_rate_kg_s: float, n_guns: int, l_gun_bed_m: float, theta_deg: float = 60.0) -> float:
    """
    Calculate spray flux J (kg / m^2 s)
    """
    theta_rad = math.radians(theta_deg)
    # Area of one spray pattern on the bed (assuming rectangular/elliptical overlap)
    # W ~ 2 * L * tan(theta/2)
    w_pattern = 2.0 * l_gun_bed_m * math.tan(theta_rad / 2.0)
    
    # Assume length of pattern is ~ w_pattern / 2 (elliptical flat spray)
    # A_one_gun = w_pattern * w_pattern / 2
    a_spray_zone = n_guns * w_pattern * (w_pattern * 0.5)
    
    return spray_rate_kg_s / max(1e-6, a_spray_zone)
