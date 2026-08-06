import math
import numpy as np
from scipy.optimize import differential_evolution
from psychrolib import GetTWetBulbFromRelHum, SetUnitSystem, SI
SetUnitSystem(SI)  # SI units: C, Pa
import streamlit as st
import pandas as pd

# ---------------------- Constants & Limits ----------------------
T_dcmp = 60  # Decomposition temperature of product (C)
R_h_limit = 0.99  # After achieving 99% exhaust humidity
PENALTY_SCALE = 1e6
EPS = 1e-12

# Physical constants
Cp_air = 1.005  # kJ/kg-K , specific heat capacity of air
Cp_L_IPA = 2.60 # kJ/kg-K , specific heat capacity of IPA liquid
Cp_V_IPA = 1.54 # kJ/kg-K , specific heat capacity of IPA Vapor
R_d = 287.058   # J/(kg-K), gas constant for dry air
R_v = 461.495   # J/(kg-K), gas constant for water vapor (will be overridden for IPA)
h_fg_i = 104.7598  # kJ/kg, enthalpy of water entering at 25 C
T_amb = 25      #Ambient temperature in room
Le = 1.0        # Lewis number ~ 1

# Default bounds (can be modified by user)
T_min = 40
T_max = 80
cfm_min = 800
cfm_max = 2400
R_h_min = 0.04
R_h_max = R_h_limit

# Equation coefficients for water (default)
antoine_A = 8.07131
antoine_B = 1730.63
antoine_C = 233.426
enthalpy_A = 1.7208
enthalpy_B = 2505.2

# IPA suggested defaults (used when toggle is ON)
antoine_A_IPA = 8.1182
antoine_B_IPA = 1580.92
antoine_C_IPA = 219.62
enthalpy_A_IPA = -1.8199
enthalpy_B_IPA = 815.0
R_v_IPA = 138.3361

# ---------------------- Helper Functions (generic) ----------------------
def saturation_pressure_from_temp(T):
    """Antoine (torr) -> kPa; coefficients for IPA."""
    return 0.133322 * (10 ** (antoine_A - (antoine_B / (antoine_C + T))))

def vapor_pressure_from_R_h(p_g, R_h):
    return p_g * max(0.0, min(1.0, R_h))

def humidity_ratio_from_vapor_pressure(P_total, p_v):
    # Generic humidity ratio: w = (Rd/Rv) * pv / (P - pv)
    return (R_d / R_v) * p_v / max(1e-9, (P_total - p_v))

def vapor_pressure_from_w(P_total, w_inlet):
    return w_inlet * P_total / (((R_d / R_v)) + w_inlet)

def R_h_from_p_v(p_v, p_g):
    return p_v / max(1e-9, p_g)

def enthalpy_vapor_from_temp(T):
    # Linear latent heat model; coefficients
    return enthalpy_A * T + enthalpy_B

def air_density(T, P_total, p_v_i, w_inlet):
    p_d = P_total - p_v_i
    return ((p_d * 1000) / (R_d * (T + 273.15))) * ((1 + w_inlet) / (1 + w_inlet * (R_v / R_d)))

def mass_flow_dry_air(air_cfm, density):
    return air_cfm * 0.00047194745 * density

def spray_rate_total(spray_rate_g_min_gun, no_of_guns):
    return spray_rate_g_min_gun * no_of_guns

def water_evaporation_rate(spray_rate_g_min, solids_fraction):
    water_fraction = 1 - solids_fraction
    return (spray_rate_g_min * water_fraction) / (1000 * 60)

def calculate_spraying_time(m_s, spray_rate_g_min_gun, no_of_guns):
    return (m_s / (spray_rate_g_min_gun * no_of_guns)) * (1000 / 60)

def exhaust_humidity_ratio(m_w, m_a, w_inlet):
    m_a_dry = m_a / (1 + w_inlet)
    return (m_w / m_a_dry) + w_inlet

def exhaust_temperature_first_law(T_inlet, w_inlet, w_exhaust, alpha):
    T_exhaust = (T_inlet * (Cp_air + enthalpy_A * w_inlet + alpha/2) + ((w_exhaust - w_inlet) * (h_fg_i - enthalpy_B)) - (alpha * T_amb)) / (Cp_air + enthalpy_A * w_exhaust + alpha/2)
    return T_exhaust

def ee_factor(T_inlet, T_exhaust, T_wbt_i, h_v_o, rho_air_i, rho_air_o, p_v_i, p_w_i):
    Num1 = (p_w_i * 1000) / (R_v * (T_wbt_i + 273.15))
    Num2 = (p_v_i * 1000) / (R_v * (T_inlet + 273.15))
    Num = Num1 - Num2
    Dnm1 = (rho_air_i + rho_air_o) / 2
    Dnm2 = Cp_air * 1000
    Dnm3 = T_inlet - T_exhaust
    Dnm4 = (h_v_o - h_fg_i) * 1000
    return Num / max(1e-9, (Dnm1 * Dnm2 * Dnm3 / max(1e-9, Dnm4)))

# ---------------------- IPA Wet-Bulb (using generic helpers) ----------------------

def inverse_antoine_T_from_pv(pv_kPa):
    """Inverse of saturation_pressure_from_temp: kPa -> C using current Antoine coefficients."""
    if pv_kPa <= 0.0:
        return -50.0
    log10_Ptorr = math.log10(pv_kPa / 0.133322)
    return (antoine_B / (antoine_A - log10_Ptorr)) - antoine_C

def GetHumRatioFromTWetBulb_IPA(TDryBulb_C, TWetBulb_C, P_kPa):
    """Forward model w(T_wb) for IPA using generic helpers"""
    if TWetBulb_C > TDryBulb_C:
        raise ValueError("Wet-bulb temperature cannot exceed dry-bulb temperature.")
    Ps   = saturation_pressure_from_temp(TWetBulb_C)       # IPA, because Antoine coefficients are overridden
    Ws   = humidity_ratio_from_vapor_pressure(P_kPa, Ps)   # saturated humidity ratio
    h_fg = enthalpy_vapor_from_temp(TWetBulb_C)            # IPA latent heat
    num  = (h_fg - Cp_L_IPA * TWetBulb_C) * Ws - Cp_air * (TDryBulb_C - TWetBulb_C)
    den  = h_fg + Cp_V_IPA * TDryBulb_C - Cp_L_IPA * TWetBulb_C
    return max(0.0, num / max(1e-9, den))

def GetTWetBulbFromRelHum_IPA(TDryBulb_C, RelHum, P_kPa, tol=1e-4, max_iter=200):
    Ps_dry = saturation_pressure_from_temp(TDryBulb_C)
    pv_in  = max(0.0, min(RelHum, 1.0)) * Ps_dry
    w_in   = humidity_ratio_from_vapor_pressure(P_kPa, pv_in)
    T_low  = inverse_antoine_T_from_pv(pv_in)
    T_high = TDryBulb_C
    T_star = 0.5 * (T_low + T_high)
    it = 0
    while (T_high - T_low) > tol and it < max_iter:
        w_star = GetHumRatioFromTWetBulb_IPA(TDryBulb_C, T_star, P_kPa)
        if w_star > w_in:
            T_high = T_star
        else:
            T_low = T_star
        T_star = 0.5 * (T_low + T_high)
        it += 1
    if it >= max_iter:
        raise RuntimeError("Convergence not reached in GetTWetBulbFromRelHum_IPA.")
    return T_star

# ---------------------- Model ----------------------
class PanCoatingModel:
    def __init__(self, **params):
        for k, v in params.items():
            setattr(self, k, v)
        if not hasattr(self, 'T_exhaust_expected'):
            self.T_exhaust_expected = None
        if not hasattr(self, 'solvent_not_water'):
            self.solvent_not_water = False

    def calculate_process_conditions(self):
        # alpha_0 = -10**5 #Lumped heat loss coeff 
        alpha_0 = -100 #Lumped heat loss coeff 
        
        p_g_i = saturation_pressure_from_temp(self.T_inlet)
        p_v_i = vapor_pressure_from_R_h(p_g_i, self.R_h)
        w_inlet = humidity_ratio_from_vapor_pressure(self.P_total, p_v_i)
        rho_air_i = air_density(self.T_inlet, self.P_total, p_v_i, w_inlet)
        h_v_i = enthalpy_vapor_from_temp(self.T_inlet)
        R_h_inlet = R_h_from_p_v(p_v_i, p_g_i)

        m_a = mass_flow_dry_air(self.air_cfm, rho_air_i)
        spray_rate_g_min = spray_rate_total(self.spray_rate_g_min_gun, self.no_of_guns)
        m_w = water_evaporation_rate(spray_rate_g_min, self.solids_fraction)
        w_exhaust = exhaust_humidity_ratio(m_w, m_a, w_inlet)

        
        def _t_exhaust_for_alpha(alpha_value: float) -> float:
            return exhaust_temperature_first_law(self.T_inlet, w_inlet, w_exhaust, float(alpha_value))

        
        expected_is_valid = (
            self.T_exhaust_expected is not None
            and np.isfinite(self.T_exhaust_expected)
            and (self.T_exhaust_expected > 0.0)
        )

        if expected_is_valid:
            def residual_alpha(alpha_arr):
                alpha_local = float(alpha_arr[0])
                
                
                T_exh = _t_exhaust_for_alpha(alpha_local)
                return abs(T_exh - self.T_exhaust_expected)

            bounds_alpha = [(alpha_0, 1000)]
            sol_alpha = differential_evolution(
                residual_alpha, bounds=bounds_alpha, tol=1e-6, maxiter=1000, polish=True, disp=False
            )
            alpha_used = float(sol_alpha.x[0])
            T_exhaust = _t_exhaust_for_alpha(alpha_used)
            print(alpha_used, "for", T_exhaust)
            err_abs = abs(T_exhaust - self.T_exhaust_expected)
            denom = self.T_exhaust_expected if self.T_exhaust_expected != 0 else 1.0
            T_exhaust_error = abs((T_exhaust - self.T_exhaust_expected) / denom) * 100.0
            

            # If err_abs < EPS, we just proceed; final T_exhaust continues outside this if-block.
        else:
            
            alpha_used = getattr(self, 'alpha_avg', None)
            
            if (alpha_used is None) or (isinstance(alpha_used, float) and np.isnan(alpha_used)):
                alpha_used = alpha_0

            T_exhaust = _t_exhaust_for_alpha(alpha_used)
            print(alpha_used, "for", T_exhaust)
            T_exhaust_error = np.nan

        
        p_g_o = saturation_pressure_from_temp(T_exhaust)
        h_v_o = enthalpy_vapor_from_temp(T_exhaust)
        p_v_o = vapor_pressure_from_w(self.P_total, w_exhaust)
        R_h_exhaust = R_h_from_p_v(p_v_o, p_g_o)

        # Wet bulb: IPA if toggle ON, else water (PsychroLib)
        if getattr(self, 'solvent_not_water', False):
            T_wbt_i = GetTWetBulbFromRelHum_IPA(self.T_inlet, R_h_inlet, self.P_total)
        else:
            P_total_Pa = self.P_total * 1000
            T_wbt_i = GetTWetBulbFromRelHum(self.T_inlet, R_h_inlet, P_total_Pa)

        rho_air_o = air_density(T_exhaust, self.P_total, p_v_o, w_exhaust)
        p_w_i = saturation_pressure_from_temp(T_wbt_i)
        ee_original = ee_factor(self.T_inlet, T_exhaust, T_wbt_i, h_v_o, rho_air_i, rho_air_o, p_v_i, p_w_i)
        spraying_time = calculate_spraying_time(self.m_s, self.spray_rate_g_min_gun, self.no_of_guns)

        # Constraints
        constraint_violated = False
        if T_exhaust >= T_dcmp - EPS:
            constraint_violated = True
        if R_h_exhaust >= R_h_limit - EPS or R_h_exhaust < 0 - EPS:
            constraint_violated = True

        R_h_exhaust_display = max(0.0, min(R_h_exhaust, R_h_limit - EPS))



        return {
            # Inputs
            'inlet_temp': self.T_inlet,
            'air_cfm': self.air_cfm,
            'total_pressure': self.P_total,
            'inlet_relative_humidity': self.R_h,
            'spray_rate_g_min_gun': self.spray_rate_g_min_gun,
            'no_of_guns': self.no_of_guns,
            'solids_fraction': self.solids_fraction,
            'mass_of_solution': self.m_s,
            # Calculated
            'inlet_humidity_ratio': w_inlet,
            'inlet_vapor_pressure': p_v_i,
            'vapor_pressure_at_inlet_wbt': p_w_i,
            'inlet_air_density': rho_air_i,
            'inlet_vapor_enthalpy': h_v_i,
            'mass_flow_air': m_a,
            'water_evap_rate': m_w,
            'outlet_saturation_pressure': p_g_o,
            'outlet_vapor_enthalpy': h_v_o,
            'outlet_air_density': rho_air_o,
            'outlet_vapor_pressure': p_v_o,
            'outlet_relative_humidity_raw': R_h_exhaust,
            'outlet_relative_humidity': R_h_exhaust_display,
            'constraints_violated': constraint_violated,
            'inlet_wet_bulb_temperature': T_wbt_i,
            'saturation_pressure_at_wbt': p_w_i,
            # Outputs
            'exhaust_temp': T_exhaust,
            'exhaust_humidity': w_exhaust,
            'environment_factor': ee_original,
            'error_exhaust_temp': T_exhaust_error,
            'spraying_time': spraying_time,
            'alpha_used': alpha_used,

        }

    def optimize_inlet_temp_const_ee(
        self,
        modified_spray_rate_g_min_gun,
        no_of_guns,
        modified_air_cfm,
        modified_T_inlet,
        modified_R_h,
        ee_target=None
    ):
        original = self.calculate_process_conditions()
        ee_original = float(ee_target) if (ee_target is not None) else original["environment_factor"]
        eff_spray = original["spray_rate_g_min_gun"] if modified_spray_rate_g_min_gun == 0 else modified_spray_rate_g_min_gun
        eff_air_cfm = original["air_cfm"] if modified_air_cfm == 0 else modified_air_cfm
        eff_T_inlet = original["inlet_temp"] if modified_T_inlet == 0 else modified_T_inlet
        eff_R_h = original["inlet_relative_humidity"] if modified_R_h == 0 else modified_R_h

        fixed_T = (modified_T_inlet != 0)
        fixed_CFM = (modified_air_cfm != 0)
        fixed_RH = (modified_R_h != 0)

        free_bounds = []
        if not fixed_T:
            free_bounds.append((T_min, T_max))
        if not fixed_CFM:
            free_bounds.append((cfm_min, cfm_max))
        if not fixed_RH:
            free_bounds.append((R_h_min, R_h_max))

        def make_full_tuple(x_free):
            it = iter(x_free)
            T   = eff_T_inlet   if fixed_T   else float(next(it))
            CFM = eff_air_cfm   if fixed_CFM else float(next(it))
            RH  = eff_R_h       if fixed_RH  else float(next(it))
            return T, CFM, RH

        def residual(x_free):
            T_in, eff_air_cfm_local, eff_R_h_local = make_full_tuple(x_free)
            tmp_model = PanCoatingModel(
                T_inlet=T_in,
                air_cfm=eff_air_cfm_local,
                P_total=self.P_total,
                R_h=eff_R_h_local,
                spray_rate_g_min_gun=eff_spray,
                no_of_guns=no_of_guns,
                solids_fraction=self.solids_fraction,
                m_s=self.m_s,
                solvent_not_water=self.solvent_not_water,
                alpha_avg=st.session_state.get("alpha_avg", -0.005),

            )
            try:
                tmp_result = tmp_model.calculate_process_conditions()
            except RuntimeError:
                return np.array([PENALTY_SCALE], dtype=float)

            R_h_exhaust_raw = tmp_result["outlet_relative_humidity_raw"]
            T_exhaust       = tmp_result["exhaust_temp"]

            violated = (R_h_exhaust_raw >= R_h_limit - EPS) or \
                       (T_exhaust       >= T_dcmp     - EPS) or \
                       (R_h_exhaust_raw <  0          - EPS)

            ee_calculated = tmp_result["environment_factor"]
            base_residual = ee_calculated - ee_original

            if violated:
                rh_over = max(0.0, R_h_exhaust_raw - R_h_limit)
                t_over  = max(0.0, T_in - T_dcmp)
                penalty = PENALTY_SCALE * (1.0 + 10.0 * (rh_over + t_over))
                return np.array([penalty], dtype=float)

            return np.array([base_residual], dtype=float)

        def objective(x_free):
            r = residual(x_free)[0]
            return r * r

        if len(free_bounds) == 0:
            T_in_new, cfm_in_new, R_h_in_new = eff_T_inlet, eff_air_cfm, eff_R_h
        else:
            sol = differential_evolution(objective, bounds=free_bounds, tol=1e-4, maxiter=2000, polish=True)
            T_in_new, cfm_in_new, R_h_in_new = make_full_tuple(sol.x)
            
        print("Calculating for Final one")
        tmp_final_model = PanCoatingModel(
            T_inlet=T_in_new,
            air_cfm=cfm_in_new,
            P_total=self.P_total,
            R_h=R_h_in_new,
            spray_rate_g_min_gun=eff_spray,
            no_of_guns=no_of_guns,
            solids_fraction=self.solids_fraction,
            m_s=self.m_s,
            solvent_not_water=self.solvent_not_water,
            alpha_avg=st.session_state.get("alpha_avg", -0.005),
        )
        final = tmp_final_model.calculate_process_conditions()

        return {
            "EE_target": ee_original,
            "spray_rate_g_min": eff_spray,
            "air_cfm": eff_air_cfm,
            "inlet_humidity": eff_R_h,
            "initial_guess_T_inlet": eff_T_inlet,
            "T_in_new_C": T_in_new,
            "cfm_new": cfm_in_new,
            "R_h_new": R_h_in_new,
            "T_exhaust_C": final["exhaust_temp"],
            "w_exhaust_kg_per_kg": final["exhaust_humidity"],
            "rho_air_in_kg_m3": final["inlet_air_density"],
            "mass_flow_air_kg_s": final["mass_flow_air"],
            "water_evap_rate_kg_s": final["water_evap_rate"],
            "spraying_time": final["spraying_time"],
            "R_h_exhaust": final["outlet_relative_humidity"],
        }

# ---------------------- UI ----------------------
st.title('Pan Coating Model')
st.subheader("Calculate Process Exhaust Parameters for Omeprezol Pellets")

# Toggle for non-water solvent to override coefficients
on = st.toggle("Solvent is NOT water")
st.session_state.solvent_not_water = on

if on:
    st.write("Please provide properties for solvent (Current inputs corresponds to IPA)")
    st.write("Please provide input for Antoine equation to calculate Saturation Vapor Pressure")
    st.write("log(P_sat[torr])/log(10) = A - B/(C + T[C])")
    aA = st.number_input('Value of Antoine coefficient A', value=float(antoine_A_IPA), key='antoineA')
    aB = st.number_input('Value of Antoine coefficient B', value=float(antoine_B_IPA), key='antoineB')
    aC = st.number_input('Value of Antoine coefficient C', value=float(antoine_C_IPA), key='antoineC')

    st.write("Please provide input for Vapor Enthalpy equation as function of Temperature")
    st.write("h_v[kJ/kg] = A * T [C] + B")
    eA = st.number_input("Value of Enthalpy coefficient A", value=float(enthalpy_A_IPA), key='enthA')
    eB = st.number_input("Value of Enthalpy coefficient B", value=float(enthalpy_B_IPA), key='enthB')

    st.write("Please provide value of gas constant (R_u/Molecular Weight of Solvent) in J/(kg-K)")
    gR = st.number_input('Value of Gas Constant', value=float(R_v_IPA), key='gasR')

    # Override globals for IPA mode
    antoine_A = aA; antoine_B = aB; antoine_C = aC
    enthalpy_A = eA; enthalpy_B = eB
    R_v = gR

# ---------------------- Session-state bootstrapping ----------------------
if "stage_mode" not in st.session_state:
    st.session_state.stage_mode = False  # False = show initial form; True = show stages
if "common_inputs" not in st.session_state:
    st.session_state.common_inputs = {}
if "stage_count" not in st.session_state:
    st.session_state.stage_count = 0
if "results_df" not in st.session_state:
    st.session_state.results_df = None
if "stage_inputs_list" not in st.session_state:
    st.session_state.stage_inputs_list = None

# ---------------- STEP 1: initial/common inputs ----------------
if not st.session_state.stage_mode:
    with st.form("input_form"):
        P_total = st.number_input('Enter pressure in kPa [Range: 90 to 101.325]' , value=101.325, key="P_total")
        no_of_guns = st.number_input('Enter no of guns', value=5, step=1, min_value=1, key="no_of_guns")
        solids_fraction = st.number_input('Enter solids fraction (Solid Content)', min_value=0.0, max_value=1.0, key="solids_fraction")
        m_s = st.number_input('Enter mass of solution in kg to be coated', min_value=0.0, key="m_s")
        no_of_stage = st.number_input('Please enter number of stages of spray rates', min_value=1, step=1, key="no_of_stage")
        next_clicked = st.form_submit_button('Next → Enter Stage Inputs', key="next_btn")
        if next_clicked:
            st.session_state.common_inputs = {
                "P_total": float(P_total),
                "no_of_guns": int(no_of_guns),
                "solids_fraction": float(solids_fraction),
                "m_s": float(m_s),
                "solvent_not_water": bool(st.session_state.solvent_not_water),
            }
            st.session_state.stage_count = int(no_of_stage)
            st.session_state.stage_mode = True
            try:
                st.rerun()
            except Exception:
                st.experimental_rerun()

# ---------------- STEP 2: stage inputs & calculation ----------------
if st.session_state.stage_mode:
    n = st.session_state.stage_count
    st.info(f"Enter inputs for {n} stage(s).")
    with st.form("stages_form"):
        for i in range(n):
            with st.expander(f"Stage {i+1}", expanded=True):
                st.number_input(f'[Stage {i+1}] Spray rate (gm/min/gun)', key=f'sr_{i}', min_value=0.0)
                st.number_input(f'[Stage {i+1}] Inlet temperature (C)', key=f'tin_{i}', min_value=0.0)
                st.number_input(f'[Stage {i+1}] Air flow rate (cfm)', key=f'cfm_{i}', min_value=0.0)
                st.number_input(f'[Stage {i+1}] Relative humidity (0–1)', key=f'rh_{i}', min_value=0.0, max_value=1.0)
                st.number_input(f'[Stage {i+1}] Expected exhaust temperature (C)', key=f'texp_{i}', min_value=0.0)

        cols = st.columns([1, 1, 3])
        with cols[0]:
            back_clicked = st.form_submit_button("← Back", help="Return to common inputs", key="back_btn")
        with cols[1]:
            calc_clicked = st.form_submit_button("Calculate", key="calc_btn_all")

        if back_clicked:
            st.session_state.stage_mode = False
            try:
                st.rerun()
            except Exception:
                st.experimental_rerun()

        if calc_clicked:
            spray_rate_g_min_gun = np.array([st.session_state[f'sr_{i}'] for i in range(n)], dtype=float)
            T_inlet = np.array([st.session_state[f'tin_{i}'] for i in range(n)], dtype=float)
            air_cfm  = np.array([st.session_state[f'cfm_{i}'] for i in range(n)], dtype=float)
            R_h      = np.array([st.session_state[f'rh_{i}']  for i in range(n)], dtype=float)
            T_exhaust_expected = np.array([st.session_state[f'texp_{i}'] for i in range(n)], dtype=float)

            # Snapshot common inputs
            P_total = st.session_state.common_inputs["P_total"]
            no_of_guns = st.session_state.common_inputs["no_of_guns"]
            solids_fraction = st.session_state.common_inputs["solids_fraction"]
            m_s = st.session_state.common_inputs["m_s"]
            solvent_not_water_flag = st.session_state.common_inputs.get("solvent_not_water", False)
            
            alpha_values = []    
            results = []
            stage_inputs_list = []
            for i in range(n):

                
                alpha_avg_to_pass = float(np.mean(alpha_values)) if len(alpha_values) > 0 else 0

                has_expected = not (np.isnan(T_exhaust_expected[i]) or T_exhaust_expected[i] is None)
    
                
                model = PanCoatingModel(
                    T_inlet=T_inlet[i],
                    air_cfm=air_cfm[i],
                    P_total=P_total,
                    R_h=R_h[i],
                    spray_rate_g_min_gun=spray_rate_g_min_gun[i],
                    no_of_guns=no_of_guns,
                    solids_fraction=solids_fraction,
                    m_s=m_s,
                    T_exhaust_expected=T_exhaust_expected[i],
                    solvent_not_water=solvent_not_water_flag,
                )
                try:
                    res = model.calculate_process_conditions()
                    
                    
                    if has_expected and 'alpha_used' in res and not np.isnan(res['alpha_used']):
                        alpha_values.append(float(res['alpha_used']))

                    

                    row = {
                        "Stage": i + 1,
                        "T_exhaust (C)": res["exhaust_temp"],
                        "Exhaust_R_h": res["outlet_relative_humidity"],
                        "Exhaust_R_h (raw)": res["outlet_relative_humidity_raw"],
                        "Error T_exhaust (%)": res["error_exhaust_temp"],
                        "Spraying Time (hrs)": res["spraying_time"],
                        "EE Factor": res["environment_factor"],
                        "alpha_used": res["alpha_used"],
                        "Constraints violated": res["constraints_violated"],
                    }
                    
                    results.append(row)
                    stage_inputs_list.append({
                        "P_total": P_total,
                        "spray_rate_g_min_gun": spray_rate_g_min_gun[i],
                        "no_of_guns": no_of_guns,
                        "solids_fraction": solids_fraction,
                        "T_inlet": T_inlet[i],
                        "air_cfm": air_cfm[i],
                        "R_h": R_h[i],
                        "T_exhaust_expected": T_exhaust_expected[i],
                        "m_s": m_s,
                        "solvent_not_water": solvent_not_water_flag,
                    })
                    
                except Exception as e:
                    st.error(f"Stage {i+1}: {e}")

                alpha_avg_final = float(np.mean(alpha_values)) if len(alpha_values) > 0 else -0.05
                st.session_state.alpha_avg = alpha_avg_final
                st.session_state.alpha_values = alpha_values
            
            if results:
                st.session_state.results_df = pd.DataFrame(results)
                st.session_state.stage_inputs_list = stage_inputs_list
                st.success("Calculated successfully for all stages.")
                st.dataframe(st.session_state.results_df.round(4), width="content")

                for i, row in enumerate(results):
                    with st.expander(f"Stage {row['Stage']} – Summary", expanded=False):
                        col1, col2, col3, col4, col5 = st.columns(5)
                        with col1:
                            st.metric("T_exhaust (C)", f"{row['T_exhaust (C)']:.4f}")
                        with col2:
                            st.metric("Exhaust_R_h (clamped)", f"{row['Exhaust_R_h']:.4f}")
                        with col3:
                            st.metric("Exhaust_R_h (raw)", f"{row['Exhaust_R_h (raw)']:.4f}")
                        with col4:
                            st.metric("Spraying Time (hrs)", f"{row['Spraying Time (hrs)']:.2f}")
                        with col5:
                            st.metric("EE Factor", f"{row['EE Factor']:.4f}")

# ---------------- Optimization: Default highest EE Selected ----------------
if ("results_df" in st.session_state and st.session_state.results_df is not None) or \
   ("calc_result" in st.session_state and "inputs_snapshot" in st.session_state):
    st.subheader("Optimize with modified inputs (using largest EE from calculated stages)")
    results_df = st.session_state.get("results_df", None)
    stage_inputs_list = st.session_state.get("stage_inputs_list", None)
    if results_df is not None and stage_inputs_list is not None and len(results_df) == len(stage_inputs_list):
        picked_idx = int(results_df["EE Factor"].idxmax())
        defaults = stage_inputs_list[picked_idx]
        ee_target_value = float(results_df.iloc[picked_idx]["EE Factor"])
        picked_stage = int(results_df.iloc[picked_idx]["Stage"])
        st.caption(f"Optimization target EE = {ee_target_value:.4f} (auto-selected: Stage {picked_stage} with largest EE)")
    else:
        st.warning("Multi-stage results not found in session. Falling back to Stage 1 snapshot.")
        defaults = st.session_state.get("inputs_snapshot", {})
        ee_target_value = float(st.session_state.get("calc_result", {}).get("environment_factor", 0.0))
        st.caption(f"Optimization target EE (Stage 1) = {ee_target_value:.4f}")

    on_bounds = st.toggle("Modify Optimization bounds")
    if on_bounds:
        st.write("")
        T_exhaust_M = st.number_input('Please provide maximum exhaust temperature limit (Product Decomposition Temperature)', value=float(T_dcmp))
        T_in_M = st.number_input('Please provide maximum inlet temperature limit ', value=float(T_max))
        T_in_m = st.number_input('Please provide minimum inlet temperature limit (Dew Point)', value=float(T_min))
        cfm_M = st.number_input('Please provide maximum cfm limit (Equipment Specification)', value=float(cfm_max))
        cfm_m = st.number_input('Please provide minimum cfm limit (Equipment Specification)', value=float(cfm_min))
        R_h_M = st.number_input('Please provide maximum R_h limit (Seasonal Variation- Monsoon)', value=float(R_h_max))
        R_h_m = st.number_input('Please provide minimum R_h limit (Seasonal Variation- Summer)', value=float(R_h_min))

        # Update globals
        globals()['T_dcmp'] = T_exhaust_M
        globals()['T_max']  = T_in_M
        globals()['T_min']  = T_in_m
        globals()['cfm_max'] = cfm_M
        globals()['cfm_min'] = cfm_m
        globals()['R_h_max'] = R_h_M
        globals()['R_h_min'] = R_h_m

    with st.form("opt_form"):
        
        solids_fraction_new = st.number_input('Enter modified solids fraction (0–1)', value=float(defaults.get("solids_fraction", 0.0)), min_value=0.0, max_value=1.0)
        m_s_new = st.number_input('Enter modified mass of solution to be coated (kg)', value=float(defaults.get("m_s", 0.0)), min_value=0.0 )
        spray_rate_g_min_gun_new = st.number_input('Enter modified spray rate in gm/min/gun (Upto 130 gm/min/gun)', value=float(defaults.get("spray_rate_g_min_gun", 0.0)))
        T_inlet_new = st.number_input('Enter modified inlet temperature in degree celcius', value=float(defaults.get("T_inlet", 0.0)))
        air_cfm_new = st.number_input('Enter modified air flow rate in cfm', value=float(defaults.get("air_cfm", 0.0)))
        R_h_new = st.number_input('Enter modified Relative humidity in fraction', value=float(defaults.get("R_h", 0.0)))
        opt_submit = st.form_submit_button("Optimize process parameters", key="opt_submit_btn")
        

        if opt_submit:
            model = PanCoatingModel(
                T_inlet=defaults.get("T_inlet", 0.0),
                air_cfm=defaults.get("air_cfm", 0.0),
                P_total=defaults.get("P_total", 101.325),
                R_h=defaults.get("R_h", 0.0),
                spray_rate_g_min_gun=defaults.get("spray_rate_g_min_gun", 0.0),
                no_of_guns=defaults.get("no_of_guns", 1),
                solids_fraction=solids_fraction_new,
                m_s=m_s_new,
                solvent_not_water=defaults.get("solvent_not_water", bool(st.session_state.solvent_not_water)),
            )
            with st.spinner("Optimizing…"):
                try:
                    result_opt = model.optimize_inlet_temp_const_ee(
                        modified_spray_rate_g_min_gun=spray_rate_g_min_gun_new,
                        no_of_guns=defaults.get("no_of_guns", 1),
                        modified_air_cfm=air_cfm_new,
                        modified_T_inlet=T_inlet_new,
                        modified_R_h=R_h_new,
                        ee_target=ee_target_value,
                    )
                    st.success("Optimization complete.")
                    colA, colB, colC, colD, colE, colF = st.columns(6)
                    colG, colH = st.columns(2)
                    with colA:
                        st.metric("T_inlet (C)", f"{result_opt['T_in_new_C']:.2f}")
                    with colB:
                        st.metric("CFM", f"{result_opt['cfm_new']:.2f}")
                    with colC:
                        st.metric("R_h_in", f"{result_opt['R_h_new']:.2f}")
                    with colD:
                        st.metric("R_h_exhaust", f"{result_opt['R_h_exhaust']:.2f}")
                    with colE:
                        st.metric("T_exhaust (C)", f"{result_opt['T_exhaust_C']:.2f}")
                    with colF:
                        st.metric("Spraying Time (hrs)", f"{result_opt['spraying_time']:.2f}")
                    colG, colH = st.columns(2)
                    
                    with colG:
                        st.metric("Alpha avg (fixed)", f"{st.session_state.get('alpha_avg', float('nan')):.4f}")
                    with colH:
                        st.metric("EE target", f"{result_opt['EE_target']:.4f}")
    
                except RuntimeError as e:
                    st.error(f"Constraint violation: {e}")
                except Exception as e:
                    st.exception(e)