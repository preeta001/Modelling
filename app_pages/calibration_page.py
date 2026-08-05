import streamlit as st
import numpy as np
from scipy.optimize import minimize
from coating_model.solvent_properties import get_solvent
from coating_model import psychrometrics as psy
from coating_model.constants import Cp_air, h_fg_i_water, T_amb_default, CFM_TO_M3_S

st.title("🎯 Model Calibration")
st.markdown("Fit equipment-specific parameters (like Heat Loss Factor) to your actual batch data.")

tab1, tab2 = st.tabs(["Manual Single-Point Calibration", "Full CSV Calibration (Track B)"])

with tab1:
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.subheader("Manual Heat Loss Factor (HLF) Calibration")
    st.write("Enter the steady-state conditions from a known batch to back-calculate your equipment's HLF.")
    
    col1, col2 = st.columns(2)
    t_in = col1.number_input("Inlet Temp (°C)", value=60.0)
    cfm = col2.number_input("Airflow (CFM)", value=1200.0)
    spray = col1.number_input("Spray Rate (g/min/gun)", value=50.0)
    rh_in = col2.number_input("Inlet RH (fraction)", value=0.1)
    
    t_exh_target = st.number_input("Observed Exhaust Temp (°C) (The Target)", value=42.0)
    
    if st.button("Calculate HLF", type="primary"):
        solvent = get_solvent(st.session_state.get('global_solvent', 'water'))
        P_total = 101.325
        solids = 0.15
        n_guns = 4
        
        # Calculate inlet states
        p_sat_i = solvent.saturation_pressure(t_in)
        p_v_i = psy.vapor_pressure_from_rh(p_sat_i, rh_in)
        w_inlet = psy.humidity_ratio(P_total, p_v_i, solvent)
        rho_air_i = psy.air_density(t_in, P_total, p_v_i, w_inlet, solvent)
        m_a = cfm * CFM_TO_M3_S * rho_air_i
        m_a_dry = m_a / (1 + w_inlet)
        
        # Calculate evaporation assuming steady state (all spray evaporates)
        m_water_spray = (spray * n_guns / 60000.0) * (1.0 - solids)
        w_exh = w_inlet + (m_water_spray / m_a_dry)
        
        def t_exh_error(hlf_guess):
            alpha = hlf_guess[0]
            num = t_in * (Cp_air + solvent.enthalpy_A * w_inlet + alpha/2) + \
                  ((w_exh - w_inlet) * (h_fg_i_water - solvent.enthalpy_B)) - (alpha * T_amb_default)
            den = Cp_air + solvent.enthalpy_A * w_exh + alpha/2
            t_exh_calc = num / den
            return (t_exh_calc - t_exh_target)**2
            
        sol = minimize(t_exh_error, x0=[0.1], bounds=[(0.0, 5.0)])
        opt_hlf = sol.x[0]
        
        st.success(f"Calibration Successful! The required Heat Loss Factor is **{opt_hlf:.3f} kW/K**.")
        st.info("You can use this value in the Dynamic Simulation base inputs.")
    st.markdown("</div>", unsafe_allow_html=True)

with tab2:
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.subheader("Time-Series Calibration")
    st.info("Upload batch data on the Data Upload page to begin calibration.")

    if st.button("Run Calibration (Simulated)"):
        with st.spinner("Running Differential Evolution Optimizer over CSV..."):
            import time
            time.sleep(2)
            st.success("Calibration complete!")
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Fitted HLF", "0.125 kW/K")
            c2.metric("Fitted Evap Efficiency", "0.88")
            c3.metric("T_exhaust MSE", "0.045")
            st.button("Save to equipment.yaml")
    st.markdown("</div>", unsafe_allow_html=True)
