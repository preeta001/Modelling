# Track A — Full Implementation Plan (All Four Stages)

**Version:** 2.0 (supersedes v1.0, which covered Stage 1 only)
**Date:** 2026-08-06
**Status:** For approval. No production code changed yet.

**Sources:** `Reference/complete_chat_conversation.md` (Stage-1 methodology), `Reference/modelling.pdf` (Track A specification, 48 pp), `Reference/EE-test-9-1-Varible-Solid-Fraction.py` (legacy EE), plant-data screenshots, and a full audit of the existing 3,187-line codebase.

**Scope:** the entire application — Stage 1 Model Validation & Calibration, Stage 2 Gun Validation, Stage 3 Model Execution, Stage 4 Optimisation & Risk. Scale-up is removed throughout, per your instruction.

### Implementation status (2026-08-06)

| Phase | Status | Evidence |
|---|---|---|
| **P0** Acceptance-set foundation | ✅ **done** (Gate 0 open on Q0) | `data/acceptance/`, `scripts/step0_verify_data.py` — 67 checks, 0 failures |
| **P1** Stage 2 gun calibration | ✅ **done** | `coating_model/gun_calibration.py`, 10 tests. A2 met: worst 0.0044 g/min |
| **P2** M0 freeze + audit | ✅ **done** | `validation/m0_legacy_adapter.py`, SHA-256 pinned |
| **P3** M1 canonical core; scale-up removed | ✅ **done** | `coating_model/energy_balance.py`. **T1 met: 1.4e-14 °C** vs M0 |
| **P4** Locked baseline + two-column display | ✅ **done** | `reports/baseline_locked.md`, rewritten `app_pages/validation_page.py` |
| **P5** Stage 3 dynamic core | ⛔ **blocked on Q3** (per-minute time-series) | — |
| **P6** RPM / atomisation modules | ⛔ blocked on P5; expected to fail G4/G5 | §2.6 |
| **P7** Stage 3 wiring | 🟡 **partial** — D10, D14, D15 fixed; dynamic core rebuild pending P5 | `app_pages/simulation_page.py` |
| **P8–P10** Stage 4, docs | ⛔ blocked on P5/P7 | — |

**Test suite: 196 passing** (was 25, of which the energy-balance test asserted only that a temperature went down).

**Defects closed:** D1, D2, D3, D4, D5, D9, D10, D13 (partial), D14, D15, D16.
**Defects open:** D6, D7, D8, D11, D12, D17, D18, D19, D20 — all inside Stage 3/4, all blocked on P5.

### Manual UI verification (2026-08-06)

App run headless on `:8501`; Stage 1 and Stage 2 driven end to end.

**Stage 1, batch 1 loaded from the acceptance set** — UI output matches the headless
calculation exactly:

| Stage | Role | Measured | Pred (cal) | Err % (cal) | Pred (locked) | Err % (locked) | α fitted |
|---|---|---|---|---|---|---|---|
| 1 | calibration | 48.519 | 48.519 | 0.0000 | 48.519 | 0.0000 | 0.11399 |
| 2 | prediction | 49.000 | 49.000 | 0.0000 | 47.923 | 2.1986 | 0.07226 |
| 3 | prediction | 49.373 | 49.373 | 0.0000 | 47.333 | 4.1318 | 0.03548 |

Locked RMSE 1.6313 °C, max 2.0400 °C. Energy balance closes on every stage; the
α-spread warning fires at 3.2×; the zero-parameter reference reports 51.601 °C vs
48.519 °C measured.

Note this page locks **within** a batch (stage 1 → stages 2–3), which is the
harshest protocol available: α varies with spray rate, and stages 2–3 spray
13–26 % harder. `reports/baseline_locked.md` locks **across** batches at matched
pump stages (0.6396 °C), which is the representative comparison.

**Stage 2** — A2 passes live: worst deviation **0.0044 g/min** over 12 stages
against the 0.005 limit. Extrapolation guard confirmed firing at 2 rpm.

**Two UI defects found and fixed during this check:**

| Found | Fix |
|---|---|
| All three Stage-1 rows defaulted to identical values, so the locked column read **0.0000** — reproducing exactly the false-perfection the page exists to expose | Batch loader reading `data/acceptance/`, sealed batch disabled in the picker, distinct fallback defaults |
| `app_pages/gun_validation.py` still had its own polyfit, asked only for the **total** rate (discarding per-gun spread), had no extrapolation guard, and published to a key nothing read — D9 was closed in the library but not the UI | Page rewired to `coating_model.gun_calibration`; publishes to `pump_calibrations` |

### Decisions taken (2026-08-06)

| # | Decision | Consequence |
|---|---|---|
| **DEC-1** | **Exhaust temperature runs free** — it is not held at a setpoint. | Stage 1 predicts exhaust temperature as planned (§8). The three identical `49.000 °C` readings (§2.8c) are recorded as a transcription/rounding artefact in `data/plant/README.md`, not as evidence of control. **Q2 is closed.** The time-series check in P5 will confirm it independently at no extra cost. |
| **DEC-2** | **Unvalidatable modules are shown, tagged `UNVALIDATED`** — not hidden, not unrestricted. | Every output carries a `VALIDATED` / `DIAGNOSTIC` / `UNVALIDATED` tag in the UI and in every export (§9.1, S3-G7). Unvalidated outputs may inform reasoning but **may not feed the optimiser** (S4-G1). |
| **DEC-3** | **Implementation starts at P0 and runs through P4.** | P0–P4 need only confirmation of the 12-row table (Q0). Data files are generated now with `confirmed_against_excel = FALSE`; every downstream number re-derives automatically when you flip that flag. |
| **DEC-4** | **The plant and gun data are an ACCEPTANCE TEST SET, not a training set.** The model is built from first principles (`modelling.pdf` Track A + the corrected EE core) and only then tested against this data. | Rewrites §2.2, §4, §6. See **§0 — the acceptance-test discipline**, which supersedes the leave-one-batch-out framing of v2.0. |
| **DEC-5** | **Only the *measured* columns are ground truth.** The `Predicted Exhaust Temp`, `Difference`, `Error %`, **`Exhaust RH`**, `Alpha`, `Alpha Avg` and `EE Factor` columns are all EE **model output** and are never validation targets. | Verified in §0.3 — the `Exhaust RH` column is reproduced by the legacy EE model to 0.0005 across all 12 rows. Validating against it would be validating against EE, not against the plant. |

---

## Table of contents

**Part 0 — Governing discipline** *(supersedes conflicting text elsewhere)*
- [§0 The acceptance-test discipline](#0-the-acceptance-test-discipline)

**Part I — Foundations**
- [§1 How to read this plan](#1-how-to-read-this-plan)
- [§2 Evidence: what I verified before planning](#2-evidence-what-i-verified-before-planning)
- [§3 Complete defect register](#3-complete-defect-register)
- [§4 Objectives and the three error targets](#4-objectives-and-the-three-error-targets)
- [§5 The gate system](#5-the-gate-system)

**Part II — The four stages**
- [§6 Stage 0 — Data foundation](#6-stage-0--data-foundation-new-prerequisite)
- [§7 Stage 2 — Gun validation *(built first; see §7.1)*](#7-stage-2--gun-validation-built-first)
- [§8 Stage 1 — Model validation & calibration](#8-stage-1--model-validation--calibration)
- [§9 Stage 3 — Model execution](#9-stage-3--model-execution)
- [§10 Stage 4 — Optimisation & risk](#10-stage-4--optimisation--risk)

**Part III — Execution**
- [§11 Chronological phase plan](#11-chronological-phase-plan)
- [§12 Repository layout](#12-repository-layout)
- [§13 Test architecture](#13-test-architecture)
- [§14 Precision and display policy](#14-precision-and-display-policy)
- [§15 Risk register](#15-risk-register)
- [§16 Questions I need answered](#16-questions-i-need-answered)

---

# Part 0 — Governing discipline

## 0. The acceptance-test discipline

**Where this section conflicts with anything later in the document, this section wins.**

### 0.1 The rule

> The plant data and gun-validation data are an **acceptance test set**. The model
> is derived from first principles — `modelling.pdf` Track A plus the corrected
> thermodynamic core — and is *then* tested against them. They are not the
> reference the model is built from, and they are not a training set.

The loop is: **build from physics → test against the plant data → if it fails, fix the physics → re-test.**

This is a stronger discipline than v2.0 of this plan assumed, and it is the right one. It also creates one specific hazard, addressed in §0.4.

### 0.2 What is actually ground truth

The plant table mixes four different kinds of column, and they are not interchangeable:

| Kind | Columns | Usable as a validation target? |
|---|---|---|
| **MEASURED** | `Actual Exhaust Temp` | **Yes — this is the thermodynamic ground truth** |
| **PROCESS_RECORD** | Solution kg, solids, pump rpm, spray rate, inlet temp, airflow, inlet RH, atomisation, pan rpm, stage time, solution sprayed, cycle time | Yes — these are model **inputs** |
| **LAB_RESULT** | Weight gain %, Assay % | **Yes** — independent measurements |
| **EE_OUTPUT** | `Predicted Exhaust Temp`, `Difference`, `Error %`, **`Exhaust RH`**, `Alpha`, `Alpha Avg`, `EE Factor` | **No — never.** These are the old model's output |

Gun-validation data is **MEASURED** throughout (six guns weighed at 5 and 10 rpm). The `m` and `c` columns are derived, so our model recomputes them from the raw gun measurements and then checks agreement — a verification, not an input.

### 0.3 Verified: the `Exhaust RH` column is EE output, not a measurement

This was not obvious — the column sits between `Error (%)` and `Time (min)`, i.e. on the boundary between model output and process record. I tested it by running the legacy EE model at each row's displayed alpha:

| Row (batch-pump) | EE-computed RH | Table RH | Δ |
|---|---|---|---|
| 1-7 | 0.1017 | 0.102 | −0.0003 |
| 1-9 | 0.1044 | 0.104 | +0.0004 |
| 2-9 | 0.1117 | 0.112 | −0.0003 |
| 4-7 | 0.1061 | 0.106 | +0.0001 |
| … all 12 rows | | | **worst 0.0005** |

Agreement to 0.0005 across all twelve rows is pure display rounding to 3 dp. **The column is computed, not measured.**

**Consequence — and it is a significant one:** the *only* thermodynamic ground truth in the entire dataset is the exhaust temperature column. Everything else in the thermodynamic block is EE output. Had the plan validated exhaust RH against that column, it would have been scoring our model against the old model — circular, and it would have looked like a pass. Exhaust RH is therefore **UNVALIDATED** until a real hygrometer reading is supplied (new question **Q8**).

### 0.4 The hazard in "iterate until it works", and the defence

Your loop is right, but a fixed test set that is consulted after every iteration stops being held out. Twenty iterations of "test → adjust → re-test" fits the model to those 12 rows through structural choices instead of through parameters — with no record that it happened, and no way to distinguish a model that generalises from one that has been steered.

Three mechanical defences, all cheap:

1. **Split the acceptance set.** Batches 1–3 are the **development acceptance set**, consulted freely during iteration. **Batch 4 is sealed** — run against it exactly once, at the very end. If batch 4 agrees with batches 1–3, the result is real. If it is much worse, the model was steered.
2. **Log every iteration.** `reports/acceptance_log.md` records each attempt: what was changed, why, the physical justification, and the resulting error. An iteration count that climbs while errors barely move is itself the signal that the physics has stopped improving.
3. **Every change must be justified physically *before* the test is run**, not after. "Changed the evaporation closure because the assumption that all sprayed solvent evaporates in the control volume is wrong (§2.5)" is legitimate. "Tried a coefficient of 0.87 because it fit better" is not, and gate G2 rejects it.

### 0.5 The honest tension this creates — and the good news

If none of the data may be used to fit anything, where do the parameters come from?

The good news is that the thermodynamic core is **almost parameter-free**. The psychrometrics, the mass balance and the adiabatic energy balance contain **zero** free parameters — they are pure thermodynamics with published constants. Running the corrected core adiabatically on row 1 gives **51.601 °C** against a measured **48.519 °C**: a genuine, honest, zero-parameter, zero-fitting prediction that is 3.08 °C high.

So the entire modelling question reduces to a single term: **the heat loss that closes that 3 °C gap.** Exactly one parameter (`UA`), plus at most one more in the dynamic model (the wetted-area fraction of §9.4).

That single parameter can be sourced three ways, in descending order of rigour:

| Source | Rigour | Feasible now? |
|---|---|---|
| **(a) First principles** — pan surface area, insulation, ambient; `UA` computed from geometry and material properties | Highest: acceptance set stays completely untouched | Needs pan dimensions and construction (**Q6**) |
| **(b) Sealed-batch calibration** — fit `UA` on one batch only, lock it, predict the other three | Standard practice, defensible | **Yes, today** |
| **(c) Per-row fitting** | None — this is what EE does, and why it reports 0.000 | Never, for our model |

**Recommendation: (a) if you can supply the equipment data, (b) otherwise.** Under (b), batch 1 becomes the calibration batch, batches 2–3 the development acceptance set, and batch 4 the sealed final test — and the headline claim becomes *"one parameter fitted on one batch predicts three unseen batches"*, which is a far stronger statement than anything the EE table currently supports.

### 0.6 What the acceptance test actually is

| Target | Ground truth | Criterion |
|---|---|---|
| **A1** Exhaust temperature, 12 stages | `Actual Exhaust Temp` | RMSE ≤ **0.654 °C**, max ≤ **1.107 °C** (the locked-EE benchmark, §2.2), zero physics violations |
| **A2** Spray rate, 12 stages | gun measurements → pump calibration | < 0.005 g/min *(already verified, §2.7)* |
| **A3** Weight gain, 4 batches | lab result | within assay uncertainty, once core mass is known (**Q1**) |
| **A4** Cycle time, 4 batches | process record | exact *(already reconciles, §2.8)* |
| **A5** Exhaust RH | **none available** | **cannot be tested** until a real measurement is supplied (**Q8**) |

A1 is the one that matters, and it is the one the plant cares about.

---

# Part I — Foundations

## 1. How to read this plan

Every module in Part II is specified with five fields. The third and fourth exist because you asked for the reasoning, not just the task list.

| Field | Meaning |
|---|---|
| **What** | The thing to be built. |
| **Why** | The physical or process reason it exists. If this field is weak, the module should not be built. |
| **Is it correct / should it be done?** | My honest assessment, including cases where the answer is *no*. |
| **Does it change the output?** | Whether it moves a number the plant cares about, or is presentation only. Modules that change nothing get de-prioritised. |
| **Gate** | The objective pass/fail test. |

### The governing rule

> **Nothing enters the model that has not matched or beaten the locked EE baseline on data it was not fitted to, while satisfying every physics check.**

Enforced mechanically, not by intention:

1. **M0 (legacy EE) is frozen.** Never edited, only wrapped and called.
2. **Every module must collapse exactly onto its parent** when its new term is switched off — tolerance `1e-9`. If it cannot, the derivation is wrong.
3. **Fitting and scoring never touch the same row.** An error produced by fitting a parameter to the row it predicts is a *calibration residual*, labelled as such, and never compared against a prediction error.
4. **A failed module is flag-disabled, not deleted and not tuned until it passes.** It moves to the future-work list with its evidence.
5. **No output leaves the validated input envelope without an abstention warning.**

---

## 2. Evidence: what I verified before planning

I ran the numbers rather than trusting the documents. Everything below is reproducible; nothing is quoted from the PDF without independent confirmation.

### 2.1 The legacy EE model reproduces exactly — Stage 1A is a formality

Audit row `E2600199`, pump 7, `alpha = 0.149`:

| Quantity | Value |
|---|---|
| `p_sat(56.507 °C)` | 16.871088521060 kPa |
| `p_v` (RH 5 %) | 0.843554426053 kPa |
| `w_inlet` | 0.005221916087 kg/kg da |
| `rho_moist` | 1.058486024426 kg/m³ |
| `m_moist` | 1.399054100610 kg/s |
| `m_dry_air` | 1.391786309292 kg/s |
| `m_solvent` | 0.002781200000 kg/s |
| `w_exhaust` | 0.007220211358 kg/kg da |
| **T_exhaust (α = 0.149)** | **48.524675 °C** |
| Measured | 48.519 °C |
| Residual | **+0.005675 °C** |

The 0.0057 °C gap is exactly what a display-rounded α produces. Outcome 1 of the four anticipated in the source `.md`. No contingency branch needed.

### 2.2 The real EE accuracy is not 0 % — it is 0.654 °C RMSE

All 12 stages, four parameter policies:

| Policy | What it is | RMSE | Max abs |
|---|---|---|---|
| Per-row fitted α | **What the table shows** | 0.000 °C | 0.000 °C |
| **Per-batch locked `Alpha Avg`** | **EE used as a predictor** | **0.654 °C** | **1.107 °C** |
| Single global α = 0.119 | EE with one plant constant | 0.718 °C | 1.494 °C |
| Corrected-physics single global UA | physically right form | 0.722 °C | 1.503 °C |

This is the single most important number in the project. The 0.000 in your table is a per-row curve fit: each row is given its own α chosen to hit that row's answer. Twelve rows, twelve free parameters, zero degrees of freedom left. It cannot be otherwise than zero.

**On your instruction to target 0 %:** we *will* deliver 0.000 — in calibration mode, exactly as today, and the app will keep showing it. What the plan adds is a **second column beside it** showing the locked-prediction error. Nothing you have now is taken away; an honest number is added next to it. §8.5 specifies the two-column display. The gate for new physics is the second column, because that is the only one that responds to a model being better.

### 2.3 The Track A failure has one identifiable cause

`app_pages/validation_page.py:19` `calculate_stage_physics` is not the legacy equation re-expressed — it is a different and incorrect energy balance. Line 48 subtracts `m_w * h_fg_ref` where `h_fg_ref = solvent.latent_heat(25 °C) = 2548.22 kJ/kg`. But `latent_heat()` (`coating_model/solvent_properties.py:32`) returns the **vapour enthalpy** `1.7208·T + 2505.2`, not a latent heat. The outlet term `m_da·w_ex·enthalpy_B` already carries that enthalpy, so phase-change energy is **counted twice**; and the liquid inlet enthalpy `h_fg_i = 104.7598 kJ/kg` is never added.

| UA (kW/K) | `calculate_stage_physics` output |
|---|---|
| 0.0 (adiabatic) | 46.391 °C |
| 0.5 | 38.453 °C |
| 1.0 | 32.587 °C |
| 5.0 | 12.621 °C |

Legacy adiabatic is **51.601 °C**. The function is 5.2 °C cold before any heat loss is applied. Measured (48.519 °C) sits *above* its adiabatic ceiling, so the optimiser over `bounds=[(0.0, 5.0)]` is driven onto `UA = 0`, still under-predicts by 2.1 °C, and every extra kW/K makes it worse. That is the physically impossible output, and it is one term.

**Verified fix:** replacing `− m_w·h_fg_ref` with `+ m_w·h_liq` (104.7598) returns **51.601381 °C** at UA = 0 — identical to legacy adiabatic to six decimals. Exact M1 ≡ M0 equivalence is achievable, not aspirational.

### 2.4 The legacy heat-loss sign error is real, and `modelling.pdf` §2.3.1 already documents it

My re-derivation and the PDF agree:

```
q_loss = α · ( (T_ex − T_in)/2 + T_amb )     [legacy, wrong]
q_loss = α · ( (T_in + T_ex)/2 − T_amb )     [correct]
```

Identical at α = 0, which is why the adiabatic core is sound and per-stage fitting hides it. It responds to ambient temperature backwards and fails on extrapolation.

### 2.5 But the PDF's prescribed fix will not help *this* dataset

The PDF says: fit absolute `UA` instead of airflow-normalised `α`, to remove a 1/CFM scaling artefact. Correct in general. Here it changes nothing, because airflow barely varies. Batch 1, correct physics:

| Stage | spray (g/min/gun) | ṁ_dry air (kg/s) | fitted UA (kW/K) |
|---|---|---|---|
| 7 | 32.72 | 1.3918 | 0.1586 |
| 8 | 36.95 | 1.3920 | 0.1006 |
| 9 | 41.17 | 1.3917 | 0.0494 |

ṁ_da is constant to four significant figures, so UA and α carry identical information. Required heat loss still collapses 3× as spray rate rises. Physical reading: **assuming 100 % of sprayed solvent evaporates inside the control volume over-predicts evaporative cooling, increasingly so at higher spray rate.** The fitted "heat loss" is absorbing that model error.

I tested the obvious remedy — one global UA plus one global evaporation efficiency η — and the optimiser drove **η = −0.057**, unphysical. Batches 2–4 are non-monotone at stage 9. So the residual is not a clean constant-efficiency deficit either. §9 treats evaporation efficiency as a hypothesis to be tested and possibly rejected, not a known fix.

### 2.6 The dataset is nearly one-dimensional — the binding constraint on the whole project

Across all 12 stages:

| Input | Span | Verdict |
|---|---|---|
| `T_inlet` | 56.507–56.622 °C (**0.115 °C**, 0.20 %) | effectively constant |
| Airflow | 2798.68–2804.13 CFM (**0.20 %**) | effectively constant |
| Inlet RH | 5 % on every row | constant |
| Solids fraction | 0.15 on every row | constant |
| Atomisation pressure | 2 bar on every row | **constant — zero information** |
| Pan RPM | {1, 2}, and *perfectly confounded* with pump stage | **unidentifiable** |
| Spray rate | 32.59–41.21 g/min/gun (**23.4 %**) | the only real variation |

Consequences, stated plainly:

- Heat-loss coefficient, evaporation efficiency and an inlet-temperature bias are **collinear** over this range. Any model with two or more free thermal parameters is unidentifiable here. This is what produced η = −0.057.
- **Atomisation pressure cannot be fitted at all.** One value, no variation, no information. Attempting a fit would be fabrication.
- **Pan RPM cannot be separated from spray rate.** Stage 7 → 1 rpm and stages 8/9 → 2 rpm in every one of the four batches. Any "RPM effect" fitted here is a spray-rate effect wearing a different label.

This is why §16 asks for the per-minute time-series, and why §15 treats "no second parameter is identifiable" as the *most likely* outcome rather than a tail risk.

### 2.7 Stage 2 (gun validation) is arithmetically verified end to end

I reproduced the entire chain from the gun-validation screenshot:

| Batch | m (calc) | m (shown) | c (calc) | c (shown) | gun-to-gun CV @5 rpm | @10 rpm |
|---|---|---|---|---|---|---|
| 1 | 4.227033 | 4.227033 | 3.130167 | 3.130167 | 2.77 % | 1.60 % |
| 2 | 4.264533 | 4.264533 | 2.832500 | 2.832500 | 2.33 % | 1.81 % |
| 3 | 4.152633 | 4.152633 | 3.683333 | 3.683333 | 2.04 % | 1.59 % |
| 4 | 4.143367 | 4.143367 | 3.585667 | 3.585667 | 3.63 % | 1.52 % |

And every one of the 12 spray rates in the plant table is reproduced from `m·RPM + c` to within display rounding (worst case **0.0044 g/min**). Two findings follow:

- **The pump calibration is the cleanest, most trustworthy chain in the entire project.** It should be built first and become the provenance layer for the spray rate that Stage 1 consumes.
- **Gun-to-gun CV of 1.5–3.6 % is measured data.** This is a real, measured input for the coating-uniformity model — far better than the invented droplet correlations currently in `coating_model/spray.py`. See §9.6.

One caveat: `m` and `c` come from a **two-point fit** (5 and 10 rpm only). With two points there is no residual and therefore no test of linearity. The intercept `c ≈ 2.8–3.7 g/min` at zero rpm is non-physical (a stopped pump delivers nothing), so the affine fit must never be extrapolated below 5 rpm. Within 7–9 rpm it is interpolation and is sound.

### 2.8 The plant table has three data-integrity findings

Internal arithmetic is perfect: `rate × time` reproduces every "Solution Sprayed" cell, and stage times sum to the shown cycle times exactly (5.80, 5.23, 5.73, 5.13 h). But:

**(a) Total sprayed ≠ recorded solution mass.**

| Batch | Total sprayed (kg) | Solution (kg) | Difference |
|---|---|---|---|
| 1 | 81.30 | 77.215 | **+5.29 %** |
| 2 | 75.39 | 77.210 | −2.36 % |
| 3 | 81.70 | 77.210 | **+5.82 %** |
| 4 | 72.06 | 77.210 | −6.67 % |

Batches 1 and 3 sprayed *more solution than the batch contained*. The "Solution (kg)" column is therefore a **nominal recipe value, not an actual**. It must not be used as the mass basis for weight gain.

**(b) Implied core mass is inconsistent.** Back-calculating from weight gain at η_dep = 1: 389.6 / 354.5 / 405.8 / 343.1 kg — an **18 % spread**. If the batch load is genuinely the same for all four batches, then either η_dep varies by 18 %, or the weight-gain assay carries that much noise, or the sprayed totals are wrong. **CQA-1 cannot be calibrated until the actual core load is known** (§16 Q1).

**(c) Three of the four stage-8 exhaust temperatures are exactly 49.000 °C.** Batches 1, 2 and 3 all read 49.000; batch 4 reads 48.947. Three identical readings to three decimals across independent batches is not what a free-running sensor produces. Either exhaust temperature is **controlled to a 49 °C setpoint** at stage 8, or the value was typed rather than measured. This matters enormously: if exhaust temperature is a controlled variable, then predicting it is predicting the controller, and the model should predict the *manipulated* variable instead. §16 Q2.

### 2.9 Time-scale separation justifies an algebraic gas phase

At 2800 CFM the volumetric flow is 1.32 m³/s. For a free gas volume of 0.8–1.5 m³ the gas residence time is **0.6–1.1 s**. The tablet bed (≈380 kg, c_p ≈ 1.5 kJ/kg·K, hA ≈ 0.15–0.30 kW/K) has a thermal time constant of **1,900–3,800 s**.

Ratio ≈ **2,000–6,000×**. The gas phase is quasi-steady on every timescale the bed cares about. So `modelling.pdf` equations (5.8) and (5.9) should be implemented as **algebraic constraints, not ODEs**. This removes the stiffest states from the integrator, makes the dynamic model roughly an order of magnitude faster, and — critically — makes the steady-state limit of the dynamic model *provably* equal to the EE equation. That equality becomes the collapse gate in §9.3. (Assumes pan free volume; confirm once pan dimensions are known — §16 Q3.)

### 2.10 Codebase audit — what is actually wired up

`pytest` reports **25 passed**. That is misleading. The audit:

| Finding | Evidence |
|---|---|
| **Three pages are permanently unreachable.** `latest_res` / `latest_inputs` are read by `cqa_page.py:10`, `optimization_page.py:11`, `execution_summary.py:14` — and **written by nothing**. CQA, Optimisation and Execution Summary always show "run a simulation first". | `grep -rn "latest_res"` returns readers only |
| **The Risk page runs a test stub.** `app_pages/uncertainty_page.py:14` does `from tests.test_uncertainty import dummy_sim_func`. Stage 4 currently propagates uncertainty through a mock that returns `1.1 if spray_rate > 50 else 0.9`. | `uncertainty_page.py:14` |
| **A Streamlit page is imported as a library.** `simulation_page.py:112` does `from app_pages.validation_page import calculate_stage_physics`, re-executing that page's `st.title`, forms and all, on import. | `simulation_page.py:112` |
| **The solvent toggle is silently ignored.** `simulation_page.py:116` passes `'solvent'`; `dynamic_model.py:15` reads `'solvent_name'`. Non-water physics never activates. | key mismatch |
| **Gun calibration output is consumed by nothing.** `pump_m` / `pump_c` are written in `gun_validation.py:44` and never read anywhere. Stage 2 is a dead end. | `grep -rn "pump_m"` |
| **`test_energy_balance.py` does not test energy conservation.** Its single assertion is `T_bed[-1] < 60.0` — that a temperature went down. `test_mass_balance.py` checks solids only and bounds water between 0 and 1.7 kg. **No conservation budget is closed anywhere in the test suite.** | both files |
| **`calibrated_UA` is meaningless.** Written by `validation_page.py:169` from the double-counting physics, read by `simulation_page.py:20` as the dynamic model's heat-loss coefficient. The corrupted number propagates into Stage 3. | both files |
| **WI is displayed as "EE Factor".** `optimization_page.py:36` and `summary_table.py` label Wetness Index as the EE factor. Real EE values here are 4.18–5.21; WI is 0–1.5. Two unrelated quantities share a label. | both files |
| **Optimiser objective is arbitrary.** `optimization_page.py` minimises `(wi − target)² + 0.1·(T_in·CFM/10000) + penalty` — an unnormalised "energy" term with a hand-picked weight of 0.1, trading physics against a fabricated cost. It also *fits a wet-bulb temperature* to reproduce another model's peak WI. | `optimization_page.py:104` |
| **Excel upload is broken.** `data_upload.py:12` writes any upload to `temp_upload.csv`, and `load_and_clean_batch_data` dispatches on that extension — an `.xlsx` is parsed as CSV. | `data_upload.py:12` |
| **Export page exports hardcoded dummy data.** `df = pd.DataFrame({'time':[0,10,20],'T_bed':[25,30,35]})`, and a YAML literal `HLF_kW_K: 0.125`. | `export_page.py:9` |
| **`configs/*.yaml` are never loaded.** Equipment, limits, products and model card exist as files; no code reads them. Limits are hardcoded at each call site instead. | `grep -rn "yaml"` |

**Summary: of the four stages you want, Stage 1 is wrong, Stage 2 is disconnected, Stage 3 is uncalibrated and partly unreachable, and Stage 4 is a mock.** The tests pass because they assert almost nothing.

---

## 3. Complete defect register

Ordered by severity. "Blocks" = which stage cannot be trusted until fixed.

| # | Defect | Location | Blocks | Fixed in |
|---|---|---|---|---|
| **D1** | Latent-heat double count + missing liquid inlet enthalpy | `validation_page.py:48` | 1, 3, 4 | §8.2 |
| **D2** | Heat-loss sign error in mean-temperature bracket | `legacy_ee_reference.py:92`, `steady_state.py:52`, `dynamic_model.py:197` | 1, 3, 4 | §8.2 |
| **D3** | Per-row refitting presented as validation | `validation_page.py:141`, `legacy_ee_reference.py:183` | 1 | §8.4 |
| **D4** | Four duplicate implementations of one equation | `legacy_ee_reference.py`, `steady_state.py`, `validation_page.py`, `dynamic_model.py` | all | §8.2 |
| **D5** | `latent_heat()` returns vapour enthalpy; `h_fg_i` mislabelled | `solvent_properties.py:32`, `constants.py:15` | all | §8.2 |
| **D6** | Heat loss applied twice in the dynamic path (bed ODE **and** exhaust equation via `alpha = UA/m_da`) | `dynamic_model.py:95,115,196` | 3, 4 | §9.3 |
| **D7** | Evaporation law is `min(cap, M_w/1.0)` — a hardcoded 1-second time constant, grid-dependent and stiff | `dynamic_model.py:86,107` | 3, 4 | §9.4 |
| **D8** | Zone-exchange terms `Q_circ` do not conserve energy on transfer | `dynamic_model.py:96,116` | 3 | §9.3 |
| **D9** | Stage-2 output never reaches the model | `gun_validation.py:44` | 2, 3 | §7 |
| **D10** | `latest_res`/`latest_inputs` never written — 3 pages dead | 3 pages | 3, 4 | §9.7 |
| **D11** | Risk page runs `tests.test_uncertainty.dummy_sim_func` | `uncertainty_page.py:14` | 4 | §10.3 |
| **D12** | Optimiser objective mixes unnormalised fabricated costs; WBT fitted to another model's output | `optimization_page.py:104` | 4 | §10.2 |
| **D13** | WI mislabelled "EE Factor" | `optimization_page.py:36`, `summary_table.py` | 3, 4 | §9.7 |
| **D14** | Solvent selection silently ignored (`solvent` vs `solvent_name`) | `simulation_page.py:116` | 3 | §9.7 |
| **D15** | Streamlit page imported as library | `simulation_page.py:112` | 3 | §9.7 |
| **D16** | No conservation tests anywhere | `tests/` | all | §13 |
| **D17** | `configs/*.yaml` never loaded; limits hardcoded per call site | all pages | 3, 4 | §12 |
| **D18** | Droplet/spray-zone correlations are invented placeholders (`d32_base = 40.0`, "Dummy scaling for demo") | `spray.py:9`, `spray_uniformity_page.py:27` | 3 | §9.6 |
| **D19** | Excel upload parsed as CSV | `data_upload.py:12` | 0 | §6 |
| **D20** | Export page ships hardcoded dummy data | `export_page.py:9` | 4 | §10.5 |

---

## 4. Objectives and the three error targets

**Objective.** A plant-scale coating model that matches or beats the locked EE thermodynamic baseline on data it has never seen; that consumes the two CPPs EE ignores (pan RPM, atomisation pressure) *where the data can support them*; that resolves time and process phase; and that is honest about the boundary of what it knows.

**Three error targets, never conflated:**

| Target | Definition | Required |
|---|---|---|
| **T1 — Software reproduction** | M1 vs M0, identical inputs and α | `|ΔT| < 1e-9 °C` |
| **T2 — Calibration residual** | Per-row fitted α (what today's table shows) | ≈ 0. Displayed, labelled *calibration* |
| **T3 — Locked prediction** | Leave-one-batch-out; parameters frozen before the fold is seen | **RMSE ≤ 0.654 °C, max ≤ 1.107 °C**, zero physics violations |

**T3 is the gate.** Anything that raises it is rejected regardless of how good its physics story is.

**Evaluation scheme — revised by DEC-4.** The v2.0 leave-one-batch-out scheme treated all 12 rows as calibration data with rotating folds. Under the acceptance-test discipline (§0) the split is fixed instead:

| Batch | Role | May be consulted |
|---|---|---|
| 1 | Calibration (only if `UA` cannot be derived from first principles — §0.5) | during calibration |
| 2, 3 | **Development acceptance set** | freely, during iteration, logged |
| 4 | **Sealed final acceptance** | **once, at the end** |

If `UA` is derived from equipment properties (§0.5 route (a)), batch 1 joins the development acceptance set and nothing is fitted at all.

LOBO is retained for one purpose only: estimating the fold-to-fold spread of `UA` for the identifiability gate G4 and for the uncertainty inputs in §10.3. It is a **diagnostic**, not the headline metric.

---

## 5. The gate system

Applies identically to every module in every stage. All five must pass. Any failure → flag off, evidence to `reports/`, item to future work.

| Gate | Test | Threshold |
|---|---|---|
| **G1 Collapse** | Module disabled ⇒ reproduces its parent exactly | `< 1e-9` |
| **G2 Physics** | Mass and energy budgets close; RH ∈ [0,1]; no negative moisture; T within bounds; **no fitted parameter resting on a bound**; every parameter physically signed | zero violations |
| **G3 Non-degradation** | LOBO error vs `reports/baseline_locked.md` | RMSE **and** max both ≤ baseline |
| **G4 Identifiability** | Parameter SE from fold-to-fold spread | `|θ|/SE(θ) > 2` and sign consistent across all 4 folds |
| **G5 Parsimony** | Improvement must exceed measurement noise | `ΔRMSE ≥ 0.05 °C` (≈ exhaust-sensor resolution) |

G2's *"no parameter resting on a bound"* clause is the one that would have caught the Track A failure on day one: the broken function pinned `UA` at 0.0 and still missed by 2 °C.

This maps onto the PDF's own four-gate filter (§13.3: rationale → data available → improves an output → validatable), with G4 and G5 added because the PDF's filter has no defence against an unidentifiable parameter, which is precisely this dataset's failure mode.

---

# Part II — The four stages

## 6. Stage 0 — Acceptance-set foundation *(new prerequisite)*

**What.** Turn the screenshots into versioned, reconciled CSVs — **labelled and stored as an acceptance test set** (DEC-4), with every column tagged by provenance (DEC-5).

**Why.** `sample_data/` is empty. The 12 stages, the gun table and the time-series exist only as images. Nothing downstream is reproducible, and no gate can be automated, until they are files. Equally important: the column-provenance tags are what stop an EE-output column being mistaken for a measurement — §0.3 shows that `Exhaust RH` looks exactly like a measurement and is not.

**Is it correct / should it be done?** Yes, and it is genuinely blocking. It is also where §2.8's three integrity findings get resolved rather than propagated.

**Does it change the output?** Indirectly and decisively — §2.8(b) shows that weight gain cannot be calibrated at all until the true core mass is known.

### 6.1 Deliverables

- `data/plant/stages_v1.csv` — 12 rows at full source precision, with `source`, `entered_by`, `confirmed_against_excel` columns.
- `data/plant/gun_calibration_v1.csv` — per-gun measurements at 5 and 10 rpm, all four batches.
- `data/plant/timeseries/<batch>.csv` — per-minute data (screenshot 3). **Needed for Stage 3.**
- `data/plant/README.md` — provenance, units, ambiguous cells, transcriber.
- `scripts/step0_verify_data.py` — recomputes every derived column and reports non-reconciling cells.
- `coating_model/io/loaders.py` — replaces `data_loader.py`; dispatches on true file type, fixing D19.

### 6.2 The transcription — **please confirm against the source Excel**

| Batch | Pump | Spray/gun | Total | T_in (°C) | CFM | RH % | Atom | Pan RPM | T_exh (°C) | α | α avg | EE | Time | Sprayed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 7 | 32.72 | 196.3 | 56.507 | 2800.63 | 5 | 2 | 1 | 48.519 | 0.149 | 0.097 | 4.6446 | 55 | 10.80 |
| 1 | 8 | 36.95 | 221.7 | 56.507 | 2801.01 | 5 | 2 | 2 | 49.000 | 0.094 | | 4.9451 | 74 | 16.40 |
| 1 | 9 | 41.17 | 247.0 | 56.514 | 2800.62 | 5 | 2 | 2 | 49.373 | 0.046 | | 5.2053 | 219 | 54.10 |
| 2 | 7 | 32.68 | 196.1 | 56.565 | 2804.13 | 5 | 2 | 1 | 48.783 | 0.139 | 0.116 | 4.7723 | 24 | 4.71 |
| 2 | 8 | 36.95 | 221.7 | 56.538 | 2800.54 | 5 | 2 | 2 | 49.000 | 0.096 | | 4.9279 | 40 | 8.87 |
| 2 | 9 | 41.21 | 247.3 | 56.534 | 2799.84 | 5 | 2 | 2 | 48.040 | 0.114 | | 4.3647 | 250 | 61.82 |
| 3 | 7 | 32.75 | 196.5 | 56.595 | 2802.65 | 5 | 2 | 1 | 48.405 | 0.160 | 0.125 | 4.5334 | 38 | 7.47 |
| 3 | 8 | 36.90 | 221.4 | 56.622 | 2801.91 | 5 | 2 | 2 | 49.000 | 0.101 | | 4.8816 | 46 | 10.19 |
| 3 | 9 | 41.06 | 246.3 | 56.552 | 2798.68 | 5 | 2 | 2 | 48.066 | 0.114 | | 4.3707 | 260 | 64.05 |
| 4 | 7 | 32.59 | 195.5 | 56.600 | 2803.38 | 5 | 2 | 1 | 47.725 | 0.198 | 0.139 | 4.1772 | 41 | 8.02 |
| 4 | 8 | 36.73 | 220.4 | 56.561 | 2801.32 | 5 | 2 | 2 | 48.947 | 0.101 | | 4.8802 | 58 | 12.78 |
| 4 | 9 | 40.88 | 245.3 | 56.519 | 2798.88 | 5 | 2 | 2 | 48.005 | 0.117 | | 4.3528 | 209 | 51.26 |

Batch-level: solution 77.215 kg (B1) / 77.21 kg (B2–4); solids 0.15; 6 guns; P = 101.325 kPa; weight gain 3.13 / 3.19 / 3.02 / 3.15 %; assay 101.60 / 100.1 / 100.9 / 101.2.

**Gate 0.** Every derived column reconciles within display rounding (32.72 × 6 = 196.32 vs shown 196.3 — flagged, both retained, never silently substituted). The three §2.8 findings are each either explained or formally recorded as known data limitations. You have signed off the CSV against the source.

---

## 7. Stage 2 — Gun validation *(built first)*

### 7.1 Why this stage moves ahead of Stage 1

The spray rate that Stage 1's thermodynamics consumes **is the output of Stage 2**. Today it is typed in by hand and Stage 2's result (`pump_m`, `pump_c`) is consumed by nothing (D9). Since §2.7 shows this chain reproduces the plant table to 0.004 g/min, building it first gives Stage 1 a *traceable, validated input* instead of a typed number — and it is the one part of the project where I can promise the numbers already work.

**Does it change the output?** Yes. Spray rate is the dominant term in the evaporation mass balance, and §2.6 shows it is the *only* input with real variation. Every Stage 1 error number depends on it being right.

### 7.2 What to build

**A. Data model.** Per-gun measurements, not just totals. Current code (`gun_validation.py:44`) fits `total / n_guns`, discarding the individual gun readings — which is precisely where the uniformity information lives.

**B. Calibration fit.**
```
rate_per_gun (g/min/gun) = m · pump_rpm + c
```
Fitted per batch by least squares over all available setpoints. With the present two setpoints (5, 10 rpm) this is exact interpolation — report it as such, with `n_points`, `dof = n − 2`, and residual `= 0 by construction` rather than an implied R² of 1.0.

**C. Guards.**
- Block extrapolation outside the calibrated rpm range (5–10). The intercept `c ≈ 3 g/min` at 0 rpm is non-physical; the model must refuse, not silently extrapolate.
- Flag `c` as a pump-offset diagnostic; a growing `c` across batches indicates pump wear or priming drift.
- Warn if any single gun deviates > 3σ from the gun mean → blocked or worn nozzle.

**D. Gun-to-gun uniformity statistic.** Compute and store CV per rpm per batch (the 1.5–3.6 % of §2.7). This is a **measured** input to §9.6's uniformity model.

**E. Wiring (fixes D9).** Persist to `data/plant/gun_calibration_v1.csv` and expose `spray_rate_from_pump(batch, rpm) → g/min/gun` for Stages 1, 3 and 4. Every downstream spray rate carries provenance: *measured* / *from calibration* / *user override*.

### 7.3 Gates

| Gate | Threshold |
|---|---|
| **S2-G1** | Recomputed `m`, `c` match the plant record | `< 1e-6` |
| **S2-G2** | Predicted spray rate matches the plant table for all 12 stages | `< 0.005 g/min` (verified achievable — §2.7) |
| **S2-G3** | Extrapolation beyond calibrated rpm is refused, not silently returned | hard fail |
| **S2-G4** | Gun-to-gun CV computed and persisted for all 4 batches | present |

**Assessment: this stage is low-risk and fully verified in advance.** It is the right place to establish the provenance, gating and reporting patterns that the harder stages reuse.

---

## 8. Stage 1 — Model validation & calibration

The subject of the source `.md`, extended.

### 8.1 M0 — freeze and audit the legacy EE

**What.** `validation/m0_legacy_adapter.py` imports `Reference/EE-test-9-1-Varible-Solid-Fraction.py` **unmodified**, with a `streamlit` shim (it imports `streamlit` at module scope and reads `st.session_state` inside the optimiser). Plus `scripts/step1a_legacy_ee_audit.py` exactly as specified in the source `.md`: fixed α, no optimiser, ≥12 decimals, all assertions, CSV output, the mandated header comment.

**Why.** Without a frozen reference there is nothing to prove equivalence *against*, and every later change is unfalsifiable.

**Does it change the output?** No — that is the point. It changes what we can *claim* about the output.

**Gate.** All assertions pass; every intermediate traceable; nothing rounded before final display; measured exhaust excluded from the prediction path; two runs byte-identical. Expected: the §2.1 table, residual 0.0057 °C, explained by α display rounding and confirmed in Step 1B by back-solving α exactly.

### 8.2 M1 — one canonical thermodynamic core *(fixes D1, D2, D4, D5)*

**What.** `coating_model/energy_balance.py` — the **only** exhaust-temperature function in the repository.

```
Per kg dry air, steady state:

  cp_a·T_in + w_in·h_v(T_in)  +  (w_ex − w_in)·h_liq(T_water_in)
= cp_a·T_ex + w_ex·h_v(T_ex)  +  q_loss

  h_v(T)  = enthalpy_A·T + enthalpy_B      [vapour enthalpy, kJ/kg]
  h_liq   = 104.7598 kJ/kg                 [liquid water at 25 °C]

  q_loss  = α·((T_in + T_ex)/2 − T_amb)    heat_loss_form = "physical_ua"
  q_loss  = α·((T_ex − T_in)/2 + T_amb)    heat_loss_form = "legacy_alpha"  [bit-exact M0]
```

Every enthalpy term individually named, unit-annotated, and appearing **exactly once**. `heat_loss_form` is an explicit switch, so the legacy convention is reproducible on demand and the physical one is available for anything that extrapolates.

Renames that prevent D1 recurring: `latent_heat()` → `vapour_enthalpy()`; `h_fg_i_water` → `h_liquid_water_at_25C`. Old names raise a deprecation error rather than silently working — the misleading *name* is what caused the bug.

`steady_state.py`, `validation_page.py` and `dynamic_model.py` all rewired to call it. `calculate_stage_physics` deleted.

**Is it correct?** Yes, and verified: §2.3 shows the corrected form returns 51.601381 °C at α = 0, matching legacy adiabatic to six decimals.

**Does it change the output?** Massively — 5.2 °C at the audit row, and it is the difference between a model that works and one that cannot reach the measurement from inside its own bounds.

**Also in this step:** remove scale-up entirely — delete `coating_model/scale_up.py`, `app_pages/scale_up_page.py`, the registry entry at `streamlit_app.py:129`, `tests` references, and the scale-up sections of `DOCUMENTATION.md`.

**Gate (T1).** `max |T_M1 − T_M0| < 1e-9 °C` across all 12 rows with `heat_loss_form="legacy_alpha"`. Zero duplicate implementations (verified by grepping for the equation constants). No scale-up symbol anywhere.

### 8.3 The alpha / UA hierarchy

**What.** One equipment-level `UA` (kW/K) is the stored parameter. Stage α is *derived* as `α = UA / ṁ_da`, never independently fitted. Fixes the source `.md` §7 concern that both are being optimised.

**Is it correct?** The hierarchy is right. But §2.5 shows it will not improve *this* dataset, because airflow is constant — I am implementing it because it is correct and because it matters the moment airflow varies, not because it will move today's number. Stated so no one later reports it as an improvement.

**Does it change the output?** On this dataset: no (< 0.01 °C). On any dataset where airflow varies: up to 3× on the heat-loss term, per PDF §2.3.1.

### 8.4 M2 — honest baseline measurement *(fixes D3)*

**What.** `validation/splits.py` (LOBO), `validation/metrics.py` (raw-precision signed/absolute/percentage; rounding only at display), `scripts/step3_baseline.py`, and the frozen `reports/baseline_locked.md`.

**Why.** This produces the number every later module is judged against. Without it, "improvement" is unmeasurable.

**Gate.** Reproduces §2.2 (locked per-batch ≈ 0.654 °C RMSE). Calibration and prediction errors appear in **separate tables with different headings**. The benchmark file is committed and tagged, and never edited afterwards.

### 8.5 The two-column display *(your 0 % requirement, honoured)*

The Stage 1 page will show, per stage, side by side:

| Stage | Measured | **Predicted (calibrated)** | **Error % (cal)** | **Predicted (locked)** | **Error % (locked)** | α fitted | UA locked | Status |
|---|---|---|---|---|---|---|---|---|

- The **calibrated** columns are today's behaviour, unchanged: per-row fitted α, error 0.000. Nothing you rely on is removed.
- The **locked** columns are the honest predictor: parameters fitted on other batches only.
- A footnote states in one line that the first is a fit and the second is a prediction, so no one mistakes one for the other.

**Does it change the output?** It changes what is *displayed*, not what is computed. But it is the single change that makes model improvement visible at all — under per-row fitting, every model scores 0.000 and better physics is indistinguishable from worse physics.

### 8.6 M3–M6 — candidate corrections, in order, one at a time

Each gets its own flag (default off), its own gate report, and is retained only on all five gates of §5.

| Module | Term | Prior assessment |
|---|---|---|
| **M3** Time/phase | dynamic states | See §9.3. Needs the time-series. Genuine prospect. |
| **M4** Pan RPM | 1 parameter | **Expected to fail G4.** RPM ∈ {1,2} perfectly confounded with pump stage (§2.6). |
| **M5** Atomisation | 1 parameter | **Cannot be fitted.** Constant at 2 bar. Will be wired and disabled; no fit attempted. |
| **M6** Equipment design | ≤ 1 parameter | Only terms touching the plant model. |

For M4 and M5, rejection is a *deliverable*, not a failure: each ships with a one-page DoE specification stating exactly which experiment would identify it (for M4: vary RPM independently of spray rate at fixed thermal conditions — approximately 6 extra stages).

---

## 9. Stage 3 — Model execution

The dynamic Track A core. This is the largest stage and the one with the most existing defects.

### 9.1 What Stage 3 must produce

| Output | Validatable against | Status |
|---|---|---|
| Exhaust T, RH vs time | plant time-series | **yes, once §16 Q3 is answered** |
| Evaporation rate, WI, EWI | indirectly (defects/LOD) | diagnostic |
| Bed temperature | nothing currently measured | **unvalidated — must be labelled so** |
| Weight gain | 4 batch values | **yes, once core mass is known (§16 Q1)** |
| Mean film thickness | tablet geometry | yes, as a batch average |
| Cycle time | 4 batch values, reconciles exactly | yes |
| Coating CV / uniformity | nothing measured | **unvalidated** |
| Dissolution / assay / RS | 4 assay values only | **not predictive — exclude from MVP** |

**The honesty rule for this stage:** every output is tagged `VALIDATED` / `DIAGNOSTIC` / `UNVALIDATED` in the UI and in every export. An unvalidated output may be shown — it must never be presented as a prediction.

### 9.2 Architecture: algebraic gas, dynamic bed

Per §2.9, the gas phase is 2,000–6,000× faster than the bed. So:

- **Gas phase — algebraic.** Solved to quasi-steady at each timestep. Replaces PDF eqs (5.8)/(5.9) as ODEs.
- **Bed phase — ODE.** States: `T_bed`, `M_water_free`, `M_water_bound`, `M_coat`.
- **Two zones — deferred behind a flag.** PDF §5.6 is right that spray/drying zones matter physically, but the zone fraction, inter-zone exchange rate and per-zone airflow split are three unidentifiable parameters (§2.6). Build single-zone first; enable two-zone only if the time-series supports it.

**Is this correct?** Yes, and it is a strict improvement on the current design: it removes the stiffest states, and it makes the steady-state limit of the dynamic model *provably* equal to the EE equation — which is what §9.3's gate exploits.

### 9.3 Energy balance *(fixes D6, D8)*

**The bug.** `dynamic_model.py` applies `UA·(T_bed − T_amb)` in the bed ODE (lines 95, 115) **and** applies `alpha = UA/m_da` inside the legacy exhaust equation (line 196). Heat loss is counted twice.

**The correct structure.** Book evaporation as mass transfer from bed liquid to gas, so the latent heat appears exactly once:

```
Bed:  M_b·cp_b · dT_b/dt = h·A·(T_g − T_b)
                          + ṁ_spray·cp_liq·(T_spray − T_b)
                          − ṁ_evap·λ(T_b)
                          − UA_bed·(T_b − T_amb)

Gas:  ṁ_da·(h_g,out − h_g,in) = −h·A·(T_g − T_b)
                                + ṁ_evap·h_v(T_b)
                                − UA_gas·(T_g − T_amb)
```

Water leaves the bed as vapour at `T_b` carrying `h_v(T_b)`; the latent heat is drawn from the bed by the `−ṁ_evap·λ(T_b)` term. The gas receives that vapour. No term appears twice.

**The gate this enables.** Set `dT_b/dt = 0`, eliminate `h·A·(T_g − T_b)` between the two equations, and the single control-volume balance of §8.2 must be recovered **algebraically**. So:

> **S3-G1: with constant inputs, the dynamic model integrated to steady state must equal M1 to `< 1e-9`.**

This is derivable, not merely hoped for. If it fails, the closure is wrong — and it would have caught D6 immediately.

Zone-exchange terms (D8) get an explicit conservation test: tablet mass, water and coating transferred out of one zone must arrive in the other, each timestep, to `1e-12`.

### 9.4 Evaporation law *(fixes D7)*

**The bug.** `m_evap = min(cap, M_w/1.0)` — a hardcoded 1-second draining constant, dimensionally arbitrary, grid-dependent and stiff.

**The replacement.** Mass-transfer-limited with the Lewis analogy, then capped by physical availability:

```
ṁ_evap = min(  k_m · A_wet · (ρ_v,sat(T_b) − ρ_v,gas),         mass-transfer limit
               ṁ_da · (w_sat(T_b) − w_in),                     air-capacity limit
               M_free/Δt + ṁ_w,spray  )                        availability limit

k_m = h / (ρ_air · cp_air · Le^{2/3}),  Le ≈ 1
```

**Why the Lewis analogy specifically.** It ties `k_m` to `h`, so the mass-transfer and heat-transfer coefficients are **one parameter, not two**. Given §2.6, adding a second free thermal parameter would be unidentifiable. This is a deliberate identifiability-driven modelling choice, and it should be stated as such in the model card.

The one genuinely new unknown is the **wetted-area fraction** `A_wet/A_bed`. That is the single fitted parameter of the evaporation law, it is physically bounded on [0, 1], and G2 rejects it if it lands on a bound.

**Does it change the output?** Yes — this is the mechanism §2.5 identified as the true source of the residual (evaporation over-predicted at high spray rate). It is the most promising candidate for actually beating the baseline.

### 9.5 Moisture states

Per the source `.md` §4: the undefined `ṁ_w,other` term in PDF eq (5.5) hides physics. Split explicitly:

```
dM_free/dt  = ṁ_w,spray − ṁ_evap − k_abs·(M_free − M_eq)
dM_bound/dt = k_abs·(M_free − M_eq)
```

`M_free` is film water available to evaporate; `M_bound` is core-absorbed water that is not. Only `M_free` feeds the availability limit in §9.4. Both non-negative by construction (enforced in the RHS, not by clipping the state afterwards — clipping breaks conservation).

**Is `k_abs` identifiable?** Not from exhaust temperature alone. It requires LOD or moisture data. Ships with `k_abs = 0` (all sprayed water is free water) as the default, which is the conservative assumption, and is enabled only if moisture data becomes available. Documented as an explicit assumption, not hidden.

### 9.6 Spray, deposition and uniformity *(fixes D18)*

**What exists.** `coating_model/spray.py:9` invents `d32_base = 40.0 µm` with heuristic exponents; `spray_uniformity_page.py:27` computes drying time as `t_flight * (d32/40.0)` with the inline comment "Dummy scaling for demo". These numbers have no source and no calibration data.

**Assessment: these should not be built as predictive models.** Both the source `.md` (§7) and the PDF are clear that droplet-size and spray-footprint correlations need spray-pattern measurements you do not have. Per the PDF's own Gate 2 (*is the necessary input data available?*), the answer is no.

**What to build instead — the parts that *are* supported by data:**

| Quantity | Basis | Verdict |
|---|---|---|
| Spray rate per gun, per kg load | measured | **build** |
| Total spray rate, atomisation pressure, gun count, gun-to-bed distance | measured/recorded | **build (as recorded inputs)** |
| **Gun-to-gun CV (1.5–3.6 %)** | **measured, §2.7** | **build — this is real uniformity data** |
| Deposition efficiency η_dep | fittable from weight gain **once core mass is known** | build after §16 Q1 |
| Mean film thickness δ = m_coat/(ρ_film·A_tablet) | geometry | build, batch-average only |
| Droplet size d32 | no data | **exclude** |
| Spray-zone area, flux J | no spray-pattern data | **exclude** |
| Π_flight regime classification | depends on d32 | **exclude** |

**On the Monte Carlo uniformity model (PDF ch. 8):** the structure is sound and `CV ∝ 1/√t` is a real result. But circulation time and spray-zone residence time are currently hardcoded (15.0 s, 0.5 s) with no measurement behind them, and nothing measures coating CV to validate against. Plan: keep it, drive its *measured* component from the gun-to-gun CV, present two bounding cases (tablets sample all guns equally → gun variance averages out; tablets preferentially sample one gun → gun variance passes through fully), and label the whole output `UNVALIDATED — RESEARCH`. It is genuinely useful for reasoning about *relative* changes; it is not a number to put on a batch record.

### 9.7 Wiring and UI corrections *(fixes D10, D13, D14, D15)*

- Introduce `coating_model/run_context.py` — a single typed results object, written once by the execution page and read by CQA, Optimisation and Execution Summary. Kills the `latest_res`/`latest_inputs` dead-key problem.
- Rename every "EE Factor (Peak WI)" label. EE factor and Wetness Index are different quantities with different scales (4.18–5.21 vs 0–1.5) and must never share a label.
- Fix the `solvent` / `solvent_name` key mismatch; add a test that the sidebar toggle actually changes a computed number.
- No page is ever imported as a library. Physics lives in `coating_model/`, pages only call it.
- Load `configs/*.yaml` (fixes D17) — one limits source, not hardcoded per call site.

### 9.8 Stage 3 gates

| Gate | Threshold |
|---|---|
| **S3-G1** | Dynamic model at steady state ≡ M1 | `< 1e-9` |
| **S3-G2** | Energy budget closes each timestep | rel. residual `< 1e-8` |
| **S3-G3** | Mass budget (water, solids) closes each timestep | rel. residual `< 1e-8` |
| **S3-G4** | Zone transfers conserve | `< 1e-12` |
| **S3-G5** | LOBO on time-series exhaust T, RH vs `baseline_locked.md` | ≤ baseline |
| **S3-G6** | Solver-independence: halving `max_step` changes outputs by | `< 1e-6` |
| **S3-G7** | Every output tagged VALIDATED / DIAGNOSTIC / UNVALIDATED | 100 % coverage |

S3-G6 exists because D7's hardcoded 1-second constant makes results depend on the integrator's step choice — a class of bug that is invisible until someone changes a tolerance.

---

## 10. Stage 4 — Optimisation & risk

### 10.1 Current state

Stage 4 does not presently function. `optimization_page.py` and `cqa_page.py` are unreachable (D10); `uncertainty_page.py` propagates uncertainty through a **test stub** (D11); the optimiser objective mixes an unnormalised fabricated energy cost at an arbitrary weight and *fits a wet-bulb temperature to reproduce another model's output* (D12); the export page ships hardcoded dummy values (D20).

**It must be rebuilt on top of a validated Stage 3, not before.** An optimiser is an amplifier: it searches for the input where the model's prediction is most extreme, which is exactly where model error is largest. Optimising an unvalidated model is worse than not optimising, because it converges confidently on the model's blind spot.

### 10.2 Optimiser *(fixes D12)*

**What.**
```
minimise    cycle_time(spray_rate)                     ← the actual business objective
subject to  WI(t)      ≤ WI_crit                       ← overwetting
            T_bed(t)   ≤ T_dcmp                        ← degradation
            RH_exh(t)  ≤ RH_max                        ← condensation
            T_exh(t)   ∈ [T_min, T_max]                ← product spec
            all inputs ∈ validated envelope            ← hard abstention
```

Constraints as **constraints**, not weighted penalties. Objective in real units the plant recognises (minutes, or kg solution per hour). No fabricated energy term with a hand-picked weight — if energy cost matters, it enters as a real tariff in currency units, or not at all.

**Why this is different from what exists.** Today's objective `(wi − target)² + 0.1·(T_in·CFM/10000) + penalty` has no units, so the 0.1 weight silently sets a physically meaningless exchange rate between wetness and airflow. The optimum it finds is an artefact of that weight.

**The abstention rule.** The validated envelope from this dataset is narrow — `T_inlet` 56.5–56.6 °C, airflow ≈ 2800 CFM, RH 5 %, solids 0.15, spray 32.6–41.2 g/min/gun. The optimiser's bounds are currently 40–90 °C and 500–3000 CFM, i.e. it roams *far* outside anything validated. It must refuse, loudly, with the specific out-of-range variable named. `coating_model/validity.py` already has the right shape for this; it simply is not called from anywhere.

**Does it change the output?** Yes, and it is the highest-consequence change in the project: this is the page that would generate a setpoint someone acts on.

### 10.3 Uncertainty *(fixes D11)*

**What.** Replace the test stub with real propagation through the validated Stage 3 model.

**Where the input distributions come from — this matters.** Not invented. Two sources:
1. **Sensor/process variability** measured from the per-minute time-series (§16 Q3) — the actual standard deviation of inlet temperature, airflow and RH within a stage.
2. **Parameter uncertainty** from the LOBO folds — the fold-to-fold spread of `UA` *is* an estimate of its uncertainty, and it is already computed for G4.

**Is it correct to do this?** Yes, but **only after** parameter distributions exist. Running Monte Carlo before then produces confident-looking distributions built on invented inputs — worse than no uncertainty at all, because it looks rigorous. This is why Stage 4 is last, and the source `.md` reaches the same conclusion ("appropriate only after parameter distributions are estimated").

**Outputs.** `P(WI > WI_crit)`, `P(T_bed > T_dcmp)`, `P(RH_exh > limit)`, and prediction intervals on exhaust temperature. Sample count justified by convergence of the reported quantile, not fixed at a round number.

### 10.4 Design space

Traffic-light map (PDF §10.3) over the **two axes with real variation** — spray rate and inlet temperature — with a fourth colour beyond green/amber/red:

- **Green** — all limits satisfied with margin.
- **Amber** — within limits but sensitive to uncertainty.
- **Red** — predicted limit violation.
- **Grey — outside the validated envelope; model abstains.**

Grey is not in the PDF. It should be, and given §2.6 it will cover most of the map. A design-space plot that quietly extrapolates is the most dangerous single artefact this application could produce; the grey region is what makes it safe.

### 10.5 Reporting *(fixes D20)*

Real export of the actual run: inputs with provenance, parameters with their lock status and uncertainty, outputs with validation tags, gate results, and the model-card version. Plus `configs/model_card.yaml` updated with the true validated envelope, locked parameters, and an explicit "must not be used for" list.

### 10.6 Stage 4 gates

| Gate | Threshold |
|---|---|
| **S4-G1** | Optimiser uses only the canonical validated physics — no private copy | code check |
| **S4-G2** | Any recommendation outside the validated envelope is refused with the variable named | 100 % |
| **S4-G3** | Every constraint enters as a constraint, not a weighted penalty | code review |
| **S4-G4** | Monte Carlo input distributions traceable to measured variability or LOBO spread | 100 %, no invented σ |
| **S4-G5** | Recommended setpoint, re-simulated, reproduces the optimiser's claimed outputs | `< 1e-6` |
| **S4-G6** | Exported report contains no hardcoded values | code check |

S4-G5 is a round-trip check: it catches the class of bug where the optimiser and the display use different code paths — exactly the D15 pattern.

---

# Part III — Execution

## 11. Chronological phase plan

Implementation order differs from stage numbering, for the reasons given in §7.1 and §10.1.

| Phase | Content | Depends on | Gates | Deliverable you can act on |
|---|---|---|---|---|
| **P0** | Data foundation (§6) | your Excel confirmation | Gate 0 | A real, versioned dataset |
| **P1** | Stage 2 gun validation (§7) | P0 | S2-G1…G4 | Traceable spray-rate provenance; verified in advance |
| **P2** | M0 freeze + audit (§8.1) | P0 | T1 prep | Proof the legacy model is understood digit by digit |
| **P3** | M1 canonical core; scale-up removal (§8.2–8.3) | P2 | T1 | **The fatal bug gone.** One source of truth |
| **P4** | M2 locked baseline + two-column display (§8.4–8.5) | P3 | T3 baseline | **The honest EE number.** Everything measurable from here |
| **P5** | Stage 3 core: algebraic gas, bed ODE, evaporation law (§9.2–9.5) | P4 + time-series | S3-G1…G7 | A dynamic model — or a documented reason it is unidentifiable |
| **P6** | M4 RPM, M5 atomisation (§8.6) | P5 | G1–G5 each | Validated, or rejected with the DoE that would settle it |
| **P7** | Stage 3 UI/wiring; spray & uniformity honest scope (§9.6–9.7) | P5 | S3-G7 | Working execution pages with validation tags |
| **P8** | Stage 4 optimiser + abstention (§10.2) | P7 | S4-G1…G3, G5 | Setpoint recommendations that refuse to extrapolate |
| **P9** | Stage 4 uncertainty, design space, reporting (§10.3–10.5) | P8 | S4-G4, G6 | Risk-aware design space with a grey zone |
| **P10** | Documentation, model card, final scope statement | all | — | Advisory-only model with an honest boundary |

**P0–P4 are the phases that turn the project around, and they are the ones whose success I can predict with confidence**, because §2.1, §2.3 and §2.7 are already verified numerically. P5 onward depends on data that does not yet exist in this repository.

---

## 12. Repository layout

```
data/plant/            stages_v1.csv, gun_calibration_v1.csv, timeseries/, README.md
validation/            m0_legacy_adapter.py, splits.py, metrics.py, gates.py
coating_model/
  energy_balance.py    THE canonical thermodynamic core (§8.2)
  evaporation.py       Lewis-analogy law (§9.4)
  gun_calibration.py   pump → spray rate provenance (§7)
  run_context.py       single typed results object (§9.7)
  io/loaders.py        replaces data_loader.py, real type dispatch
  config.py            loads configs/*.yaml — currently never read
scripts/               step0_… step1a_… step3_… one runnable script per phase
reports/               baseline_locked.md + one gate report per module (committed)
tests/                 equivalence, conservation, collapse, solver-independence
```

**Deleted:** `coating_model/scale_up.py`, `app_pages/scale_up_page.py`, `calculate_stage_physics` in `validation_page.py`, and the `tests.test_uncertainty` import in `uncertainty_page.py`.

---

## 13. Test architecture *(fixes D16)*

Current suite: 25 tests, all passing, and `test_energy_balance.py` asserts only that a temperature decreased. Replace with five classes:

| Class | Asserts | Example |
|---|---|---|
| **Equivalence** | M_k with new term off ≡ M_(k−1) | `|ΔT| < 1e-9` |
| **Conservation** | closed budgets, every timestep | energy and mass residual `< 1e-8` |
| **Bounds** | physical validity | RH ∈ [0,1], M_water ≥ 0, no parameter on a bound |
| **Numerical** | solver independence | halve `max_step` ⇒ Δ < 1e-6 |
| **Regression** | pinned values from `reports/` | 12-row exhaust temperatures to 1e-9 |

Every test names the defect it prevents, so a future change that reintroduces D1 fails with a message that says so.

---

## 14. Precision and display policy

You asked whether three decimals are real and whether to keep them. Answer, applied throughout:

- **Internal:** full float64 precision always. Never round before a downstream calculation.
- **Validation/diagnostic tables:** 3–4 decimals, to expose optimiser and rounding behaviour.
- **Factory-facing display:** tied to instrument resolution. Exhaust temperature to 2 dp at most.
- Three decimals in a result do **not** create physical accuracy; they reveal that the calculation carries more digits than the input widget accepted. Uploaded Excel can also carry more precision than the manual input control.

**And a caution from the data itself:** §2.8(c) — three of the four stage-8 exhaust readings are exactly 49.000 °C. That third decimal is not a measurement in at least those rows. It is a further reason to fix display precision to what the instrument can actually resolve.

---

## 15. Risk register

| Risk | Likelihood | Consequence | Response |
|---|---|---|---|
| No second parameter is identifiable from 12 rows (§2.6) | **High** | M4, M5 and possibly M3 all fail G4 | Legitimate outcome. Deliverable becomes corrected M1/M2 — already far better than today — plus a DoE specification. **Do not fabricate a fit.** |
| Time-series unavailable | Medium | No validated Stage 3 | Ship Stage 1 + 2. State plainly that dynamics are unvalidated. |
| Core mass unknown (§2.8b) | Medium | η_dep and weight gain uncalibratable | Report weight gain as a *ratio to the batch's own record*, not an absolute prediction, until resolved. |
| Exhaust temperature is a controlled variable (§2.8c) | **Unknown — needs answer** | The entire Stage 1 premise inverts: we would be predicting a controller setpoint | §16 Q2. If yes, the model must predict the manipulated variable instead. This changes Stage 1's target. |
| RPM confounded with spray rate | **Certain in this dataset** | M4 rejected | Rejection *is* the finding. Specify the experiment. |
| Atomisation constant at 2 bar | **Certain** | M5 cannot be fitted | Wire it, disable it, specify the experiment. |
| Optimiser recommends outside validated envelope | High without abstention | **Unsafe plant setpoint** | S4-G2 hard abstention; grey zone on the design space |
| Pressure to make numbers look good | — | Model becomes untrustworthy | Gates are mechanical; baseline is committed and immutable; a module that fails is reported as failed |

**What I will not do:** report a calibration residual as accuracy; fit a parameter to a row and then score on that row; retain a module because its physics story is attractive when the gates reject it; present droplet-size or spray-coverage numbers that have no measurement behind them; or let an optimiser recommend a setpoint outside the validated envelope.

**What you gain even in the worst case:** an energy balance that is correct (today's is 5.2 °C wrong before any fitting), one source of truth instead of four drifting copies, a gun-calibration chain wired into the model instead of dead-ended, an honest error number instead of a fitted zero, no scale-up, working Stage 3/4 pages instead of three unreachable ones, real conservation tests, and a precise specification of the two experiments that would unlock RPM and atomisation.

---

## 16. Questions I need answered

Ordered by how much they change the plan. **Q1–Q3 are blocking for Stages 3–4; P0–P4 can start on Q0 alone.**

**Q0 — the 12-row table in §6.2.** Confirm against the source Excel. I transcribed it from a screenshot; one wrong digit invalidates everything downstream. *(Blocking for P0.)*

**Q1 — What is the actual tablet core load per batch (kg)?**
§2.8(b): back-calculated core mass ranges 343–406 kg across the four batches, an 18 % spread. Weight gain, film thickness and deposition efficiency are all uncalibratable until this is known. Also: is the load the same for all four batches?

**Q2 — ~~Is exhaust temperature controlled to a setpoint?~~ CLOSED by DEC-1.**
Answer: exhaust runs free. The three identical `49.000 °C` readings are treated as a transcription/rounding artefact and recorded as a known data limitation. P5 will re-confirm from the time-series at no extra cost.

**Q3 — Can you export the per-minute time-series (screenshot 3) to CSV?**
This is the highest-value item on the list. It is the difference between a real dynamic model and dynamics bolted on for appearance, and it is also the only thing that can break the collinearity in §2.6 — a warm-up transient contains far more information about `UA` than twelve near-identical steady rows.

**Q4 — Is ambient temperature recorded?**
The model hardcodes 25 °C everywhere, and heat loss is proportional to `(T_mean − T_amb)`. An unrecorded ambient drifting between batches is a strong candidate for the batch-level residual pattern in §2.5.

**Q5 — Is inlet RH = 5 % measured, or a typed default?**
It is identical on all 12 rows. If it is a default, the psychrometric inlet state is uncertain and no downstream modelling repairs that. Screenshot 3 has a "Dehumidification Temperature" column, which suggests the inlet air is conditioned — in which case inlet RH may be knowable far more precisely than 5 %.

**Q6 — Pan dimensions and free volume?**
Needed to confirm the time-scale separation in §2.9 (currently assumed) and to compute bed surface area for the heat- and mass-transfer terms. The `configs/equipment.yaml` entries top out at a 60-inch/750 L pan, which is too small for a ~380 kg load at 2800 CFM — so none of the stored equipment records match your actual coater.

**Q8 — Is there a *measured* exhaust RH anywhere? (new, from §0.3)**
The `Exhaust RH` column in the plant table is EE model output, not a measurement — verified to 0.0005 across all 12 rows. So exhaust humidity currently has **no ground truth at all**, and acceptance target A5 cannot be evaluated. If the coater logs a real exhaust hygrometer reading, it would add a second independent thermodynamic target and would substantially strengthen the whole validation — exhaust RH constrains the *mass* balance, whereas exhaust temperature constrains the *energy* balance. One measurement, twice the leverage.

**Q7 — Is there any measured bed temperature, LOD/moisture, or coating-CV data?**
Each unlocks a Stage 3 output that is otherwise permanently unvalidated. Even one batch would change what can be claimed.

---

*End of plan. §11 is the execution order; §16 Q0 is the only thing blocking the start.*
