"""Gate T1 -- M1 must reproduce the frozen legacy EE model exactly.

Prevents defects D1, D2, D4, D5 from recurring. If someone reintroduces the
latent-heat double count, or changes the heat-loss sign, or adds a fifth copy of
the equation that drifts, these tests fail with a message that says so.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from coating_model.energy_balance import (
    PhysicsViolation,
    calculate_exhaust_state,
    solve_alpha_for_measured_exhaust,
)
from validation.acceptance import ACCEPTANCE_DIR
from validation.m0_legacy_adapter import (
    assert_frozen,
    m0_exhaust_temperature,
)

TOL = 1e-9  # PLAN gate T1


def _rows():
    df = pd.read_csv(ACCEPTANCE_DIR / "stages_v1.csv")
    return [
        dict(
            T_inlet_C=float(r.T_inlet_C),
            air_cfm=float(r.air_cfm),
            RH_inlet=float(r.RH_inlet_fraction),
            spray_rate_g_min_gun=float(r.spray_rate_g_min_gun),
            no_of_guns=int(r.no_of_guns),
            solids_fraction=float(r.solids_fraction),
            P_total_kPa=float(r.P_total_kPa),
            _alpha=float(r.alpha_ee_output),
            _measured=float(r.T_exhaust_meas_C),
            _batch=int(r.batch_index),
            _pump=int(r.pump_rpm),
        )
        for _, r in df.iterrows()
    ]


def test_legacy_reference_is_frozen():
    """The M0 baseline must never be edited."""
    assert_frozen()


@pytest.mark.parametrize("row", _rows(), ids=lambda r: f"B{r['_batch']}p{r['_pump']}")
def test_m1_equals_m0_exhaust_temperature(row):
    """T1: identical inputs and alpha must give identical exhaust temperature."""
    kw = {k: v for k, v in row.items() if not k.startswith("_")}
    m1 = calculate_exhaust_state(**kw, heat_loss_form="legacy_alpha", alpha=row["_alpha"])
    m0 = m0_exhaust_temperature(**kw, alpha=row["_alpha"])

    assert abs(m1.T_exhaust_C - m0["T_exhaust_C"]) < TOL, (
        f"M1 diverged from the frozen M0 baseline by "
        f"{abs(m1.T_exhaust_C - m0['T_exhaust_C']):.3e} C. The canonical core no "
        f"longer reproduces legacy EE -- defect D1/D2/D4 has been reintroduced."
    )


@pytest.mark.parametrize("row", _rows(), ids=lambda r: f"B{r['_batch']}p{r['_pump']}")
def test_m1_equals_m0_intermediates(row):
    """Every psychrometric intermediate must match, not just the final answer."""
    kw = {k: v for k, v in row.items() if not k.startswith("_")}
    m1 = calculate_exhaust_state(**kw, heat_loss_form="legacy_alpha", alpha=row["_alpha"])
    m0 = m0_exhaust_temperature(**kw, alpha=row["_alpha"])

    for name, got, want in [
        ("w_inlet", m1.w_inlet, m0["w_inlet"]),
        ("w_exhaust", m1.w_exhaust, m0["w_exhaust"]),
        ("m_dry_air", m1.m_dry_air_kg_s, m0["m_dry_air_kg_s"]),
        ("rho_moist", m1.rho_moist_inlet, m0["rho_moist_inlet"]),
        ("RH_exhaust", m1.RH_exhaust, m0["RH_exhaust"]),
    ]:
        assert got == pytest.approx(want, rel=1e-12, abs=1e-12), (
            f"{name}: M1 {got!r} != M0 {want!r}"
        )


def test_heat_loss_forms_agree_only_at_zero_alpha():
    """The sign defect (D2) is invisible at alpha=0 and real everywhere else."""
    kw = dict(T_inlet_C=56.507, air_cfm=2800.63, RH_inlet=0.05,
              spray_rate_g_min_gun=32.72, no_of_guns=6, solids_fraction=0.15)

    a = calculate_exhaust_state(**kw, heat_loss_form="legacy_alpha", alpha=0.0)
    b = calculate_exhaust_state(**kw, heat_loss_form="physical_ua", alpha=0.0)
    assert abs(a.T_exhaust_C - b.T_exhaust_C) < 1e-12, "adiabatic core must be identical"

    a = calculate_exhaust_state(**kw, heat_loss_form="legacy_alpha", alpha=0.149)
    b = calculate_exhaust_state(**kw, heat_loss_form="physical_ua", alpha=0.149)
    assert abs(a.T_exhaust_C - b.T_exhaust_C) > 0.5, (
        "the two heat-loss conventions must differ once alpha != 0; if they agree, "
        "the sign distinction has been lost"
    )


def test_adiabatic_is_parameter_free_and_matches_known_value():
    """Zero-parameter prediction, pinned. Regression guard against defect D1.

    The broken implementation returned 46.391 C here (5.2 C cold) because it
    double-counted the latent heat.
    """
    s = calculate_exhaust_state(
        T_inlet_C=56.507, air_cfm=2800.63, RH_inlet=0.05,
        spray_rate_g_min_gun=32.72, no_of_guns=6, solids_fraction=0.15, alpha=0.0,
    )
    assert s.T_exhaust_C == pytest.approx(51.601381, abs=1e-5), (
        "adiabatic prediction moved -- the energy balance has changed. The known "
        "failure mode is counting phase-change energy twice (defect D1), which "
        "drags this value down to ~46.39 C."
    )


def test_closed_form_alpha_reproduces_measurement():
    """The diagnostic alpha solve must be exact, and needs no optimiser."""
    kw = dict(T_inlet_C=56.507, air_cfm=2800.63, RH_inlet=0.05,
              spray_rate_g_min_gun=32.72, no_of_guns=6, solids_fraction=0.15)
    target = 48.519
    a = solve_alpha_for_measured_exhaust(target, **kw, heat_loss_form="legacy_alpha")
    back = calculate_exhaust_state(**kw, heat_loss_form="legacy_alpha", alpha=a)
    assert back.T_exhaust_C == pytest.approx(target, abs=1e-10)


def test_alpha_and_ua_are_mutually_exclusive():
    kw = dict(T_inlet_C=56.5, air_cfm=2800.0, RH_inlet=0.05,
              spray_rate_g_min_gun=32.7, no_of_guns=6, solids_fraction=0.15)
    with pytest.raises(ValueError):
        calculate_exhaust_state(**kw)
    with pytest.raises(ValueError):
        calculate_exhaust_state(**kw, alpha=0.1, UA_kW_K=0.1)


def test_ua_and_alpha_are_equivalent_at_fixed_airflow():
    """alpha = UA / m_dry_air, so the two parameterisations must agree."""
    kw = dict(T_inlet_C=56.507, air_cfm=2800.63, RH_inlet=0.05,
              spray_rate_g_min_gun=32.72, no_of_guns=6, solids_fraction=0.15)
    by_ua = calculate_exhaust_state(**kw, UA_kW_K=0.2074)
    by_alpha = calculate_exhaust_state(**kw, alpha=0.2074 / by_ua.m_dry_air_kg_s)
    assert by_ua.T_exhaust_C == pytest.approx(by_alpha.T_exhaust_C, abs=1e-12)
