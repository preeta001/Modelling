import numpy as np

def simulate_monte_carlo_exposure(
    n_tablets: int,
    t_coat_s: float,
    mean_circulation_time_s: float,
    mean_residence_time_s: float,
    spray_flux_kg_m2_s: float,
    a_tablet_m2: float,
    solids_fraction: float,
    eta_dep: float
) -> dict:
    """
    Simulate individual tablet coating mass to get CV_m.
    PDF Chapter 8.
    """
    # Initialize arrays
    m_coat_i = np.zeros(n_tablets)
    visits_i = np.zeros(n_tablets, dtype=int)
    
    # Number of visits for each tablet is roughly t_coat / mean_circulation
    # We can model visits as Poisson or just by summing random times
    # For speed, vectorized approximation:
    expected_visits = t_coat_s / mean_circulation_time_s
    # Visits ~ Poisson(expected)
    visits_i = np.random.poisson(expected_visits, n_tablets)
    
    for i in range(n_tablets):
        if visits_i[i] == 0:
            continue
            
        # Draw residence times for each visit (Log-normal is typical)
        # mean = exp(mu + sigma^2 / 2) -> simplified approx
        sigma = 0.5 # assumed variance of residence time
        mu = np.log(mean_residence_time_s) - 0.5 * sigma**2
        res_times = np.random.lognormal(mu, sigma, visits_i[i])
        
        # Coating added per visit: J * A * eta * x_s * t_res
        m_added = spray_flux_kg_m2_s * a_tablet_m2 * eta_dep * solids_fraction * res_times
        m_coat_i[i] = np.sum(m_added)
        
    mean_m = np.mean(m_coat_i)
    std_m = np.std(m_coat_i)
    cv_m = std_m / max(1e-9, mean_m)
    
    return {
        'm_coat_i': m_coat_i,
        'visits_i': visits_i,
        'mean_m': mean_m,
        'cv_m': cv_m
    }
