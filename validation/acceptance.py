"""Acceptance-test harness (PLAN section 0).

The plant data is a TEST set, not a training set. This module mechanically
enforces the two rules that keep that claim honest:

1. **The SEALED batch cannot be touched by accident.** Any run that would score
   against it must pass `unseal=True` and give a reason, which is logged. The
   default path physically cannot see it.

2. **Calibration and prediction are never reported together as one number.**
   A parameter fitted to the row it predicts yields a *calibration residual*
   (target T2); a parameter locked before the row is seen yields a *prediction
   error* (target T3). They live in separate result objects with separate labels.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
import pandas as pd

from .metrics import ErrorMetrics, compute_metrics

REPO = Path(__file__).resolve().parents[1]
ACCEPTANCE_DIR = REPO / "data" / "acceptance"

ROLE_CALIBRATION = "calibration"
ROLE_DEVELOPMENT = "development"
ROLE_SEALED = "SEALED"

#: Only these columns may be scored against. Everything else in the source table
#: is either a model input or the OLD model's output (PLAN DEC-5).
VALID_TARGETS = {"T_exhaust_meas_C", "cycle_time_h", "weight_gain_pct", "assay_pct"}


class SealedDataError(RuntimeError):
    """Raised on an attempt to score against the sealed batch without unsealing."""


class InvalidTargetError(ValueError):
    """Raised when scoring against a column that is not ground truth."""


def load_acceptance_set(path: Path | None = None) -> pd.DataFrame:
    df = pd.read_csv(path or ACCEPTANCE_DIR / "stages_v1.csv")
    if "acceptance_role" not in df.columns:
        raise ValueError("acceptance set is missing the acceptance_role column")
    return df


def visible_rows(df: pd.DataFrame, unseal: bool = False) -> pd.DataFrame:
    """Rows the caller is allowed to see. The sealed batch is withheld by default."""
    return df if unseal else df[df.acceptance_role != ROLE_SEALED].copy()


@dataclass
class AcceptanceResult:
    """Outcome of scoring a model against the acceptance set."""

    label: str
    kind: str  # "calibration_residual" | "locked_prediction"
    target: str
    per_row: pd.DataFrame
    overall: ErrorMetrics
    by_role: dict[str, ErrorMetrics] = field(default_factory=dict)
    sealed_included: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def is_prediction(self) -> bool:
        return self.kind == "locked_prediction"

    def headline(self) -> str:
        tag = "PREDICTION" if self.is_prediction else "CALIBRATION FIT (not accuracy)"
        return (
            f"{self.label}: RMSE {self.overall.rmse:.4f} C, "
            f"max |err| {self.overall.max_abs:.4f} C, "
            f"bias {self.overall.bias:+.4f} C  [{tag}]"
        )


def _score(
    df: pd.DataFrame,
    predictions: np.ndarray,
    *,
    label: str,
    kind: str,
    target: str,
    sealed_included: bool,
    extra: dict[str, np.ndarray] | None = None,
) -> AcceptanceResult:
    if target not in VALID_TARGETS:
        raise InvalidTargetError(
            f"{target!r} is not ground truth. Valid targets: {sorted(VALID_TARGETS)}. "
            f"Columns ending in _ee_output are the OLD model's output (PLAN DEC-5) "
            f"and scoring against them would validate this model against EE, not "
            f"against the plant."
        )

    measured = df[target].to_numpy(dtype=float)
    err = predictions - measured

    per_row = pd.DataFrame(
        {
            "batch": df.batch_index.to_numpy(),
            "role": df.acceptance_role.to_numpy(),
            "pump_rpm": df.pump_rpm.to_numpy(),
            "measured": measured,
            "predicted": predictions,
            "signed_err": err,
            "abs_err": np.abs(err),
            "pct_err": np.abs(err) / np.abs(measured) * 100.0,
        }
    )
    if extra:
        for k, v in extra.items():
            per_row[k] = v

    by_role = {
        role: compute_metrics(g.measured.to_numpy(), g.predicted.to_numpy())
        for role, g in per_row.groupby("role")
    }

    return AcceptanceResult(
        label=label,
        kind=kind,
        target=target,
        per_row=per_row,
        overall=compute_metrics(measured, predictions),
        by_role=by_role,
        sealed_included=sealed_included,
    )


def run_calibration_fit(
    df: pd.DataFrame,
    fit_and_predict: Callable[[pd.Series], tuple[float, float]],
    *,
    label: str,
    target: str = "T_exhaust_meas_C",
    unseal: bool = False,
) -> AcceptanceResult:
    """Per-row fitting. Produces a CALIBRATION RESIDUAL, never an accuracy figure.

    `fit_and_predict(row) -> (prediction, fitted_parameter)`. This is what the
    legacy EE table does, and it is why that table reports 0.000.
    """
    rows = visible_rows(df, unseal)
    preds, params = [], []
    for _, r in rows.iterrows():
        p, theta = fit_and_predict(r)
        preds.append(p)
        params.append(theta)

    res = _score(
        rows,
        np.asarray(preds, dtype=float),
        label=label,
        kind="calibration_residual",
        target=target,
        sealed_included=unseal,
        extra={"fitted_param": np.asarray(params, dtype=float)},
    )
    res.notes.append(
        "Each row was given its own free parameter chosen to reproduce that row's "
        "own measurement. Zero degrees of freedom remain, so a near-zero error is "
        "arithmetically guaranteed and says nothing about predictive skill."
    )
    return res


def run_locked_prediction(
    df: pd.DataFrame,
    predict: Callable[[pd.Series], float],
    *,
    label: str,
    target: str = "T_exhaust_meas_C",
    unseal: bool = False,
    unseal_reason: str = "",
) -> AcceptanceResult:
    """Score a model whose parameters were locked BEFORE these rows were seen."""
    if unseal and not unseal_reason:
        raise SealedDataError(
            "Unsealing the final acceptance batch requires an explicit reason. "
            "It may be used exactly once, at the end (PLAN section 0.4)."
        )
    rows = visible_rows(df, unseal)
    preds = np.asarray([predict(r) for _, r in rows.iterrows()], dtype=float)

    res = _score(
        rows,
        preds,
        label=label,
        kind="locked_prediction",
        target=target,
        sealed_included=unseal,
    )
    if unseal:
        res.notes.append(f"SEALED BATCH INCLUDED. Reason: {unseal_reason}")
    else:
        res.notes.append(
            f"Sealed batch withheld ({int((df.acceptance_role == ROLE_SEALED).sum())} "
            f"rows not scored)."
        )
    return res


def check_non_degradation(
    candidate: AcceptanceResult,
    baseline: AcceptanceResult,
    *,
    parsimony_threshold: float = 0.05,
) -> dict[str, object]:
    """Gates G3 and G5 (PLAN section 5).

    G3: the candidate's RMSE **and** max error must both be <= the baseline's.
    G5: to justify a new parameter the RMSE gain must exceed measurement noise.
    """
    if not candidate.is_prediction or not baseline.is_prediction:
        raise ValueError(
            "Non-degradation can only be assessed between locked predictions. "
            "Comparing against a calibration residual is meaningless."
        )

    d_rmse = baseline.overall.rmse - candidate.overall.rmse
    d_max = baseline.overall.max_abs - candidate.overall.max_abs
    g3 = candidate.overall.better_than_or_equal(baseline.overall)
    g5 = d_rmse >= parsimony_threshold

    return {
        "G3_non_degradation": bool(g3),
        "G5_parsimony": bool(g5),
        "delta_rmse": float(d_rmse),
        "delta_max_abs": float(d_max),
        "verdict": (
            "RETAIN" if (g3 and g5)
            else "RETAIN (neutral, no new parameter)" if g3
            else "REJECT"
        ),
        "reason": (
            f"RMSE {candidate.overall.rmse:.4f} vs baseline {baseline.overall.rmse:.4f} "
            f"(delta {d_rmse:+.4f}); max {candidate.overall.max_abs:.4f} vs "
            f"{baseline.overall.max_abs:.4f} (delta {d_max:+.4f})"
        ),
    }
