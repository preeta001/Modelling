import streamlit as st
import pandas as pd
from coating_model.summary_table import generate_stage_summary

st.title("📋 Execution Summary")
st.markdown("The final Track A recommendation table based on your latest model execution.")

if 'quick_predict_run' not in st.session_state and 'simulation_run' not in st.session_state:
    st.warning("Please run either **Quick Predict** or **Dynamic Simulation** first to generate a summary.")
    st.stop()

# Mocking the transfer of state from other pages for demonstration if needed,
# but ideally they save their `res` and `inputs` to st.session_state
if 'latest_res' in st.session_state and 'latest_inputs' in st.session_state:
    res = st.session_state['latest_res']
    inputs = st.session_state['latest_inputs']
else:
    st.info("Using placeholder data since no recent run state was found. Go to Quick Predict and hit Predict first.")
    from coating_model.dynamic_model import run_dynamic_simulation
    import numpy as np
    inputs = {
        'batch_load_kg': 100.0, 'cp_core_kJ_kgK': 1.1, 'A_bed_m2': 2.0, 'h_conv_W_m2K': 50.0,
        'HLF_kW_K': 0.1, 'no_of_guns': 4, 'solids_fraction': 0.15, 'eta_dep': 0.95,
        'evap_efficiency': 0.8, 'T_inlet': 60.0, 'air_cfm': 1200.0, 'R_h_inlet': 0.1,
        'spray_rate_g_min_gun': 50.0
    }
    res = run_dynamic_simulation((0, 60), np.array([40.0, 0.0, 0.0, 40.0, 0.0, 0.0]), inputs, dt_eval_s=10)

limits = {'T_exh_min': 35, 'T_exh_max': 48, 'RH_exh_min': 0.1, 'RH_exh_max': 0.8, 'WI_min': 0.1, 'WI_max': 0.95}

# Generate the table
df_summary = generate_stage_summary(res, inputs, limits)

st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.subheader("Final Recommendation Table")
st.dataframe(df_summary, use_container_width=True, hide_index=True)

csv = df_summary.to_csv(index=False).encode('utf-8')
st.download_button(
    label="Download Run Report (CSV)",
    data=csv,
    file_name="track_a_run_report.csv",
    mime="text/csv",
    type="primary"
)

st.markdown("""
**Legend:**
- ✅ **Within Spec**: The predicted output is safely within the defined limits.
- ⚠️ **Borderline**: The predicted output is within 10% of a limit boundary. Monitor closely.
- ❌ **Out of Spec**: The parameter is outside safe operating limits. Use the Optimization page to find a better setpoint.
""")
st.markdown("</div>", unsafe_allow_html=True)
