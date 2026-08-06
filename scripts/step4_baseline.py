"""P4 -- establish the locked EE benchmark that every later module must beat.

Produces reports/baseline_locked.md. That file is committed and NEVER edited
afterwards: it is the fixed yardstick for gate G3.

Four parameter policies are evaluated. The first is what the plant's current
table shows; the rest are what EE actually achieves when used as a predictor.

Run:  python scripts/step4_baseline.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from coating_model.energy_balance import (  # noqa: E402
    calculate_exhaust_state,
    solve_alpha_for_measured_exhaust,
)
from validation.acceptance import (  # noqa: E402
    ROLE_SEALED,
    load_acceptance_set,
    run_calibration_fit,
    run_locked_prediction,
    visible_rows,
)

REPO = Path(__file__).resolve().parents[1]
REPORTS = REPO / "reports"


def row_inputs(r: pd.Series) -> dict:
    return dict(
        T_inlet_C=float(r.T_inlet_C),
        air_cfm=float(r.air_cfm),
        RH_inlet=float(r.RH_inlet_fraction),
        spray_rate_g_min_gun=float(r.spray_rate_g_min_gun),
        no_of_guns=int(r.no_of_guns),
        solids_fraction=float(r.solids_fraction),
        P_total_kPa=float(r.P_total_kPa),
    )


def predict(r: pd.Series, *, form: str, alpha=None, UA=None) -> float:
    return calculate_exhaust_state(
        **row_inputs(r), heat_loss_form=form, alpha=alpha, UA_kW_K=UA,
        check_physics=False,
    ).T_exhaust_C


def main() -> int:
    df = load_acceptance_set()
    open_rows = visible_rows(df, unseal=False)
    n_sealed = int((df.acceptance_role == ROLE_SEALED).sum())

    print("=" * 78)
    print("  P4 -- LOCKED EE BASELINE")
    print("=" * 78)
    print(f"  visible rows : {len(open_rows)}   sealed (withheld): {n_sealed}")

    results = []

    # --- policy 1: per-row fitted alpha -- what the plant table shows --------
    def fit_row(r):
        a = solve_alpha_for_measured_exhaust(
            float(r.T_exhaust_meas_C), **row_inputs(r), heat_loss_form="legacy_alpha"
        )
        return predict(r, form="legacy_alpha", alpha=a), a

    cal = run_calibration_fit(df, fit_row, label="Per-row fitted alpha (legacy EE table)")
    print("\n" + cal.headline())
    print("  fitted alpha per row:",
          ", ".join(f"{v:.4f}" for v in cal.per_row.fitted_param))

    # --- policy 2: per-batch locked Alpha Avg -- EE as a predictor -----------
    alpha_avg = (
        df.groupby("batch_index").alpha_avg_ee_output.first().to_dict()
    )
    lock_batch = run_locked_prediction(
        df,
        lambda r: predict(r, form="legacy_alpha", alpha=float(alpha_avg[r.batch_index])),
        label="Per-batch locked Alpha Avg (legacy form)",
    )
    results.append(lock_batch)

    # --- policy 3: single global alpha, legacy form --------------------------
    a_glob = float(np.mean(list(alpha_avg.values())))
    results.append(
        run_locked_prediction(
            df,
            lambda r: predict(r, form="legacy_alpha", alpha=a_glob),
            label=f"Single global alpha = {a_glob:.5f} (legacy form)",
        )
    )

    # --- policy 4: single global UA, corrected physics -----------------------
    # UA is fitted on the CALIBRATION batch only, then locked. Nothing is fitted
    # on the rows being predicted.
    calib = df[df.acceptance_role == "calibration"]
    from scipy.optimize import minimize_scalar

    def calib_rmse(ua: float) -> float:
        e = [predict(r, form="physical_ua", UA=ua) - float(r.T_exhaust_meas_C)
             for _, r in calib.iterrows()]
        return float(np.sqrt(np.mean(np.square(e))))

    ua_locked = float(minimize_scalar(calib_rmse, bounds=(-1.0, 5.0), method="bounded").x)
    results.append(
        run_locked_prediction(
            df,
            lambda r: predict(r, form="physical_ua", UA=ua_locked),
            label=f"Locked UA = {ua_locked:.5f} kW/K, corrected physics "
                  f"(fitted on batch {calib.batch_index.iloc[0]} only)",
        )
    )

    # --- policy 5: EE under the SAME protocol as policy 4 --------------------
    # This is the only apples-to-apples comparison: legacy equation, one alpha,
    # fitted on the calibration batch only. Policies 2 and 3 are leaky (see the
    # leakage table in the report), so beating them is not the honest test.
    def calib_rmse_alpha(a: float) -> float:
        e = [predict(r, form="legacy_alpha", alpha=a) - float(r.T_exhaust_meas_C)
             for _, r in calib.iterrows()]
        return float(np.sqrt(np.mean(np.square(e))))

    a_locked = float(
        minimize_scalar(calib_rmse_alpha, bounds=(-1.0, 5.0), method="bounded").x
    )
    ee_matched = run_locked_prediction(
        df,
        lambda r: predict(r, form="legacy_alpha", alpha=a_locked),
        label=f"EE legacy form, locked alpha = {a_locked:.5f} "
              f"(fitted on batch {calib.batch_index.iloc[0]} only) -- MATCHED PROTOCOL",
    )
    results.append(ee_matched)

    # --- policy 6: zero-parameter adiabatic ---------------------------------
    results.append(
        run_locked_prediction(
            df,
            lambda r: predict(r, form="physical_ua", alpha=0.0),
            label="Adiabatic -- ZERO free parameters",
        )
    )

    for res in results:
        print("\n" + res.headline())

    baseline = lock_batch  # headline benchmark (leaky -- see report)
    matched = ee_matched   # the honest like-for-like benchmark for gate G3
    dev_matched = matched.by_role["development"]
    print(f"\n  MATCHED-PROTOCOL out-of-sample (batches 2-3): "
          f"RMSE {dev_matched.rmse:.4f} C, max {dev_matched.max_abs:.4f} C")

    # ---------------------------------------------------------------- report
    REPORTS.mkdir(exist_ok=True)
    out = REPORTS / "baseline_locked.md"
    L: list[str] = []
    L.append("# Locked EE baseline — the frozen benchmark\n")
    L.append("**Generated by** `scripts/step4_baseline.py`. "
             "**Do not edit.** This file is the fixed yardstick for gate G3 "
             "(PLAN §5). Regenerate only if the acceptance set itself changes.\n")
    L.append(f"- Rows scored: **{len(open_rows)}** "
             f"(sealed batch withheld: {n_sealed} rows)\n"
             f"- Target: `T_exhaust_meas_C` — the only thermodynamic ground truth "
             f"in the dataset (PLAN §0.2)\n")

    L.append("\n## The benchmark — two of them, and the difference matters\n")
    L.append(f"**Headline (as EE is normally quoted):** RMSE "
             f"{baseline.overall.rmse:.4f} °C, max {baseline.overall.max_abs:.4f} °C. "
             f"This uses the per-batch `Alpha Avg`, which is **leaky** — see below.\n")
    L.append(f"\n**Gate G3 benchmark (matched protocol, out-of-sample):**\n")
    L.append(f"> **RMSE ≤ {dev_matched.rmse:.4f} °C** and "
             f"**max |err| ≤ {dev_matched.max_abs:.4f} °C**\n")
    L.append(f"\nThis is EE's legacy equation with **one** alpha fitted on batch "
             f"{calib.batch_index.iloc[0]} only, scored on batches 2–3 which it never "
             f"saw. Any candidate module is measured the same way, on the same rows, "
             f"with the same number of parameters fitted on the same batch. Beating "
             f"the headline number instead would be beating a benchmark that has "
             f"already seen the answer.\n")

    L.append("\n### Leakage hierarchy — why there are two numbers\n")
    L.append("\n| Policy | Params | Fitted on | Leaky? |")
    L.append("|---|---|---|---|")
    L.append("| Per-row fitted alpha | 9 (one per row) | the row it predicts | "
             "**totally** — 0.000 is arithmetic, not skill |")
    L.append("| Per-batch `Alpha Avg` | 1 per batch | rows of the *same* batch | "
             "**yes** — each batch's parameter saw that batch's measurements |")
    L.append("| Single global alpha | 1 | the mean of all batches' fitted alphas | "
             "**mildly** — derived from every batch, including those scored |")
    L.append("| **Locked alpha / locked UA** | **1** | **batch "
             f"{calib.batch_index.iloc[0]} only** | **no — genuinely out-of-sample "
             "on batches 2–3** |")
    L.append("| Adiabatic | 0 | nothing | no |")
    L.append("\nThe practical consequence: EE's apparent 0.43 °C on batches 2–3 "
             f"under the leaky policy becomes **{dev_matched.rmse:.4f} °C** once it is "
             f"held to the same standard we hold ourselves to.\n")

    L.append("\n## Calibration fit vs locked prediction\n")
    L.append("These are different quantities and are never compared with each other.\n")
    L.append("\n| Policy | Kind | n | RMSE (°C) | MAE (°C) | max abs (°C) | bias (°C) | max err (%) |")
    L.append("|---|---|---|---|---|---|---|---|")

    def line(r):
        m = r.overall
        kind = "prediction" if r.is_prediction else "**calibration fit**"
        return (f"| {r.label} | {kind} | {m.n} | {m.rmse:.4f} | {m.mae:.4f} | "
                f"{m.max_abs:.4f} | {m.bias:+.4f} | {m.max_pct:.4f} |")

    L.append(line(cal))
    for r in results:
        L.append(line(r))

    L.append("\n### Why the first row reads ~0.000\n")
    L.append(cal.notes[0] + "\n")
    L.append(f"\nFitted alpha per row: "
             f"{', '.join(f'{v:.4f}' for v in cal.per_row.fitted_param)} — "
             f"a {cal.per_row.fitted_param.max() / max(1e-9, cal.per_row.fitted_param.min()):.1f}× "
             f"spread across rows at essentially constant airflow. A physical "
             f"equipment property does not vary like that; the parameter is "
             f"absorbing model error (PLAN §2.5).\n")

    L.append("\n## Per-row detail — locked benchmark policy\n")
    L.append("\n| batch | role | pump | measured | predicted | signed err | % err |")
    L.append("|---|---|---|---|---|---|---|")
    for _, r in baseline.per_row.iterrows():
        L.append(f"| {int(r.batch)} | {r.role} | {int(r.pump_rpm)} | "
                 f"{r.measured:.3f} | {r.predicted:.4f} | {r.signed_err:+.4f} | "
                 f"{r.pct_err:.4f} |")

    L.append("\n## By acceptance role\n")
    L.append("\n| Policy | role | n | RMSE (°C) | max abs (°C) |")
    L.append("|---|---|---|---|---|")
    for r in results:
        for role, m in sorted(r.by_role.items()):
            L.append(f"| {r.label} | {role} | {m.n} | {m.rmse:.4f} | {m.max_abs:.4f} |")

    L.append("\n## Notes\n")
    L.append(f"- The **adiabatic** row is a genuine zero-parameter, zero-fitting "
             f"prediction: pure thermodynamics with published constants. It is "
             f"{results[-1].overall.bias:+.3f} °C biased, which is exactly the gap "
             f"the single heat-loss parameter exists to close (PLAN §0.5).\n")
    L.append(f"- **Locked UA** was fitted on batch "
             f"{calib.batch_index.iloc[0]} only and then frozen; the other batches "
             f"are genuine out-of-sample predictions.\n")
    L.append("- The sealed batch is withheld from every policy above. It is run "
             "exactly once, at the end (PLAN §0.4).\n")

    out.write_text("\n".join(L), encoding="utf-8")
    print(f"\nwritten: {out.relative_to(REPO)}")
    print(f"\nBENCHMARK: RMSE <= {baseline.overall.rmse:.4f} C, "
          f"max <= {baseline.overall.max_abs:.4f} C")
    return 0


if __name__ == "__main__":
    sys.exit(main())
