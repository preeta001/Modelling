import streamlit as st
from coating_model.steady_state import calculate_steady_state

st.title("Steady State Thermodynamics")
st.markdown("Matches the legacy multi-stage EE model behavior.")

col1, col2 = st.columns(2)
with col1:
    T_inlet = st.number_input("Inlet Temp (°C)", 20.0, 100.0, 60.0)
    air_cfm = st.number_input("Airflow (CFM)", 100.0, 5000.0, 1200.0)
    RH_inlet = st.number_input("Inlet RH (fraction)", 0.0, 1.0, 0.1)
with col2:
    spray = st.number_input("Spray Rate (g/min/gun)", 0.0, 200.0, 30.0)
    guns = st.number_input("Number of guns", 1, 10, 4)
    solids = st.number_input("Solids fraction", 0.01, 0.5, 0.15)
    
if st.button("Calculate Steady State"):
    res = calculate_steady_state(
        T_inlet=T_inlet,
        air_cfm=air_cfm,
        R_h_inlet=RH_inlet,
        spray_rate_g_min_gun=spray,
        no_of_guns=guns,
        solids_fraction=solids,
        alpha_hlf=-100.0 # Match legacy default
    )
    
    st.subheader("Results")
    c1, c2, c3 = st.columns(3)
    c1.metric("Exhaust Temp", f"{res['T_exhaust']:.1f} °C")
    c2.metric("Exhaust RH", f"{res['RH_exhaust']*100:.1f} %")
    c3.metric("EE Factor", f"{res['ee_factor']:.2f}")
