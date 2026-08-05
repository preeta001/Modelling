import numpy as np
from scipy.integrate import solve_ivp
from typing import Dict, Any, Tuple
from .constants import Cp_air, T_amb_default, h_fg_i_water, CFM_TO_M3_S
from .solvent_properties import get_solvent
from . import psychrometrics as psy

def run_dynamic_simulation(
    time_span_s: Tuple[float, float],
    initial_state: np.ndarray, # [T_s, M_w_s, M_c_s, T_d, M_w_d, M_c_d]
    inputs: Dict[str, Any],
    dt_eval_s: float = 10.0
) -> Dict[str, Any]:
    
    solvent = get_solvent(inputs.get('solvent_name', 'water'))
    P_total = inputs.get('P_total', 101.325)
    no_of_guns = inputs.get('no_of_guns', 4)
    solids_fraction = inputs.get('solids_fraction', 0.15)
    
    M_core = inputs['batch_load_kg']
    cp_core = inputs['cp_core_kJ_kgK']
    A_bed = inputs['A_bed_m2']
    h_conv = inputs['h_conv_W_m2K'] / 1000.0 # kW
    
    # Absolute Heat Loss Coefficient (UA)
    UA = inputs['HLF_kW_K'] 
    
    eta_dep = inputs.get('eta_dep', 0.95)
    
    f_s = 0.20 # 20% in spray zone
    f_d = 0.80 # 80% in drying zone
    
    def get_val(key, t, default=None):
        if key not in inputs:
            if default is not None:
                return default
            raise KeyError(f"Missing required input: {key}")
        val = inputs[key]
        if callable(val): return val(t)
        return val

    def rhs(t, y):
        T_s, M_w_s, M_c_s, T_d, M_w_d, M_c_d = y
        
        M_w_s = max(0.0, M_w_s)
        M_w_d = max(0.0, M_w_d)
        
        T_inlet = get_val('T_inlet', t)
        air_cfm = get_val('air_cfm', t)
        R_h_inlet = get_val('R_h_inlet', t)
        spray_rate = get_val('spray_rate_g_min_gun', t)
        pan_rpm = get_val('pan_rpm', t, default=10.0) 
        
        tau_c = max(1.0, 150.0 / max(1e-3, pan_rpm))
        
        p_sat_i = solvent.saturation_pressure(T_inlet)
        p_v_i = psy.vapor_pressure_from_rh(p_sat_i, R_h_inlet)
        w_inlet = psy.humidity_ratio(P_total, p_v_i, solvent)
        rho_air_i = psy.air_density(T_inlet, P_total, p_v_i, w_inlet, solvent)
        m_a = air_cfm * CFM_TO_M3_S * rho_air_i
        m_a_dry = m_a / (1 + w_inlet)
        
        spray_rate_total_kg_s = (spray_rate * no_of_guns) / 60000.0
        m_water_spray = spray_rate_total_kg_s * (1.0 - solids_fraction)
        m_solid_spray = spray_rate_total_kg_s * solids_fraction
        
        M_b = M_core + M_c_s + M_c_d + M_w_s + M_w_d
        m_circ = M_b / tau_c
        
        M_core_s = M_core * f_s
        M_core_d = M_core * f_d
        
        M_bed_s = M_core_s + M_c_s + M_w_s
        M_bed_d = M_core_d + M_c_d + M_w_d
        
        cp_s = (M_core_s*cp_core + M_c_s*cp_core + M_w_s*solvent.Cp_L) / max(1e-6, M_bed_s)
        cp_d = (M_core_d*cp_core + M_c_d*cp_core + M_w_d*solvent.Cp_L) / max(1e-6, M_bed_d)
        
        # SPRAY ZONE
        m_a_dry_s = m_a_dry * f_s
        w_sat_s = psy.humidity_ratio(P_total, solvent.saturation_pressure(T_s), solvent)
        m_evap_cap_s = max(0.0, m_a_dry_s * (w_sat_s - w_inlet) * inputs.get('evap_efficiency', 0.8))
        if M_w_s <= 1e-6 and m_water_spray <= 1e-6:
            m_evap_s = 0.0
        else:
            m_evap_s = min(m_evap_cap_s, m_water_spray + M_w_s/1.0)
            
        dM_w_s_dt = m_water_spray - m_evap_s + m_circ * (M_w_d/max(1e-6, M_bed_d)) - m_circ * (M_w_s/max(1e-6, M_bed_s))
        dM_c_s_dt = m_solid_spray * eta_dep + m_circ * (M_c_d/max(1e-6, M_bed_d)) - m_circ * (M_c_s/max(1e-6, M_bed_s))
        
        T_gas_s = T_inlet - (m_evap_s * solvent.latent_heat(T_inlet)) / max(1e-6, m_a_dry_s * Cp_air)
        Q_gas_s = h_conv * A_bed * f_s * (T_gas_s - T_s)
        Q_spray = spray_rate_total_kg_s * solvent.Cp_L * (inputs.get('T_spray', T_amb_default) - T_s)
        Q_evap_s = m_evap_s * solvent.latent_heat(T_s)
        Q_loss_s = UA * f_s * (T_s - T_amb_default)
        Q_circ_s = m_circ * cp_d * T_d - m_circ * cp_s * T_s
        
        dT_s_dt = (Q_gas_s + Q_spray - Q_evap_s - Q_loss_s + Q_circ_s) / max(1e-6, M_bed_s * cp_s)
        
        # DRYING ZONE
        m_a_dry_d = m_a_dry * f_d
        w_sat_d = psy.humidity_ratio(P_total, solvent.saturation_pressure(T_d), solvent)
        m_evap_cap_d = max(0.0, m_a_dry_d * (w_sat_d - w_inlet) * inputs.get('evap_efficiency', 0.8))
        if M_w_d <= 1e-6:
            m_evap_d = 0.0
        else:
            m_evap_d = min(m_evap_cap_d, M_w_d/1.0)
            
        dM_w_d_dt = - m_evap_d + m_circ * (M_w_s/max(1e-6, M_bed_s)) - m_circ * (M_w_d/max(1e-6, M_bed_d))
        dM_c_d_dt = m_circ * (M_c_s/max(1e-6, M_bed_s)) - m_circ * (M_c_d/max(1e-6, M_bed_d))
        
        T_gas_d = T_inlet - (m_evap_d * solvent.latent_heat(T_inlet)) / max(1e-6, m_a_dry_d * Cp_air)
        Q_gas_d = h_conv * A_bed * f_d * (T_gas_d - T_d)
        Q_evap_d = m_evap_d * solvent.latent_heat(T_d)
        Q_loss_d = UA * f_d * (T_d - T_amb_default)
        Q_circ_d = m_circ * cp_s * T_s - m_circ * cp_d * T_d
        
        dT_d_dt = (Q_gas_d - Q_evap_d - Q_loss_d + Q_circ_d) / max(1e-6, M_bed_d * cp_d)
        
        return [dT_s_dt, dM_w_s_dt, dM_c_s_dt, dT_d_dt, dM_w_d_dt, dM_c_d_dt]

    t_eval = np.arange(time_span_s[0], time_span_s[1] + dt_eval_s / 2, dt_eval_s)
    t_eval = t_eval[t_eval <= time_span_s[1]]
    
    sol = solve_ivp(
        rhs, time_span_s, initial_state,
        t_eval=t_eval, method='LSODA', rtol=1e-4, atol=1e-5, max_step=1.0
    )
    
    time_arr = sol.t
    T_s_arr, M_w_s_arr, M_c_s_arr, T_d_arr, M_w_d_arr, M_c_d_arr = sol.y
    
    n_steps = len(time_arr)
    T_bed_arr = np.zeros(n_steps)
    M_water_arr = np.zeros(n_steps)
    M_coat_arr = np.zeros(n_steps)
    
    T_exh_arr = np.zeros(n_steps)
    RH_exh_arr = np.zeros(n_steps)
    w_exh_arr = np.zeros(n_steps)
    m_evap_arr = np.zeros(n_steps)
    m_evap_cap_arr = np.zeros(n_steps)
    wi_arr = np.zeros(n_steps)
    
    for i in range(n_steps):
        t = time_arr[i]
        T_inlet = get_val('T_inlet', t)
        air_cfm = get_val('air_cfm', t)
        R_h_inlet = get_val('R_h_inlet', t)
        spray_rate = get_val('spray_rate_g_min_gun', t)
        
        M_w_s = max(0.0, M_w_s_arr[i])
        M_w_d = max(0.0, M_w_d_arr[i])
        T_s = T_s_arr[i]
        T_d = T_d_arr[i]
        
        M_water_arr[i] = M_w_s + M_w_d
        M_coat_arr[i] = M_c_s_arr[i] + M_c_d_arr[i]
        T_bed_arr[i] = T_s * f_s + T_d * f_d
        
        p_sat_i = solvent.saturation_pressure(T_inlet)
        p_v_i = psy.vapor_pressure_from_rh(p_sat_i, R_h_inlet)
        w_inlet = psy.humidity_ratio(P_total, p_v_i, solvent)
        rho_air_i = psy.air_density(T_inlet, P_total, p_v_i, w_inlet, solvent)
        m_a = air_cfm * CFM_TO_M3_S * rho_air_i
        m_a_dry = m_a / (1 + w_inlet)
        
        m_water_spray = (spray_rate * no_of_guns) / 60000.0 * (1.0 - solids_fraction)
        
        m_a_dry_s = m_a_dry * f_s
        w_sat_s = psy.humidity_ratio(P_total, solvent.saturation_pressure(T_s), solvent)
        m_evap_cap_s = max(0.0, m_a_dry_s * (w_sat_s - w_inlet) * inputs.get('evap_efficiency', 0.8))
        if M_w_s <= 1e-6 and m_water_spray <= 1e-6:
            m_evap_s = 0.0
        else:
            m_evap_s = min(m_evap_cap_s, m_water_spray + M_w_s/1.0)
            
        m_a_dry_d = m_a_dry * f_d
        w_sat_d = psy.humidity_ratio(P_total, solvent.saturation_pressure(T_d), solvent)
        m_evap_cap_d = max(0.0, m_a_dry_d * (w_sat_d - w_inlet) * inputs.get('evap_efficiency', 0.8))
        if M_w_d <= 1e-6:
            m_evap_d = 0.0
        else:
            m_evap_d = min(m_evap_cap_d, M_w_d/1.0)
            
        m_evap_total = m_evap_s + m_evap_d
        m_evap_cap_total = m_evap_cap_s + m_evap_cap_d
        m_evap_arr[i] = m_evap_total
        m_evap_cap_arr[i] = m_evap_cap_total
        
        wi_arr[i] = m_water_spray / max(1e-9, m_evap_cap_s)
        
        w_exhaust = w_inlet + (m_evap_total / max(1e-9, m_a_dry))
        w_exh_arr[i] = w_exhaust
        
        alpha = UA / max(1e-6, m_a_dry)
        num = T_inlet * (Cp_air + solvent.enthalpy_A * w_inlet + alpha/2) + \
              ((w_exhaust - w_inlet) * (h_fg_i_water - solvent.enthalpy_B)) - (alpha * T_amb_default)
        den = Cp_air + solvent.enthalpy_A * w_exhaust + alpha/2
        T_exh = num / den
        T_exh_arr[i] = T_exh
        
        p_sat_o = solvent.saturation_pressure(T_exh)
        p_v_o = psy.vapor_pressure_from_humidity_ratio(P_total, w_exhaust, solvent)
        R_h_exh_raw = psy.relative_humidity(p_v_o, p_sat_o)
        RH_exh_arr[i] = max(0.0, min(R_h_exh_raw, 0.99))
        
    wi_crit = inputs.get('WI_crit', 1.05)
    excess_wi = np.maximum(0.0, wi_arr - wi_crit)
    ewi = float(np.trapezoid(excess_wi, x=time_arr))
    
    weight_gain_pct = (M_coat_arr[-1] / max(1e-9, M_core)) * 100.0
    
    return {
        'time_s': time_arr,
        'T_bed': T_bed_arr,
        'M_water': M_water_arr,
        'M_coat': M_coat_arr,
        'T_exhaust': T_exh_arr,
        'RH_exhaust': RH_exh_arr,
        'w_exhaust': w_exh_arr,
        'm_evap': m_evap_arr,
        'm_evap_cap': m_evap_cap_arr,
        'WI': wi_arr,
        'EWI': ewi,
        'weight_gain_pct': weight_gain_pct
    }
