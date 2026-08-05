import streamlit as st
import numpy as np
import pandas as pd
from scipy.optimize import differential_evolution
from psychrolib import GetTWetBulbFromRelHum, SetUnitSystem, SI
SetUnitSystem(SI)

from coating_model.solvent_properties import get_solvent

st.title("⚙️ Model Validation & Calibration")
st.markdown("Calibrate the mechanistic model against historical data to find the absolute Heat Loss Factor ($UA$) and Environment Factor (EE).")

# ---------------------- Constants & Helpers ----------------------
Cp_air = 1.005  # kJ/kg-K
R_d = 287.058   # J/(kg-K)
T_amb = 25.0    # Ambient temp
EPS = 1e-12

def calculate_stage_physics(inputs, solvent, UA_kW_K):
    """Calculates steady state physics and returns exhaust temp and other CTQs"""
    P_total = inputs['P_total']
    
    # Inlet psychrometrics
    p_g_i = solvent.saturation_pressure(inputs['T_inlet'])
    p_v_i = p_g_i * max(0.0, min(1.0, inputs['R_h']))
    w_inlet = (R_d / solvent.R_v) * p_v_i / max(1e-9, (P_total - p_v_i))
    rho_air_i = ((P_total - p_v_i) * 1000 / (R_d * (inputs['T_inlet'] + 273.15))) * ((1 + w_inlet) / (1 + w_inlet * (solvent.R_v / R_d)))
    
    # Mass flows
    m_a = inputs['air_cfm'] * 0.00047194745 * rho_air_i  # kg/s dry air
    spray_rate_kg_s = (inputs['spray_rate_g_min_gun'] * inputs['no_of_guns']) / 60000.0
    m_w = spray_rate_kg_s * (1.0 - inputs['solids_fraction']) # kg/s water/solvent
    w_exhaust = (m_w / (m_a / (1 + w_inlet))) + w_inlet
    
    # Energy Balance to find T_exhaust solving:
    # m_da*(cp_a*T_in + w_in*hv_in) = m_da*(cp_a*T_ex + w_ex*hv_ex) + m_evap*h_fg + UA*((T_in+T_ex)/2 - T_amb)
    h_fg_ref = solvent.latent_heat(T_amb) # approx
    hv_in = solvent.latent_heat(inputs['T_inlet'])
    
    # Rearranging for T_ex:
    # hv_ex(T_ex) = enthalpy_A * T_ex + enthalpy_B
    # This leads to a linear equation for T_ex.
    # Numerator = m_da*(cp_a*T_in + w_in*hv_in) - m_evap*h_fg_ref - m_da*w_ex*enthalpy_B - UA*(T_in/2 - T_amb)
    # Denominator = m_da*cp_a + m_da*w_ex*enthalpy_A + UA/2
    m_da = m_a / (1 + w_inlet)
    
    Numerator = (m_da * (Cp_air * inputs['T_inlet'] + w_inlet * hv_in) 
                 - m_w * h_fg_ref 
                 - m_da * w_exhaust * solvent.enthalpy_B 
                 - UA_kW_K * (inputs['T_inlet']/2.0 - T_amb))
                 
    Denominator = (m_da * Cp_air 
                   + m_da * w_exhaust * solvent.enthalpy_A 
                   + UA_kW_K / 2.0)
                   
    T_exhaust = Numerator / max(1e-9, Denominator)
    
    # Calculate EE
    p_g_o = solvent.saturation_pressure(T_exhaust)
    p_v_o = w_exhaust * P_total / ((R_d / solvent.R_v) + w_exhaust)
    R_h_exhaust = p_v_o / max(1e-9, p_g_o)
    rho_air_o = ((P_total - p_v_o) * 1000 / (R_d * (T_exhaust + 273.15))) * ((1 + w_exhaust) / (1 + w_exhaust * (solvent.R_v / R_d)))
    
    # Wet bulb
    if solvent.name == 'water':
        T_wbt_i = GetTWetBulbFromRelHum(inputs['T_inlet'], inputs['R_h'], P_total * 1000)
    else:
        # Simplification for custom solvent - using dew point approx or iterative solver
        # For UI purposes, we'll just approximate it or assume user provides it, 
        # but here we'll use a simple approximation if psychrolib fails
        T_wbt_i = inputs['T_inlet'] - 10.0 # Placeholder for non-water WBT
        
    p_w_i = solvent.saturation_pressure(T_wbt_i)
    hv_o = solvent.latent_heat(T_exhaust)
    
    Num = (p_w_i * 1000 / (solvent.R_v * (T_wbt_i + 273.15))) - (p_v_i * 1000 / (solvent.R_v * (inputs['T_inlet'] + 273.15)))
    Dnm1 = (rho_air_i + rho_air_o) / 2.0
    Dnm2 = Cp_air * 1000
    Dnm3 = inputs['T_inlet'] - T_exhaust
    Dnm4 = (hv_o - h_fg_ref) * 1000
    EE_factor = Num / max(1e-9, (Dnm1 * Dnm2 * Dnm3 / max(1e-9, Dnm4)))
    
    spraying_time = (inputs['m_s'] / (inputs['spray_rate_g_min_gun'] * inputs['no_of_guns'])) * (1000 / 60)
    
    return {
        'T_exhaust': T_exhaust,
        'R_h_exhaust': R_h_exhaust,
        'EE_factor': EE_factor,
        'spraying_time': spraying_time,
        'm_da': m_da
    }

# ---------------------- UI ----------------------

tabs = st.tabs(["Manual Stage Builder", "CSV Upload"])

with tabs[0]:
    st.subheader("Manual Data Entry (Stage Builder)")
    
    with st.form("common_inputs_form"):
        col1, col2 = st.columns(2)
        with col1:
            P_total = st.number_input('Pressure (kPa)', value=101.325)
            no_of_guns = st.number_input('Number of Guns', value=5, min_value=1)
            m_s = st.number_input('Batch Mass to Coat (kg)', value=100.0, min_value=0.1)
        with col2:
            solids_fraction = st.number_input('Solids Fraction', value=0.15, min_value=0.01, max_value=1.0)
            no_of_stage = st.number_input('Number of Stages', value=1, min_value=1, max_value=10)
        
        st.form_submit_button("Update Stages")

    st.markdown("### Stage Inputs")
    solvent = get_solvent(st.session_state.get('global_solvent', 'water'))
    
    stage_inputs = []
    with st.form("stages_calibration_form"):
        for i in range(int(no_of_stage)):
            st.markdown(f"**Stage {i+1}**")
            c1, c2, c3, c4, c5 = st.columns(5)
            with c1: sr = st.number_input(f'Spray Rate (g/min/gun)', key=f'sr_{i}', value=50.0)
            with c2: tin = st.number_input(f'T_inlet (°C)', key=f'tin_{i}', value=60.0)
            with c3: cfm = st.number_input(f'Airflow (CFM)', key=f'cfm_{i}', value=1000.0)
            with c4: rh = st.number_input(f'Inlet RH (0-1)', key=f'rh_{i}', value=0.05)
            with c5: texp = st.number_input(f'Measured T_exhaust (°C)', key=f'texp_{i}', value=45.0)
            
            stage_inputs.append({
                'P_total': P_total, 'no_of_guns': no_of_guns, 'solids_fraction': solids_fraction,
                'm_s': m_s, 'spray_rate_g_min_gun': sr, 'T_inlet': tin, 'air_cfm': cfm, 'R_h': rh,
                'T_exhaust_expected': texp
            })
            
        calibrate_btn = st.form_submit_button("Calibrate Model (Find UA & EE)", type="primary")

    if calibrate_btn:
        with st.spinner("Running Differential Evolution to find UA..."):
            results = []
            ua_values = []
            
            for i, inputs in enumerate(stage_inputs):
                # Optimization objective
                def objective(UA_array):
                    UA = float(UA_array[0])
                    res = calculate_stage_physics(inputs, solvent, UA)
                    return abs(res['T_exhaust'] - inputs['T_exhaust_expected'])
                
                # Fit UA (bounds: 0.0 to 5.0 kW/K)
                sol = differential_evolution(objective, bounds=[(0.0, 5.0)], tol=1e-5, maxiter=500)
                best_UA = float(sol.x[0])
                ua_values.append(best_UA)
                
                # Get full results with best UA
                final_res = calculate_stage_physics(inputs, solvent, best_UA)
                
                # Equivalent alpha calculation to show backward compatibility (alpha = UA / m_da)
                equiv_alpha = best_UA / final_res['m_da']
                
                results.append({
                    "Stage": i + 1,
                    "Target T_exh": inputs['T_exhaust_expected'],
                    "Pred T_exh": final_res['T_exhaust'],
                    "Fitted UA (kW/K)": best_UA,
                    "Equiv. Alpha": equiv_alpha,
                    "EE Factor": final_res['EE_factor'],
                    "Exhaust RH": final_res['R_h_exhaust'],
                    "Spray Time (h)": final_res['spraying_time'] / 60.0
                })
            
            # Save calibration globals
            st.session_state.calibrated_UA = float(np.mean(ua_values))
            st.session_state.stage_inputs_list = stage_inputs
            st.session_state.results_df = pd.DataFrame(results)
            
            st.success(f"Calibration successful! Average UA = {st.session_state.calibrated_UA:.4f} kW/K")
            st.dataframe(st.session_state.results_df.round(4), use_container_width=True)

with tabs[1]:
    st.info("CSV Upload for batch calibration goes here. Ensure columns match the CPP list.")
    # Implementation of CSV reader...
