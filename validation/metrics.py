"""Error metrics at raw precision.

Rounding happens only at the display layer (PLAN section 14). Rounding before
an error calculation is one of the ways a model can appear to have zero error.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ErrorMetrics:
    n: int
    rmse: float
    mae: float
    max_abs: float
    bias: float
    max_pct: float

    def better_than_or_equal(self, other: "ErrorMetrics", tol: float = 0.0) -> bool:
        """Gate G3: non-degradation requires BOTH rmse and max_abs to hold."""
        return (self.rmse <= other.rmse + tol) and (self.max_abs <= other.max_abs + tol)

    def as_row(self, label: str) -> dict:
        return {
            "policy": label,
            "n": self.n,
            "RMSE (C)": self.rmse,
            "MAE (C)": self.mae,
            "max |err| (C)": self.max_abs,
            "bias (C)": self.bias,
            "max err (%)": self.max_pct,
        }


def compute_metrics(measured: np.ndarray, predicted: np.ndarray) -> ErrorMetrics:
    y = np.asarray(measured, dtype=float)
    p = np.asarray(predicted, dtype=float)
    if y.shape != p.shape:
        raise ValueError(f"shape mismatch: {y.shape} vs {p.shape}")

    mask = np.isfinite(y) & np.isfinite(p)
    y, p = y[mask], p[mask]
    if y.size == 0:
        raise ValueError("no finite pairs to score")

    err = p - y  # signed, prediction minus measurement
    with np.errstate(divide="ignore", invalid="ignore"):
        pct = np.where(y != 0, np.abs(err) / np.abs(y) * 100.0, np.nan)

    return ErrorMetrics(
        n=int(y.size),
        rmse=float(np.sqrt(np.mean(err**2))),
        mae=float(np.mean(np.abs(err))),
        max_abs=float(np.max(np.abs(err))),
        bias=float(np.mean(err)),
        max_pct=float(np.nanmax(pct)) if np.any(np.isfinite(pct)) else float("nan"),
    )
