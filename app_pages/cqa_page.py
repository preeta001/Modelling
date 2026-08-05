import streamlit as st
import numpy as np
import plotly.graph_objects as go
from coating_model.cqa import predict_film_thickness_distribution, predict_assay_distribution, calculate_thermal_exposure_integral, calculate_moisture_exposure_integral
from coating_model.exposure import simulate_monte_carlo_exposure

st.title("🎯 Product Quality (CQA) Module")
st.markdown("Translates physical microenvironmental states into final Critical Quality Attributes (Track A, Layer 5).")

if 'latest_res' not in st.session_state or 'latest_inputs' not in st.session_state:
    st.warning("Please run the Dynamic Simulation first to generate data for CQA predictions.")
    st.stop()

res = st.session_state['latest_res']
inputs = st.session_state['latest_inputs']

st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.subheader("Final Coating Quality")

# Assume some defaults if not simulated fully in exposure module
t_coat = res['time_s'][-1] if 'time_s' in res else 3600.0
spray_rate_kg_s = inputs.get('spray_rate_g_min_gun', 50.0) * inputs.get('no_of_guns', 4) / 60000.0
flux = spray_rate_kg_s / 0.5 # rough estimate of area

mc_res = simulate_monte_carlo_exposure(
    n_tablets=2000,
    t_coat_s=t_coat,
    mean_circulation_time_s=15.0,
    mean_residence_time_s=0.5,
    spray_flux_kg_m2_s=flux,
    a_tablet_m2=0.0001,
    solids_fraction=inputs.get('solids_fraction', 0.15),
    eta_dep=inputs.get('eta_dep', 0.95)
)

ft_dist = predict_film_thickness_distribution(mc_res['m_coat_i'], 0.0001, 1300.0)
assay_dist = predict_assay_distribution(mc_res['m_coat_i'], 0.10) # 10% active

c1, c2, c3 = st.columns(3)
c1.metric("Target Weight Gain", f"{res.get('weight_gain_pct', 0):.2f} %")
c2.metric("Mean Film Thickness", f"{np.mean(ft_dist):.1f} µm")
c3.metric("Assay Uniformity (RSD)", f"{mc_res['cv_m']*100:.2f} %")

st.markdown("### Film Thickness Distribution")
fig1 = go.Figure(data=[go.Histogram(x=ft_dist, nbinsx=40, marker_color='#2ca02c')])
fig1.update_layout(template='plotly_dark', xaxis_title="Film Thickness (µm)", yaxis_title="Count", margin=dict(l=0, r=0, t=30, b=0))
st.plotly_chart(fig1, use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)


st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.subheader("Related Substances (Degradation Risk)")

# Get arrays if they exist in full resolution, else mock them
if 'T_bed_pred' in res and 'RH_exhaust_pred' in res:
    t_bed = res['T_bed_pred']
    aw = res['RH_exhaust_pred'] # use exhaust RH as proxy for water activity
    time_s = res['time_s']
else:
    # fallback
    t_bed = np.linspace(30, 45, 100)
    aw = np.linspace(0.1, 0.4, 100)
    time_s = np.linspace(0, t_coat, 100)

h_t = calculate_thermal_exposure_integral(t_bed, time_s, t_ref_C=40.0)
h_m = calculate_moisture_exposure_integral(aw, time_s)

c4, c5 = st.columns(2)
c4.metric("Thermal Exposure Integral (H_T)", f"{h_t:.0f} K·s", help="Cumulative temperature above 40°C")
c5.metric("Moisture Exposure Integral (H_M)", f"{h_m:.0f} s", help="Cumulative water activity")

st.info("Degradation kinetics follow an Arrhenius-moisture coupled exposure integral. Minimizing H_T and H_M minimizes Related Substances (RS).")

with st.expander("📖 What does this mean? (PDF Ch. 9.6)"):
    st.write("""
    **Physical Interpretation:**
    Chemical degradation is a cumulative process, not an instantaneous one. 
    A tablet that spends 20 minutes above 50°C with high moisture sees significantly more degradation than one that hits 50°C for only 2 minutes, even if their peak values are identical.
    """)
st.markdown("</div>", unsafe_allow_html=True)
