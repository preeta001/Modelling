"""STAGE 2 -- Spray pump / gun calibration.

Rewired in P1 to use `coating_model.gun_calibration`. The previous version had
its own polyfit, asked only for the TOTAL spray rate (discarding the per-gun
measurements where the uniformity information lives), had no extrapolation
guard, and wrote a result that no other page ever read (defect D9).

This page is the provenance layer for the spray rate Stage 1 and Stage 3 consume.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from coating_model.gun_calibration import (
    GUN_COLUMNS,
    ExtrapolationError,
    fit_pump_calibration,
    gun_outliers,
    load_calibrations,
    mean_gun_cv_pct,
)

ACCEPTANCE_CSV = (
    Path(__file__).resolve().parents[1] / "data" / "acceptance" / "gun_calibration_v1.csv"
)

st.title("🔫 Stage 2 — Spray Pump Calibration")
st.caption(
    "Maps pump setpoint (RPM) → spray rate per gun, from measured per-gun output. "
    "Every downstream spray rate carries provenance back to these measurements."
)

with st.expander("📖 Why per-gun measurements, not just the total?", expanded=False):
    st.markdown(
        """
The gun-to-gun spread is **measured uniformity data**. Averaging it away at entry
throws out the only empirical handle on coating uniformity this process has —
and it is the honest replacement for droplet-size correlations that have no
supporting measurements.

Two guards this page enforces:

* **Extrapolation is refused** outside the calibrated RPM range. The fitted
  intercept (~3 g/min at 0 rpm) is non-physical — a stopped pump delivers
  nothing — so the straight line is only meaningful between the calibration
  points.
* **Blocked-nozzle detection uses a median/MAD score, not 3σ.** With 6 guns the
  largest attainable z-score is (n−1)/√n = **2.04**, so a "3-sigma" rule can
  never fire: one badly blocked gun inflates σ enough to hide itself.
        """
    )

# --------------------------------------------------------------------- source
src = st.radio(
    "Data source",
    ["Acceptance set (plant gun-validation record)", "Manual entry"],
    horizontal=True,
)

cals: dict[int, object] = {}

if src.startswith("Acceptance") and ACCEPTANCE_CSV.exists():
    raw = pd.read_csv(ACCEPTANCE_CSV)
    cals = load_calibrations(ACCEPTANCE_CSV)
    st.dataframe(
        raw[["batch_index", "pump_rpm", *GUN_COLUMNS]],
        use_container_width=True, hide_index=True,
    )
elif src.startswith("Acceptance"):
    st.warning(f"No gun-validation record found at {ACCEPTANCE_CSV}.")
else:
    st.markdown("### Enter measured output per gun (g/min)")
    n_pts = st.number_input("Number of pump setpoints", 2, 10, 2)
    default = pd.DataFrame({"pump_rpm": np.linspace(5.0, 10.0, int(n_pts))})
    for c in GUN_COLUMNS:
        default[c] = np.linspace(24.0, 45.0, int(n_pts))
    edited = st.data_editor(default, use_container_width=True, hide_index=True,
                            num_rows="fixed")
    if st.button("Fit calibration", type="primary"):
        cals = {
            1: fit_pump_calibration(
                edited.pump_rpm.to_numpy(float),
                edited[GUN_COLUMNS].to_numpy(float),
                batch_index=1,
            )
        }

# --------------------------------------------------------------------- output
if cals:
    st.markdown("### Fitted calibrations")
    rows = []
    for b, cal in sorted(cals.items()):
        rows.append({
            "Batch": b,
            "m (g/min per rpm)": cal.m,
            "c (g/min)": cal.c,
            "Valid range (rpm)": f"{cal.rpm_min:g}–{cal.rpm_max:g}",
            "Setpoints": cal.n_points,
            "dof": cal.dof,
            "Mean gun CV (%)": mean_gun_cv_pct(cal),
        })
    num = st.column_config.NumberColumn
    st.dataframe(
        pd.DataFrame(rows), use_container_width=True, hide_index=True,
        column_config={
            "m (g/min per rpm)": num(format="%.6f"),
            "c (g/min)": num(format="%.6f"),
            "Mean gun CV (%)": num(format="%.2f"),
        },
    )

    warnings = [w for cal in cals.values() for w in cal.warnings()]
    if warnings:
        st.warning("\n\n".join(f"- {w}" for w in warnings))

    # ---- curve
    fig = go.Figure()
    for b, cal in sorted(cals.items()):
        x = np.linspace(cal.rpm_min, cal.rpm_max, 50)
        fig.add_trace(go.Scatter(x=x, y=cal.m * x + cal.c, mode="lines",
                                 name=f"Batch {b} fit"))
        fig.add_trace(go.Scatter(
            x=list(cal.gun_means), y=list(cal.gun_means.values()),
            mode="markers", name=f"Batch {b} measured",
            marker=dict(size=10, symbol="circle-open")))
    fig.update_layout(template="plotly_dark", xaxis_title="Pump RPM",
                      yaxis_title="Spray rate per gun (g/min)",
                      margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig, use_container_width=True)

    # ---- acceptance target A2
    stages_csv = ACCEPTANCE_CSV.parent / "stages_v1.csv"
    if stages_csv.exists() and len(cals) > 1:
        st.markdown("### Acceptance target A2 — does the calibration reproduce the plant?")
        stages = pd.read_csv(stages_csv)
        chk = []
        for _, r in stages.iterrows():
            cal = cals.get(int(r.batch_index))
            if cal is None:
                continue
            pred = cal.spray_rate_per_gun(float(r.pump_rpm))
            chk.append({"Batch": int(r.batch_index), "Pump RPM": int(r.pump_rpm),
                        "Predicted": pred, "Plant table": float(r.spray_rate_g_min_gun),
                        "Δ (g/min)": pred - float(r.spray_rate_g_min_gun)})
        cdf = pd.DataFrame(chk)
        worst = cdf["Δ (g/min)"].abs().max()
        (st.success if worst < 0.005 else st.error)(
            f"{'✅' if worst < 0.005 else '❌'} A2: worst deviation "
            f"**{worst:.4f} g/min** against a 0.005 g/min limit "
            f"({len(cdf)} stages). Residual is display rounding in the source table."
        )
        st.dataframe(cdf, use_container_width=True, hide_index=True,
                     column_config={"Predicted": num(format="%.4f"),
                                    "Plant table": num(format="%.2f"),
                                    "Δ (g/min)": num(format="%.4f")})

    # ---- calculator, with the extrapolation guard live
    st.markdown("### Calculator")
    q1, q2, q3 = st.columns(3)
    batch_pick = q1.selectbox("Batch", sorted(cals))
    cal = cals[batch_pick]
    rpm_q = q2.number_input("Pump RPM", value=float(cal.rpm_min), step=0.5)
    guns_q = q3.number_input("Number of guns", 1, 12, 6)
    try:
        per_gun = cal.spray_rate_per_gun(rpm_q)
        a, b = st.columns(2)
        a.metric("Spray rate per gun", f"{per_gun:.3f} g/min")
        b.metric("Total spray rate", f"{per_gun * guns_q:.2f} g/min")
    except ExtrapolationError as exc:
        st.error(f"🚫 Refused: {exc}")

    st.session_state["pump_calibrations"] = cals
    st.success(
        f"Calibration published to the session for {len(cals)} batch(es). "
        f"Stage 1 and Stage 3 will resolve spray rate from it with full provenance."
    )
else:
    st.info("Choose a data source above to fit a calibration.")
