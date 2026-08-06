"""Tests for the acceptance-test discipline itself (PLAN section 0).

The harness is what keeps the held-out claim honest, so it needs tests as much
as the physics does.
"""
from __future__ import annotations

import numpy as np
import pytest

from validation.acceptance import (
    ROLE_SEALED,
    InvalidTargetError,
    SealedDataError,
    check_non_degradation,
    load_acceptance_set,
    run_locked_prediction,
    visible_rows,
)
from validation.metrics import compute_metrics


@pytest.fixture(scope="module")
def df():
    return load_acceptance_set()


def test_sealed_batch_is_withheld_by_default(df):
    vis = visible_rows(df)
    assert len(vis) == 9
    assert ROLE_SEALED not in set(vis.acceptance_role)
    assert 4 not in set(vis.batch_index), "batch 4 is sealed and must not be visible"


def test_sealed_batch_requires_an_explicit_reason(df):
    with pytest.raises(SealedDataError):
        run_locked_prediction(
            df, lambda r: 48.0, label="peek", unseal=True, unseal_reason=""
        )
    res = run_locked_prediction(
        df, lambda r: 48.0, label="final", unseal=True,
        unseal_reason="final acceptance run, one time only",
    )
    assert res.sealed_included
    assert len(res.per_row) == 12
    assert any("SEALED BATCH INCLUDED" in n for n in res.notes)


def test_ee_output_columns_cannot_be_validation_targets(df):
    """DEC-5: scoring against the old model's output must be impossible."""
    for bad in ("RH_exhaust_ee_output", "alpha_ee_output", "ee_factor_ee_output"):
        with pytest.raises(InvalidTargetError):
            run_locked_prediction(df, lambda r: 0.1, label="bad", target=bad)


def test_measured_column_is_accepted_as_target(df):
    res = run_locked_prediction(
        df, lambda r: float(r.T_exhaust_meas_C), label="oracle"
    )
    assert res.overall.rmse == pytest.approx(0.0, abs=1e-12)
    assert res.is_prediction


def test_non_degradation_rejects_a_worse_model(df):
    base = run_locked_prediction(df, lambda r: 48.5, label="base")
    worse = run_locked_prediction(df, lambda r: 45.0, label="worse")
    verdict = check_non_degradation(worse, base)
    assert verdict["G3_non_degradation"] is False
    assert verdict["verdict"] == "REJECT"


def test_non_degradation_requires_both_rmse_and_max(df):
    """G3 is not satisfied by improving the average while a single row worsens."""
    measured = df[df.acceptance_role != ROLE_SEALED].T_exhaust_meas_C.to_numpy()

    base_pred = measured + np.array([0.5] * len(measured))
    cand_pred = measured + np.array([0.0] * (len(measured) - 1) + [1.4])

    base = compute_metrics(measured, base_pred)
    cand = compute_metrics(measured, cand_pred)
    assert cand.rmse < base.rmse, "candidate has the better average"
    assert cand.max_abs > base.max_abs, "but a worse worst case"
    assert not cand.better_than_or_equal(base), "G3 must reject it"


def test_parsimony_gate_blocks_a_trivial_improvement(df):
    base = run_locked_prediction(df, lambda r: float(r.T_exhaust_meas_C) + 0.50,
                                 label="base")
    tiny = run_locked_prediction(df, lambda r: float(r.T_exhaust_meas_C) + 0.49,
                                 label="tiny gain")
    v = check_non_degradation(tiny, base)
    assert v["G3_non_degradation"] is True
    assert v["G5_parsimony"] is False
    assert v["verdict"] == "RETAIN (neutral, no new parameter)"


def test_calibration_residual_cannot_be_compared_to_a_prediction(df):
    from validation.acceptance import run_calibration_fit

    cal = run_calibration_fit(
        df, lambda r: (float(r.T_exhaust_meas_C), 0.1), label="perfect fit"
    )
    pred = run_locked_prediction(df, lambda r: 48.5, label="honest")
    assert cal.overall.rmse == pytest.approx(0.0, abs=1e-12)
    with pytest.raises(ValueError):
        check_non_degradation(cal, pred)
    with pytest.raises(ValueError):
        check_non_degradation(pred, cal)


def test_acceptance_roles_are_exactly_as_planned(df):
    counts = df.groupby("acceptance_role").batch_index.nunique().to_dict()
    assert counts == {"calibration": 1, "development": 2, "SEALED": 1}
