import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go

st.title("🔫 Spray Pump Calibration (Gun Validation)")
st.markdown("Map machine setpoints (Pump RPM) to mechanistic model inputs (Spray Rate in g/min/gun).")

# Initialize session state for data table
if 'pump_data' not in st.session_state:
    st.session_state.pump_data = pd.DataFrame({
        "Pump_RPM": [10.0, 20.0, 30.0],
        "Spray_Rate_g_min": [50.0, 100.0, 150.0]
    })
if 'num_guns_calib' not in st.session_state:
    st.session_state.num_guns_calib = 4

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("1. Enter Calibration Data")
    st.session_state.num_guns_calib = st.number_input("Number of Guns used for this test", value=st.session_state.num_guns_calib, min_value=1)
    
    st.markdown("Enter TOTAL measured spray rate for the given Pump RPM:")
    edited_df = st.data_editor(
        st.session_state.pump_data,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True
    )
    st.session_state.pump_data = edited_df

    if st.button("Calculate Calibration Curve", type="primary"):
        df = st.session_state.pump_data.dropna()
        if len(df) < 2:
            st.error("Need at least 2 data points for linear regression.")
        else:
            x = df["Pump_RPM"].values
            # We want spray rate PER GUN for the mechanistic model
            y = df["Spray_Rate_g_min"].values / st.session_state.num_guns_calib
            
            # y = mx + c
            m, c = np.polyfit(x, y, 1)
            st.session_state.pump_m = m
            st.session_state.pump_c = c
            
            st.success(f"Calibration successful! \n\n**Rate/gun = {m:.3f} × RPM + {c:.3f}**")

with col2:
    if 'pump_m' in st.session_state:
        m = st.session_state.pump_m
        c = st.session_state.pump_c
        
        st.subheader("2. Calibration Curve")
        
        df = st.session_state.pump_data.dropna()
        x_meas = df["Pump_RPM"].values
        y_meas = df["Spray_Rate_g_min"].values / st.session_state.num_guns_calib
        
        x_line = np.linspace(0, max(x_meas) * 1.2, 50)
        y_line = m * x_line + c
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x_meas, y=y_meas, mode='markers', name='Measured Data', marker=dict(size=10, color='#ff7f0e')))
        fig.add_trace(go.Scatter(x=x_line, y=y_line, mode='lines', name='Linear Fit', line=dict(color='#1f77b4', dash='dash')))
        fig.update_layout(template='plotly_dark', xaxis_title="Pump RPM", yaxis_title="Spray Rate PER GUN (g/min)")
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("3. Calculator")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Predict Spray Rate from RPM**")
            test_rpm = st.number_input("Enter Pump RPM:", value=15.0)
            pred_rate = m * test_rpm + c
            st.metric("Predicted Rate (g/min/gun)", f"{pred_rate:.2f}")
            
        with c2:
            st.markdown("**Find RPM for Target Spray Rate**")
            target_rate = st.number_input("Enter Target Rate (g/min/gun):", value=75.0)
            req_rpm = (target_rate - c) / m if m != 0 else 0
            st.metric("Required Pump RPM", f"{req_rpm:.2f}")

    else:
        st.info("Enter data and click 'Calculate' to see the curve and calculator.")
