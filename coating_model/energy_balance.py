"""M1 -- THE canonical steady-state thermodynamic core.

This is the ONLY exhaust-temperature calculation in the repository. Every page,
every module and every optimiser calls this function. Four drifting copies of
this equation previously existed (defect D4) and they disagreed with each other.

--------------------------------------------------------------------------------
THE ENERGY BALANCE, per kg of dry air
--------------------------------------------------------------------------------

    cp_a*T_in + w_in*h_v(T_in) + (w_ex - w_in)*h_liq
  = cp_a*T_ex + w_ex*h_v(T_ex) + q_loss

    h_v(T) = enthalpy_A*T + enthalpy_B     vapour enthalpy      [kJ/kg]
    h_liq  = 104.7598                      liquid water at 25 C [kJ/kg]

Every enthalpy term appears EXACTLY ONCE. The previous implementation in
app_pages/validation_page.py subtracted `m_w * latent_heat(25)` -- but
`latent_heat()` returned the *vapour* enthalpy (2548.22 kJ/kg), which the outlet
term `w_ex*h_v(T_ex)` already carried. Phase-change energy was counted twice and
the liquid inlet enthalpy was never added, making the function 5.2 C cold before
any heat loss was applied (defect D1). That is why Track A produced physically
impossible output.

--------------------------------------------------------------------------------
THE HEAT-LOSS TERM -- two conventions, explicitly selectable
--------------------------------------------------------------------------------

    "physical_ua"   q_loss = a * ((T_in + T_ex)/2 - T_amb)      <- correct
    "legacy_alpha"  q_loss = a * ((T_ex - T_in)/2 + T_amb)      <- reproduces M0

The legacy form has a sign error inside the mean-temperature bracket: it responds
to ambient temperature backwards. The two are identical at a = 0, which is why
the adiabatic core is sound and why per-stage fitting hides the defect entirely
(modelling.pdf section 2.3.1, independently re-derived).

`legacy_alpha` exists so M0 equivalence is provable on demand. `physical_ua` is
the default for anything that extrapolates.

--------------------------------------------------------------------------------
FREE PARAMETERS
--------------------------------------------------------------------------------

Run adiabatically (alpha = 0, evaporated_fraction = 1) this model has ZERO free
parameters -- it is pure thermodynamics with published constants. On the audit
row it predicts 51.601 C against a measured 48.519 C, a genuine zero-fitting
prediction that is 3.08 C high. The whole modelling question is the single
heat-loss term that closes that gap.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from .constants import CFM_TO_M3_S, Cp_air, R_d, T_amb_default
from .solvent_properties import Solvent, get_solvent

HeatLossForm = Literal["physical_ua", "legacy_alpha"]

#: Enthalpy of liquid water entering at 25 C, kJ/kg. Named for what it IS.
#: The legacy name `h_fg_i` implied a latent heat and directly caused defect D1.
H_LIQUID_WATER_AT_25C = 104.7598


class PhysicsViolation(ValueError):
    """Raised when a computed state is not physically possible."""


@dataclass(frozen=True)
class ExhaustState:
    """Complete steady-state result. All values at full precision, unrounded."""

    # inlet
    p_sat_inlet_kPa: float
    p_v_inlet_kPa: float
    w_inlet: float
    rho_moist_inlet: float
    m_moist_air_kg_s: float
    m_dry_air_kg_s: float
    # spray / evaporation
    spray_total_g_min: float
    m_solvent_sprayed_kg_s: float
    m_evaporated_kg_s: float
    w_exhaust: float
    # energy terms (per kg dry air, kJ/kg)
    term_inlet_sensible: float
    term_inlet_vapour: float
    term_liquid_in: float
    term_outlet_vapour_offset: float
    numerator: float
    denominator: float
    # heat loss
    heat_loss_form: str
    alpha: float
    UA_kW_K: float
    q_loss_kJ_per_kg_da: float
    # outlet
    T_exhaust_C: float
    p_sat_exhaust_kPa: float
    p_v_exhaust_kPa: float
    RH_exhaust: float

    @property
    def energy_residual_kJ_per_kg_da(self) -> float:
        """Closure of the balance as solved. Must be ~0 to machine precision."""
        return _energy_residual(self)


def _energy_residual(s: ExhaustState) -> float:
    """Re-evaluate the balance at the solved T_ex. This is the conservation check."""
    solvent = get_solvent("water")
    eA, eB = solvent.enthalpy_A, solvent.enthalpy_B
    T_in_side = (
        Cp_air * _T_in_of(s)
        + s.w_inlet * (eA * _T_in_of(s) + eB)
        + (s.w_exhaust - s.w_inlet) * H_LIQUID_WATER_AT_25C
    )
    T_ex_side = (
        Cp_air * s.T_exhaust_C
        + s.w_exhaust * (eA * s.T_exhaust_C + eB)
        + s.q_loss_kJ_per_kg_da
    )
    return T_in_side - T_ex_side


def _T_in_of(s: ExhaustState) -> float:
    """Recover T_inlet from the stored sensible term (Cp_air * T_in)."""
    return s.term_inlet_sensible / Cp_air


def heat_loss_per_kg_da(
    alpha: float,
    T_inlet_C: float,
    T_exhaust_C: float,
    T_amb_C: float,
    form: HeatLossForm,
) -> float:
    """q_loss in kJ per kg dry air, under the selected convention."""
    if form == "physical_ua":
        return alpha * ((T_inlet_C + T_exhaust_C) / 2.0 - T_amb_C)
    if form == "legacy_alpha":
        return alpha * ((T_exhaust_C - T_inlet_C) / 2.0 + T_amb_C)
    raise ValueError(f"unknown heat_loss_form {form!r}")


def calculate_exhaust_state(
    T_inlet_C: float,
    air_cfm: float,
    RH_inlet: float,
    spray_rate_g_min_gun: float,
    no_of_guns: int,
    solids_fraction: float,
    *,
    P_total_kPa: float = 101.325,
    solvent_name: str = "water",
    heat_loss_form: HeatLossForm = "physical_ua",
    alpha: float | None = None,
    UA_kW_K: float | None = None,
    T_amb_C: float = T_amb_default,
    evaporated_fraction: float = 1.0,
    check_physics: bool = True,
) -> ExhaustState:
    """Solve the steady-state exhaust condition.

    Exactly one of `alpha` (kJ/kg-da per K) or `UA_kW_K` (absolute, kW/K) must be
    given. `UA_kW_K` is the preferred parameterisation: it is an equipment
    property, whereas alpha = UA / m_dry_air changes with airflow. On a dataset
    where airflow is constant the two are interchangeable; where it varies, the
    normalised form is wrong by up to 3x (modelling.pdf section 2.3.1).

    `evaporated_fraction` is the fraction of sprayed solvent that evaporates
    inside the control volume. 1.0 reproduces the legacy assumption. It is the
    hypothesis parameter for PLAN section 2.5 and defaults to the legacy value so
    that M1 == M0 out of the box.
    """
    if (alpha is None) == (UA_kW_K is None):
        raise ValueError("Supply exactly one of alpha or UA_kW_K.")
    if not 0.0 <= RH_inlet <= 1.0:
        raise ValueError(f"RH_inlet must be a fraction in [0,1], got {RH_inlet}")
    if not 0.0 <= solids_fraction < 1.0:
        raise ValueError(f"solids_fraction must be in [0,1), got {solids_fraction}")
    if not 0.0 <= evaporated_fraction <= 1.0:
        raise ValueError(
            f"evaporated_fraction must be in [0,1], got {evaporated_fraction}"
        )

    solvent: Solvent = get_solvent(solvent_name)
    eA, eB = solvent.enthalpy_A, solvent.enthalpy_B

    # --- 1. inlet air state -------------------------------------------------
    p_sat_i = solvent.saturation_pressure(T_inlet_C)
    if p_sat_i <= 0.0:
        raise PhysicsViolation(f"non-positive saturation pressure at {T_inlet_C} C")
    p_v_i = p_sat_i * RH_inlet
    if p_v_i >= P_total_kPa:
        raise PhysicsViolation("inlet vapour pressure exceeds total pressure")

    w_inlet = (R_d / solvent.R_v) * p_v_i / (P_total_kPa - p_v_i)
    rho_moist = ((P_total_kPa - p_v_i) * 1000.0 / (R_d * (T_inlet_C + 273.15))) * (
        (1.0 + w_inlet) / (1.0 + w_inlet * (solvent.R_v / R_d))
    )
    m_moist = air_cfm * CFM_TO_M3_S * rho_moist
    m_da = m_moist / (1.0 + w_inlet)
    if m_da <= 0.0:
        raise PhysicsViolation("non-positive dry-air mass flow")

    # --- 2. spray and evaporation ------------------------------------------
    spray_total = spray_rate_g_min_gun * no_of_guns
    m_solvent = spray_total * (1.0 - solids_fraction) / 60000.0  # kg/s
    m_evap = m_solvent * evaporated_fraction
    w_exhaust = w_inlet + m_evap / m_da
    if w_exhaust < w_inlet:
        raise PhysicsViolation("exhaust humidity ratio below inlet")

    # --- 3. resolve the heat-loss coefficient ------------------------------
    a = float(alpha) if alpha is not None else float(UA_kW_K) / m_da
    ua = a * m_da

    # --- 4. solve the balance for T_exhaust --------------------------------
    # Both forms are linear in T_ex, so this is a closed-form solve, not a search.
    term_inlet_sensible = Cp_air * T_inlet_C
    term_inlet_vapour = w_inlet * (eA * T_inlet_C + eB)
    term_liquid_in = (w_exhaust - w_inlet) * H_LIQUID_WATER_AT_25C
    term_outlet_vapour_offset = -w_exhaust * eB

    base_num = (
        term_inlet_sensible
        + term_inlet_vapour
        + term_liquid_in
        + term_outlet_vapour_offset
    )
    if heat_loss_form == "physical_ua":
        numerator = base_num - a * T_inlet_C / 2.0 + a * T_amb_C
    elif heat_loss_form == "legacy_alpha":
        numerator = base_num + a * T_inlet_C / 2.0 - a * T_amb_C
    else:
        raise ValueError(f"unknown heat_loss_form {heat_loss_form!r}")

    denominator = Cp_air + eA * w_exhaust + a / 2.0
    if abs(denominator) < 1e-12:
        raise PhysicsViolation("degenerate energy balance: denominator is zero")

    T_exhaust = numerator / denominator
    if not math.isfinite(T_exhaust):
        raise PhysicsViolation("non-finite exhaust temperature")

    q_loss = heat_loss_per_kg_da(a, T_inlet_C, T_exhaust, T_amb_C, heat_loss_form)

    # --- 5. exhaust state ---------------------------------------------------
    p_sat_o = solvent.saturation_pressure(T_exhaust)
    p_v_o = w_exhaust * P_total_kPa / ((R_d / solvent.R_v) + w_exhaust)
    RH_exhaust = p_v_o / max(1e-12, p_sat_o)

    state = ExhaustState(
        p_sat_inlet_kPa=p_sat_i,
        p_v_inlet_kPa=p_v_i,
        w_inlet=w_inlet,
        rho_moist_inlet=rho_moist,
        m_moist_air_kg_s=m_moist,
        m_dry_air_kg_s=m_da,
        spray_total_g_min=spray_total,
        m_solvent_sprayed_kg_s=m_solvent,
        m_evaporated_kg_s=m_evap,
        w_exhaust=w_exhaust,
        term_inlet_sensible=term_inlet_sensible,
        term_inlet_vapour=term_inlet_vapour,
        term_liquid_in=term_liquid_in,
        term_outlet_vapour_offset=term_outlet_vapour_offset,
        numerator=numerator,
        denominator=denominator,
        heat_loss_form=heat_loss_form,
        alpha=a,
        UA_kW_K=ua,
        q_loss_kJ_per_kg_da=q_loss,
        T_exhaust_C=T_exhaust,
        p_sat_exhaust_kPa=p_sat_o,
        p_v_exhaust_kPa=p_v_o,
        RH_exhaust=RH_exhaust,
    )

    if check_physics:
        assert_physically_valid(state)
    return state


def assert_physically_valid(s: ExhaustState, energy_tol: float = 1e-9) -> None:
    """Gate G2. Raises PhysicsViolation on any breach."""
    if s.w_inlet < 0.0 or s.w_exhaust < 0.0:
        raise PhysicsViolation(f"negative humidity ratio: {s.w_inlet}, {s.w_exhaust}")
    if s.w_exhaust < s.w_inlet:
        raise PhysicsViolation("exhaust drier than inlet with a positive spray rate")
    if s.m_dry_air_kg_s <= 0.0 or s.rho_moist_inlet <= 0.0:
        raise PhysicsViolation("non-positive air mass flow or density")
    if s.m_evaporated_kg_s < 0.0:
        raise PhysicsViolation("negative evaporation rate")
    if not math.isfinite(s.T_exhaust_C):
        raise PhysicsViolation("non-finite exhaust temperature")
    if s.RH_exhaust < 0.0:
        raise PhysicsViolation(f"negative exhaust RH: {s.RH_exhaust}")
    resid = s.energy_residual_kJ_per_kg_da
    if abs(resid) > energy_tol:
        raise PhysicsViolation(
            f"energy balance does not close: residual {resid:.3e} kJ/kg-da "
            f"(tolerance {energy_tol:.1e}). A term is double-counted or missing."
        )


def solve_alpha_for_measured_exhaust(
    T_exhaust_measured_C: float, **kwargs
) -> float:
    """Diagnostic ONLY: the alpha that reproduces a measured exhaust temperature.

    This is a CALIBRATION residual tool. A value produced by fitting alpha to the
    row it then predicts is not an accuracy figure, and PLAN section 4 (target T2)
    requires it to be labelled as such wherever it is displayed. Never use this
    inside a prediction path.

    Closed-form: T_ex is a ratio of two expressions linear in alpha, so setting
    T_ex = target gives a linear equation in alpha. No optimiser is needed --
    the legacy model's use of differential_evolution here was unnecessary and
    non-deterministic.
    """
    kwargs.pop("alpha", None)
    kwargs.pop("UA_kW_K", None)
    kwargs["check_physics"] = False

    s0 = calculate_exhaust_state(alpha=0.0, **kwargs)
    s1 = calculate_exhaust_state(alpha=1.0, **kwargs)

    # T(a) = (N0 + a*dN) / (D0 + a*dD)  =>  a = (T*D0 - N0) / (dN - T*dD)
    N0, D0 = s0.numerator, s0.denominator
    dN, dD = s1.numerator - N0, s1.denominator - D0
    den = dN - T_exhaust_measured_C * dD
    if abs(den) < 1e-15:
        raise PhysicsViolation("alpha is not identifiable at this operating point")
    return (T_exhaust_measured_C * D0 - N0) / den
