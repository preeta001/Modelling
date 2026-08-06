# Acceptance test set — provenance and known limitations

> ## ⚠ THIS IS A TEST SET, NOT A TRAINING SET
>
> Per **PLAN DEC-4**, the model is built from first principles
> (`modelling.pdf` Track A + the corrected thermodynamic core) and only *then*
> tested against this data. **Do not build the model from these files.**
>
> **Batch 4 is SEALED** — run against it exactly once, at the very end.
> Consulting it during iteration voids the held-out claim (PLAN §0.4).
>
> | Batch | Role |
> |---|---|
> | 1 | calibration (only if `UA` cannot be derived from equipment properties) |
> | 2, 3 | development acceptance — consult freely, log every iteration |
> | 4 | **SEALED** — one run, at the end |

**Status: Gate 0 OPEN.** Every row carries `confirmed_against_excel = FALSE`.
Nothing in this directory may be used to support a validation claim until that
flag is `TRUE`. Set it only after checking each cell against the source Excel.

Verify with:

```bash
python scripts/step0_verify_data.py
```

Current result: **67 checks, 0 failures, 17 observations.**

---

## Files

| File | Content | Source |
|---|---|---|
| `stages_v1.csv` | 12 batch-stages (4 batches × 3 pump speeds) | `Reference/{5819572C-…}.png` |
| `gun_calibration_v1.csv` | 6-gun spray measurements at 5 and 10 rpm, 4 batches | `Reference/{98A64565-…}.png` |
| `COLUMN_PROVENANCE.csv` | per-column provenance and target eligibility | derived |
| `timeseries/` | **MISSING** — per-minute plant data | `Reference/{4F6B0C6A-…}.png` |

## Column provenance — read this before using any column

Per **DEC-5**, the source table mixes measurements with the old model's output.
`COLUMN_PROVENANCE.csv` labels every column; the verifier fails if any column is
unlabelled.

| Provenance | Columns | Valid target? |
|---|---|---|
| **MEASURED** | `T_inlet_C`, `air_cfm`, **`T_exhaust_meas_C`** | `T_exhaust_meas_C` — **the thermodynamic ground truth** |
| **LAB_RESULT** | `weight_gain_pct`, `assay_pct` | yes |
| **PROCESS_RECORD** | pump rpm, spray rate, times, masses, cycle time | inputs; `cycle_time_h` is a target |
| **MEASURED_UNVERIFIED** | `RH_inlet_fraction` | input, but see L6 |
| **EE_OUTPUT** | `alpha_ee_output`, `alpha_avg_ee_output`, `ee_factor_ee_output`, **`RH_exhaust_ee_output`** | **NEVER** |

### The `Exhaust RH` trap

The source table's `Exhaust RH` column looks exactly like a measurement — it sits
between `Error (%)` and `Time (min)` and carries plausible values (0.101–0.112).
It is **EE model output**. Running the legacy model at each row's displayed alpha
reproduces it to within **0.0005 across all twelve rows**, i.e. pure display
rounding to 3 dp.

It is stored here as `RH_exhaust_ee_output` so the name itself prevents the
mistake. **Validating our exhaust RH against it would be scoring our model
against the old model, and it would look like a pass.**

Consequence: **exhaust humidity has no ground truth at all.** Acceptance target
A5 cannot be evaluated until a real hygrometer reading is supplied — see PLAN
§16 Q8. This matters more than it may appear: exhaust RH constrains the *mass*
balance, whereas exhaust temperature constrains the *energy* balance. One
measurement would roughly double the validation leverage of this dataset.

`timeseries/` is empty. It is required for Stage 3 (dynamic model) and is the
highest-value outstanding item — see PLAN §16 Q3.

## Transcription

Transcribed from screenshots by Claude on 2026-08-06. **Not yet checked against
the source Excel.** Screenshot transcription can misread digits; one wrong digit
invalidates every number downstream. Batch IDs for batches 2–4 are recorded as
`UNKNOWN_B2/3/4` — only batch 1 (`E2600199`) is named in the source material.

## Units

| Column | Unit | Note |
|---|---|---|
| `spray_rate_g_min_gun` | g/min per gun | 6 guns |
| `spray_rate_total_g_min_reported` | g/min | as displayed; see rounding note below |
| `T_inlet_C`, `T_exhaust_meas_C` | °C | |
| `air_cfm` | CFM | convert to kg dry air/s before any psychrometry |
| `RH_inlet_fraction` | fraction | source column reads `5`, i.e. 5 % → 0.05 |
| `atomisation_bar` | bar | |
| `pan_rpm` | rpm | pan, not pump |
| `alpha_shown`, `alpha_avg_batch` | — | legacy EE heat-loss parameter, per-row fitted |
| `solution_sprayed_kg`, `total_sprayed_kg` | kg | solution, not solids |
| `solution_mass_nominal_kg` | kg | **nominal recipe value — see L1** |

## Display rounding

The table shows rounded values, and re-deriving a column from displayed inputs
magnifies that rounding. Example: batch 3, pump 9 — the true per-gun rate is
41.0570, so the plant's total is 41.0570 × 6 = 246.342 → shown as 246.3. Using
the displayed 41.06 instead gives 246.36, an apparent 0.06 discrepancy that is
purely an artefact. `step0_verify_data.py` derives its tolerances from the
half-ulp of each displayed digit rather than guessing them.

---

## Known limitations

### L1 — `solution_mass_nominal_kg` is a recipe value, not an actual

Total sprayed vs the recorded solution mass:

| Batch | Total sprayed | Nominal solution | Difference |
|---|---|---|---|
| 1 | 81.30 kg | 77.215 kg | **+5.29 %** |
| 2 | 75.39 kg | 77.210 kg | −2.36 % |
| 3 | 81.70 kg | 77.210 kg | **+5.82 %** |
| 4 | 72.06 kg | 77.210 kg | −6.67 % |

Batches 1 and 3 sprayed more solution than the batch nominally contained.
**Do not use this column as the mass basis for weight gain.**

### L2 — Batch core load is unknown, so weight gain cannot be calibrated

Back-calculating core mass from weight gain at η_dep = 1 gives 343.1 / 354.5 /
389.6 / 405.8 kg — a **16.8 % spread**. If the load is genuinely identical
across batches, then η_dep varies by that much, or the weight-gain assay is that
noisy, or the sprayed totals are wrong. CQA-1 is blocked until the true core
load is supplied (PLAN §16 Q1).

### L3 — The dataset is nearly one-dimensional

| Input | Span | Consequence |
|---|---|---|
| `T_inlet_C` | 0.115 °C (0.20 %) | effectively constant |
| `air_cfm` | 0.19 % | effectively constant |
| `RH_inlet_fraction` | **0** | constant |
| `atomisation_bar` | **0** | **no atomisation parameter is fittable** |
| `pan_rpm` | {1, 2}, confounded with pump stage | **no RPM effect is separable from spray rate** |
| `spray_rate_g_min_gun` | 23.4 % | the only independent variation |

Heat-loss coefficient, evaporation efficiency and an inlet-temperature bias are
collinear over this range. Any model with two or more free thermal parameters is
unidentifiable here.

### L4 — Three exhaust readings are identical

`T_exhaust = 49.000 °C` appears in batches 1, 2 and 3, all at pump 8. Per
**DEC-1** (confirmed by the process owner) exhaust temperature is **not**
setpoint-controlled, so these are recorded as a transcription/rounding artefact.
Consequence: the third decimal is not a real measurement in at least those rows,
which is a further reason to fix factory-facing display precision to the
instrument's actual resolution (PLAN §14). This will be re-checked against the
time-series in P5 at no extra cost.

### L5 — Pump calibration has zero degrees of freedom

`m` and `c` are fitted from two setpoints (5 and 10 rpm), so the fit is exact
interpolation and linearity is untested. The intercept (2.83–3.68 g/min at
0 rpm) is non-physical — a stopped pump delivers nothing. **Extrapolation below
5 rpm or above 10 rpm must be refused, not silently returned.** Within the
operating range of 7–9 rpm this is interpolation and is sound: the calibration
reproduces all 12 plant spray rates to within 0.0044 g/min.

### L6 — Ambient temperature and inlet RH are unverified

The model hardcodes `T_amb = 25 °C`, and heat loss scales with
`(T_mean − T_amb)`. Inlet RH is 5 % on every row, which may be a typed default
rather than a measurement. Both are open questions (PLAN §16 Q4, Q5).

---

## Useful measured quantity: gun-to-gun CV

| Batch | CV @ 5 rpm | CV @ 10 rpm |
|---|---|---|
| 1 | 2.77 % | 1.60 % |
| 2 | 2.33 % | 1.81 % |
| 3 | 2.04 % | 1.59 % |
| 4 | 3.63 % | 1.52 % |

This is **measured** spray-uniformity data, and it is the empirical input to the
Stage 3 uniformity model (PLAN §9.6) — in place of the invented droplet-size
correlations currently in `coating_model/spray.py`.
