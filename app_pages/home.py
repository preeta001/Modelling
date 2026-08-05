import streamlit as st

st.title("💊 Track A: Practical Integrated Coating Model")
st.markdown("### Digital Twin for Tablet Coating Optimization")

st.markdown("""
<div class="glass-card">
    <h2>Welcome to the Track A Digital Twin</h2>
    <p>This application implements the causal thermodynamic and quality models described in <i>modelling.pdf</i>. 
    It is designed to give you rigorous control over your coating process through a strict two-step methodology.</p>
</div>
""", unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    <div class="glass-card" style="border-top: 4px solid #58a6ff;">
        <h3>🔬 STEP 1: Model Execution</h3>
        <p>Run forward predictions based purely on mechanistic physics and user-entered Critical Process Parameters (CPPs).</p>
        <ul>
            <li><b>Works instantly</b> (No plant data required)</li>
            <li>Predicts <code>T_exhaust</code>, <code>RH_exhaust</code>, <code>Wetness Index (WI)</code></li>
            <li>Generates a comprehensive Recommendation Table</li>
        </ul>
        <br>
        <i>Use this to explore the design space and optimize parameters before running a batch.</i>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Go to Quick Predict ⚡"):
        st.switch_page("app_pages/quick_predict.py")

with col2:
    st.markdown("""
    <div class="glass-card" style="border-top: 4px solid #3fb950;">
        <h3>🧪 STEP 2: Model Validation</h3>
        <p>Upload historical plant CSV data to compare theoretical predictions against reality, calibrate the model, and apply bias correction.</p>
        <ul>
            <li><b>Requires plant CSV data</b></li>
            <li>Calibrates Heat Loss and Evaporation Efficiency</li>
            <li>Applies ML Hybrid Bias Correction</li>
            <li>Generates per-phase error metrics (RMSE, R²)</li>
        </ul>
        <br>
        <i>Use this to validate the digital twin against your specific equipment.</i>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Go to Data Upload 📂"):
        st.switch_page("app_pages/data_upload.py")
