import numpy as np
from typing import Dict, Any, Callable

def run_monte_carlo_propagation(
    n_samples: int,
    base_inputs: Dict[str, Any],
    input_distributions: Dict[str, tuple], # e.g. {'air_cfm': ('normal', 1200, 50)}
    sim_func: Callable
) -> Dict[str, np.ndarray]:
    """
    Run N simulations with sampled inputs to propagate uncertainty.
    Returns array of final states for plotting distributions.
    """
    results = {
        'T_bed_final': np.zeros(n_samples),
        'M_water_final': np.zeros(n_samples),
        'WI_peak': np.zeros(n_samples)
    }
    
    for i in range(n_samples):
        # Create a sample dict
        sampled_inputs = base_inputs.copy()
        
        for k, dist in input_distributions.items():
            dist_type = dist[0]
            if dist_type == 'normal':
                sampled_inputs[k] = np.random.normal(dist[1], dist[2])
            elif dist_type == 'uniform':
                sampled_inputs[k] = np.random.uniform(dist[1], dist[2])
                
        # Run sim (mocking WI for now since it's just a fast loop)
        res = sim_func(sampled_inputs)
        
        results['T_bed_final'][i] = res['T_bed'][-1] if isinstance(res.get('T_bed'), np.ndarray) else res.get('T_exhaust', 0)
        # Mock other properties for testing architecture
        results['M_water_final'][i] = res.get('M_water_final', 0.0)
        results['WI_peak'][i] = res.get('WI_peak', 0.0)
        
    return results

def calculate_failure_probability(samples: np.ndarray, threshold: float, condition: str = '>') -> float:
    """Calculate P(fail) from MC samples."""
    if len(samples) == 0: return 0.0
    if condition == '>':
        fails = np.sum(samples > threshold)
    else:
        fails = np.sum(samples < threshold)
    return float(fails / len(samples))
