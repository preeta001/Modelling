import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.optimize import differential_evolution

from coating_model.batch_runner import run_batch_from_csv
from coating_model.data_loader import generate_synthetic_batch
from coating_model.solvent_properties import get_solvent

st.title("📈 Simulation & Optimization")
st.markdown("Simulate the dynamic batch trajectory or optimize parameters to maintain Environmental Equivalence (EE) at faster spray rates.")

# Get global solvent
solvent_name = st.session_state.get('global_solvent', 'water')
solvent = get_solvent(solvent_name)
st.caption(f"Using Solvent Physics: **{solvent.name.upper()}**")

# Base inputs from calibration if available
default_UA = st.session_state.get('calibrated_UA', 0.1)

tab1, tab2 = st.tabs(["1. Dynamic Simulation", "2. EE Optimization Engine"])

def plot_and_summarize(res, inputs_used):
    c1, c2, c3 = st.columns(3)
    c1.metric("Final T_exhaust", f"{res['T_exhaust_pred'][-1]:.1f} °C")
    
    wi = res.get('WI_pred', np.zeros_like(res['time_s']))
    c2.metric("Peak WI", f"{np.max(wi):.2f}")
    c3.metric("Final Weight Gain", f"{res['weight_gain_pct']:.1f} %")
    
    time_min = res['time_s']/60
    t_bed = res['T_bed_pred']
    t_exh = res['T_exhaust_pred']
    
    st.markdown("### Thermal Trajectories")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=time_min, y=t_bed, name='T_bed', line=dict(color='#ff7f0e')))
    fig.add_trace(go.Scatter(x=time_min, y=t_exh, name='T_exhaust', line=dict(color='#1f77b4')))
    
    # Overlay phase changes
    if 'phase' in res:
        phases = res['phase']
        change_idx = np.where(phases[:-1] != phases[1:])[0]
        for idx in change_idx:
            fig.add_vline(x=time_min[idx], line_dash="dot", line_color="gray", opacity=0.5)
            fig.add_annotation(x=time_min[idx], y=max(t_exh), text=phases[idx+1], showarrow=False, xanchor="left", xshift=5)

    fig.update_layout(template='plotly_dark', xaxis_title="Time (min)", yaxis_title="Temp (°C)", margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("### Wetness Index")
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=time_min, y=wi, name='Wetness Index', line=dict(color='#d62728'), fill='tozeroy'))
    fig2.add_hline(y=1.0, line_dash="dash", line_color="white", annotation_text="Risk Threshold")
    fig2.update_layout(template='plotly_dark', xaxis_title="Time (min)", yaxis_title="WI", margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig2, use_container_width=True)

with tab1:
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.subheader("Global Batch Parameters")
    c1, c2, c3, c4 = st.columns(4)
    batch_mass = c1.number_input("Batch Mass (kg)", value=100.0, min_value=1.0)
    solids_frac = c2.number_input("Solids Fraction (0-1)", value=0.15, min_value=0.01, max_value=1.0)
    num_guns = c3.number_input("Number of Guns", value=4, min_value=1)
    pan_rpm = c4.number_input("Pan RPM", value=10.0, min_value=1.0)
    
    st.subheader("Stage Builder")
    num_stages = st.number_input("Number of Stages", min_value=1, max_value=20, value=1, step=1)
    
    stage_data = []
    for i in range(num_stages):
        st.markdown(f"**Stage {i+1}**")
        col1, col2, col3, col4, col5 = st.columns(5)
        duration = col1.number_input(f"Duration (min)", value=60.0 if i==0 else 15.0, min_value=1.0, key=f"dur_{i}")
        t_inlet = col2.number_input(f"T_inlet (°C)", value=60.0 if i==0 else 45.0, min_value=20.0, key=f"tin_{i}")
        airflow = col3.number_input(f"Airflow (CFM)", value=1200.0, min_value=100.0, key=f"air_{i}")
        spray = col4.number_input(f"Spray (g/min/gun)", value=50.0 if i==0 else 0.0, min_value=0.0, key=f"spray_{i}")
        rh_in = col5.number_input(f"Inlet RH (0-1)", value=0.05, min_value=0.0, max_value=1.0, key=f"rhin_{i}")
        
        stage_data.append({
            "Phase": f"Stage {i+1}",
            "Duration (min)": duration,
            "T_inlet (°C)": t_inlet,
            "Airflow (CFM)": airflow,
            "Spray Rate (g/min/gun)": spray,
            "Inlet RH": rh_in
        })
        
    edited_df = pd.DataFrame(stage_data)
    
    if st.button("Run Multi-Stage Recipe", type="primary"):
        with st.spinner("Integrating ODEs..."):
            times, t_in, air, spray_r, rhs, phases = [], [], [], [], [], []
            t_current = 0
            for idx, row in edited_df.iterrows():
                duration_s = int(row["Duration (min)"] * 60)
                times.extend(range(t_current, t_current + duration_s))
                t_in.extend([row["T_inlet (°C)"]] * duration_s)
                air.extend([row["Airflow (CFM)"]] * duration_s)
                spray_r.extend([row["Spray Rate (g/min/gun)"]] * duration_s)
                rhs.extend([row["Inlet RH"]] * duration_s)
                phases.extend([row["Phase"]] * duration_s)
                t_current += duration_s
                
            ts_df = pd.DataFrame({
                'time_s': times, 'T_inlet': t_in, 'airflow': air,
                'spray_rate': spray_r, 'inlet_RH': rhs, 'phase': phases
            })
            
            inputs_used = {
                'batch_load_kg': batch_mass, 'solids_fraction': solids_frac,
                'no_of_guns': num_guns, 'pan_rpm': pan_rpm,
                'HLF_kW_K': default_UA, 'cp_core_kJ_kgK': 1.1, 'A_bed_m2': 2.0,
                'h_conv_W_m2K': 50.0, 'eta_dep': 0.95, 'evap_efficiency': 0.8,
                'solvent_name': solvent_name, 'initial_T_bed': 30.0,
                'T_inlet': ts_df['T_inlet'].mean(), 'air_cfm': ts_df['airflow'].mean(),
                'spray_rate_g_min_gun': ts_df['spray_rate'].max(), 'R_h_inlet': ts_df['inlet_RH'].mean()
            }
            
            res = run_batch_from_csv(ts_df, inputs_used)
            res['phase'] = ts_df['phase'].values
            st.session_state['latest_res'] = res
            st.session_state['latest_inputs'] = inputs_used
            st.session_state['simulation_run'] = True
            plot_and_summarize(res, inputs_used)
    st.markdown("</div>", unsafe_allow_html=True)

with tab2:
    from coating_model.energy_balance import calculate_exhaust_state
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.subheader("Environmental Equivalence (EE) Optimization")
    st.write("Find the optimal Inlet Temp and Airflow to hit a target EE at a higher spray rate.")
    
    col1, col2 = st.columns(2)
    with col1:
        target_T_exh = st.number_input("Target exhaust temperature (°C)", value=48.5,
                                       help="Optimise inlet temp and airflow to hit "
                                            "this exhaust condition at the new spray rate.")
        new_spray_rate = st.number_input("Desired Spray Rate (g/min/gun)", value=75.0)
        solids_frac_opt = st.number_input("Solids Fraction", value=0.15)
        batch_mass_opt = st.number_input("Batch Mass (kg)", value=100.0)
        
    with col2:
        st.markdown("**Bounds**")
        T_in_min = st.number_input("Min T_inlet (°C)", value=40.0)
        T_in_max = st.number_input("Max T_inlet (°C)", value=80.0)
        cfm_min = st.number_input("Min Airflow (CFM)", value=800.0)
        cfm_max = st.number_input("Max Airflow (CFM)", value=2400.0)
        rh_fixed = st.number_input("Inlet RH (Fixed)", value=0.05)
        
    if st.button("Optimize Parameters", type="primary"):
        with st.spinner("Running Optimization..."):
            def objective(x):
                T_in, cfm = x
                inputs = {
                    'P_total': 101.325, 'no_of_guns': 4, 'solids_fraction': solids_frac_opt,
                    'm_s': batch_mass_opt, 'spray_rate_g_min_gun': new_spray_rate,
                    'T_inlet': T_in, 'air_cfm': cfm, 'R_h': rh_fixed
                }
                try:
                    st_ = calculate_exhaust_state(
                        T_inlet_C=inputs['T_inlet'], air_cfm=inputs['air_cfm'],
                        RH_inlet=inputs['R_h'],
                        spray_rate_g_min_gun=inputs['spray_rate_g_min_gun'],
                        no_of_guns=inputs['no_of_guns'],
                        solids_fraction=inputs['solids_fraction'],
                        P_total_kPa=inputs['P_total'], solvent_name=solvent_name,
                        UA_kW_K=default_UA, check_physics=False)
                    return abs(st_.T_exhaust_C - target_T_exh)
                except Exception:
                    return 1e6
            
            bounds = [(T_in_min, T_in_max), (cfm_min, cfm_max)]
            sol = differential_evolution(objective, bounds=bounds, tol=1e-4)
            
            best_T_in, best_cfm = sol.x
            
            # Verify constraints
            inputs_opt = {
                'P_total': 101.325, 'no_of_guns': 4, 'solids_fraction': solids_frac_opt,
                'm_s': batch_mass_opt, 'spray_rate_g_min_gun': new_spray_rate,
                'T_inlet': best_T_in, 'air_cfm': best_cfm, 'R_h': rh_fixed
            }
            res_opt = calculate_exhaust_state(
                T_inlet_C=inputs_opt['T_inlet'], air_cfm=inputs_opt['air_cfm'],
                RH_inlet=inputs_opt['R_h'],
                spray_rate_g_min_gun=inputs_opt['spray_rate_g_min_gun'],
                no_of_guns=inputs_opt['no_of_guns'],
                solids_fraction=inputs_opt['solids_fraction'],
                P_total_kPa=inputs_opt['P_total'], solvent_name=solvent_name,
                UA_kW_K=default_UA, check_physics=False)
            
            st.success("Optimization Complete!")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Optimal T_inlet", f"{best_T_in:.1f} °C")
            c2.metric("Optimal Airflow", f"{best_cfm:.0f} CFM")
            c3.metric("Pred. T_exhaust", f"{res_opt.T_exhaust_C:.2f} °C")
            c4.metric("Exhaust RH", f"{res_opt.RH_exhaust:.3f}")
    st.markdown("</div>", unsafe_allow_html=True)
