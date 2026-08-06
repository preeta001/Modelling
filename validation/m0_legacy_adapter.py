"""M0 -- frozen legacy EE reference.

Loads the legacy EE physics from `Reference/EE-test-9-1-Varible-Solid-Fraction.py`
WITHOUT modifying it, so that every later model can be proved equivalent to it.

Two obstacles the legacy file presents, and how they are handled:

1. It imports `streamlit` at module scope and builds a full UI from line 397 on.
   We load only the physics prefix (everything before the first module-level
   `st.` statement) into a private namespace, with a `streamlit` stub in place.

2. Nothing stops the reference from being edited by accident. We record a
   SHA-256 of the file; `assert_frozen()` fails loudly if it ever changes.

This module is READ-ONLY with respect to the legacy file. It never writes to it.
"""
from __future__ import annotations

import hashlib
import sys
import types
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
LEGACY_PATH = REPO / "Reference" / "EE-test-9-1-Varible-Solid-Fraction.py"

# SHA-256 of the legacy file as audited on 2026-08-06. If this changes, the
# frozen baseline has moved and every equivalence claim must be re-established.
LEGACY_SHA256 = "162ceb7ce5625f44eaaabc8b0fe762e1af76047e6a35d9cd7922a4d88227705b"

# Functions the physics prefix must expose. If any is missing, the split point
# was wrong and we refuse to proceed rather than silently load a partial model.
REQUIRED_SYMBOLS = (
    "saturation_pressure_from_temp",
    "vapor_pressure_from_R_h",
    "humidity_ratio_from_vapor_pressure",
    "vapor_pressure_from_w",
    "air_density",
    "mass_flow_dry_air",
    "spray_rate_total",
    "water_evaporation_rate",
    "exhaust_humidity_ratio",
    "exhaust_temperature_first_law",
    "ee_factor",
    "calculate_spraying_time",
    "PanCoatingModel",
)


def file_sha256(path: Path = LEGACY_PATH) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_frozen(path: Path = LEGACY_PATH) -> None:
    """Fail if the legacy reference has been modified since it was audited."""
    actual = file_sha256(path)
    if actual != LEGACY_SHA256:
        raise RuntimeError(
            f"M0 reference has CHANGED.\n"
            f"  expected sha256 {LEGACY_SHA256}\n"
            f"  actual   sha256 {actual}\n"
            f"The legacy EE file is the frozen baseline and must never be edited. "
            f"Restore it, or -- if the change was deliberate -- re-run the Step 1A "
            f"audit and update LEGACY_SHA256 with a recorded justification."
        )


class _StreamlitStub(types.ModuleType):
    """Absorbs any `st.*` access without doing anything.

    The physics prefix imports streamlit but only touches it inside methods we
    never call. The stub keeps the import working headlessly.
    """

    def __init__(self) -> None:
        super().__init__("streamlit")
        self.session_state: dict[str, Any] = {}

    def __getattr__(self, name: str):
        def _noop(*_a, **_kw):
            return None

        return _noop


def _split_physics_prefix(source: str) -> str:
    """Return the source up to (not including) the first module-level `st.` call."""
    lines = source.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith("st."):
            return "".join(lines[:i])
    raise RuntimeError(
        "Could not find the start of the Streamlit UI in the legacy file. "
        "The physics/UI split point is no longer detectable; inspect the file."
    )


_module: types.ModuleType | None = None


def load_legacy(check_frozen: bool = True) -> types.ModuleType:
    """Load (once) the legacy physics into a private module object."""
    global _module
    if _module is not None:
        return _module

    if check_frozen:
        assert_frozen()

    source = LEGACY_PATH.read_text(encoding="utf-8")
    prefix = _split_physics_prefix(source)

    mod = types.ModuleType("m0_legacy_ee")
    mod.__file__ = str(LEGACY_PATH)

    saved = sys.modules.get("streamlit")
    sys.modules["streamlit"] = _StreamlitStub()
    try:
        exec(compile(prefix, str(LEGACY_PATH), "exec"), mod.__dict__)
    finally:
        if saved is not None:
            sys.modules["streamlit"] = saved
        else:
            sys.modules.pop("streamlit", None)

    missing = [s for s in REQUIRED_SYMBOLS if not hasattr(mod, s)]
    if missing:
        raise RuntimeError(
            f"Legacy physics prefix is missing expected symbols: {missing}. "
            f"The split point is wrong -- refusing to load a partial reference."
        )

    _module = mod
    return mod


def m0_exhaust_temperature(
    T_inlet_C: float,
    air_cfm: float,
    RH_inlet: float,
    spray_rate_g_min_gun: float,
    no_of_guns: int,
    solids_fraction: float,
    alpha: float,
    P_total_kPa: float = 101.325,
) -> dict[str, float]:
    """Run the legacy EE chain at a FIXED alpha and return every intermediate.

    No optimiser. Measured exhaust temperature is never an input here -- it may
    only be compared against the result afterwards.
    """
    L = load_legacy()

    p_g_i = L.saturation_pressure_from_temp(T_inlet_C)
    p_v_i = L.vapor_pressure_from_R_h(p_g_i, RH_inlet)
    w_inlet = L.humidity_ratio_from_vapor_pressure(P_total_kPa, p_v_i)
    rho_air_i = L.air_density(T_inlet_C, P_total_kPa, p_v_i, w_inlet)
    m_a = L.mass_flow_dry_air(air_cfm, rho_air_i)
    spray_total = L.spray_rate_total(spray_rate_g_min_gun, no_of_guns)
    m_w = L.water_evaporation_rate(spray_total, solids_fraction)
    w_exhaust = L.exhaust_humidity_ratio(m_w, m_a, w_inlet)
    T_exhaust = L.exhaust_temperature_first_law(T_inlet_C, w_inlet, w_exhaust, alpha)

    p_g_o = L.saturation_pressure_from_temp(T_exhaust)
    p_v_o = L.vapor_pressure_from_w(P_total_kPa, w_exhaust)
    RH_exhaust = L.R_h_from_p_v(p_v_o, p_g_o)

    return {
        "p_sat_inlet_kPa": p_g_i,
        "p_v_inlet_kPa": p_v_i,
        "w_inlet": w_inlet,
        "rho_moist_inlet": rho_air_i,
        "m_moist_air_kg_s": m_a,
        "m_dry_air_kg_s": m_a / (1.0 + w_inlet),
        "spray_total_g_min": spray_total,
        "m_solvent_kg_s": m_w,
        "w_exhaust": w_exhaust,
        "alpha_used": alpha,
        "T_exhaust_C": T_exhaust,
        "p_sat_exhaust_kPa": p_g_o,
        "p_v_exhaust_kPa": p_v_o,
        "RH_exhaust": RH_exhaust,
    }


if __name__ == "__main__":  # pragma: no cover
    print(f"legacy file : {LEGACY_PATH}")
    print(f"sha256      : {file_sha256()}")
    load_legacy(check_frozen=False)
    print("physics prefix loaded; all required symbols present.")
