"""Gate G2 -- conservation and physical bounds.

Replaces the old tests/test_energy_balance.py, whose only assertion was that a
temperature went down (defect D16). These close actual budgets.
"""
from __future__ import annotations

import numpy as np
import pytest

from coating_model.energy_balance import (
    H_LIQUID_WATER_AT_25C,
    PhysicsViolation,
    calculate_exhaust_state,
)
from coating_model.constants import Cp_air
from coating_model.solvent_properties import get_solvent

BASE = dict(T_inlet_C=56.507, air_cfm=2800.63, RH_inlet=0.05,
            spray_rate_g_min_gun=32.72, no_of_guns=6, solids_fraction=0.15)

GRID = [
    dict(T_inlet_C=t, air_cfm=c, RH_inlet=rh, spray_rate_g_min_gun=s,
         no_of_guns=6, solids_fraction=f)
    for t in (40.0, 56.5, 75.0)
    for c in (1200.0, 2800.0)
    for rh in (0.02, 0.05, 0.40)
    for s in (0.0, 32.72, 90.0)
    for f in (0.10, 0.15)
]


@pytest.mark.parametrize("form", ["physical_ua", "legacy_alpha"])
@pytest.mark.parametrize("alpha", [0.0, 0.05, 0.149, 0.5])
def test_energy_balance_closes(form, alpha):
    """The solved state must satisfy the balance it was derived from."""
    s = calculate_exhaust_state(**BASE, heat_loss_form=form, alpha=alpha)
    assert abs(s.energy_residual_kJ_per_kg_da) < 1e-9, (
        f"energy balance does not close: residual "
        f"{s.energy_residual_kJ_per_kg_da:.3e} kJ/kg-da. A term is double-counted "
        f"or missing -- this is the signature of defect D1."
    )


@pytest.mark.parametrize("case", GRID, ids=lambda c: "x".join(str(v) for v in c.values()))
def test_physical_bounds_across_operating_grid(case):
    """No physically impossible state anywhere in a wide operating envelope."""
    s = calculate_exhaust_state(**case, alpha=0.1)
    assert s.w_inlet >= 0.0
    assert s.w_exhaust >= s.w_inlet
    assert s.m_dry_air_kg_s > 0.0
    assert s.rho_moist_inlet > 0.0
    assert s.m_evaporated_kg_s >= 0.0
    assert np.isfinite(s.T_exhaust_C)
    assert s.RH_exhaust >= 0.0
    assert abs(s.energy_residual_kJ_per_kg_da) < 1e-8


def test_water_mass_balance_closes():
    """Evaporated water must equal the humidity the air picks up."""
    s = calculate_exhaust_state(**BASE, alpha=0.1)
    picked_up = s.m_dry_air_kg_s * (s.w_exhaust - s.w_inlet)
    assert picked_up == pytest.approx(s.m_evaporated_kg_s, rel=1e-12)


def test_solvent_mass_split_is_consistent():
    """Sprayed solvent = evaporated + not-evaporated, exactly."""
    for frac in (0.0, 0.5, 0.8, 1.0):
        s = calculate_exhaust_state(**BASE, alpha=0.1, evaporated_fraction=frac)
        assert s.m_evaporated_kg_s == pytest.approx(
            s.m_solvent_sprayed_kg_s * frac, rel=1e-12
        )
        assert s.m_evaporated_kg_s <= s.m_solvent_sprayed_kg_s + 1e-15


def test_zero_spray_gives_no_humidification_and_no_cooling():
    """With no spray and no heat loss, exhaust must equal inlet."""
    s = calculate_exhaust_state(
        **{**BASE, "spray_rate_g_min_gun": 0.0}, alpha=0.0
    )
    assert s.w_exhaust == pytest.approx(s.w_inlet, abs=1e-15)
    assert s.T_exhaust_C == pytest.approx(s.T_inlet_recovered(), abs=1e-9) if hasattr(
        s, "T_inlet_recovered"
    ) else s.T_exhaust_C == pytest.approx(56.507, abs=1e-9)


def test_more_spray_means_more_cooling():
    """Monotonicity: evaporative cooling must increase with spray rate."""
    temps = [
        calculate_exhaust_state(**{**BASE, "spray_rate_g_min_gun": s}, alpha=0.1).T_exhaust_C
        for s in (0.0, 20.0, 40.0, 60.0, 80.0)
    ]
    assert all(a > b for a, b in zip(temps, temps[1:])), (
        f"exhaust temperature must fall as spray rate rises, got {temps}"
    )


def test_heat_loss_responds_correctly_to_ambient():
    """The physical form must lose MORE heat when ambient is colder.

    The legacy form gets this backwards (defect D2). This test pins the correct
    behaviour so a future 'simplification' cannot quietly restore the bug.
    """
    warm = calculate_exhaust_state(**BASE, heat_loss_form="physical_ua",
                                   alpha=0.15, T_amb_C=35.0)
    cold = calculate_exhaust_state(**BASE, heat_loss_form="physical_ua",
                                   alpha=0.15, T_amb_C=5.0)
    assert cold.q_loss_kJ_per_kg_da > warm.q_loss_kJ_per_kg_da
    assert cold.T_exhaust_C < warm.T_exhaust_C

    lw = calculate_exhaust_state(**BASE, heat_loss_form="legacy_alpha",
                                 alpha=0.15, T_amb_C=35.0)
    lc = calculate_exhaust_state(**BASE, heat_loss_form="legacy_alpha",
                                 alpha=0.15, T_amb_C=5.0)
    assert lc.q_loss_kJ_per_kg_da < lw.q_loss_kJ_per_kg_da, (
        "the legacy form is expected to respond to ambient backwards; if it no "
        "longer does, the two forms are no longer distinct"
    )


def test_liquid_enthalpy_is_used_not_vapour_enthalpy():
    """Guards the exact defect D1: the inlet water term must be LIQUID enthalpy."""
    s = calculate_exhaust_state(**BASE, alpha=0.0)
    expected = (s.w_exhaust - s.w_inlet) * H_LIQUID_WATER_AT_25C
    assert s.term_liquid_in == pytest.approx(expected, rel=1e-12)

    solvent = get_solvent("water")
    vapour_at_25 = solvent.enthalpy_A * 25.0 + solvent.enthalpy_B
    assert H_LIQUID_WATER_AT_25C < 200.0 < vapour_at_25, (
        "liquid and vapour enthalpies must not be confusable in magnitude"
    )


def test_invalid_inputs_are_rejected():
    with pytest.raises(ValueError):
        calculate_exhaust_state(**{**BASE, "RH_inlet": 1.5}, alpha=0.0)
    with pytest.raises(ValueError):
        calculate_exhaust_state(**{**BASE, "solids_fraction": 1.0}, alpha=0.0)
    with pytest.raises(ValueError):
        calculate_exhaust_state(**BASE, alpha=0.0, evaporated_fraction=1.2)
