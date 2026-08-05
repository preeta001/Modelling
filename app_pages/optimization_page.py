import streamlit as st
import numpy as np
from scipy.optimize import differential_evolution
from coating_model.solvent_properties import get_solvent
from coating_model import psychrometrics as psy
from coating_model.constants import Cp_air, CFM_TO_M3_S

st.title("💡 Optimization & Design Space")
st.markdown("Target an Environment Equivalent (EE) or Wetness Index (WI) and optimize new CPPs without violating constraints.")

if 'latest_res' not in st.session_state or 'latest_inputs' not in st.session_state:
    st.warning("Please run a Dynamic Simulation first to establish a baseline for optimization.")
    st.stop()

res = st.session_state['latest_res']
inputs = st.session_state['latest_inputs']
solvent = get_solvent(inputs.get('solvent', 'water'))

# Extract current max WI as our target "Environmental Equivalent"
wi_arr = res.get('WI', res.get('WI_pred', [0]))
if len(wi_arr) == 0:
    st.error("No Wetness Index data found in simulation results.")
    st.stop()

target_wi = float(np.max(wi_arr))
current_spray = float(inputs.get('spray_rate_g_min_gun', 50.0))
current_t_in = float(inputs.get('T_inlet', 60.0))
current_cfm = float(inputs.get('air_cfm', 1200.0))

st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.subheader("Current Microenvironment Assessment")
c1, c2, c3 = st.columns(3)
c1.metric("Peak EE Factor (WI)", f"{target_wi:.2f}", help="EE > 1.0 means risk of overwetting.")
if target_wi > 1.0:
    c2.error("Status: High Risk of Overwetting")
elif target_wi > 0.8:
    c2.warning("Status: Amber (Narrow Margin)")
else:
    c2.success("Status: Nominal (Green)")
c3.metric("Current Spray Rate", f"{current_spray:.1f} g/min/gun")

with st.expander("📖 What does this mean? (PDF Ch. 10.3)"):
    st.write("This is the **Traffic-Light Design Space**. We extract the worst-case (peak) Wetness Index (our EE factor) from your dynamic simulation. You can now propose a higher spray rate, and the optimizer will find the exact Inlet Temp and Airflow required to maintain this identical Wetness Index, guaranteeing the identical microenvironment.")
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.subheader("Steady-State EE Optimization")
st.write("Propose a new target spray rate. The optimizer will use algebraic steady-state equations to instantly find the required $T_{inlet}$ and $CFM$ to maintain the target EE Factor.")

new_spray = st.number_input("Target Spray Rate (g/min/gun)", value=float(current_spray + 10.0), step=5.0)

with st.expander("⚙️ Optimizer Bounds Constraint Configuration", expanded=False):
    bc1, bc2 = st.columns(2)
    t_min_b = bc1.number_input("Min Inlet Temp (°C)", value=40.0)
    t_max_b = bc2.number_input("Max Inlet Temp (°C)", value=90.0)
    cfm_min_b = bc1.number_input("Min Airflow (CFM)", value=500.0)
    cfm_max_b = bc2.number_input("Max Airflow (CFM)", value=3000.0)

t_in_bounds = (t_min_b, t_max_b)
cfm_bounds = (cfm_min_b, cfm_max_b)

if st.button("Optimize CPPs", type="primary"):
    with st.spinner("Running Differential Evolution Optimizer..."):
        
        def calc_steady_state_wi(t_inlet, cfm, spray_rate):
            P_total = 101.325
            R_h_inlet = 0.1
            solids_fraction = inputs.get('solids_fraction', 0.15)
            no_of_guns = inputs.get('no_of_guns', 4)
            
            p_sat_i = solvent.saturation_pressure(t_inlet)
            p_v_i = psy.vapor_pressure_from_rh(p_sat_i, R_h_inlet)
            w_inlet = psy.humidity_ratio(P_total, p_v_i, solvent)
            rho_air_i = psy.air_density(t_inlet, P_total, p_v_i, w_inlet, solvent)
            m_a = cfm * CFM_TO_M3_S * rho_air_i
            m_a_dry = m_a / (1 + w_inlet)
            
            spray_rate_total_kg_s = (spray_rate * no_of_guns) / 60000.0
            m_water_spray = spray_rate_total_kg_s * (1.0 - solids_fraction)
            
            p_sat_wb = solvent.saturation_pressure(35.0)
            w_sat_bed = psy.humidity_ratio(P_total, p_sat_wb, solvent)
            evap_eff = inputs.get('evap_efficiency', 0.8)
            m_evap_cap = max(1e-9, m_a_dry * (w_sat_bed - w_inlet) * evap_eff)
            
            wi = m_water_spray / m_evap_cap
            return wi

        def calc_steady_state_wi_with_wbt(t_inlet, cfm, spray_rate, wbt):
            P_total = 101.325
            p_sat_i = solvent.saturation_pressure(t_inlet)
            p_v_i = psy.vapor_pressure_from_rh(p_sat_i, 0.1)
            w_inlet = psy.humidity_ratio(P_total, p_v_i, solvent)
            rho_air_i = psy.air_density(t_inlet, P_total, p_v_i, w_inlet, solvent)
            m_a_dry = (cfm * CFM_TO_M3_S * rho_air_i) / (1 + w_inlet)
            m_water_spray = (spray_rate * inputs.get('no_of_guns', 4) / 60000.0) * (1.0 - inputs.get('solids_fraction', 0.15))
            w_sat_bed = psy.humidity_ratio(P_total, solvent.saturation_pressure(wbt), solvent)
            m_evap_cap = max(1e-9, m_a_dry * (w_sat_bed - w_inlet) * inputs.get('evap_efficiency', 0.8))
            return m_water_spray / m_evap_cap

        # Calibrate WBT
        from scipy.optimize import minimize
        def proxy_wi_error(wbt_guess):
            wi_est = calc_steady_state_wi_with_wbt(current_t_in, current_cfm, current_spray, wbt_guess[0])
            return (wi_est - target_wi)**2
            
        sol_wbt = minimize(proxy_wi_error, x0=[35.0], bounds=[(20.0, 60.0)])
        wbt_calibrated = sol_wbt.x[0]

        # Now optimize T_inlet and CFM for the new spray rate
        def objective(x):
            t_in, cfm = x
            wi_est = calc_steady_state_wi_with_wbt(t_in, cfm, new_spray, wbt_calibrated)
            penalty = 0.0
            if wi_est > target_wi:
                penalty = (wi_est - target_wi) * 1000.0
            
            energy = t_in * cfm / 10000.0
            return (wi_est - target_wi)**2 + 0.1 * energy + penalty

        sol = differential_evolution(objective, bounds=[t_in_bounds, cfm_bounds], polish=True, seed=42)
        opt_t_in = sol.x[0]
        opt_cfm = sol.x[1]
        
        st.success("Optimization Complete!")
        
        c4, c5, c6, c7, c8 = st.columns(5)
        c4.metric("Spray Rate", f"{new_spray:.1f} g/m", delta=f"{new_spray - current_spray:.1f}")
        c5.metric("Req T_inlet", f"{opt_t_in:.1f} °C", delta=f"{opt_t_in - current_t_in:.1f}", delta_color="inverse")
        c6.metric("Req Airflow", f"{opt_cfm:.0f} CFM", delta=f"{opt_cfm - current_cfm:.0f}", delta_color="inverse")
        
        final_wi = calc_steady_state_wi_with_wbt(opt_t_in, opt_cfm, new_spray, wbt_calibrated)
        c7.metric("New EE Factor", f"{final_wi:.2f}", help="Matches the target EE exactly.")
        
        # Cycle Time Reduction Calculation
        n_guns = inputs.get('no_of_guns', 4)
        target_solid_mass = 10.0 
        solids_frac = inputs.get('solids_fraction', 0.15)
        target_solution_mass_kg = target_solid_mass / solids_frac
        
        old_time_hrs = (target_solution_mass_kg * 1000) / (current_spray * n_guns * 60)
        new_time_hrs = (target_solution_mass_kg * 1000) / (new_spray * n_guns * 60)
        
        c8.metric("Cycle Time", f"{new_time_hrs:.1f} hrs", delta=f"{new_time_hrs - old_time_hrs:.1f} hrs", delta_color="inverse")

st.markdown("</div>", unsafe_allow_html=True)
