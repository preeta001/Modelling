"""Stage 0 acceptance-set verification.

Recomputes every derived column in the plant record from its raw inputs and
reports any cell that does not reconcile. This script asserts nothing about
physics -- it only checks that the transcribed dataset is internally consistent
with itself, and that its provenance labelling is complete.

Per PLAN DEC-4 this data is an ACCEPTANCE TEST SET, not a training set.
Per PLAN DEC-5 only MEASURED / LAB_RESULT columns may be validation targets;
EE_OUTPUT columns are the old model's output and are never targets.

Run:  python scripts/step0_verify_data.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "data" / "acceptance"

# Tolerances are DERIVED from the display-rounding budget of the source table,
# not guessed. Each displayed value carries a half-ulp of its last shown digit,
# and that error propagates through the arithmetic being checked.
#
#   spray rate per gun shown to 2 dp -> +/- 0.005 g/min
#   total spray rate   shown to 1 dp -> +/- 0.05  g/min
#   solution sprayed   shown to 2 dp -> +/- 0.005 kg
#   stage time         shown to 0 dp -> +/- 0.5   min
#   cycle time         shown to 1 dp -> +/- 0.05  h
HALF_ULP_RATE_GUN = 0.005
HALF_ULP_RATE_TOTAL = 0.05
HALF_ULP_SPRAYED = 0.005
HALF_ULP_TIME_MIN = 0.5
TOL_CYCLE_H = 0.05 + 3 * HALF_ULP_TIME_MIN / 60.0   # 3 stages summed
TOL_GUN_FIT = 1e-6          # m and c are quoted to 8 dp


def tol_spray_total(no_of_guns: float) -> float:
    """Tolerance on (rate_per_gun x guns) vs the shown total.

    The plant computes the total from the FULL-PRECISION per-gun rate, but the
    table only shows that rate to 2 dp -- so re-multiplying the displayed value
    magnifies its rounding error by the gun count. Ignoring this produces a
    false failure (e.g. B3 pump 9: 41.0570 x 6 = 246.342 -> shown 246.3, while
    41.06 x 6 = 246.36).
    """
    return no_of_guns * HALF_ULP_RATE_GUN + HALF_ULP_RATE_TOTAL


def tol_solution_kg(stage_time_min: float) -> float:
    """Tolerance on (total rate x time / 1000) vs the shown solution sprayed."""
    return (HALF_ULP_RATE_TOTAL * stage_time_min / 1000.0
            + HALF_ULP_RATE_TOTAL * 0.0
            + HALF_ULP_SPRAYED)


class Report:
    def __init__(self) -> None:
        self.checks = 0
        self.failures: list[str] = []
        self.notes: list[str] = []

    def check(self, ok: bool, label: str, detail: str = "") -> None:
        self.checks += 1
        if not ok:
            self.failures.append(f"{label}: {detail}")

    def note(self, text: str) -> None:
        self.notes.append(text)

    def summary(self) -> int:
        print()
        print("=" * 78)
        print(f"  checks run   : {self.checks}")
        print(f"  failures     : {len(self.failures)}")
        print(f"  observations : {len(self.notes)}")
        print("=" * 78)
        for f in self.failures:
            print(f"  FAIL  {f}")
        for n in self.notes:
            print(f"  NOTE  {n}")
        print()
        return 1 if self.failures else 0


def verify_stages(rep: Report) -> pd.DataFrame:
    df = pd.read_csv(DATA / "stages_v1.csv")
    print("\n--- stages_v1.csv --------------------------------------------------")
    print(f"{'batch':>5} {'pump':>4} {'guns*rate':>10} {'shown':>8} {'d':>7} "
          f"{'rate*t/1000':>12} {'shown':>8} {'d':>7}")

    for _, r in df.iterrows():
        # (a) total spray rate = per-gun rate x gun count
        total_calc = r.spray_rate_g_min_gun * r.no_of_guns
        d_total = total_calc - r.spray_rate_total_g_min_reported
        rep.check(
            abs(d_total) <= tol_spray_total(r.no_of_guns),
            f"B{r.batch_index} pump{r.pump_rpm} total spray rate",
            f"calc {total_calc:.2f} vs shown {r.spray_rate_total_g_min_reported:.1f} "
            f"(tol {tol_spray_total(r.no_of_guns):.3f})",
        )

        # (b) solution sprayed = total rate x stage time
        sprayed_calc = r.spray_rate_total_g_min_reported * r.stage_time_min / 1000.0
        d_spray = sprayed_calc - r.solution_sprayed_kg
        rep.check(
            abs(d_spray) <= tol_solution_kg(r.stage_time_min),
            f"B{r.batch_index} pump{r.pump_rpm} solution sprayed",
            f"calc {sprayed_calc:.3f} vs shown {r.solution_sprayed_kg:.2f} "
            f"(tol {tol_solution_kg(r.stage_time_min):.3f})",
        )

        print(f"{int(r.batch_index):>5} {int(r.pump_rpm):>4} {total_calc:>10.2f} "
              f"{r.spray_rate_total_g_min_reported:>8.1f} {d_total:>+7.2f} "
              f"{sprayed_calc:>12.3f} {r.solution_sprayed_kg:>8.2f} {d_spray:>+7.3f}")

    # (c) batch-level totals
    print("\n--- batch reconciliation -------------------------------------------")
    print(f"{'batch':>5} {'sum sprayed':>12} {'shown':>8} {'nominal sol':>12} "
          f"{'delta %':>8} {'cycle calc':>11} {'shown':>7} {'core@eta=1':>11}")

    core_masses = []
    for b, g in df.groupby("batch_index"):
        sum_sprayed = g.solution_sprayed_kg.sum()
        shown_total = g.total_sprayed_kg.iloc[0]
        nominal = g.solution_mass_nominal_kg.iloc[0]
        cycle_calc = g.stage_time_min.sum() / 60.0
        cycle_shown = g.cycle_time_h.iloc[0]
        over_pct = (shown_total / nominal - 1.0) * 100.0
        core = shown_total * g.solids_fraction.iloc[0] / (g.weight_gain_pct.iloc[0] / 100.0)
        core_masses.append(core)

        rep.check(
            abs(sum_sprayed - shown_total) <= 3 * HALF_ULP_SPRAYED + HALF_ULP_SPRAYED,
            f"B{b} total sprayed", f"sum {sum_sprayed:.2f} vs shown {shown_total:.2f}",
        )
        rep.check(
            abs(cycle_calc - cycle_shown) <= TOL_CYCLE_H,
            f"B{b} cycle time", f"calc {cycle_calc:.2f} h vs shown {cycle_shown:.1f} h",
        )
        if abs(over_pct) > 1.0:
            rep.note(
                f"B{b}: total sprayed {shown_total:.2f} kg is {over_pct:+.2f}% vs the "
                f"nominal solution mass {nominal:.3f} kg -- 'Solution (kg)' is a recipe "
                f"value, NOT an actual. Do not use it as the weight-gain mass basis."
            )

        print(f"{int(b):>5} {sum_sprayed:>12.2f} {shown_total:>8.2f} {nominal:>12.3f} "
              f"{over_pct:>+8.2f} {cycle_calc:>11.2f} {cycle_shown:>7.1f} {core:>11.1f}")

    spread = (max(core_masses) - min(core_masses)) / np.mean(core_masses) * 100.0
    rep.note(
        f"Implied core mass at eta_dep=1 spans {min(core_masses):.1f}-{max(core_masses):.1f} kg "
        f"({spread:.1f}% spread). CQA-1 (weight gain) cannot be calibrated until the true "
        f"batch core load is supplied. See PLAN section 16 Q1."
    )

    # (d) input variance -- the identifiability picture
    print("\n--- input variance (identifiability) -------------------------------")
    for col, unit in [("T_inlet_C", "C"), ("air_cfm", "CFM"),
                      ("RH_inlet_fraction", "-"), ("atomisation_bar", "bar"),
                      ("pan_rpm", "rpm"), ("spray_rate_g_min_gun", "g/min/gun")]:
        v = df[col]
        span = v.max() - v.min()
        pct = span / v.mean() * 100.0 if v.mean() else 0.0
        if span == 0:
            flag = "  <-- CONSTANT: zero information"
        elif col == "pan_rpm":
            flag = "  <-- varies, but CONFOUNDED with pump stage"
        elif pct > 10:
            flag = "  <-- the only independent variation"
        else:
            flag = ""
        print(f"  {col:<24} {v.min():>9.3f} .. {v.max():<9.3f} {unit:<10} "
              f"span {span:>8.3f} ({pct:>5.2f}%){flag}")

    if df.atomisation_bar.nunique() == 1:
        rep.note("Atomisation pressure is constant -- it carries zero information. "
                 "No atomisation parameter can be fitted from this dataset.")

    conf = df.groupby("pan_rpm").pump_rpm.apply(lambda s: sorted(s.unique())).to_dict()
    rep.note(f"Pan RPM is confounded with pump stage: {conf}. Any fitted 'RPM effect' "
             f"is indistinguishable from a spray-rate effect.")

    # (e) suspicious exhaust readings
    dupes = df.T_exhaust_meas_C.value_counts()
    for val, n in dupes[dupes > 1].items():
        rows = df[df.T_exhaust_meas_C == val]
        rep.note(
            f"T_exhaust = {val:.3f} C appears {n} times "
            f"(batches {sorted(rows.batch_index.tolist())}, pump {sorted(rows.pump_rpm.tolist())}). "
            f"Recorded per DEC-1 as a transcription/rounding artefact; exhaust is NOT setpoint-controlled."
        )

    unconfirmed = (df.confirmed_against_excel.astype(str).str.upper() != "TRUE").sum()
    if unconfirmed:
        rep.note(f"{unconfirmed}/{len(df)} stage rows are NOT yet confirmed against the source "
                 f"Excel (confirmed_against_excel=FALSE). Gate 0 stays OPEN until this is TRUE.")
    return df


def verify_guns(rep: Report, stages: pd.DataFrame) -> None:
    guns = pd.read_csv(DATA / "gun_calibration_v1.csv")
    gun_cols = [f"gun_{i}" for i in range(1, 7)]

    print("\n--- gun_calibration_v1.csv -----------------------------------------")
    print(f"{'batch':>5} {'rpm':>4} {'mean calc':>10} {'shown':>10} "
          f"{'CV %':>6} {'min gun':>8} {'max gun':>8}")

    for _, r in guns.iterrows():
        vals = r[gun_cols].to_numpy(dtype=float)
        mean_calc = vals.mean()
        cv = vals.std(ddof=1) / mean_calc * 100.0
        rep.check(
            abs(mean_calc - r.mean_shown) <= 1e-6,
            f"B{r.batch_index} {r.pump_rpm}rpm gun mean",
            f"calc {mean_calc:.7f} vs shown {r.mean_shown:.7f}",
        )
        # 3-sigma blocked/worn nozzle screen
        z = np.abs(vals - mean_calc) / vals.std(ddof=1)
        if (z > 3).any():
            bad = [gun_cols[i] for i in np.where(z > 3)[0]]
            rep.note(f"B{r.batch_index} {r.pump_rpm}rpm: {bad} deviate >3 sigma -- check nozzle.")
        print(f"{int(r.batch_index):>5} {int(r.pump_rpm):>4} {mean_calc:>10.4f} "
              f"{r.mean_shown:>10.4f} {cv:>6.2f} {vals.min():>8.3f} {vals.max():>8.3f}")

    # Recompute m, c and drive the plant spray rates
    print("\n--- pump calibration -> plant spray rates --------------------------")
    print(f"{'batch':>5} {'m calc':>11} {'m shown':>11} {'c calc':>11} {'c shown':>11}")

    fits: dict[int, tuple[float, float]] = {}
    for b, g in guns.groupby("batch_index"):
        x = g.pump_rpm.to_numpy(dtype=float)
        y = g[gun_cols].to_numpy(dtype=float).mean(axis=1)
        m, c = np.polyfit(x, y, 1)
        fits[int(b)] = (m, c)
        rep.check(abs(m - g.m_shown.iloc[0]) <= TOL_GUN_FIT,
                  f"B{b} slope m", f"calc {m:.8f} vs shown {g.m_shown.iloc[0]:.8f}")
        rep.check(abs(c - g.c_shown.iloc[0]) <= TOL_GUN_FIT,
                  f"B{b} intercept c", f"calc {c:.8f} vs shown {g.c_shown.iloc[0]:.8f}")
        print(f"{int(b):>5} {m:>11.8f} {g.m_shown.iloc[0]:>11.8f} "
              f"{c:>11.8f} {g.c_shown.iloc[0]:>11.8f}")

        if len(x) == 2:
            rep.note(f"B{b}: pump fit uses {len(x)} setpoints ({x.tolist()} rpm) -> dof=0, "
                     f"exact interpolation, linearity untested. Intercept c={c:.3f} g/min at "
                     f"0 rpm is non-physical: block extrapolation below {x.min():.0f} rpm.")

    print(f"\n{'batch':>5} {'pump':>5} {'predicted':>11} {'plant table':>12} {'delta':>9}")
    worst = 0.0
    for _, r in stages.iterrows():
        m, c = fits[int(r.batch_index)]
        pred = m * r.pump_rpm + c
        d = pred - r.spray_rate_g_min_gun
        worst = max(worst, abs(d))
        rep.check(abs(d) <= 0.005,
                  f"B{r.batch_index} pump{r.pump_rpm} spray rate from calibration",
                  f"predicted {pred:.4f} vs table {r.spray_rate_g_min_gun:.2f}")
        print(f"{int(r.batch_index):>5} {int(r.pump_rpm):>5} {pred:>11.4f} "
              f"{r.spray_rate_g_min_gun:>12.2f} {d:>+9.4f}")

    rep.note(f"Gun calibration reproduces all {len(stages)} plant spray rates; "
             f"worst deviation {worst:.4f} g/min (display rounding).")

    cvs = []
    for _, r in guns.iterrows():
        vals = r[gun_cols].to_numpy(dtype=float)
        cvs.append(vals.std(ddof=1) / vals.mean() * 100.0)
    rep.note(f"Measured gun-to-gun CV spans {min(cvs):.2f}-{max(cvs):.2f}%. This is real "
             f"uniformity data and is the empirical input for the Stage 3 uniformity model.")


def verify_provenance(rep: Report, stages: pd.DataFrame) -> None:
    """Enforce DEC-4 and DEC-5: every column labelled, EE output quarantined."""
    prov = pd.read_csv(DATA / "COLUMN_PROVENANCE.csv").set_index("column")

    print("\n--- column provenance (DEC-5) --------------------------------------")
    missing = [c for c in stages.columns if c not in prov.index]
    rep.check(not missing, "provenance coverage", f"unlabelled columns: {missing}")

    by_kind: dict[str, list[str]] = {}
    for c in stages.columns:
        if c in prov.index:
            by_kind.setdefault(str(prov.loc[c, "provenance"]), []).append(c)
    for kind in sorted(by_kind):
        print(f"  {kind:<24} {', '.join(by_kind[kind])}")

    targets = [c for c in stages.columns
               if c in prov.index
               and str(prov.loc[c, "usable_as_validation_target"]).upper() == "YES"]
    ee_cols = by_kind.get("EE_OUTPUT", [])
    print(f"\n  valid acceptance targets : {targets}")
    print(f"  EE output (NEVER targets): {ee_cols}")

    rep.check("T_exhaust_meas_C" in targets, "ground truth present",
              "T_exhaust_meas_C must be a validation target")
    for c in ee_cols:
        rep.check(str(prov.loc[c, "usable_as_validation_target"]).upper() == "NEVER",
                  f"{c} quarantined", "EE output must be marked NEVER")
    rep.note(
        "Exhaust RH has NO measured ground truth: the table column is EE model output "
        "(reproduced to 0.0005 across all 12 rows). Acceptance target A5 cannot be "
        "evaluated until a real hygrometer reading is supplied -- see PLAN Q8."
    )

    print("\n--- acceptance roles (DEC-4) ---------------------------------------")
    for role, g in stages.groupby("acceptance_role"):
        print(f"  {role:<12} batches {sorted(g.batch_index.unique().tolist())} "
              f"({len(g)} stages)")
    sealed = stages[stages.acceptance_role == "SEALED"]
    rep.check(len(sealed) > 0, "sealed batch reserved",
              "at least one batch must be sealed for final acceptance")
    rep.note(f"Batch {sorted(sealed.batch_index.unique().tolist())} is SEALED: run against it "
             f"exactly once, at the end. Consulting it during iteration voids the held-out claim "
             f"(PLAN 0.4).")


def main() -> int:
    rep = Report()
    stages = verify_stages(rep)
    verify_guns(rep, stages)
    verify_provenance(rep, stages)
    code = rep.summary()
    print("GATE 0:", "OPEN - awaiting Excel confirmation (Q0)" if code == 0
          else "FAILED - reconciliation errors above")
    return code


if __name__ == "__main__":
    sys.exit(main())
