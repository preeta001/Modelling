import streamlit as st
import pandas as pd

st.title("Export & Reports")

st.markdown("Download simulation results, calibrated parameters, and validation reports.")

# Dummy dataframe for export
df = pd.DataFrame({'time': [0, 10, 20], 'T_bed': [25, 30, 35]})

csv = df.to_csv(index=False).encode('utf-8')

st.download_button(
    label="Download Simulation Results as CSV",
    data=csv,
    file_name='simulation_results.csv',
    mime='text/csv',
)

yaml_data = """
HLF_kW_K: 0.125
evap_efficiency: 0.88
"""

st.download_button(
    label="Download Calibrated Parameters (YAML)",
    data=yaml_data,
    file_name='fitted_parameters.yaml',
    mime='text/yaml',
)
