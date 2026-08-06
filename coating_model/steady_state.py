"""Steady-state facade -- delegates to the canonical core.

This module used to carry its own copy of the exhaust-temperature equation. It
was one of four copies (defect D4) and they disagreed. It now forwards to
`coating_model.energy_balance`, which is the single source of truth.

The public signature is preserved so existing callers keep working, but the
physics behind it has changed in one important way: the default heat-loss
convention is now the physically correct one. Pass
`heat_loss_form="legacy_alpha"` for bit-exact legacy reproduction.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .energy_balance import (
    HeatLossForm,
    calculate_exhaust_state,
    solve_alpha_for_measured_exhaust,
)
from . import psychrometrics as psy
from .constants import CFM_TO_M3_S, Cp_air, h_fg_i_water
from .solvent_properties import get_solvent


def mass_flow_dry_air(air_cfm: float, density: float) -> float:
    """Moist-air mass flow (kg/s) from volumetric flow and density.

    NOTE the name is historical and misleading: this returns MOIST air mass flow.
    Divide by (1 + w) for dry air. Retained for backward compatibility only --
    new code should use `ExhaustState.m_dry_air_kg_s`.
    """
    return air_cfm * CFM_TO_M3_S * density


def calculate_steady_state(
    T_inlet: float,
    air_cfm: float,
    R_h_inlet: float,
    spray_rate_g_min_gun: float,
    no_of_guns: int,
    solids_fraction: float,
    P_total: float = 101.325,
    solvent_name: str = "water",
    alpha_hlf: float = 0.0,
    T_exhaust_expected: Optional[float] = None,
    heat_loss_form: HeatLossForm = "physical_ua",
    evaporated_fraction: float = 1.0,
) -> Dict[str, Any]:
    """Steady-state exhaust condition.

    If `T_exhaust_expected` is given, alpha is solved in CLOSED FORM to reproduce
    it. That is a calibration residual, not a prediction -- the returned dict is
    tagged `is_calibration_fit=True` so downstream code cannot mistake one for
    the other (defect D3).

    The legacy implementation used `differential_evolution` for this solve, which
    was both unnecessary (the equation is linear in alpha) and non-deterministic.
    """
    kw = dict(
        T_inlet_C=T_inlet,
        air_cfm=air_cfm,
        RH_inlet=R_h_inlet,
        spray_rate_g_min_gun=spray_rate_g_min_gun,
        no_of_guns=no_of_guns,
        solids_fraction=solids_fraction,
        P_total_kPa=P_total,
        solvent_name=solvent_name,
        heat_loss_form=heat_loss_form,
        evaporated_fraction=evaporated_fraction,
    )

    is_fit = T_exhaust_expected is not None and T_exhaust_expected > 0
    alpha = (
        solve_alpha_for_measured_exhaust(float(T_exhaust_expected), **kw)
        if is_fit
        else float(alpha_hlf)
    )

    s = calculate_exhaust_state(**kw, alpha=alpha)

    solvent = get_solvent(solvent_name)
    T_wbt_i = psy.get_wet_bulb_temperature(T_inlet, R_h_inlet, P_total, solvent)
    rho_air_o = psy.air_density(
        s.T_exhaust_C, P_total, s.p_v_exhaust_kPa, s.w_exhaust, solvent
    )
    p_w_i = solvent.saturation_pressure(T_wbt_i)
    h_v_o = solvent.enthalpy_A * s.T_exhaust_C + solvent.enthalpy_B

    num = (p_w_i * 1000) / (solvent.R_v * (T_wbt_i + 273.15)) - (
        s.p_v_inlet_kPa * 1000
    ) / (solvent.R_v * (T_inlet + 273.15))
    dnm = ((s.rho_moist_inlet + rho_air_o) / 2) * (Cp_air * 1000) * (
        T_inlet - s.T_exhaust_C
    ) / max(1e-9, (h_v_o - h_fg_i_water) * 1000)
    ee_factor = num / max(1e-9, dnm)

    return {
        "T_exhaust": s.T_exhaust_C,
        "w_exhaust": s.w_exhaust,
        "RH_exhaust": max(0.0, min(s.RH_exhaust, 0.99)),
        "RH_exhaust_raw": s.RH_exhaust,
        "ee_factor": ee_factor,
        "alpha_used": s.alpha,
        "UA_kW_K": s.UA_kW_K,
        "T_wbt_i": T_wbt_i,
        "m_w": s.m_evaporated_kg_s,
        "m_a_dry": s.m_dry_air_kg_s,
        "heat_loss_form": s.heat_loss_form,
        "energy_residual": s.energy_residual_kJ_per_kg_da,
        # Defect D3 guard: a fitted result must never be reported as accuracy.
        "is_calibration_fit": bool(is_fit),
        "state": s,
    }
