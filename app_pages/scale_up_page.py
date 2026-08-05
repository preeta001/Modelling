import streamlit as st
from coating_model.scale_up import scale_rpm_linear, scale_rpm_froude

st.title("Equipment Scale-Up Engine")

col1, col2 = st.columns(2)
with col1:
    st.subheader("Source Equipment")
    d_source = st.number_input("Diameter (m)", 0.5, 2.0, 0.6)
    rpm_source = st.number_input("Validated RPM", 1.0, 30.0, 15.0)

with col2:
    st.subheader("Target Equipment")
    d_target = st.number_input("Target Diameter (m)", 0.5, 2.0, 1.2)
    
n_lin = scale_rpm_linear(rpm_source, d_source, d_target)
n_fro = scale_rpm_froude(rpm_source, d_source, d_target)

st.divider()
st.subheader("Recommended Target RPM")

c1, c2 = st.columns(2)
c1.metric("Constant Linear Speed (Dose Conserved)", f"{n_lin:.1f} RPM")
c2.metric("Constant Froude (Uniformity Conserved)", f"{n_fro:.1f} RPM")

st.info("Notice the divergence. For active/functional coatings where uniformity is critical, Froude scaling is preferred. For cosmetic coatings, Linear scaling may be sufficient.")
