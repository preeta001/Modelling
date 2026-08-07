# The Coating Model, Explained End to End

**A 360° walkthrough: every parameter, every equation, every law, every source paper, every check.**

Version 1.0 · 2026-08-07 · Companion to `PLAN_TRACK_A_REBUILD.md`

---

## How to read this document

It is written to be read by someone who has never seen the code, and to be *verifiable* by someone holding the source papers. Three conventions:

| Marker | Meaning |
|---|---|
| 📗 **Plain English** | The idea with no mathematics. Read these alone for a working understanding. |
| 🔢 **The equation** | The formula as implemented, with a pointer to the exact line of code. |
| 📄 **Source** | The paper the equation comes from, with DOI, so you can check it against the original. |
| ⚠️ **Caution** | A place where the model is uncertain, approximate, or known to be wrong. |

**If you read only one section**, read [§10 Error and accuracy analysis](#10-error-and-accuracy-analysis). It contains the single most consequential number in the project: how much room there actually is to improve on the existing model.

### Contents

**Part A — What the model is**
[§1 The big picture](#1-the-big-picture) · [§2 The physical laws](#2-the-physical-laws-underneath) · [§3 Every parameter](#3-every-parameter-what-why-where)

**Part B — The mathematics**
[§4 Every equation, derived](#4-every-equation-derived-from-scratch) · [§5 Equation → source paper map](#5-equation--source-paper-map) · [§6 The four workflows](#6-the-four-workflows) · [§7 How data flows through the code](#7-how-data-flows-through-the-code)

**Part C — How we know it works**
[§8 The non-degradation checks in full](#8-the-non-degradation-checks-in-full) · [§9 A fully worked example](#9-a-fully-worked-example) · [§10 Error and accuracy analysis](#10-error-and-accuracy-analysis)

**Part D — What is wrong or missing**
[§11 Lacunae](#11-lacunae--what-is-missing-or-unproven) · [§12 Where accuracy is lost, ranked](#12-where-accuracy-is-lost-ranked) · [§13 Alternative tracks](#13-alternative-tracks-worth-considering) · [§14 Glossary](#14-glossary)

---

# Part A — What the model is

## 1. The big picture

### 1.1 What physically happens in a coating pan

📗 **Plain English.** Tablets tumble inside a rotating perforated drum. Spray guns mist a liquid coating onto them. Hot dry air is blown through the tumbling bed and out an exhaust duct. The air does two jobs at once: it delivers heat, and it carries away the evaporating solvent. What is left behind on each tablet is a thin polymer film.

Everything the model does follows from one observation: **the exhaust air is a witness to what happened inside.** If a lot of solvent evaporated, the exhaust air is wetter and colder (evaporation absorbs heat). If little evaporated, it is drier and warmer. So by measuring exhaust temperature you can infer the drying environment the tablets actually experienced.

That inference is what the model formalises.

### 1.2 The causal chain

The model is deliberately built in three layers rather than predicting quality directly from machine settings.

```
   CPPs                    CTQs                        CQAs
(what you set)      (what the tablets feel)      (what the patient gets)
──────────────      ───────────────────────      ──────────────────────
Inlet temperature   Evaporation rate             Loss on drying (moisture)
Airflow             Bed temperature              Weight gain
Inlet humidity      Bed humidity / water         Film thickness
Spray rate          Wetness index                Dissolution
Solids fraction     Solvent load                 Assay / uniformity
Pan RPM             Mixing, circulation time     Related substances
Atomisation P       Droplet size, deposition     Appearance
Gun count/spacing   Spray flux                   Colour uniformity
```

📗 **Why not predict quality straight from settings?** Because the relationship is not stable. "Inlet temperature 60 °C" means completely different things in a 24-inch pan versus a 60-inch pan, in humid summer air versus dry winter air, at 200 g/min versus 400 g/min spray. The middle layer — the CTQs — is what stays physically comparable across all those situations. A statistical model fitted directly from CPPs to CQAs has to relearn everything for each new equipment/product/season; a mechanistic model that passes through the CTQ layer transfers.

📄 **Source:** `modelling.pdf` §3.1–3.2, Table 3.1. The PDF states the rule explicitly: *"Never pretend that a general heat-balance equation alone can predict assay or RS. The causal chain must pass through the intermediate CTQ layer."*

### 1.3 What this code currently does and does not do

| Layer | Status | Where |
|---|---|---|
| Psychrometry (air property calculations) | ✅ validated | `coating_model/psychrometrics.py`, `solvent_properties.py` |
| Steady-state energy & mass balance → exhaust temperature | ✅ validated against 9 plant stages | `coating_model/energy_balance.py` |
| Pump → spray-rate calibration | ✅ validated to 0.0044 g/min | `coating_model/gun_calibration.py` |
| Dynamic (time-resolved) bed model | 🚧 structurally wrong, being rebuilt | `coating_model/dynamic_model.py` |
| Spray / droplet / uniformity | ⛔ placeholder numbers, no data to fit | `coating_model/spray.py`, `exposure.py` |
| CQA prediction (dissolution, assay, RS) | ⛔ framework only | `coating_model/cqa.py` |
| Uncertainty / risk | ⛔ currently a test stub | `coating_model/uncertainty.py` |

⚠️ Only the first three rows produce numbers you should act on. Everything else renders but is labelled `UNVALIDATED` in the app.

---

## 2. The physical laws underneath

Only four laws are doing real work. Everything else is bookkeeping.

### 2.1 Law 1 — Conservation of energy (First Law of Thermodynamics)

📗 **Plain English.** Energy cannot appear or vanish. Every joule entering the pan must leave it, be stored in it, or be spent doing something. In steady state nothing is stored, so:

> energy carried in by hot air + energy carried in by the sprayed liquid
> = energy carried out by exhaust air + energy lost through the walls

The subtle part is *evaporation*. Turning liquid water into vapour costs about **2,260 kJ per kilogram** — an enormous amount, roughly five times what it takes to heat that same water from freezing to boiling. That energy has to come from somewhere, and it comes from the air. This is why exhaust air is cooler than inlet air: the evaporating solvent is stealing heat. It is the same reason sweating cools you down.

🔢 Per kilogram of dry air (`coating_model/energy_balance.py:266`):

```
cp_a·T_in + ω_in·h_v(T_in) + (ω_ex − ω_in)·h_liq   =   cp_a·T_ex + ω_ex·h_v(T_ex) + q_loss
└──────────────┬──────────────┘ └───────┬────────┘      └──────────┬──────────┘ └──┬──┘
   heat in the incoming air      liquid water            heat in the exhaust    wall
   (dry air + its vapour)        being added             (dry air + more vapour) losses
```

⚠️ **This single equation is where the original code failed.** The old version subtracted the *vapour* enthalpy (≈2,548 kJ/kg) for the incoming liquid water instead of the *liquid* enthalpy (104.76 kJ/kg), while the outlet term already carried the vapour enthalpy. The phase change was therefore paid for twice. The consequence was a prediction 5.2 °C too cold — so cold that the measured value lay *outside* what the model could reach even with heat loss set to zero. See [§10.6](#106-case-study-how-the-gates-caught-a-plausible-but-wrong-module).

### 2.2 Law 2 — Conservation of mass

📗 **Plain English.** Solvent atoms are not created or destroyed. Every gram of water sprayed either evaporates into the air, stays on the tablets as wet film, soaks into the tablet core, or drips away. In the steady-state model we assume all of it evaporates, so:

> water that evaporated = extra water the air is now carrying

🔢 `energy_balance.py:255`:
```
ṁ_evap = ṁ_dry_air · (ω_ex − ω_in)
```

This is checked as a hard test — `tests/test_conservation.py::test_water_mass_balance_closes` asserts the two sides agree to 1 part in 10¹².

### 2.3 Law 3 — Ideal gas law and Dalton's law of partial pressures

📗 **Plain English.** Air is a mixture of dry air and water vapour. Dalton's law says each behaves as if the other were not there — the total pressure is just the sum of their separate pressures. This lets us treat "how much water is in the air" as a pressure, which is far easier to work with. The ideal gas law then converts pressures into densities and masses.

🔢 The humidity ratio (`energy_balance.py:239`):
```
ω = (R_d / R_v) · p_v / (P_total − p_v) = 0.62199 · p_v / (P − p_v)
```

📗 **Why 0.62199?** It is the ratio of the molecular weight of water (18.015) to that of air (28.966). Water molecules are lighter, so a given *number* of water molecules weighs less than the same number of air molecules — hence the correction factor.

### 2.4 Law 4 — Vapour–liquid equilibrium (the Antoine equation)

📗 **Plain English.** At any temperature, there is a maximum amount of water vapour air can hold. Warm air holds much more — this is why a cold drink "sweats" (the air touching it cools below its capacity and dumps the excess as droplets). The Antoine equation gives that maximum, called the **saturation pressure**.

🔢 `coating_model/solvent_properties.py:20`:
```
log₁₀(p_sat in torr) = A − B / (C + T)          then × 0.133322 to convert torr → kPa
```
With A = 8.07131, B = 1730.63, C = 233.426 for water.

⚠️ **A units trap that has bitten this code before.** Antoine coefficients are published in many unit systems. These particular ones give **torr**, not kPa or bar. Forgetting the 0.133322 conversion makes the saturation pressure 7.5× too large, which silently poisons every humidity calculation downstream. The conversion is applied inside `saturation_pressure()` so it can only be done once and cannot be forgotten by a caller.

---

## 3. Every parameter: what, why, where

### 3.1 Physical constants — fixed by nature, never fitted

These are not adjustable. They come from thermodynamic tables. Defined in `coating_model/constants.py` and `solvent_properties.py`.

| Symbol | Code name | Value | Units | What it is | Why this value |
|---|---|---|---|---|---|
| c_p,a | `Cp_air` | 1.005 | kJ/kg·K | Specific heat of dry air | Energy to warm 1 kg of air by 1 K. Standard value near ambient. |
| R_d | `R_d` | 287.058 | J/kg·K | Gas constant, dry air | Universal gas constant ÷ molar mass of air (8314/28.966). |
| R_v | `R_v` | 461.495 | J/kg·K | Gas constant, water vapour | 8314/18.015. Ratio R_d/R_v = 0.62199 appears in every humidity formula. |
| h_liq | `H_LIQUID_WATER_AT_25C` | 104.7598 | kJ/kg | Enthalpy of liquid water at 25 °C | Heat content of the spray liquid as it arrives. ≈ 4.18 × 25. |
| A, B, C | `antoine_A/B/C` | 8.07131, 1730.63, 233.426 | — | Antoine coefficients, water | Empirical fit to measured vapour pressure, valid ~1–100 °C. |
| a_h, b_h | `enthalpy_A`, `enthalpy_B` | 1.7208, 2505.2 | kJ/kg·K, kJ/kg | Vapour enthalpy line: h_v(T) = a_h·T + b_h | Linearisation of steam-table vapour enthalpy over the working range. At 50 °C gives 2591 kJ/kg (steam tables: 2592). |
| — | `CFM_TO_M3_S` | 0.00047194745 | — | Cubic feet/min → m³/s | Exact unit conversion. |

⚠️ **Naming caution, and it matters.** The function `enthalpy_vapor_from_temp()` in the legacy code (and `latent_heat()` in an early refactor) returns the **total vapour enthalpy**, *not* the latent heat of vaporisation. Latent heat is the *difference* h_v − h_liq ≈ 2,486 kJ/kg at 25 °C; total vapour enthalpy is ≈ 2,548 kJ/kg. The misleading name is what caused the fatal double-count. The canonical core renames it `vapour_enthalpy()` and makes the old name raise an error rather than silently work.

### 3.2 Fitted parameters — the only adjustable knobs

📗 **Plain English.** Here is something reassuring about this model: the psychrometrics, the mass balance and the adiabatic (no-heat-loss) energy balance contain **zero** adjustable numbers. They are pure physics. Run that way, on the audit row, the model predicts 51.601 °C against a measured 48.519 °C — a genuine prediction with nothing fitted, 3.08 °C high.

That 3.08 °C gap is the entire job of the fitted parameters. There are only two, and one of them is currently switched off.

| Symbol | Code name | Physical meaning | Typical value here | How obtained | Status |
|---|---|---|---|---|---|
| UA | `UA_kW_K` | Overall heat-loss conductance: pan walls, ducting, uninsulated surfaces. Units kW per K of temperature difference. | 0.10–0.16 kW/K | Fitted on the calibration batch, then locked | **active** |
| α | `alpha` | UA normalised by dry-air mass flow: α = UA / ṁ_da. The legacy model's parameter. | 0.035–0.198 | Derived from UA, never fitted independently | derived |
| η_evap | `evaporated_fraction` | Fraction of sprayed solvent that evaporates *inside* the control volume | 1.0 (assumed) | Hypothesis — **tested and rejected**, see §10.6 | **disabled** |

📗 **Why UA rather than α?** α depends on airflow, so it is not a property of the equipment — it changes when you change the fan. UA *is* an equipment property. If you fit α on one airflow and reuse it at another, the heat-loss term is wrong by the airflow ratio, up to 3× over a typical operating range.

⚠️ On *this particular dataset* the distinction makes no measurable difference, because airflow varies by only 0.19 % across all 12 stages. The correction is right and matters the moment airflow varies; it will not improve today's numbers. Stated here so nobody later reports it as an improvement.

📄 **Source:** `modelling.pdf` §2.3.1 identifies both the sign error and the α-vs-UA issue. Independently re-derived — see §4.7.

### 3.3 Process inputs — measured or set on the machine

| Input | Code name | Units | Role | Notes |
|---|---|---|---|---|
| Inlet temperature | `T_inlet_C` | °C | Drives everything | **Dominates the error budget — 94 % of variance, see §10.2** |
| Airflow | `air_cfm` | CFM | Sets drying capacity | Converted to kg dry air/s immediately |
| Inlet relative humidity | `RH_inlet` | fraction 0–1 | Sets how much water the air can still absorb | ⚠️ 0.05 on every row — possibly a typed default |
| Spray rate per gun | `spray_rate_g_min_gun` | g/min/gun | Sets the solvent load | From Stage 2 calibration, not typed |
| Number of guns | `no_of_guns` | — | Multiplies spray rate | 6 here |
| Solids fraction | `solids_fraction` | fraction | Splits spray into solids (stay) and solvent (evaporate) | 0.15 here |
| Total pressure | `P_total_kPa` | kPa | Psychrometric reference | 101.325 (atmospheric) |
| Ambient temperature | `T_amb_C` | °C | Heat-loss driving force | ⚠️ Hard-coded 25 °C — not measured |
| Pan RPM | `pan_rpm` | rpm | Recorded, **not used** in the thermodynamics | See §10.5 — likely matters, cannot be proven here |
| Atomisation pressure | `atomisation_bar` | bar | Recorded, **not used** | Constant 2 bar — zero information |

### 3.4 Where every parameter is actually used

A reading guide for the code:

| Parameter | Enters at | Used in |
|---|---|---|
| A, B, C | `solvent_properties.py:20` | p_sat(T_inlet), p_sat(T_exhaust), wet-bulb iteration |
| R_d, R_v | `energy_balance.py:239` | ω, air density, p_v from ω |
| c_p,a | `energy_balance.py:266,283` | Numerator and denominator of the exhaust-temperature solve |
| a_h, b_h | `energy_balance.py:267,269` | Inlet vapour term, outlet vapour offset |
| h_liq | `energy_balance.py:268` | The liquid-water inlet term — **the one that was wrong** |
| UA → α | `energy_balance.py:259` | α = UA/ṁ_da, then both numerator and denominator |
| η_evap | `energy_balance.py:253` | Scales ṁ_evap, hence ω_ex, hence everything |
| CFM_TO_M3_S | `energy_balance.py:247` | Volumetric → mass flow |

---

# Part B — The mathematics

## 4. Every equation, derived from scratch

This section builds the model in the order the code executes it. Each step feeds the next.

### 4.1 Step 1 — How much water is already in the incoming air?

📗 The air arriving is not bone dry. Before we can ask how much *more* water it can absorb, we need to know what it starts with.

🔢 **(a) Saturation pressure** — the maximum vapour pressure at this temperature:
```
p_sat = 0.133322 · 10^(A − B/(C + T_in))
```
At T_in = 56.507 °C → **16.871089 kPa**.

🔢 **(b) Actual vapour pressure** — relative humidity is *by definition* the fraction of the maximum:
```
p_v = RH · p_sat = 0.05 × 16.871089 = 0.843554 kPa
```

🔢 **(c) Humidity ratio** — convert pressure to a mass ratio, which is what mass balances need:
```
ω_in = 0.62199 · p_v / (P − p_v) = 0.62199 × 0.843554 / (101.325 − 0.843554)
     = 0.0052219 kg water per kg dry air
```
📗 So each kilogram of dry air is carrying about 5.2 grams of water. Very dry air.

### 4.2 Step 2 — How much air is flowing, by mass?

📗 **Why mass and not volume?** The fan is rated in CFM (a *volume* per time), but energy and mass balances need *mass* per time. Hot air is less dense, so 2800 CFM of hot air is fewer kilograms than 2800 CFM of cold air. Getting this wrong is a classic error.

🔢 **(a) Moist-air density** (`energy_balance.py:243`):
```
ρ = [ (P − p_v)·1000 / (R_d·(T+273.15)) ] · (1 + ω) / (1 + ω·R_v/R_d)
```
📗 The first bracket is the ideal gas law for the dry-air portion. The second factor corrects for the vapour riding along: it adds mass (numerator) but takes up more volume per unit mass (denominator).
→ **1.0584860 kg/m³**

🔢 **(b) Moist-air mass flow:**
```
ṁ_moist = 2800.63 × 0.00047194745 × 1.0584860 = 1.3990541 kg/s
```

🔢 **(c) Dry-air mass flow** — the accounting basis for everything after this:
```
ṁ_da = ṁ_moist / (1 + ω_in) = 1.3990541 / 1.0052219 = 1.3917863 kg/s
```
📗 **Why work "per kg of dry air"?** Because the mass of dry air is *conserved* through the pan — none is created or destroyed. The mass of water is not (it increases). Anchoring the books to the unchanging quantity makes the algebra clean. This is standard practice in psychrometrics and the reason humidity ratio is defined per kg dry air.

⚠️ The legacy function name `mass_flow_dry_air()` actually returns **moist**-air flow. The name is wrong and was a source of confusion. The canonical core keeps both quantities explicitly and separately named.

### 4.3 Step 3 — How much solvent evaporates?

🔢 ```
spray_total = 32.72 × 6 = 196.32 g/min
ṁ_solvent   = 196.32 × (1 − 0.15) / 60000 = 0.00278120 kg/s
ṁ_evap      = ṁ_solvent × η_evap = 0.00278120 kg/s      (η_evap = 1)
```
📗 The (1 − solids) factor is because only the solvent evaporates; the 15 % solids stay behind on the tablets — that is the entire point of the process. The 60000 converts g/min to kg/s.

⚠️ **The assumption in `η_evap = 1`.** We are asserting that *all* sprayed solvent evaporates inside the pan before the air leaves. In reality some leaves with the tablets as wet film, some soaks into the cores. §10.6 tests whether relaxing this helps — it does not, and the reason is instructive.

### 4.4 Step 4 — How wet is the exhaust air?

🔢 ```
ω_ex = ω_in + ṁ_evap / ṁ_da = 0.0052219 + 0.00278120/1.3917863 = 0.0072202 kg/kg
```
📗 The air arrived with 5.22 g of water per kg and leaves with 7.22 g — it picked up 2.0 g per kilogram of air. That is Law 2 (§2.2) in one line.

### 4.5 Step 5 — Solving for exhaust temperature

📗 **The idea.** We now know everything except the exhaust temperature. Write the energy balance, and T_ex is the only unknown. Because the vapour enthalpy is *linear* in temperature (h_v = a_h·T + b_h), the whole equation is linear in T_ex — so it can be solved exactly with algebra. No iteration, no optimiser.

**The derivation, line by line.** Start from §2.1:
```
c_p·T_in + ω_in·h_v(T_in) + (ω_ex−ω_in)·h_liq = c_p·T_ex + ω_ex·h_v(T_ex) + q_loss
```
Substitute h_v(T) = a_h·T + b_h on both sides:
```
c_p·T_in + ω_in·(a_h·T_in + b_h) + (ω_ex−ω_in)·h_liq
  = c_p·T_ex + ω_ex·(a_h·T_ex + b_h) + q_loss
```
Take q_loss = α·((T_in + T_ex)/2 − T_amb) and gather every T_ex term on the left:
```
T_ex·(c_p + a_h·ω_ex + α/2)
  = T_in·(c_p + a_h·ω_in − α/2) + (ω_ex − ω_in)·(h_liq − b_h) + α·T_amb
```
🔢 **Therefore** (`energy_balance.py:271–288`):
```
              T_in·(c_p + a_h·ω_in − α/2) + (ω_ex − ω_in)·(h_liq − b_h) + α·T_amb
    T_ex  =  ─────────────────────────────────────────────────────────────────────
                            c_p + a_h·ω_ex + α/2
```

📗 **Reading the physics off the formula:**
- The `(ω_ex − ω_in)·(h_liq − b_h)` term is the evaporative cooling. Since b_h = 2505.2 ≫ h_liq = 104.76, this is a large **negative** number — it pulls the temperature down. That is the sweating effect.
- The `α` terms are the wall losses. Increasing α cools the exhaust further.
- The denominator grows with ω_ex: wetter air has more thermal inertia per kg of dry air.

🔢 **Result for the audit row at α = 0:** T_ex = **51.601381 °C**. At α = 0.11399: **48.5189 °C** against a measured 48.519 °C.

### 4.6 Step 6 — Exhaust humidity (a by-product, and a warning)

🔢 ```
p_v,ex = ω_ex·P / (0.62199 + ω_ex)
RH_ex  = p_v,ex / p_sat(T_ex)
```
→ RH_ex = 0.1017 for the audit row.

⚠️ **There is no measured exhaust RH anywhere in the dataset to check this against.** The `Exhaust RH` column in the plant table is not a measurement — it is the old model's own output, verified reproducible to 0.0005 across all 12 rows. Validating our RH against it would be scoring this model against the model it replaces. Exhaust RH is therefore tagged `UNVALIDATED`. Getting one real hygrometer reading would be the single highest-value data addition available, because RH constrains the **mass** balance where temperature constrains the **energy** balance.

### 4.7 The heat-loss term, and the sign error

📗 **Plain English.** Heat leaks out through the pan walls. Newton's law of cooling says the leak is proportional to how much hotter the equipment is than the room:

> heat lost = (conductance) × (equipment temperature − room temperature)

Since the air cools as it passes through, we use the *average* of inlet and exhaust as the representative temperature.

🔢 **Correct** (`heat_loss_form="physical_ua"`):
```
q_loss = α · ( (T_in + T_ex)/2 − T_amb )
```

🔢 **What the legacy code implements** (`heat_loss_form="legacy_alpha"`):
```
q_loss = α · ( (T_ex − T_in)/2 + T_amb )
```

⚠️ **Why this is wrong and why nobody noticed.** The sign inside the bracket is flipped. The legacy form says heat loss *increases* when the room gets hotter — physically backwards. Yet:
- At α = 0 the two forms are **identical**, so the parameter-free core is sound.
- With α fitted separately per stage, the wrong functional form plus a free parameter still hits the calibration point exactly. The error is invisible in the calibration table.
- It only shows up when you extrapolate, or when ambient temperature changes.

Both forms are kept and explicitly selectable so the legacy model remains reproducible on demand, and `tests/test_conservation.py::test_heat_loss_responds_correctly_to_ambient` pins the correct behaviour so a future "simplification" cannot quietly restore the bug.

📄 **Source:** `modelling.pdf` §2.3.1, eqs (2.9) vs (2.10). Independently re-derived here from the First Law.

### 4.8 The Environmental Equivalency (EE) factor

📗 **Plain English.** The EE factor is a single number summarising "how aggressive is the drying environment". Two batches with the same EE are *supposed* to have equivalent drying conditions even at different scales. It is essentially a ratio of the air's water-absorbing capacity to its heat-delivering capacity.

🔢 `coating_model/steady_state.py:88` — retained for backward comparability:
```
        ρ_v,wb(T_wb) − ρ_v(T_in)
EE = ───────────────────────────────────
      ρ̄_air · c_p · (T_in − T_ex) / Δh_v
```
where T_wb is the inlet wet-bulb temperature.

⚠️ **Two cautions.**
1. **EE is not the Wetness Index.** They are different quantities with different scales — EE ≈ 4.2–5.2 here, WI ≈ 0–1.5. The old code labelled WI as "EE Factor" in two places. Fixed, but worth knowing if you read old screenshots.
2. **Equal EE does not guarantee equal tablet conditions.** The literature is explicit: at 15 inch, EEF = 2.78 gave bed RH 30 %; at 24 inch, EEF = 2.77 gave bed RH 40 %. Nearly identical EE, very different microenvironment.

📄 **Source:** Ebey (1987) for the original concept; Strong (2009) DOI 10.1208/s12249-009-9204-7 for the psychrometric analysis; Pandey, Bindra & Felton (2014) for the equal-EE-≠-equal-conditions finding.

### 4.9 The wet-bulb temperature

📗 **Plain English.** The wet-bulb temperature is the coldest an evaporating wet surface can get in a given airstream — the temperature at which evaporative cooling exactly balances heat arriving from the air. It is a natural floor for the tablet bed temperature and a useful reference.

🔢 `coating_model/psychrometrics.py:34` solves iteratively by bisection:
```
(h_fg(T*) − c_p,L·T*)·ω_sat(T*) − c_p,a·(T_db − T*) = 0
```

### 4.10 The Wetness Index

📗 **Plain English.** The simplest useful safety metric in the whole model: *are you spraying faster than the air can dry?*

🔢 `coating_model/wetness.py:4`:
```
WI = solvent applied / drying capacity
```
- WI < 1 — the air can keep up. Safe.
- WI ≈ 1 — no margin. Any disturbance causes wetting.
- WI > 1 — solvent accumulates. Overwetting, sticking, picking.

🔢 The cumulative version is a better defect predictor than any single peak:
```
EWI = ∫ max(0, WI(t) − WI_crit) dt
```
📗 A brief spike above the limit may be harmless; sustained overwetting is not. EWI captures both magnitude and duration.

📄 **Source:** `modelling.pdf` §5.4, eqs (5.6)–(5.7).

### 4.11 Weight gain and film thickness

🔢 ```
WG(t) = η_dep · ∫ ṁ_spray·x_s dτ / M_core          (fraction of core mass gained)
δ     = m_coat / (ρ_film · A_tablet)                (mean dry film thickness)
```
📗 Weight gain is nothing more than "how much solid stuck, divided by how much tablet you started with". Film thickness spreads that mass over the tablet surface at the film's density.

⚠️ **Currently uncalibratable.** η_dep needs the true batch core load, which is not recorded. Back-calculating it from the four weight-gain values gives core masses spanning 343–406 kg — a 17 % spread. Either the load varies, or η_dep varies by that much, or the sprayed totals are unreliable. Also note the `Solution (kg)` column is a *nominal recipe* value: batches 1 and 3 sprayed 5–6 % **more** solution than the batch nominally contained, so it must not be used as the mass basis.

📄 **Source:** `modelling.pdf` §9.1–9.2, eqs (9.1)–(9.2).

---

## 5. Equation → source paper map

**This is the table to use for baseline verification against the literature.**

| # | Equation | Implemented in | Primary source | DOI / locator |
|---|---|---|---|---|
| E1 | Antoine saturation pressure | `solvent_properties.py:20` | Standard correlation; coefficients in torr | — |
| E2 | Humidity ratio ω = 0.622 p_v/(P−p_v) | `energy_balance.py:239` | Standard psychrometry (ASHRAE) | — |
| E3 | Moist-air density | `energy_balance.py:243` | Standard psychrometry | — |
| E4 | Steady-state energy balance → T_ex | `energy_balance.py:271` | **am Ende & Berchielli (2005)** — closed-form thermodynamic model | 10.1081/PDT-35915 |
| E5 | EE / EEF concept | `steady_state.py:88` | **Ebey (1987)**, *Pharm. Technol.* 11, 40–50 | — |
| E6 | EEF psychrometric analysis | `steady_state.py:88` | **Strong (2009)**, *AAPS PharmSciTech* 10(1) 303–309 | 10.1208/s12249-009-9204-7 |
| E7 | Heat loss q = UA·(T̄ − T_amb) | `energy_balance.py:213` | Newton cooling; sign correction per `modelling.pdf` §2.3.1 | — |
| E8 | Wet-bulb temperature | `psychrometrics.py:34` | Standard adiabatic-saturation balance | — |
| E9 | Dynamic bed temperature ODE | `dynamic_model.py:98` 🚧 | **Rodrigues et al. (2023)**, *Comput. Chem. Eng.* | 10.1016/j.compchemeng.2023.108... |
| E10 | Two-zone (spray/drying) model | `dynamic_model.py` 🚧 | **Page, Baumann & Kleinebudde (2006)**, *AAPS PharmSciTech* 7(4) E42 | 10.1208/pt070242 |
| E11 | Wetness index, EWI | `wetness.py:4` | `modelling.pdf` §5.4 (synthesised) | — |
| E12 | Droplet size ← atomisation P | `spray.py:9` ⛔ **placeholder** | **Niblett et al. (2017)** — Ni, ψ | not implemented from source |
| E13 | Flight-drying number Π | `spray.py:22` ⛔ **placeholder** | Niblett et al. (2017) | not implemented from source |
| E14 | Monte Carlo coating mass, CV | `exposure.py:12` ⛔ uncalibrated | **Pandey, Katakdaunde & Turton (2006)**, *AAPS PharmSciTech* 7(4) E83 | 10.1208/pt070483 |
| E15 | Residence / circulation time | `exposure.py` ⛔ uncalibrated | **Kalbag et al. (2008)**, *Chem. Eng. Sci.* 63, 2881–2894 | 10.1016/j.ces.2008.03.009 |
| E16 | CV ∝ 1/√t_f | `spray_uniformity_page.py` | Pandey et al. (2006) | 10.1208/pt070483 |
| E17 | Weight gain | `cqa.py:5` | `modelling.pdf` §9.1 | — |
| E18 | Film thickness | `cqa.py:8` | `modelling.pdf` §9.2 | — |
| E19 | Thermal / moisture exposure integrals | `cqa.py:16,21` | **Kestur et al. (2014)**, *Int. J. Pharm.* 476, 93–98 | — |
| E20 | Assay from coating mass | `cqa.py:13` | **Chen et al. (2010)**; **Just et al. (2013)** | — |

⚠️ **Rows E12–E15 are the important caveat.** These are *not* implementations of the cited papers. `spray.py:9` contains `d32_base = 40.0` with heuristic exponents and an inline comment reading "Dummy scaling for demo". The correlations require spray-pattern measurements (spray angle, pattern width, overlap, droplet velocity) that do not exist in this dataset. Do not verify these against Niblett or Pandey — there is nothing there to verify yet. The honest replacement is described in §13.

### 5.1 Thermodynamic model families considered

📄 From `modelling.pdf` Table 4.1, ranked by suitability:

| Rank | Model | Type | Validation scale |
|---|---|---|---|
| 1 | am Ende & Berchielli (2005) | Steady, lumped | 1–220 kg |
| 2 | Rodrigues et al. (2023) | Dynamic macro | 7 pilot batches |
| 3 | Page et al. (2006) | Dynamic two-zone | Bohle Lab-Coater |
| 4 | Strong (2009) | Steady psychrometric | Theoretical |
| 5 | Cha et al. (2019) | Dynamic evaporation + penetration | GEA ConsiGma |
| 6 | Ebey (1987) | Steady EE | Industrial |

**What is implemented today is #1/#6** (the steady lumped balance — they share the same core). #2 and #3 are the targets for the dynamic rebuild.

---

## 6. The four workflows

### Stage 1 — Model validation & calibration
**Page:** `app_pages/validation_page.py` · **Core:** `coating_model/energy_balance.py` · **Status:** ✅ validated

```
Load a batch from the acceptance set
        ↓
For each stage: inlet T, airflow, RH, spray rate, measured exhaust T
        ↓
┌───────────────────────────┬────────────────────────────────┐
│ PASS 1 — calibration      │ PASS 2 — locked prediction     │
│ fit α per row to hit that  │ freeze stage 1's α, use it on  │
│ row's own measurement      │ the later stages               │
│ → error ≈ 0.000 (a FIT)   │ → real error (a PREDICTION)    │
└───────────────────────────┴────────────────────────────────┘
        ↓
Two-column table + physics checks + α-spread warning + zero-parameter reference
```

📗 **Why both columns?** Because with one free parameter per row and zero degrees of freedom left, near-zero error is *arithmetically guaranteed* — every model scores 0.000, so a better model is indistinguishable from a worse one. The locked column is the only one that responds to the physics actually improving. Both are shown so nothing you are used to seeing is taken away.

### Stage 2 — Gun / pump calibration
**Page:** `app_pages/gun_validation.py` · **Core:** `coating_model/gun_calibration.py` · **Status:** ✅ validated

```
Six guns weighed at two pump speeds (5 and 10 rpm), per batch
        ↓
Least-squares line:  rate_per_gun = m·rpm + c
        ↓
Guards: refuse extrapolation outside 5–10 rpm │ flag non-physical intercept
        │ detect blocked nozzles (median/MAD)  │ compute gun-to-gun CV
        ↓
Publish with provenance → consumed by Stages 1 and 3
```

**Verified:** reproduces all 12 plant spray rates to within **0.0044 g/min**; m and c match the plant record to 1e-6.

⚠️ Two structural limitations. Only two calibration points exist, so the fit has **zero degrees of freedom** — linearity is untested and there is no residual to inspect. And the intercept (2.8–3.7 g/min at 0 rpm) is non-physical, since a stopped pump delivers nothing. Within 7–9 rpm this is interpolation and sound; outside 5–10 rpm the code refuses to answer.

### Stage 3 — Model execution
**Pages:** `simulation_page.py`, `spray_uniformity_page.py`, `cqa_page.py`, `execution_summary.py` · **Status:** 🚧 rebuilding

⚠️ **Three known structural faults in the dynamic core:**
1. Heat loss is applied **twice** — once in the bed ODE (`dynamic_model.py:95`) and again through α = UA/ṁ_da inside the exhaust equation (`dynamic_model.py:196`).
2. Evaporation uses `min(capacity, M_w/1.0)` — a hard-coded 1-second draining time constant with no physical justification, which makes results depend on the integrator's step size.
3. Zone-exchange terms do not conserve energy on transfer.

The rebuild plan uses an **algebraic gas phase** with a **dynamic bed**, justified by timescale separation: gas residence is 0.6–1.1 s while the bed's thermal time constant is 1,900–3,800 s — a ratio of 2,000–6,000×. That separation also makes the steady-state limit of the dynamic model *provably* equal to the Stage 1 core, which becomes the collapse test.

### Stage 4 — Risk & design space
**Page:** `uncertainty_page.py` · **Status:** ⛔ mock

⚠️ Currently imports `dummy_sim_func` from the **test suite** and propagates uncertainty through a stub returning `1.1 if spray_rate > 50 else 0.9`. Rebuild is blocked until Stage 3 is validated, and correctly so: an optimiser searches for where the model's prediction is most extreme, which is exactly where model error is largest. Optimising an unvalidated model is worse than not optimising, because it converges confidently on the blind spot.

---

## 7. How data flows through the code

```
data/acceptance/gun_calibration_v1.csv          data/acceptance/stages_v1.csv
   (6 guns × 2 speeds × 4 batches)                (12 stages, provenance-tagged)
            │                                              │
            ▼                                              │
  gun_calibration.fit_pump_calibration()                    │
            │  m, c, gun CV, guards                         │
            ▼                                              │
  spray_rate_for_stage(batch, rpm) ──────────┐              │
            SprayRate(value, source)         │              │
                                            ▼              ▼
                              ╔══════════════════════════════════════╗
                              ║  coating_model/energy_balance.py     ║
                              ║  calculate_exhaust_state(...)        ║
                              ║  THE single canonical core           ║
                              ╚══════════════════════════════════════╝
                                            │
        ┌───────────────────┬───────────────┼───────────────┬──────────────────┐
        ▼                   ▼               ▼               ▼                  ▼
 steady_state.py      validation_page   dynamic_model   simulation_page   optimiser
 (EE factor facade)   (Stage 1 UI)      (🚧 Stage 3)     (Stage 3 UI)      (⛔ Stage 4)
        │
        ▼
 validation/acceptance.py ── gates G1–G5 ──▶ reports/baseline_locked.md
        ▲                                        (frozen benchmark)
        │
 validation/m0_legacy_adapter.py
 (frozen legacy EE, SHA-256 pinned)
```

📗 **The single most important structural property:** there is exactly **one** implementation of the exhaust-temperature equation. There used to be four, and they disagreed. Anything that needs the physics calls `calculate_exhaust_state()`; nothing reimplements it. A test greps for the equation's constants to keep it that way.

---

# Part C — How we know it works

## 8. The non-degradation checks in full

📗 **The problem these solve.** Adding modules to a model feels like progress but often is not. A new term with a free parameter will almost always reduce the error on the data you fitted it to — that is arithmetic, not physics. Without mechanical checks, a model accumulates complexity while quietly getting worse at prediction. These gates make "did that help?" an objective question.

### 8.1 The three error targets — never mixed

| Target | Definition | Requirement |
|---|---|---|
| **T1 — software reproduction** | Canonical core vs frozen legacy, same inputs and α | \|ΔT\| < 1e-9 °C · **achieved: 1.4e-14** |
| **T2 — calibration residual** | Per-row fitted α | ≈ 0, always labelled *a fit* |
| **T3 — locked prediction** | Parameters frozen before the rows are seen | **RMSE ≤ 0.6396 °C, max ≤ 1.2336 °C** |

⚠️ T2 and T3 must never be compared with each other. `validation/acceptance.py:check_non_degradation()` raises an exception if you try.

### 8.2 The five gates

Every candidate module must pass **all five**. Any failure → the module is flag-disabled, its evidence filed, and it goes to the future-work list. It is not tuned until it passes.

| Gate | Question | Test | Threshold |
|---|---|---|---|
| **G1 Collapse** | Does it reduce to its parent when switched off? | Disable the new term, compare | < 1e-9 |
| **G2 Physics** | Is the result physically possible? | Mass/energy closure, bounds, **no fitted parameter resting on a bound** | zero violations |
| **G3 Non-degradation** | Does it predict unseen data at least as well? | RMSE **and** max both ≤ benchmark | both must hold |
| **G4 Identifiability** | Is the parameter actually determined by the data? | \|θ\|/SE(θ) from fold spread | > 2, consistent sign |
| **G5 Parsimony** | Is the gain bigger than measurement noise? | ΔRMSE | ≥ 0.05 °C |

📗 **G2's bound clause is the one that earns its keep.** A parameter sitting exactly on its allowed limit is the optimiser telling you it wanted to go further but could not — which means the model structure is wrong, not that the parameter value is right. The original Track A failure pinned UA at 0.0 and still missed by 2 °C; that clause alone would have caught it on day one. §10.6 shows it catching a second, much more plausible case.

📗 **G3 requires *both* RMSE and maximum error.** A change can improve the average while making one stage dramatically worse. In a pharmaceutical process the worst case is what causes a batch deviation, so a better mean with a worse worst-case is a rejection.

### 8.3 The acceptance-test discipline

📗 **Plain English.** The plant data is a *final exam*, not a textbook. The model is built from physics and then tested against the data. This is stricter than the usual practice of fitting to the data and reporting the fit.

| Batch | Role | May be consulted |
|---|---|---|
| 1 | Calibration — the one parameter is fitted here | during calibration |
| 2, 3 | Development acceptance | freely, logged |
| 4 | **SEALED** | **once, at the very end** |

⚠️ **The hazard in "iterate until it works".** A fixed test set consulted after every iteration stops being held out. Twenty rounds of test → adjust → retest fits the model to those rows through *structural* choices, with no record it happened. Three defences: the sealed batch (physically withheld by `validation/acceptance.py`, and unsealing requires a written reason); an iteration log; and the rule that every change must be justified physically *before* the test is run.

### 8.4 The leakage hierarchy — why the benchmark is 0.6396 and not 0.43

This is subtle and it changes the target, so it is worth being precise.

| Policy | Free parameters | Fitted on | Leaky? | RMSE |
|---|---|---|---|---|
| Per-row fitted α | 9 (one per row) | the row it predicts | **totally** | 0.0000 |
| Per-batch `Alpha Avg` | 1 per batch | rows of the *same* batch | **yes** | 0.5958 |
| Single global α | 1 | mean of all batches' fitted α | mildly | 0.6520 |
| **Locked α, matched protocol** | **1** | **batch 1 only** | **no** | **0.7117** (dev rows: **0.6396**) |
| Adiabatic | 0 | nothing | no | 2.4179 |

📗 The per-batch `Alpha Avg` looks like a fair benchmark but is not: it is the *average of parameters fitted to that batch's own three rows*. Predicting batch 2 with batch 2's alpha-average has already seen batch 2's answers. Held to the same standard we hold ourselves to, EE scores **0.6396 °C** — and that is the number in gate G3.

### 8.5 What is tested, where

| Test file | Guards | Count |
|---|---|---|
| `test_m0_m1_equivalence.py` | T1; legacy frozen by SHA-256; both heat-loss forms distinct; adiabatic value pinned | 30 |
| `test_conservation.py` | Energy closure; mass closure; bounds over a 108-point operating grid; monotonicity; ambient response; liquid-vs-vapour enthalpy | 130 |
| `test_gun_calibration.py` | A2 target; extrapolation refusal; zero-dof flag; blocked-nozzle detection; provenance | 10 |
| `test_acceptance_harness.py` | Sealed batch withheld; EE-output columns rejected as targets; G3 needs both metrics; G5 parsimony; fit-vs-prediction separation | 9 |
| others | psychrometrics, spray, CQA, exposure, summary, batch runner | 17 |
| **Total** | | **196 passing** |

📗 Each test names the defect it prevents, so a future change that reintroduces the latent-heat double count fails with a message saying exactly that.

---

## 9. A fully worked example

Every number for batch 1, stage 1 (pump 7 rpm). You can check each line by hand.

**Inputs:** T_in = 56.507 °C · airflow = 2800.63 CFM · RH_in = 0.05 · spray = 32.72 g/min/gun × 6 guns · solids = 0.15 · P = 101.325 kPa · T_amb = 25 °C

| Step | Quantity | Value | Units |
|---|---|---|---|
| 1a | p_sat(T_in) | 16.871088521060 | kPa |
| 1b | p_v = 0.05 × p_sat | 0.843554426053 | kPa |
| 1c | ω_in | 0.005221916087 | kg/kg da |
| 2a | ρ_moist | 1.058486024426 | kg/m³ |
| 2b | ṁ_moist | 1.399054100610 | kg/s |
| 2c | ṁ_dry air | 1.391786309292 | kg/s |
| 3a | spray total | 196.32 | g/min |
| 3b | ṁ_solvent | 0.002781200000 | kg/s |
| 4 | ω_ex | 0.007220211358 | kg/kg da |
| 5 | **T_ex at α = 0 (no fitting at all)** | **51.601381** | **°C** |
| 5 | **T_ex at α = 0.11399 (fitted)** | **48.518900** | **°C** |
| — | Measured | 48.519 | °C |
| 6 | RH_ex (unvalidated) | 0.1017 | fraction |
| — | Energy residual | 0.0e+00 | kJ/kg da |

**Batch 1 through the Stage 1 workflow:**

| Stage | Pump | Measured | Pred (calibrated) | Err % | Pred (locked) | Err % | α fitted |
|---|---|---|---|---|---|---|---|
| 1 | 7 | 48.519 | 48.519 | 0.0000 | 48.519 | 0.0000 | 0.11399 |
| 2 | 8 | 49.000 | 49.000 | 0.0000 | 47.923 | 2.1986 | 0.07226 |
| 3 | 9 | 49.373 | 49.373 | 0.0000 | 47.333 | 4.1318 | 0.03548 |

📗 **How to read this.** The calibrated column reproduces the plant's familiar 0.000 exactly. The locked column freezes stage 1's α and predicts stages 2–3 — and the error grows to 4.1 %. That growth *is the finding*: α falls from 0.114 to 0.035 (a 3.2× spread) as spray rate rises 26 %, at essentially constant airflow. A genuine equipment heat-loss property cannot behave that way. The parameter is absorbing something the model is missing.

⚠️ Note this page locks *within* a batch, which is the harshest protocol available. The benchmark report locks *across* batches at matched pump stages, giving 0.6396 °C. Both are honest; they answer different questions.

---

## 10. Error and accuracy analysis

### 10.1 Sensitivity — how much does each input matter?

Partial derivatives of exhaust temperature with respect to each input, at the audit row:

| Input | ∂T_ex/∂x | Interpretation |
|---|---|---|
| Inlet temperature | **+0.876 °C per °C** | A 1 °C inlet error becomes a 0.88 °C exhaust error |
| Solids fraction | +5.435 °C per unit | 1 percentage point of solids → 0.054 °C |
| Inlet RH | −0.204 °C per unit | 10 RH points → 0.02 °C. Almost irrelevant at these low humidities |
| Spray rate | −0.141 °C per g/min/gun | 1 g/min/gun → 0.14 °C |
| Airflow | +0.00165 °C per CFM | 100 CFM → 0.17 °C |
| **α (heat loss)** | **−25.6 °C per unit α** | Very high leverage — hence its power to absorb model error |

### 10.2 The error budget — and the most consequential number in the project

Propagating plausible instrument uncertainties (stated as assumptions, not measurements):

| Input | 1σ assumed | Basis | Contribution to T_ex | Share of variance |
|---|---|---|---|---|
| Inlet temperature | ±0.5 °C | RTD/thermocouple typical | **0.438 °C** | **94.4 %** |
| Airflow | ±2 % (56 CFM) | pitot/orifice typical | 0.092 °C | 4.2 % |
| Spray rate | ±1 % | gun calibration + pump drift | 0.047 °C | 1.1 % |
| Solids fraction | ±0.005 | solution preparation | 0.027 °C | 0.4 % |
| Inlet RH | ±0.02 | capacitive sensor | 0.004 °C | 0.0 % |
| **Combined (RSS)** | | | **0.451 °C** | 100 % |

📗 **What this means, in plain English.** Even with a *perfect* model, the exhaust temperature prediction would still scatter by about **±0.45 °C**, purely because the inputs are measured imperfectly. That is a noise floor. You cannot predict better than your inputs allow.

**Now compare it to the benchmark:**

```
EE's out-of-sample RMSE (gate G3 benchmark) ........... 0.6396 °C
Irreducible input-measurement noise floor ............. 0.4510 °C
Model-error component  = √(0.6396² − 0.4510²) ......... 0.4535 °C
```

⚠️ **The headroom is small, and you should know this before investing further.** Roughly **half the variance** in the current benchmark is measurement noise, not model error. Even if Track A drove its own model error to *exactly zero*, the RMSE would fall from 0.6396 to 0.4510 °C — a **29 % improvement, and no more**. Anyone claiming a much larger gain on this dataset is either leaking the answer or fitting noise.

📗 **The practical implication is a redirection.** The single highest-value action for accuracy is **not** more modelling — it is calibrating the inlet temperature sensor, because it carries 94 % of the input-uncertainty budget. Halving its error from ±0.5 to ±0.25 °C would cut the noise floor from 0.451 to 0.243 °C, which is a bigger and far cheaper win than any model refinement available here.

### 10.3 Residual structure — where the remaining error actually sits

With a single global UA = 0.11953 kW/K over the 9 visible rows:

| Grouping | n | Mean residual | Std dev |
|---|---|---|---|
| Pan RPM = 1 | 3 | **+0.7276 °C** | 0.196 |
| Pan RPM = 2 | 6 | **−0.3696 °C** | 0.498 |
| Pump 7 | 3 | +0.7276 °C | 0.196 |
| Pump 8 | 3 | −0.3100 °C | **0.059** |
| Pump 9 | 3 | −0.4293 °C | 0.778 |

**Gap between RPM = 1 and RPM = 2 groups: +1.10 °C** (pooled σ = 0.433 °C, so ≈ 2.5σ).

📗 **This is the largest structured error left in the model, and it is a genuinely interesting finding.** The residual is not random noise — it splits cleanly along the pan RPM 1 → 2 transition. That is a real, physically plausible signal: pan speed controls how fast tablets circulate through the spray zone, which changes the effective heat- and mass-transfer area, which would shift exhaust temperature.

⚠️ **And it cannot be proven from this data.** Pan RPM is **perfectly confounded** with pump stage: every pump-7 row has RPM = 1, and every pump-8/9 row has RPM = 2, in all four batches. The +1.10 °C could be an RPM effect or a spray-rate effect, and no statistical method can separate them. This is the single strongest argument for the experiment in §13.1.

Note also that pump 8 has a remarkably tight residual (σ = 0.059 °C) while pump 9 is loose (σ = 0.778 °C) — worth investigating whether stage-9 conditions are less stable, or whether the long stage-9 durations (219–260 min) average over drifting ambient conditions.

### 10.4 Accuracy by output

| Output | Ground truth available? | Accuracy | Status |
|---|---|---|---|
| Exhaust temperature | ✅ measured | 0.64 °C RMSE out-of-sample | **VALIDATED** |
| Spray rate from pump rpm | ✅ measured | 0.0044 g/min | **VALIDATED** |
| Cycle time | ✅ process record | exact | **VALIDATED** |
| Exhaust RH | ❌ column is EE output | untestable | **UNVALIDATED** |
| Weight gain | ✅ lab, but core mass unknown | untestable | **BLOCKED** |
| Bed temperature | ❌ nothing measured | untestable | **UNVALIDATED** |
| Coating uniformity / CV | ❌ nothing measured | untestable | **UNVALIDATED** |
| Droplet size, spray flux | ❌ no spray-pattern data | placeholder numbers | **NOT A MODEL** |
| Dissolution / assay / RS | 4 assay values only | not predictive | **FRAMEWORK ONLY** |

### 10.5 Why α varies, and what it is really absorbing

Fitted α across batch 1: 0.114 → 0.072 → 0.035, a 3.2× fall as spray rate rises 26 %, at constant airflow. Since UA and α carry identical information when airflow is fixed, this is not the airflow-normalisation artefact the PDF describes. Candidate explanations:

1. **Incomplete evaporation** — not all sprayed solvent evaporates in the control volume. **Tested and rejected**, see §10.6.
2. **Pan RPM / mixing effect** — supported by the +1.10 °C split in §10.3, but unidentifiable.
3. **Unrecorded ambient temperature drift** — heat loss scales with (T̄ − T_amb) and T_amb is hard-coded at 25 °C. Batch-level residual differences are consistent with this.
4. **Sensor lag or location bias** at long stage durations.
5. **Inlet RH being a typed default (0.05 everywhere)** rather than a measurement.

📗 Honest position: the cause is not yet determined, and this dataset cannot determine it. Explanations 2 and 3 are the most likely and both are testable with data you may already have.

### 10.6 Case study: how the gates caught a plausible but wrong module

📗 This is worth reading in full, because it shows the gate system doing exactly the job it exists for.

**The hypothesis.** §10.5 explanation 1: perhaps not all sprayed solvent evaporates inside the pan. Add one parameter, η_evap, fit it alongside UA on the calibration batch, and see if it predicts the unseen batches better.

**The result.**

| Model | Parameters | Fitted on | Dev RMSE | Dev max |
|---|---|---|---|---|
| Baseline (UA only) | UA = 0.10305 | batch 1 | 0.6403 °C | 1.2363 °C |
| Candidate (UA + η_evap) | UA = 0.38111, **η_evap = 0.0100** | batch 1 | **0.6023 °C** | **0.9344 °C** |

**It improved both metrics.** RMSE fell 6 %, worst case fell 24 %. Gate G3 **passes**. On error metrics alone, this looks like Track A beating EE.

**Then the other gates fired:**

- **G2 Physics — FAIL.** η_evap = 0.0100 is sitting exactly on its lower bound. The model is claiming that **1 % of the sprayed solvent evaporates** and 99 % leaves the pan as liquid. For a process whose entire purpose is drying, that is absurd. The parameter on a bound is the optimiser saying "I wanted to go further"— i.e. the structure is wrong.
- **G5 Parsimony — FAIL.** ΔRMSE = +0.038 °C, below the 0.05 °C threshold. The improvement is smaller than the exhaust sensor can resolve.

**Verdict: REJECTED.**

📗 And the diagnostic explains *why* the hypothesis is wrong. With UA locked, 6 of 9 rows are predicted **too hot**, and reducing evaporation makes them hotter still. Those rows would need η_evap > 1 — more solvent evaporating than was sprayed. The hypothesis has the wrong sign for two-thirds of the data. It only helps the high-spray stages, which is why a free fit drives it to a meaningless extreme to buy a small average gain.

⚠️ **Without G2 and G5, this module would have shipped**, with a headline reading "Track A improves worst-case error by 24 %", built on a model that says the coating solution does not dry. That is the failure mode these gates exist to prevent, and it was not hypothetical — the candidate looked good and had a genuine physical story behind it.

---

# Part D — What is wrong or missing

## 11. Lacunae — what is missing or unproven

### 11.1 Structural lacunae (from `modelling.pdf` §2.3, all still open)

| # | Lacuna | Consequence | Addressable? |
|---|---|---|---|
| L1 | **Zero-dimensional.** The pan is one well-mixed volume; no spray zone vs drying zone. | Local overwetting in the spray zone is invisible. In a 48-inch pan the spray zone is only 15–25 % of the bed. | Needs two-zone model + zone fraction data |
| L2 | **Steady-state only.** No time variable. | Warm-up transients, spray ramps, stoppages, cooling — precisely where defects form — cannot be modelled. | Needs the per-minute time-series |
| L3 | **Predicts air, not product.** Exhaust conditions ≠ tablet conditions. | Bed microenvironment can differ by up to 10 RH points from bulk exhaust. | Needs in-bed sensors |
| L4 | **No tablet motion.** Pan RPM appears nowhere in the thermodynamics. | The primary driver of coating uniformity is absent. | Needs an RPM-decoupled experiment |
| L5 | **No droplet/spray dynamics.** Atomisation pressure, nozzle, droplet size absent. | Cannot distinguish spray-drying from overwetting. | Needs spray-pattern measurements |
| L6 | **Deterministic.** Single point prediction, no confidence interval. | No probability of specification failure. | Needs §10.2's error budget wired in |

### 11.2 Data lacunae — the binding constraint

⚠️ This is the real limitation, more than any modelling choice.

| Missing | Effect | Impact |
|---|---|---|
| **Per-minute time-series** | No dynamic model can be identified or validated | **Blocks Stages 3 and 4 entirely** |
| **Measured exhaust RH** | The mass balance has no independent check | Would roughly double validation leverage |
| **Batch core load (kg)** | η_dep and weight gain uncalibratable | Blocks CQA-1 |
| **Ambient temperature** | Heat-loss driving force is assumed | A leading candidate for batch-level residuals |
| **Inlet RH verification** | 0.05 on all 12 rows — measurement or default? | Inlet state uncertain |
| **Pan dimensions / free volume** | Timescale separation and bed area assumed | Needed for the dynamic rebuild |
| **Bed temperature, LOD, coating CV** | Three outputs permanently unvalidated | Each unlocks a Stage 3 output |
| **RPM varied independently of spray rate** | The +1.10 °C effect cannot be attributed | Blocks the RPM module |
| **Atomisation pressure varied** | Constant at 2 bar — zero information | Blocks the atomisation module |

### 11.3 The dataset is nearly one-dimensional

| Input | Span across all 12 stages | Consequence |
|---|---|---|
| Inlet temperature | 0.115 °C (0.20 %) | effectively constant |
| Airflow | 0.19 % | effectively constant |
| Inlet RH | **0** | constant |
| Atomisation pressure | **0** | **no parameter fittable** |
| Pan RPM | {1, 2}, confounded with pump stage | **not separable** |
| Spray rate | 23.4 % | the only independent variation |

⚠️ Heat-loss conductance, evaporation efficiency and an inlet-temperature bias are **collinear** over this range. Any model with two or more free thermal parameters is unidentifiable here — which is exactly what §10.6 demonstrated empirically.

### 11.4 Data-integrity findings

1. **`Solution (kg)` is a nominal recipe value, not an actual.** Total sprayed differs by −6.7 % to +5.8 %; batches 1 and 3 sprayed *more* than the batch nominally contained. Must not be used as the weight-gain mass basis.
2. **Implied core mass spans 343–406 kg** (17 %) across four batches.
3. **Three of four stage-8 exhaust readings are exactly 49.000 °C.** Confirmed not setpoint-controlled, so recorded as a transcription/rounding artefact — meaning the third decimal is not a real measurement in those rows.
4. **Gun calibration has zero degrees of freedom** — two points, so linearity is untested.

### 11.5 Code-level defects still open

| # | Defect | Location | Blocks |
|---|---|---|---|
| D6 | Heat loss applied twice | `dynamic_model.py:95,196` | Stage 3 |
| D7 | Hard-coded 1-second evaporation constant → grid-dependent | `dynamic_model.py:86,107` | Stage 3 |
| D8 | Zone transfers do not conserve | `dynamic_model.py:96,116` | Stage 3 |
| D11 | Risk page propagates a test stub | `uncertainty_page.py:14` | Stage 4 |
| D12 | Optimiser objective mixes unnormalised fabricated costs | `optimization_page.py:104` | Stage 4 |
| D17 | `configs/*.yaml` never loaded; limits hard-coded per call site | all pages | 3, 4 |
| D18 | Droplet correlations are invented placeholders | `spray.py:9` | Stage 3 |
| D19 | Excel upload parsed as CSV | `data_upload.py:12` | Stage 0 |
| D20 | Export page ships hardcoded dummy data | `export_page.py:9` | Stage 4 |

Also: four pages (`data_upload`, `optimization_page`, `steady_state_page`, and formerly `calibration_page`) are **orphaned** — present as files but not registered in navigation, so unreachable. `calibration_page.py` was removed during this review: it was unreachable, held a fifth copy of the energy balance, and its second tab displayed **hardcoded fake calibration results** after a 2-second sleep.

---

## 12. Where accuracy is lost, ranked

Ordered by how much accuracy each costs you *today*.

| Rank | Source | Magnitude | Fix | Effort |
|---|---|---|---|---|
| **1** | **Inlet temperature sensor uncertainty** | 0.438 °C (94 % of input variance) | Calibrate the sensor | **Low — best return available** |
| **2** | **Unattributed RPM/spray-rate effect** | +1.10 °C group offset | DoE decoupling RPM from spray rate | Medium |
| **3** | **Unrecorded ambient temperature** | unknown; plausibly batch-level | Log it | **Very low** |
| **4** | **Model error in the thermal closure** | 0.454 °C | Dynamic model — needs time-series | High |
| **5** | Inlet RH possibly a typed default | up to 0.004 °C direct, but corrupts the inlet state | Verify against the dehumidifier record | Low |
| 6 | Airflow measurement | 0.092 °C | Calibrate | Medium |
| 7 | Heat-loss functional form (sign error) | ~0 here; up to 3× on extrapolation | **Already fixed** | Done |
| 8 | Zero-dimensional assumption (L1) | unquantified | Two-zone model | High |
| 9 | Spray rate uncertainty | 0.047 °C | Already well controlled | — |
| 10 | Display rounding in the source table | ≤ 0.0005 °C | Export at full precision | Low |

📗 **The headline.** Items 1 and 3 are cheap instrumentation actions and together address more error than the entire modelling programme can. Item 2 is one modest experiment. Item 4 is the expensive one and it is currently blocked on data. **Fix the instrumentation before investing more in equations.**

---

## 13. Alternative tracks worth considering

Beyond the current Track A. Each is described with what it buys, what it costs, and my honest assessment.

### 13.1 Track A+ — a minimal DoE to unlock what is already built ⭐ *strongly recommended*

📗 The cheapest high-value option. The model is not limited by its equations; it is limited by a dataset in which only one variable moves.

**The experiment:** roughly 8–12 stages breaking the confounding:

| Run group | Vary | Hold constant | Unlocks |
|---|---|---|---|
| A | Pan RPM (1, 2, 3) | spray rate, inlet T, airflow | The +1.10 °C effect → M4 |
| B | Atomisation pressure (1.5, 2.0, 2.5 bar) | everything else | M5 (currently impossible) |
| C | Inlet temperature (±5 °C) | everything else | Breaks thermal collinearity; identifies UA properly |
| D | Airflow (±15 %) | everything else | Separates UA from α; validates the sign fix |

**Cost:** a few production or engineering batches. **Return:** makes three currently-unidentifiable modules testable, and would let UA be estimated properly rather than absorbing model error.

⚠️ Group C is the one that matters most for accuracy. With inlet temperature spanning 0.115 °C, the model is essentially being asked to extrapolate from a single point.

### 13.2 Track B — reduced-order digital twin with hybrid residual learning

📗 Run the mechanistic model, then train a small machine-learning model on its *errors* rather than on the process. The ML model only has to learn the bias, not the physics, so it needs far less data and degrades gracefully to the mechanistic model when uncertain.

**Pros:** could capture the RPM effect empirically without identifying it mechanistically; well-precedented.
**Cons:** with 12 rows there is nothing to train on — you would be fitting noise. Also harder to defend to a regulator than a mechanistic term.
**Assessment:** genuinely promising, but only after §13.1. Needs tens of batches minimum.
📄 `modelling.pdf` ch. 12.

### 13.3 Track C — instrumentation-first

📗 Not a modelling track at all: spend the effort on sensors instead of equations. Add an in-bed temperature probe, an exhaust hygrometer, an ambient logger, and calibrate the inlet RTD.

**Pros:** §10.2 shows this addresses more error than the entire modelling programme. Also converts three permanently-unvalidated outputs into validatable ones, and an in-bed probe directly attacks lacuna L3.
**Cons:** capital and qualification effort; in-bed probes are awkward in production.
**Assessment:** **highest return per unit effort of anything on this list.** Should run in parallel with §13.1.

### 13.4 Track D — two-zone mechanistic model (Page et al.)

📗 Split the pan into a spray zone and a drying zone with tablets circulating between them. Physically much closer to reality and the natural route to overwetting prediction.

**Pros:** addresses L1 directly; well-documented source (Page 2006, DOI 10.1208/pt070242); makes the wetness index locally meaningful.
**Cons:** introduces at least three new unidentifiable parameters (zone fraction, exchange rate, airflow split). Gate G4 would reject all of them on current data.
**Assessment:** correct long-term direction, premature now. Build the single-zone dynamic model first.

### 13.5 Track E — control-oriented model (Rodrigues et al. 2023)

📗 Rather than the most accurate possible predictions, build the model deliberately for closed-loop control — accept larger absolute error in exchange for correct *directional* response and fast execution.

**Pros:** validated on 7 pilot batches; a lower accuracy bar; opens real-time exhaust-temperature control.
**Cons:** requires the time-series; control implementation is a separate regulatory conversation.
**Assessment:** attractive if the business goal is process stability rather than prediction. Worth an explicit decision.
📄 Rodrigues et al. (2023), DOI 10.1016/j.compchemeng.2023.108...

### 13.6 Track F — CFD/DEM surrogate

📗 Simulate individual tablet motion and airflow in detail offline, then fit a fast surrogate for the app.

**Pros:** the only route to genuine spatial resolution and true uniformity prediction; industrial precedent (Pfizer/Bohle, AbbVie, Lilly).
**Cons:** months of specialist effort, licences, and it still needs experimental validation.
**Assessment:** out of scope for now. Revisit if uniformity becomes the binding business problem.

### 13.7 Recommended sequence

```
NOW      Track C (instrumentation) ─┐
         Track A+ (small DoE) ──────┼──▶ both cheap, both unblock everything else
              │                    │
              ▼                    │
THEN     Finish Track A: dynamic single-zone model (needs the time-series)
              │
              ▼
LATER    Track D (two-zone) if overwetting is the problem
         Track E (control) if stability is the goal
         Track B (hybrid ML) once tens of batches exist
         Track F (CFD/DEM) only if uniformity becomes binding
```

⚠️ **The one thing I would not do** is add more mechanistic modules to the current dataset. §10.6 shows what happens: plausible physics, improved error metrics, and a parameter claiming the coating solution does not dry. More equations on twelve near-identical rows produces confident nonsense, not accuracy.

---

## 14. Glossary

| Term | Meaning |
|---|---|
| **CPP** | Critical Process Parameter — something you set on the machine |
| **CTQ** | Critical-to-Quality intermediate — a physical state the tablets experience |
| **CQA** | Critical Quality Attribute — a property of the finished product |
| **Humidity ratio (ω)** | kg of water vapour per kg of *dry* air. Unlike RH, unchanged by heating |
| **Relative humidity (RH)** | Fraction of the maximum water the air could hold at that temperature |
| **Saturation pressure** | The maximum vapour pressure at a given temperature (Antoine) |
| **Wet-bulb temperature** | Coldest an evaporating wet surface can get in a given airstream |
| **Enthalpy** | Total heat content per kg |
| **Latent heat** | Energy to change phase without changing temperature (~2,260 kJ/kg for water) |
| **Vapour enthalpy** | Total heat content of vapour (~2,548 kJ/kg at 25 °C). **Not** the latent heat |
| **α (alpha)** | Heat-loss conductance normalised by dry-air mass flow. Airflow-dependent |
| **UA** | Absolute heat-loss conductance, kW/K. An equipment property |
| **EE / EEF** | Environmental Equivalency factor — a scalar summary of drying aggressiveness |
| **WI** | Wetness Index — solvent applied ÷ drying capacity. > 1 means overwetting risk |
| **EWI** | Cumulative excess wetness integral — magnitude *and* duration of overwetting |
| **η_dep** | Deposition efficiency — fraction of sprayed solids that actually sticks |
| **η_evap** | Fraction of sprayed solvent evaporating inside the control volume |
| **Calibration residual** | Error when the parameter was fitted to the same row. **Not accuracy** |
| **Locked prediction** | Error when the parameter was frozen before seeing the row. **Real accuracy** |
| **Leakage** | Any path by which the answer influences the prediction |
| **Sealed batch** | Held-out data consulted exactly once, at the very end |
| **Collapse test** | Check that a module with its new term disabled reproduces its parent exactly |
| **Identifiability** | Whether the data can actually determine a parameter's value |

---

## Where to look next

| Question | File |
|---|---|
| What is the plan and what is the status? | `PLAN_TRACK_A_REBUILD.md` |
| What is the frozen benchmark? | `reports/baseline_locked.md` |
| What data exists and what are its limits? | `data/acceptance/README.md` |
| Which columns are real measurements? | `data/acceptance/COLUMN_PROVENANCE.csv` |
| The canonical physics | `coating_model/energy_balance.py` |
| The gate implementations | `validation/acceptance.py` |
| Verify the dataset reconciles | `python scripts/step0_verify_data.py` |
| Regenerate the benchmark | `python scripts/step4_baseline.py` |
| Run all checks | `python -m pytest tests/ -q` |
