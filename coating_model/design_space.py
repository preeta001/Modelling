import numpy as np

def generate_design_space_map(
    param1_range: np.ndarray,
    param2_range: np.ndarray,
    param1_name: str,
    param2_name: str,
    base_inputs: dict,
    sim_func: callable,
    eval_func: callable
) -> dict:
    """
    Generate a 2D grid mapping failure probability or a specific CQA.
    """
    nx = len(param1_range)
    ny = len(param2_range)
    
    grid_z = np.zeros((ny, nx))
    
    for i, p2 in enumerate(param2_range):
        for j, p1 in enumerate(param1_range):
            inputs = base_inputs.copy()
            inputs[param1_name] = p1
            inputs[param2_name] = p2
            
            res = sim_func(inputs)
            val = eval_func(res)
            grid_z[i, j] = val
            
    return {
        'x': param1_range,
        'y': param2_range,
        'z': grid_z,
        'x_name': param1_name,
        'y_name': param2_name
    }
