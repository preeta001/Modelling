from enum import Enum
import numpy as np

class ProcessPhase(Enum):
    PREHEATING = 1
    SPRAY_RAMP = 2
    STEADY_SPRAY = 3
    PAUSE = 4
    FINAL_DRYING = 5
    COOLING = 6

def detect_phases(time_s: np.ndarray, spray_rate_g_min: np.ndarray, T_exhaust_C: np.ndarray) -> np.ndarray:
    """
    Auto-detect the process phases based on spray rate and temperature profile.
    Returns an array of ProcessPhase enums matching the time array length.
    """
    n = len(time_s)
    phases = np.full(n, ProcessPhase.PREHEATING, dtype=object)
    
    spray_threshold = 1.0 # g/min threshold for "spraying"
    
    first_spray_idx = -1
    last_spray_idx = -1
    
    for i in range(n):
        if spray_rate_g_min[i] > spray_threshold:
            if first_spray_idx == -1:
                first_spray_idx = i
            last_spray_idx = i
            
    for i in range(n):
        if i < first_spray_idx:
            phases[i] = ProcessPhase.PREHEATING
        elif first_spray_idx <= i <= last_spray_idx:
            if spray_rate_g_min[i] < spray_threshold:
                phases[i] = ProcessPhase.PAUSE
            else:
                # Naive ramp detection
                if i > 0 and spray_rate_g_min[i] > spray_rate_g_min[i-1] * 1.1:
                    phases[i] = ProcessPhase.SPRAY_RAMP
                else:
                    phases[i] = ProcessPhase.STEADY_SPRAY
        else:
            # Post spray: Drying then cooling
            # Heuristic: if T_exhaust is dropping rapidly, it's cooling.
            # Simplified for now: just call it FINAL_DRYING
            phases[i] = ProcessPhase.FINAL_DRYING
            
    return phases
