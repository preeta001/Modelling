"""STAGE 1 -- Model validation & calibration.

Rewritten in P3/P4. The previous version carried its own copy of the energy
balance (`calculate_stage_physics`) which double-counted the latent heat and made
the model physically impossible (defect D1). All physics now comes from
`coating_model.energy_balance`, the single canonical core.

The table shows BOTH error columns side by side (PLAN section 8.5):
  * calibrated -- per-row fitted alpha, exactly as today, reading ~0.000
  * locked     -- one parameter fitted elsewhere, then frozen: a real prediction
Under per-row fitting every model scores 0.000, so better physics is
indistinguishable from worse physics. The locked column is what makes model
improvement visible at all.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from coating_model.energy_balance import (
    PhysicsViolation,
    calculate_exhaust_state,
    solve_alpha_for_measured_exhaust,
)

st.title("⚙️ Stage 1 — Model Validation & Calibration")
st.caption(
    "Physics: `coating_model.energy_balance` — the single canonical core. "
    "Verified equal to the frozen legacy EE model to 1e-14 °C."
)

with st.expander("📖 Why two error columns?", expanded=False):
    st.markdown(
        """
**Calibrated error** fits a separate heat-loss parameter to *each row*, chosen to
reproduce that row's own measurement. With one free parameter per row and zero
degrees of freedom left, a near-zero error is arithmetically guaranteed. This is
what the current plant table reports.

**Locked error** fits the parameter once, on a different batch, then freezes it.
That is a genuine prediction and the only column that responds to the model
actually being better.

Both are shown because the first is what you are used to seeing, and the second
is what tells you whether the model works.
        """
    )

solvent_name = st.session_state.get("global_solvent", "water")
HEAT_LOSS_FORMS = {
    "Corrected physics — q = α·((T_in+T_ex)/2 − T_amb)": "physical_ua",
    "Legacy EE convention — reproduces the old model exactly": "legacy_alpha",
}

c1, c2, c3 = st.columns(3)
form_label = c1.selectbox("Heat-loss convention", list(HEAT_LOSS_FORMS))
heat_loss_form = HEAT_LOSS_FORMS[form_label]
T_amb = c2.number_input("Ambient temperature (°C)", value=25.0, step=0.5)
P_total = c3.number_input("Pressure (kPa)", value=101.325)

ACCEPTANCE_CSV = Path(__file__).resolve().parents[1] / "data" / "acceptance" / "stages_v1.csv"

# Deliberately DIFFERENT per stage. Identical defaults would make the locked
# column read 0.0000 -- the exact false-perfection this page exists to expose.
FALLBACK = [
    (32.72, 56.507, 2800.63, 0.05, 48.519),
    (36.95, 56.507, 2801.01, 0.05, 49.000),
    (41.17, 56.514, 2800.62, 0.05, 49.373),
]


def _seed_state(n: int, values: list[tuple]) -> None:
    for i in range(n):
        v = values[i] if i < len(values) else values[-1]
        for key, val in zip(("sr", "ti", "cf", "rh", "te"), v):
            st.session_state[f"{key}{i}"] = float(val)


st.markdown("### Load data")
if ACCEPTANCE_CSV.exists():
    acc = pd.read_csv(ACCEPTANCE_CSV)
    l1, l2, l3 = st.columns([2, 1, 3])
    choice = l1.selectbox(
        "Batch from the acceptance set",
        [f"Batch {b}" for b in sorted(acc.batch_index.unique())],
    )
    batch_no = int(choice.split()[-1])
    grp = acc[acc.batch_index == batch_no].sort_values("pump_rpm")
    role = str(grp.acceptance_role.iloc[0])

    if role == "SEALED":
        l3.error(
            f"🔒 Batch {batch_no} is the **sealed** final-acceptance batch. It may be "
            f"run exactly once, at the end. Loading it here during development "
            f"voids the held-out claim (PLAN §0.4)."
        )
    else:
        l3.caption(f"Role: **{role}** — {len(grp)} stages, pump "
                   f"{', '.join(str(int(r)) for r in grp.pump_rpm)} rpm.")

    if l2.button("Load batch", disabled=(role == "SEALED")):
        st.session_state["n_stages_val"] = len(grp)
        _seed_state(len(grp), [
            (r.spray_rate_g_min_gun, r.T_inlet_C, r.air_cfm,
             r.RH_inlet_fraction, r.T_exhaust_meas_C)
            for _, r in grp.iterrows()
        ])
        st.session_state["loaded_batch"] = batch_no
        st.rerun()

    if "loaded_batch" in st.session_state:
        st.success(f"Loaded batch {st.session_state['loaded_batch']} "
                   f"from the acceptance set.")
else:
    st.info("No acceptance set found — using manual entry.")

st.markdown("### Stage inputs")
b1, b2, b3 = st.columns(3)
no_of_guns = b1.number_input("Number of guns", value=6, min_value=1)
solids_fraction = b2.number_input("Solids fraction", value=0.15, min_value=0.01,
                                  max_value=0.99)
# Seed the key BEFORE the widget exists. Passing both key= and value= makes
# Streamlit warn that the default is being overridden by session state.
st.session_state.setdefault("n_stages_val", 3)
n_stages = b3.number_input("Number of stages", min_value=1, max_value=12,
                           key="n_stages_val")

for _i in range(int(n_stages)):
    if f"sr{_i}" not in st.session_state:
        _seed_state(int(n_stages), FALLBACK)
        break

rows = []
with st.form("stages"):
    for i in range(int(n_stages)):
        st.markdown(f"**Stage {i + 1}**")
        k1, k2, k3, k4, k5 = st.columns(5)
        rows.append(
            dict(
                spray_rate_g_min_gun=k1.number_input(
                    "Spray (g/min/gun)", key=f"sr{i}", format="%.4f"),
                T_inlet_C=k2.number_input(
                    "T_inlet (°C)", key=f"ti{i}", format="%.4f"),
                air_cfm=k3.number_input(
                    "Airflow (CFM)", key=f"cf{i}", format="%.4f"),
                RH_inlet=k4.number_input(
                    "Inlet RH (0–1)", key=f"rh{i}", format="%.4f"),
                T_exhaust_measured=k5.number_input(
                    "Measured T_exhaust (°C)", key=f"te{i}", format="%.4f"),
            )
        )
    go = st.form_submit_button("Run validation", type="primary")

if go:
    common = dict(
        no_of_guns=int(no_of_guns),
        solids_fraction=float(solids_fraction),
        P_total_kPa=float(P_total),
        solvent_name=solvent_name,
        heat_loss_form=heat_loss_form,
        T_amb_C=float(T_amb),
    )

    try:
        # --- pass 1: per-row calibration (target T2) ------------------------
        alphas = []
        for r in rows:
            kw = {k: v for k, v in r.items() if k != "T_exhaust_measured"}
            alphas.append(
                solve_alpha_for_measured_exhaust(
                    r["T_exhaust_measured"], **kw, **common
                )
            )

        # --- pass 2: locked parameter (target T3) ---------------------------
        # WITHIN-BATCH locking: stage 1's alpha is frozen and used to predict the
        # later stages. This is deliberately the harshest test available here --
        # alpha varies strongly with spray rate (PLAN section 2.5), and the later
        # stages spray 13-26% harder, so this exposes that dependence directly.
        # reports/baseline_locked.md instead locks ACROSS batches at matched pump
        # stages, which is the gentler and more representative protocol.
        alpha_locked = alphas[0]

        table, violations = [], []
        for i, (r, a_fit) in enumerate(zip(rows, alphas)):
            kw = {k: v for k, v in r.items() if k != "T_exhaust_measured"}
            meas = r["T_exhaust_measured"]

            s_cal = calculate_exhaust_state(**kw, **common, alpha=a_fit,
                                            check_physics=False)
            s_lock = calculate_exhaust_state(**kw, **common, alpha=alpha_locked,
                                             check_physics=False)
            for s in (s_cal, s_lock):
                if abs(s.energy_residual_kJ_per_kg_da) > 1e-9:
                    violations.append(
                        f"Stage {i+1}: energy residual "
                        f"{s.energy_residual_kJ_per_kg_da:.2e} kJ/kg-da")

            err_cal = s_cal.T_exhaust_C - meas
            err_lock = s_lock.T_exhaust_C - meas
            table.append({
                "Stage": i + 1,
                "Role": "calibration" if i == 0 else "prediction",
                "Measured": meas,
                "Predicted (calibrated)": s_cal.T_exhaust_C,
                "Error % (cal)": abs(err_cal) / abs(meas) * 100 if meas else np.nan,
                "Predicted (locked)": s_lock.T_exhaust_C,
                "Error % (locked)": abs(err_lock) / abs(meas) * 100 if meas else np.nan,
                "α fitted": a_fit,
                "UA (kW/K)": s_cal.UA_kW_K,
                "Exhaust RH": s_lock.RH_exhaust,
            })

        df = pd.DataFrame(table)
        st.session_state.alpha_locked = float(alpha_locked)
        st.session_state.stage1_results = df

        pred = df[df.Role == "prediction"]
        m1, m2, m3 = st.columns(3)
        m1.metric("Calibration error", f"{df['Error % (cal)'].max():.4f} %",
                  help="Per-row fit. A fit, not accuracy.")
        if len(pred):
            e = (pred["Predicted (locked)"] - pred["Measured"]).to_numpy()
            m2.metric("Locked prediction RMSE",
                      f"{np.sqrt(np.mean(e**2)):.4f} °C",
                      help="Parameter frozen from stage 1. This is the real number.")
            m3.metric("Locked max error", f"{np.max(np.abs(e)):.4f} °C")

        # Display precision is tied to what the instrument can resolve
        # (PLAN section 14); diagnostics carry more digits than plant-facing
        # values. column_config is used rather than a pandas Styler because
        # st.dataframe does not apply Styler.format to numeric columns.
        num = st.column_config.NumberColumn
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Measured": num("Measured", format="%.3f", help="Plant measurement"),
                "Predicted (calibrated)": num("Predicted (cal)", format="%.3f"),
                "Error % (cal)": num("Error % (cal)", format="%.4f",
                                     help="Calibration residual — a fit, not accuracy"),
                "Predicted (locked)": num("Predicted (locked)", format="%.3f"),
                "Error % (locked)": num("Error % (locked)", format="%.4f",
                                        help="Genuine prediction error"),
                "α fitted": num("α fitted", format="%.5f"),
                "UA (kW/K)": num("UA (kW/K)", format="%.5f"),
                "Exhaust RH": num("Exhaust RH", format="%.4f",
                                  help="UNVALIDATED — no measured exhaust RH exists "
                                       "in the dataset (PLAN §0.3)"),
            },
        )

        st.caption(
            "**Calibrated** columns fit one parameter per row against that row's own "
            "measurement — a calibration residual, not accuracy. **Locked** columns "
            "freeze the stage-1 parameter and predict the rest. Only the locked "
            "columns measure predictive skill."
        )

        if violations:
            st.error("Physics violations:\n\n" + "\n".join(f"- {v}" for v in violations))
        else:
            st.success("✅ Energy balance closes on every stage (residual < 1e-9 kJ/kg-da).")

        spread = max(alphas) / min(alphas) if min(alphas) > 0 else float("inf")
        if spread > 1.5:
            st.warning(
                f"Fitted α varies {spread:.1f}× across stages "
                f"({min(alphas):.4f} → {max(alphas):.4f}). A real equipment heat-loss "
                f"property should not vary like that at near-constant airflow — the "
                f"parameter is absorbing model error, most likely the assumption that "
                f"100 % of sprayed solvent evaporates inside the pan."
            )

        adiabatic = calculate_exhaust_state(
            **{k: v for k, v in rows[0].items() if k != "T_exhaust_measured"},
            **{**common, "heat_loss_form": "physical_ua"}, alpha=0.0,
        )
        st.info(
            f"**Zero-parameter reference:** run adiabatically (no fitting at all), "
            f"stage 1 predicts **{adiabatic.T_exhaust_C:.3f} °C** against a measured "
            f"**{rows[0]['T_exhaust_measured']:.3f} °C** — a gap of "
            f"{adiabatic.T_exhaust_C - rows[0]['T_exhaust_measured']:+.3f} °C. "
            f"That gap is the entire job of the single heat-loss parameter."
        )

    except PhysicsViolation as exc:
        st.error(f"Physically impossible state: {exc}")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Calculation failed: {exc}")
