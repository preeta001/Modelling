"""Stage 2 -- pump / gun calibration.

Maps a pump setpoint (RPM) to spray rate per gun, fitted from *measured* per-gun
output. This is the provenance layer for the spray rate that Stage 1 and Stage 3
consume: no downstream module should ever take a hand-typed spray rate without
recording where it came from.

Acceptance target A2 (PLAN section 0.6): the calibration must reproduce the plant
table's spray rates to < 0.005 g/min. Verified in PLAN section 2.7.

Design notes
------------
* Per-gun measurements are retained, not just their mean. The gun-to-gun spread
  is real, measured uniformity data (1.5-3.6% CV) and is the empirical input to
  the Stage 3 uniformity model.
* Extrapolation outside the calibrated RPM range is REFUSED, not silently
  returned. The fitted intercept (~3 g/min at 0 rpm) is non-physical -- a stopped
  pump delivers nothing -- so the affine model is valid only between the
  calibration points.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import numpy as np
import pandas as pd

GUN_COLUMNS = [f"gun_{i}" for i in range(1, 7)]


class SprayRateSource(str, Enum):
    """Provenance of a spray rate handed to the model."""

    MEASURED = "measured"                # weighed directly
    CALIBRATION = "from_calibration"     # m * rpm + c, inside the fitted range
    USER_OVERRIDE = "user_override"      # typed by hand -- always flagged


class ExtrapolationError(ValueError):
    """Raised when a pump RPM falls outside the calibrated range."""


@dataclass(frozen=True)
class PumpCalibration:
    """rate_per_gun (g/min/gun) = m * pump_rpm + c, valid on [rpm_min, rpm_max]."""

    batch_index: int
    m: float
    c: float
    rpm_min: float
    rpm_max: float
    n_points: int
    residual_rmse: float
    gun_cv_pct: dict[float, float] = field(default_factory=dict)
    gun_means: dict[float, float] = field(default_factory=dict)
    gun_outlier_index: dict[float, list[int]] = field(default_factory=dict)

    @property
    def dof(self) -> int:
        """Degrees of freedom. Zero means exact interpolation: linearity untested."""
        return self.n_points - 2

    @property
    def is_exact_interpolation(self) -> bool:
        return self.dof <= 0

    def spray_rate_per_gun(
        self, pump_rpm: float, allow_extrapolation: bool = False
    ) -> float:
        """Spray rate per gun (g/min) at the given pump setpoint.

        Refuses to extrapolate by default. The intercept is non-physical, so a
        value returned outside the calibrated range would be meaningless while
        looking perfectly reasonable.
        """
        if not allow_extrapolation and not (self.rpm_min <= pump_rpm <= self.rpm_max):
            raise ExtrapolationError(
                f"pump_rpm={pump_rpm} is outside the calibrated range "
                f"[{self.rpm_min}, {self.rpm_max}] for batch {self.batch_index}. "
                f"The fitted intercept c={self.c:.3f} g/min at 0 rpm is non-physical, "
                f"so this calibration must not be extrapolated. Supply calibration "
                f"points covering {pump_rpm} rpm, or pass allow_extrapolation=True "
                f"and treat the result as unvalidated."
            )
        return self.m * pump_rpm + self.c

    def total_spray_rate(self, pump_rpm: float, no_of_guns: int, **kw) -> float:
        """Total spray rate (g/min) across all guns."""
        return self.spray_rate_per_gun(pump_rpm, **kw) * no_of_guns

    def required_rpm(self, target_rate_per_gun: float) -> float:
        """Inverse: pump RPM needed for a target per-gun rate."""
        if abs(self.m) < 1e-12:
            raise ValueError("Degenerate calibration: slope is zero.")
        rpm = (target_rate_per_gun - self.c) / self.m
        if not (self.rpm_min <= rpm <= self.rpm_max):
            raise ExtrapolationError(
                f"target {target_rate_per_gun} g/min/gun needs {rpm:.2f} rpm, outside "
                f"the calibrated range [{self.rpm_min}, {self.rpm_max}]."
            )
        return rpm

    def warnings(self) -> list[str]:
        out: list[str] = []
        if self.is_exact_interpolation:
            out.append(
                f"Batch {self.batch_index}: fitted from {self.n_points} setpoints "
                f"(dof={self.dof}). The fit is exact interpolation and linearity is "
                f"untested. Add a third setpoint to test it."
            )
        if self.c > 0.5:
            out.append(
                f"Batch {self.batch_index}: intercept c={self.c:.3f} g/min at 0 rpm is "
                f"non-physical (a stopped pump delivers nothing). Extrapolation below "
                f"{self.rpm_min} rpm is refused."
            )
        for rpm, cv in sorted(self.gun_cv_pct.items()):
            if cv > 5.0:
                out.append(
                    f"Batch {self.batch_index} @ {rpm} rpm: gun-to-gun CV {cv:.2f}% "
                    f"exceeds 5% -- check for a blocked or worn nozzle."
                )
        for rpm, idx in sorted(self.gun_outlier_index.items()):
            if idx:
                out.append(
                    f"Batch {self.batch_index} @ {rpm} rpm: gun(s) "
                    f"{[i + 1 for i in idx]} are statistical outliers -- check for a "
                    f"blocked or worn nozzle."
                )
        return out


def fit_pump_calibration(
    pump_rpm: np.ndarray, per_gun: np.ndarray, batch_index: int = 0
) -> PumpCalibration:
    """Least-squares fit of per-gun spray rate against pump RPM.

    Parameters
    ----------
    pump_rpm : (n_points,) setpoints
    per_gun  : (n_points, n_guns) measured rate per gun, g/min
    """
    pump_rpm = np.asarray(pump_rpm, dtype=float)
    per_gun = np.asarray(per_gun, dtype=float)
    if per_gun.ndim != 2:
        raise ValueError("per_gun must be 2-D: (n_points, n_guns)")
    if len(pump_rpm) != per_gun.shape[0]:
        raise ValueError("pump_rpm and per_gun disagree on the number of setpoints")
    if len(pump_rpm) < 2:
        raise ValueError("At least two setpoints are needed to fit a line")

    means = per_gun.mean(axis=1)
    m, c = np.polyfit(pump_rpm, means, 1)

    resid = means - (m * pump_rpm + c)
    rmse = float(np.sqrt(np.mean(resid**2)))

    cv, gm, out_idx = {}, {}, {}
    for i, rpm in enumerate(pump_rpm):
        row = per_gun[i]
        gm[float(rpm)] = float(row.mean())
        cv[float(rpm)] = (
            float(row.std(ddof=1) / row.mean() * 100.0) if len(row) > 1 else 0.0
        )
        out_idx[float(rpm)] = gun_outliers(row)

    return PumpCalibration(
        batch_index=int(batch_index),
        m=float(m),
        c=float(c),
        rpm_min=float(pump_rpm.min()),
        rpm_max=float(pump_rpm.max()),
        n_points=int(len(pump_rpm)),
        residual_rmse=rmse,
        gun_cv_pct=cv,
        gun_means=gm,
        gun_outlier_index=out_idx,
    )


def gun_outliers(per_gun_row: np.ndarray, threshold: float = 3.5) -> list[int]:
    """Indices (0-based) of guns whose output is anomalous -- a blocked or worn nozzle.

    Uses the median / MAD modified z-score (Iglewicz & Hoaglin), NOT a mean/σ
    z-score, because a mean/σ rule cannot work at this sample size.

    With n guns, the largest attainable z-score is (n-1)/sqrt(n). For n = 6 that
    is **2.04**, so a "3-sigma" rule can never fire no matter how badly one gun
    is blocked: the outlier inflates σ enough to mask itself. A gun delivering
    12 g/min against five delivering ~45 scores z = 2.04 and passes.

    The median and MAD are insensitive to a minority of gross outliers, so the
    same case scores a modified z of ~297 and is caught.
    """
    v = np.asarray(per_gun_row, dtype=float)
    if v.size < 3:
        return []
    med = np.median(v)
    mad = np.median(np.abs(v - med))
    if mad < 1e-12:
        # Degenerate spread: fall back to an absolute relative-deviation rule so
        # identical readings plus one rogue gun are still caught.
        if med == 0.0:
            return []
        rel = np.abs(v - med) / abs(med)
        return [int(i) for i in np.where(rel > 0.10)[0]]
    modified_z = 0.6745 * np.abs(v - med) / mad
    return [int(i) for i in np.where(modified_z > threshold)[0]]


def mean_gun_cv_pct(cal: PumpCalibration) -> float:
    """Mean gun-to-gun CV across setpoints -- the measured uniformity floor."""
    return float(np.mean(list(cal.gun_cv_pct.values()))) if cal.gun_cv_pct else 0.0


def load_calibrations(csv_path: str | Path) -> dict[int, PumpCalibration]:
    """Load per-batch calibrations from a gun-measurement CSV."""
    df = pd.read_csv(csv_path)
    missing = [c for c in ["batch_index", "pump_rpm", *GUN_COLUMNS] if c not in df.columns]
    if missing:
        raise ValueError(f"gun calibration file is missing columns: {missing}")

    out: dict[int, PumpCalibration] = {}
    for b, g in df.groupby("batch_index"):
        out[int(b)] = fit_pump_calibration(
            g["pump_rpm"].to_numpy(dtype=float),
            g[GUN_COLUMNS].to_numpy(dtype=float),
            batch_index=int(b),
        )
    return out


@dataclass(frozen=True)
class SprayRate:
    """A spray rate together with where it came from."""

    value_g_min_gun: float
    source: SprayRateSource
    detail: str = ""

    @property
    def is_traceable(self) -> bool:
        return self.source is not SprayRateSource.USER_OVERRIDE


def spray_rate_for_stage(
    calibrations: dict[int, PumpCalibration],
    batch_index: int,
    pump_rpm: float,
    override: float | None = None,
) -> SprayRate:
    """Resolve the spray rate for a stage, recording its provenance."""
    if override is not None:
        return SprayRate(
            float(override),
            SprayRateSource.USER_OVERRIDE,
            "typed by hand; not traceable to a gun measurement",
        )
    cal = calibrations.get(int(batch_index))
    if cal is None:
        raise KeyError(
            f"No pump calibration for batch {batch_index}. Run Stage 2 first, or "
            f"supply an explicit override (which will be flagged as untraceable)."
        )
    return SprayRate(
        cal.spray_rate_per_gun(pump_rpm),
        SprayRateSource.CALIBRATION,
        f"m={cal.m:.8f}, c={cal.c:.8f}, batch {batch_index}, {pump_rpm} rpm",
    )
