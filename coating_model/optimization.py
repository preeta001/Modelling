from scipy.optimize import differential_evolution
import numpy as np

def optimize_cpp(
    base_inputs: dict,
    sim_func: callable,
    bounds: list,
    weights: dict
) -> dict:
    """
    Multi-objective optimization.
    weights = {'p_fail': 1.0, 'time': 0.1, 'energy': 0.1, 'cv': 0.5}
    bounds = [(min, max), ...] for [spray_rate, airflow, rpm, t_inlet]
    """
    def objective(x):
        spray, air, rpm, t_inlet = x
        inputs = base_inputs.copy()
        inputs['spray_rate_g_min_gun'] = spray
        inputs['air_cfm'] = air
        inputs['rpm'] = rpm
        inputs['T_inlet'] = t_inlet
        
        # In a real run, sim_func evaluates ODEs
        # Here we mock it for the test
        res = sim_func(inputs)
        
        # Dummy metrics
        p_fail = res.get('P_fail', 0.0)
        time_cost = 1000.0 / max(1.0, spray) # Faster spray = less time
        energy_cost = air * t_inlet / 1000.0 # Higher air/temp = more energy
        cv_cost = 10.0 / max(1.0, rpm) # Higher RPM = better uniformity
        
        cost = (
            weights.get('p_fail', 1.0) * p_fail +
            weights.get('time', 0.1) * time_cost +
            weights.get('energy', 0.1) * energy_cost +
            weights.get('cv', 0.1) * cv_cost
        )
        return cost
        
    sol = differential_evolution(objective, bounds, maxiter=20, popsize=5, polish=True, disp=False)
    
    return {
        'spray_rate_g_min_gun': sol.x[0],
        'air_cfm': sol.x[1],
        'rpm': sol.x[2],
        'T_inlet': sol.x[3],
        'cost': sol.fun
    }
