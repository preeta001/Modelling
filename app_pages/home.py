"""Home / overview.

Rewritten during the P1-P4 app check. The previous version described a two-step
workflow that no longer exists and its "Go to Quick Predict" button called
st.switch_page("app_pages/quick_predict.py") -- a file that does not exist, which
crashed the app. The second button targeted an unregistered page and would have
failed the same way.

Navigation targets here are validated against the registered page list at import
time, so a dead link fails loudly in tests rather than silently in front of a user.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

REPO = Path(__file__).resolve().parents[1]


def _page_exists(rel: str) -> bool:
    return (REPO / rel).exists()


st.title("💊 Track A — Practical Integrated Coating Model")
st.markdown("#### Plant-scale tablet pan coating: thermodynamics, spray and quality")

st.info(
    "**Status: under rebuild.** Stages 1 and 2 are validated against plant data. "
    "Stages 3 and 4 are being reconstructed and their outputs are **not yet "
    "trustworthy** — see the status table below and `PLAN_TRACK_A_REBUILD.md`."
)

st.markdown("### The four stages")

STAGES = [
    {
        "n": "STEP 1", "icon": "🧪", "title": "Model Validation & Calibration",
        "page": "app_pages/validation_page.py",
        "status": "validated",
        "what": "Predicts exhaust temperature from inlet conditions, airflow and "
                "spray rate, and scores it against plant measurements.",
        "detail": "Shows the calibrated error (per-row fit, reads ~0.000) **and** the "
                  "locked prediction error side by side. Only the second responds to "
                  "the model actually being better.",
    },
    {
        "n": "STEP 2", "icon": "🔫", "title": "Gun / Pump Calibration",
        "page": "app_pages/gun_validation.py",
        "status": "validated",
        "what": "Maps pump RPM to spray rate per gun from measured per-gun output.",
        "detail": "Reproduces all 12 plant spray rates to within 0.0044 g/min. "
                  "Refuses to extrapolate outside the calibrated RPM range.",
    },
    {
        "n": "STEP 3", "icon": "🔬", "title": "Model Execution",
        "page": "app_pages/simulation_page.py",
        "status": "rebuilding",
        "what": "Dynamic batch simulation, spray/uniformity and CQA predictions.",
        "detail": "The dynamic core still applies heat loss twice and uses a "
                  "hard-coded 1-second evaporation constant. Numbers will render; "
                  "they are not yet defensible.",
    },
    {
        "n": "STEP 4", "icon": "🎲", "title": "Risk & Design Space",
        "page": "app_pages/uncertainty_page.py",
        "status": "mock",
        "what": "Uncertainty propagation and traffic-light design space.",
        "detail": "Currently propagates a **test stub**, not the real model. "
                  "Blocked until Stage 3 is rebuilt and validated.",
    },
]

BADGE = {
    "validated": ("✅ Validated", "#3fb950"),
    "rebuilding": ("🚧 Rebuilding — outputs unvalidated", "#d29922"),
    "mock": ("⛔ Mock — do not use", "#f85149"),
}

cols = st.columns(2)
for i, s in enumerate(STAGES):
    label, colour = BADGE[s["status"]]
    with cols[i % 2]:
        with st.container(border=True):
            st.markdown(f"##### {s['icon']} {s['n']}: {s['title']}")
            st.markdown(
                f"<span style='color:{colour};font-weight:600'>{label}</span>",
                unsafe_allow_html=True,
            )
            st.write(s["what"])
            st.caption(s["detail"])
            if _page_exists(s["page"]):
                st.page_link(s["page"], label=f"Open {s['title']}", icon="➡️")
            else:
                st.error(f"Page missing: `{s['page']}`")

st.markdown("### How the model is kept honest")
g1, g2, g3 = st.columns(3)
g1.metric("M1 vs frozen legacy EE", "1.4e-14 °C",
          help="The canonical core reproduces the legacy model exactly.")
g2.metric("Gate G3 benchmark", "0.6396 °C",
          help="EE's out-of-sample RMSE under a matched protocol. Any new module "
               "must match or beat this without physics violations.")
g3.metric("Test suite", "196 passing",
          help="Equivalence, conservation, bounds and acceptance-harness tests.")

st.caption(
    "Plant data is an **acceptance test set**, not training data. Batch 4 is sealed "
    "and run once, at the end. Full methodology in `PLAN_TRACK_A_REBUILD.md`; the "
    "frozen benchmark is `reports/baseline_locked.md`."
)
