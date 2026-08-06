"""Stage 2 gates S2-G1..G4 (PLAN section 7.3)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from coating_model.gun_calibration import (
    ExtrapolationError,
    SprayRateSource,
    fit_pump_calibration,
    gun_outliers,
    load_calibrations,
    mean_gun_cv_pct,
    spray_rate_for_stage,
)
from validation.acceptance import ACCEPTANCE_DIR


@pytest.fixture(scope="module")
def cals():
    return load_calibrations(ACCEPTANCE_DIR / "gun_calibration_v1.csv")


@pytest.fixture(scope="module")
def stages():
    return pd.read_csv(ACCEPTANCE_DIR / "stages_v1.csv")


def test_s2_g1_recomputed_fit_matches_plant_record(cals):
    """S2-G1: our m and c must reproduce the plant's to 1e-6."""
    df = pd.read_csv(ACCEPTANCE_DIR / "gun_calibration_v1.csv")
    for b, g in df.groupby("batch_index"):
        cal = cals[int(b)]
        assert cal.m == pytest.approx(float(g.m_shown.iloc[0]), abs=1e-6)
        assert cal.c == pytest.approx(float(g.c_shown.iloc[0]), abs=1e-6)


def test_s2_g2_calibration_reproduces_plant_spray_rates(cals, stages):
    """S2-G2 / acceptance target A2: < 0.005 g/min on all 12 stages."""
    worst = 0.0
    for _, r in stages.iterrows():
        pred = cals[int(r.batch_index)].spray_rate_per_gun(float(r.pump_rpm))
        worst = max(worst, abs(pred - float(r.spray_rate_g_min_gun)))
    assert worst < 0.005, f"worst spray-rate deviation {worst:.5f} g/min exceeds 0.005"


def test_s2_g3_extrapolation_is_refused(cals):
    """S2-G3: outside the calibrated range the model must refuse, not guess."""
    cal = cals[1]
    assert cal.rpm_min == 5.0 and cal.rpm_max == 10.0

    for rpm in (0.0, 4.9, 10.1, 25.0):
        with pytest.raises(ExtrapolationError):
            cal.spray_rate_per_gun(rpm)

    # ...and must still work inside it
    for rpm in (5.0, 7.0, 9.0, 10.0):
        assert cal.spray_rate_per_gun(rpm) > 0.0

    # explicit opt-out is allowed but the caller has to ask for it
    assert cal.spray_rate_per_gun(0.0, allow_extrapolation=True) == pytest.approx(cal.c)


def test_zero_rpm_intercept_is_flagged_as_non_physical(cals):
    """A stopped pump delivers nothing; a positive intercept must be warned about."""
    for cal in cals.values():
        assert cal.c > 0.5
        assert any("non-physical" in w for w in cal.warnings())


def test_two_point_fit_is_flagged_as_zero_dof(cals):
    for cal in cals.values():
        assert cal.n_points == 2
        assert cal.dof == 0
        assert cal.is_exact_interpolation
        assert any("exact interpolation" in w for w in cal.warnings())


def test_s2_g4_gun_cv_is_computed_and_in_expected_range(cals):
    """S2-G4: measured gun-to-gun CV, the empirical uniformity input."""
    for b, cal in cals.items():
        assert set(cal.gun_cv_pct) == {5.0, 10.0}
        for cv in cal.gun_cv_pct.values():
            assert 0.5 < cv < 10.0, f"batch {b} gun CV {cv} is implausible"
    overall = [mean_gun_cv_pct(c) for c in cals.values()]
    assert 1.0 < min(overall) and max(overall) < 5.0


def test_outlier_detection_finds_a_planted_blocked_nozzle():
    rpm = np.array([5.0, 10.0])
    per_gun = np.array([[24.0, 24.1, 23.9, 24.05, 23.95, 24.0],
                        [45.0, 45.1, 44.9, 45.05, 44.95, 12.0]])  # gun 6 blocked
    assert gun_outliers(per_gun[1]) == [5]
    assert gun_outliers(per_gun[0]) == []
    cal = fit_pump_calibration(rpm, per_gun, batch_index=99)
    assert any("nozzle" in w for w in cal.warnings())


def test_required_rpm_is_the_exact_inverse(cals):
    cal = cals[1]
    for rpm in (5.5, 7.0, 8.3, 9.9):
        rate = cal.spray_rate_per_gun(rpm)
        assert cal.required_rpm(rate) == pytest.approx(rpm, abs=1e-10)


def test_spray_rate_provenance_is_recorded(cals):
    got = spray_rate_for_stage(cals, batch_index=1, pump_rpm=7)
    assert got.source is SprayRateSource.CALIBRATION
    assert got.is_traceable
    assert got.value_g_min_gun == pytest.approx(32.7194, abs=1e-3)

    typed = spray_rate_for_stage(cals, batch_index=1, pump_rpm=7, override=99.0)
    assert typed.source is SprayRateSource.USER_OVERRIDE
    assert not typed.is_traceable, "a hand-typed rate must never look traceable"

    with pytest.raises(KeyError):
        spray_rate_for_stage(cals, batch_index=999, pump_rpm=7)


def test_fit_rejects_degenerate_input():
    with pytest.raises(ValueError):
        fit_pump_calibration(np.array([5.0]), np.array([[24.0, 24.1]]))
    with pytest.raises(ValueError):
        fit_pump_calibration(np.array([5.0, 10.0]), np.array([24.0, 45.0]))
