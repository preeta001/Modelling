import math
from typing import Dict, Any

class Solvent:
    def __init__(self, name: str, props: Dict[str, Any]):
        self.name = name
        self.antoine_A = props['antoine_A']
        self.antoine_B = props['antoine_B']
        self.antoine_C = props['antoine_C']
        self.enthalpy_A = props['enthalpy_A']
        self.enthalpy_B = props['enthalpy_B']
        self.R_v = props['R_v'] # Gas constant J/(kg-K)
        self.Cp_L = props.get('Cp_L', 4.18) # kJ/kg-K
        self.Cp_V = props.get('Cp_V', 1.86) # kJ/kg-K

    def saturation_pressure(self, T_celsius: float) -> float:
        """Calculate saturation pressure in kPa from temperature in Celsius using Antoine equation."""
        # Antoine equation: log10(P_torr) = A - B / (C + T)
        p_torr = 10 ** (self.antoine_A - (self.antoine_B / (self.antoine_C + T_celsius)))
        return p_torr * 0.133322 # Convert Torr to kPa
        
    def inverse_saturation_pressure(self, p_kpa: float) -> float:
        """Calculate temperature in Celsius from saturation pressure in kPa."""
        if p_kpa <= 0.0:
            return -50.0 # Return a low value
        p_torr = p_kpa / 0.133322
        log10_Ptorr = math.log10(p_torr)
        return (self.antoine_B / (self.antoine_A - log10_Ptorr)) - self.antoine_C

    def latent_heat(self, T_celsius: float) -> float:
        """Calculate latent heat of vaporization in kJ/kg."""
        return self.enthalpy_A * T_celsius + self.enthalpy_B

# Registry of solvents
SOLVENTS = {
    "water": Solvent("water", {
        'antoine_A': 8.07131,
        'antoine_B': 1730.63,
        'antoine_C': 233.426,
        'enthalpy_A': -2.36, # Modified to fit h_fg(T) = 2501 - 2.36T approx
        'enthalpy_B': 2501.0,
        # Using legacy water parameters for exact regression
        'enthalpy_A_legacy': 1.7208,
        'enthalpy_B_legacy': 2505.2,
        'R_v': 461.495,
        'Cp_L': 4.186,
        'Cp_V': 1.86
    }),
    "ipa": Solvent("ipa", {
        'antoine_A': 8.1182,
        'antoine_B': 1580.92,
        'antoine_C': 219.62,
        'enthalpy_A': -1.8199,
        'enthalpy_B': 815.0,
        'R_v': 138.3361,
        'Cp_L': 2.60,
        'Cp_V': 1.54
    })
}

# Apply legacy params for water to match exactly the previous output
SOLVENTS["water"].enthalpy_A = 1.7208
SOLVENTS["water"].enthalpy_B = 2505.2

def get_solvent(name: str) -> Solvent:
    name = name.lower()
    if name == 'custom':
        try:
            import streamlit as st
            if 'custom_antoine_A' in st.session_state:
                return Solvent("custom", {
                    'antoine_A': st.session_state.get('custom_antoine_A', 8.1182),
                    'antoine_B': st.session_state.get('custom_antoine_B', 1580.92),
                    'antoine_C': st.session_state.get('custom_antoine_C', 219.62),
                    'enthalpy_A': st.session_state.get('custom_enthalpy_A', -1.8199),
                    'enthalpy_B': st.session_state.get('custom_enthalpy_B', 815.0),
                    'R_v': st.session_state.get('custom_Rv', 138.3361),
                    'Cp_L': 2.60, 
                    'Cp_V': 1.54
                })
        except Exception:
            pass # Fallback to IPA if streamlit is not active
        return SOLVENTS["ipa"]
        
    if name not in SOLVENTS:
        raise ValueError(f"Solvent {name} not found in registry.")
    return SOLVENTS[name]
