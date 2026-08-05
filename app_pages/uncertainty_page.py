import streamlit as st
import numpy as np
import plotly.graph_objects as go
from coating_model.uncertainty import run_monte_carlo_propagation, calculate_failure_probability

st.title("Uncertainty & Risk (Monte Carlo)")

col1, col2 = st.columns(2)
samples = col1.number_input("Monte Carlo Samples", 100, 5000, 500)
wi_limit = col2.number_input("WI Critical Limit", 1.0, 1.5, 1.05)

if st.button("Run Uncertainty Propagation"):
    with st.spinner(f"Running {samples} simulations..."):
        from tests.test_uncertainty import dummy_sim_func
        
        base_inputs = {'T_inlet': 60.0, 'spray_rate': 40.0}
        input_dists = {
            'T_inlet': ('normal', 60.0, 2.0),
            'spray_rate': ('uniform', 30.0, 70.0)
        }
        
        res = run_monte_carlo_propagation(samples, base_inputs, input_dists, dummy_sim_func)
        
        p_fail = calculate_failure_probability(res['WI_peak'], wi_limit, '>')
        
        st.metric("P(Overwetting | WI > Limit)", f"{p_fail * 100:.1f} %")
        
        fig = go.Figure(data=[go.Histogram(x=res['WI_peak'], marker_color='#FFEA00')])
        fig.add_vline(x=wi_limit, line_dash="dash", line_color="#FF1744", annotation_text="Limit")
        fig.update_layout(
            template='plotly_dark',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            title="Distribution of Peak Wetness Index",
            xaxis_title="Peak WI",
            yaxis_title="Frequency"
        )
        st.plotly_chart(fig, use_container_width=True)
