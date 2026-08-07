import streamlit as st
import plotly.graph_objects as go
import numpy as np
from coating_model.spray import calculate_droplet_size, classify_spray_regime, calculate_spray_flux
from coating_model.exposure import simulate_monte_carlo_exposure

st.title("💧 Spray & Uniformity Module")
st.markdown("Translates macroscopic spray rates into microscopic droplet dynamics and Monte Carlo tablet-level coating distributions (Track A, Layers 3 & 4).")

st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
col1, col2 = st.columns(2)

with col1:
    st.subheader("Spray Configuration")
    p_atom = st.number_input("Atomisation Pressure (bar)", value=3.0, step=0.1)
    spray_rate = st.number_input("Spray Rate per Gun (g/min)", value=50.0, step=1.0)
    n_guns = st.number_input("Number of Guns", 1, 10, 4)
    l_gun_bed = st.number_input("Gun-to-Bed Distance (m)", 0.1, 0.5, 0.2)
    
with col2:
    st.subheader("Droplet Dynamics (Layer 3)")
    d32 = calculate_droplet_size(p_atom, spray_rate)
    st.metric("Sauter Mean Diameter (d32)", f"{d32:.1f} µm")
    
    # Mock drying time calculation for the regime
    t_flight = l_gun_bed / 10.0 # ~10 m/s droplet velocity
    t_dry = t_flight * (d32 / 40.0) # Dummy scaling for demo
    regime = classify_spray_regime(t_dry, t_flight)
    
    color = "normal"
    if regime == "SPRAY_DRYING" or regime == "OVERWETTING":
        color = "inverse"
    st.metric("Spray Regime (Pi_flight)", regime, delta_color=color)
    
    flux = calculate_spray_flux(spray_rate / 60000.0, n_guns, l_gun_bed)
    st.metric("Spray Flux (J_spray)", f"{flux*1000:.3f} g/(m²·s)")

with st.expander("📖 What do these metrics mean? (PDF Ch. 7)"):
    st.write(r"""
    **Physical Interpretation:**
    - **d32**: The average droplet size. High atomisation pressure decreases droplet size; high spray rate increases it.
    - **Spray Regime**: Evaluates the Drying-vs-Flight dimensionless number ($\Pi_{flight}$). If droplets dry before hitting the bed ($\Pi < 1$), it causes spray drying and poor adhesion. If they arrive too wet ($\Pi \gg 1$), it causes overwetting.
    - **Spray Flux ($J_{spray}$)**: The mass of spray arriving per square meter of spray zone per second. Drives the instantaneous wetting rate of individual tablets.
    """)
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.subheader("Monte Carlo Tablet Exposure (Layer 4)")
st.write("Simulates the random paths of 5,000 tablets moving in and out of the spray zone.")

if st.button("Run Monte Carlo Uniformity Simulation", type="primary"):
    with st.spinner("Tracking 5,000 tablets..."):
        t_coat = 3600.0
        res = simulate_monte_carlo_exposure(
            n_tablets=5000,
            t_coat_s=t_coat,
            mean_circulation_time_s=15.0,
            mean_residence_time_s=0.5,
            spray_flux_kg_m2_s=flux,
            a_tablet_m2=0.0001,
            solids_fraction=0.15,
            eta_dep=0.95
        )
        
        c1, c2 = st.columns(2)
        c1.metric("Final Coating CV", f"{res['cv_m']*100:.2f} %")
        c2.metric("Mean Coating per Tablet", f"{res['mean_m']*1000:.2f} mg")
        
        # Coating Mass Distribution
        fig = go.Figure(data=[go.Histogram(x=res['m_coat_i']*1000, nbinsx=50, marker_color='#ff7f0e')])
        fig.update_layout(template='plotly_dark', title="Final Coating Mass Distribution", xaxis_title="Coating Mass (mg)", yaxis_title="Count", margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig, use_container_width=True)
        
        # CV vs Time prediction (CV ~ 1/sqrt(t))
        t_eval = np.linspace(60, t_coat, 50)
        cv_t = res['cv_m'] * np.sqrt(t_coat / t_eval)
        
        fig2 = go.Figure(data=[go.Scatter(x=t_eval/60, y=cv_t*100, mode='lines', line=dict(color='#1f77b4', width=3))])
        fig2.update_layout(template='plotly_dark', title="Coating Uniformity (CV) vs. Time", xaxis_title="Time (min)", yaxis_title="CV (%)", margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig2, use_container_width=True)
        
        with st.expander("📖 What does this graph show? (PDF Eq 8.9)"):
            st.write(r"""
            **Physical Interpretation:**
            The $CV$ of coating mass decays proportional to $1/\sqrt{t_{coat}}$. Doubling the coating time only reduces the CV by ~29%. To achieve better uniformity faster, you must increase the spray zone width (more guns) or decrease the circulation time (higher RPM).
            """)
st.markdown("</div>", unsafe_allow_html=True)
