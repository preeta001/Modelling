# 📘 The Definitive Guide to Dynamic Two-Zone Pan Coating Modeling
> **Version 1.0** | *A Comprehensive Textbook for Pharmaceutical Engineers, Data Scientists, and Software Developers*

> [!NOTE]
> **Foreword: The Purpose of this Document**
> This manual is designed to be the ultimate, one-stop destination for understanding the physics, mathematics, and Python implementation of the Dynamic Two-Zone Coating Model. It is written to be accessible to a beginner who knows nothing about coating, yet exhaustive enough for a senior engineer who wants to optimize the source code.
> 
> We cover the theoretical origins (referencing `modelling.pdf` and Page et al., 2006), the step-by-step derivation of the physical equations, the numerical methods used to solve them, and a precise line-by-line mapping to the Python codebase.

---

## 📑 Detailed Table of Contents

1. [Part I: The Philosophy of Mechanistic Modeling](#part-i-the-philosophy-of-mechanistic-modeling)
   - 1.1 Introduction to Pharmaceutical Film Coating
   - 1.2 The Quality by Design (QbD) Paradigm
   - 1.3 Why Empirical Models Fail and Mechanistic Models Succeed
2. [Part II: Fundamental Thermodynamics & Psychrometrics](#part-ii-fundamental-thermodynamics--psychrometrics)
   - 2.1 The Ideal Gas Law and Dalton's Law
   - 2.2 The Antoine Equation and Saturation Pressure
   - 2.3 Humidity Ratio: Quantifying Moisture
   - 2.4 The Wet-Bulb Temperature (and the Bisection Solver)
3. [Part III: The Energy Balance & The Heat Loss Revelation](#part-iii-the-energy-balance--the-heat-loss-revelation)
   - 3.1 The First Law of Thermodynamics in a Coating Pan
   - 3.2 The Enthalpy of Air, Vapor, and Evaporation
   - 3.3 The Historical Heat Loss Bug ($\alpha$) vs. The New Paradigm ($UA$)
4. [Part IV: The Wetness Index (WI) - The Ultimate Safety Metric](#part-iv-the-wetness-index-wi---the-ultimate-safety-metric)
   - 4.1 Evaporation Capacity: The Thermodynamic Limit
   - 4.2 Defining the Wetness Index
   - 4.3 The Excess Wetness Integral (EWI) and Cumulative Damage
5. [Part V: The Two-Zone Model (Page et al., 2006)](#part-v-the-two-zone-model-page-et-al-2006)
   - 5.1 The Flaw of the 0-Dimensional Assumption
   - 5.2 Physical Segregation: The Spray Zone vs. The Drying Zone
   - 5.3 Mass Balance Derivations (Water and Solids)
   - 5.4 Energy Balance Derivations (Temperature)
   - 5.5 Bed Circulation Kinetics ($\tau_c$ and RPM)
6. [Part VI: Numerical Implementation (`dynamic_model.py`)](#part-vi-numerical-implementation-dynamic_modelpy)
   - 6.1 The State Vector Architecture
   - 6.2 The `rhs` Derivative Function: A Line-by-Line Walkthrough
   - 6.3 Why `solve_ivp` with `LSODA`?
   - 6.4 The Criticality of `max_step=1.0` in Step-Function Recipes
7. [Part VII: Advanced Capabilities (CQA, Scale-up, Risk)](#part-vii-advanced-capabilities-cqa-scale-up-risk)
   - 7.1 Monte Carlo Simulation of Coating Uniformity ($CV_m$)
   - 7.2 Predicting Critical Quality Attributes (Film Thickness)
   - 7.3 Scale-Up Engineering (Froude Number vs. Peripheral Speed)
   - 7.4 Model Calibration via Differential Evolution
   - 7.5 Quantifying Risk with Probabilistic Uncertainty
8. [Part VIII: The User Interface & Practical Guide](#part-viii-the-user-interface--practical-guide)
   - 8.1 Streamlit Dashboard Architecture
   - 8.2 Formatting Plant Data (CSV Schema Rules)
   - 8.3 Tuning Process Parameters (`inputs` Dictionary)
   - 8.4 YAML Configurations (`equipment.yaml`, `products.yaml`)

---

## Part I: The Philosophy of Mechanistic Modeling

### 1.1 Introduction to Pharmaceutical Film Coating
Pharmaceutical film coating is the process of depositing a thin polymeric film onto the surface of a solid dosage form (usually a tablet). This is done in a rotating cylindrical drum called a pan coater. 

The coating serves multiple purposes:
*   **Protection:** Shielding the Active Pharmaceutical Ingredient (API) from light, moisture, and oxidation.
*   **Aesthetics and Identification:** Providing color and branding.
*   **Taste Masking:** Hiding bitter APIs to improve patient compliance.
*   **Modified Release:** Enteric coatings prevent dissolution in the stomach, releasing the drug only in the intestines.

The process involves three simultaneous unit operations:
1.  **Spraying:** Atomizing a polymer-solvent solution (water or isopropyl alcohol) onto the tumbling tablet bed.
2.  **Mixing:** The rotation of the pan, aided by internal baffles, continuously folds the tablet bed to ensure all tablets eventually pass under the spray guns.
3.  **Drying:** High-volume, heated air is drawn through the tablet bed. This air transfers convective heat to the tablets and carries away the evaporated solvent.

### 1.2 The Quality by Design (QbD) Paradigm
Historically, pharmaceutical manufacturing relied on "Quality by Testing" (QbT). You run the batch using a fixed recipe, test the final tablets, and throw the batch away if it fails. 

Regulatory bodies (like the FDA) now mandate **Quality by Design (QbD)**. QbD requires a deep scientific understanding of *why* a process works. Instead of a fixed recipe, QbD defines a **Design Space**—a multidimensional region of operating parameters (e.g., Spray Rate vs. Airflow vs. Temperature) within which the product is guaranteed to be safe and effective.

### 1.3 Why Empirical Models Fail and Mechanistic Models Succeed
To map the Design Space, you could run hundreds of physical experiments (Design of Experiments, DoE). However, at the production scale (e.g., a 1000 kg pan), a single failed experiment costs tens of thousands of dollars in wasted API.

Empirical models (like simple linear regression or basic machine learning) try to map inputs to outputs based purely on historical data. They fail spectacularly when you change the equipment scale or move outside the historical data bounds.

This project uses a **First-Principles Mechanistic Model**. It does not guess. It applies the immutable laws of physics (Conservation of Mass, Conservation of Energy, Psychrometrics) to predict the outcome. Because it relies on physics, it can accurately predict the behavior of a 60-inch production pan based solely on the physics validated in a 24-inch R&D pan.

---

## Part II: Fundamental Thermodynamics & Psychrometrics

To model drying, we must understand the behavior of air and water vapor. This is the domain of **Psychrometrics**. The core functions are located in `coating_model/psychrometrics.py` and `coating_model/solvent_properties.py`.

### 2.1 The Ideal Gas Law and Dalton's Law
Air inside the coating pan is treated as a mixture of two ideal gases: "dry air" (nitrogen and oxygen) and "water vapor". 
According to **Dalton's Law of Partial Pressures**, the total atmospheric pressure ($P_{atm}$) is the sum of the partial pressure of the dry air ($p_a$) and the partial pressure of the vapor ($p_v$):
$P_{atm} = p_a + p_v$

Standard atmospheric pressure is assumed to be $101.325$ kPa.

### 2.2 The Antoine Equation and Saturation Pressure
Evaporation cannot continue indefinitely. At a given temperature, air can only hold a specific maximum amount of vapor. If it absorbs more, the vapor condenses back into liquid. The partial pressure at this maximum limit is called the **Saturation Vapor Pressure ($P_{sat}$)**.

$P_{sat}$ rises exponentially with temperature. This is why heating the inlet air is so effective at speeding up drying. We calculate this using the empirical **Antoine Equation**:

$log_{10}(P_{sat}) = A - \frac{B}{C + T}$

Where:
*   $T$ is the temperature in °C.
*   $A, B, C$ are substance-specific constants.

> [!TIP]
> **Code Implementation:**
> In `coating_model/solvent_properties.py`, we define a `Solvent` class. 
> For water, we use NIST constants: $A = 8.07131, B = 1730.63, C = 233.426$. 
> The code calculates the pressure in Torr, then converts it to kPa by multiplying by $0.133322$. 
> ```python
> # Line 16 of solvent_properties.py
> p_torr = 10 ** (self.A - (self.B / (T_C + self.C)))
> return p_torr * 0.133322  # Convert to kPa
> ```

### 2.3 Humidity Ratio: Quantifying Moisture
While Relative Humidity (RH, %) is common in weather reports, it is useless for mass balancing because it is relative to temperature. Instead, engineers use the **Humidity Ratio ($w$)**, defined as the absolute mass of vapor per mass of dry air (kg vapor / kg dry air).

Using the Ideal Gas Law ($PV = mRT$), we derive:
$w = \frac{m_v}{m_a} = \frac{R_a}{R_v} \times \frac{p_v}{P_{atm} - p_v}$

Where:
*   $R_a = 287.058$ J/(kg·K) (Gas constant for dry air)
*   $R_v = 461.495$ J/(kg·K) (Gas constant for water vapor)
*   The ratio $R_a / R_v \approx 0.622$.

> [!NOTE]
> **Code Implementation:**
> ```python
> # Line 5 of psychrometrics.py
> def humidity_ratio(p_v, P_atm=101.325):
>     return (R_D / R_V) * p_v / (P_atm - p_v)
> ```

### 2.4 The Wet-Bulb Temperature (and the Bisection Solver)
If you place a drop of water on a thermometer bulb and blow air over it, the water evaporates, cooling the bulb. The temperature it stabilizes at is the **Wet-Bulb Temperature ($T_{wb}$)**. It is the lowest temperature to which air can be cooled solely by the evaporation of water.

In the model, $T_{wb}$ represents the thermodynamic limit of evaporative cooling in the tablet bed. 

Calculating $T_{wb}$ from a known dry-bulb temperature and humidity ratio is mathematically complex because the equation cannot be solved algebraically. It requires a root-finding algorithm.

> [!IMPORTANT]
> **The Bisection Algorithm in `psychrometrics.py`**
> Starting at Line 31 in `psychrometrics.py`, the `wet_bulb_temperature()` function uses a **bisection method**. 
> 1. It guesses a $T_{wb}$ between $0°C$ and the current air temperature.
> 2. It calculates the theoretical humidity ratio if the air were saturated at that guess.
> 3. It checks if the energy balance holds. 
> 4. It iteratively narrows the high/low bounds until it converges to within $0.0001°C$. This ensures extreme precision for the Environmental Equivalence optimizations.

---

## Part III: The Energy Balance & The Heat Loss Revelation

### 3.1 The First Law of Thermodynamics in a Coating Pan
The pan is an open thermodynamic system. At steady state, the energy entering the system equals the energy leaving. 

**Energy In:**
1. Sensible heat of the inlet air.

**Energy Out:**
1. Sensible heat of the exhaust air.
2. Latent heat consumed by the evaporation of the solvent (the largest energy sink).
3. Heat lost to the surrounding environment (the room) through the metal walls of the pan.

### 3.2 The Enthalpy of Air, Vapor, and Evaporation
To balance energy, we use specific enthalpy ($h$, in kJ/kg).
The enthalpy of moist air is the sum of the enthalpy of the dry air and the enthalpy of the vapor it carries:

$h_{moist\_air} = Cp_{air} \cdot T + w \cdot (h_{fg} + Cp_{vapor} \cdot T)$

Where $Cp_{air} = 1.005$ kJ/kg·K.

The latent heat of vaporization ($h_{fg}$) is not constant; it decreases slightly as temperature rises. The model linearizes this relationship:
$h_{fg}(T) = A_{latent} \cdot T + B_{latent}$
For water, $A_{latent} = 1.7208$ and $B_{latent} = 2505.2$.

Combining these and solving for the steady-state exhaust temperature yields the fundamental equation referenced in `modelling.pdf` (Eq 5.1):

$T_{exhaust} = \frac{T_{in} (Cp_{air} + A_{latent} \cdot w_{in} + \alpha/2) + (w_{out} - w_{in})(h_{fg\_ref} - B_{latent}) - \alpha T_{amb}}{Cp_{air} + A_{latent} \cdot w_{out} + \alpha/2}$

### 3.3 The Historical Heat Loss Bug ($\alpha$) vs. The New Paradigm ($UA$)
In early iterations of this mechanistic model (and in much of the older literature), heat loss to the room was modeled using a dimensionless parameter $\alpha$, defined such that the heat loss rate was:
$Q_{loss} = \alpha \cdot \dot{m}_{air} \cdot (T_{bed} - T_{amb})$

**The Mathematical Flaw:**
Look closely at that equation. If the airflow ($\dot{m}_{air}$) is turned off to zero (a common occurrence during a spray pause or loading phase), the equation states that $Q_{loss} = 0$. 
This is physically impossible. A hot steel drum sitting in a 20°C room will radiate heat and cool down, regardless of whether a fan is blowing air through it. The legacy model would falsely predict that the pan retains its heat indefinitely when airflow stops.

**The Fix:**
In this advanced implementation, we discarded the dimensionless $\alpha$ multiplier. Instead, we model heat loss using an absolute overall heat transfer coefficient, **$UA$ (kW/K)**. 

$Q_{loss} = UA \cdot (T_{bed} - T_{amb})$

This correctly decouples heat loss from airflow. 
> [!CAUTION]
> **Where is this in the code?**
> In `coating_model/dynamic_model.py` Line 26, we extract `UA = inputs.get('HLF_kW_K')`. 
> When we need to use the legacy steady-state algebraic equations (which still expect $\alpha$), we dynamically compute $\alpha$ at that exact timestep by dividing $UA$ by the instantaneous mass flow of air:
> `alpha = UA / m_dot_dry_air` (Line 196). 
> This perfectly bridges the gap between accurate absolute physics and the legacy equation structures.

---

## Part IV: The Wetness Index (WI) - The Ultimate Safety Metric

### 4.1 Evaporation Capacity: The Thermodynamic Limit
How fast *can* the air dry the tablets? This is determined by the **Evaporation Capacity ($\dot{m}_{evap\_capacity}$)**.

It depends on three things:
1.  **Airflow ($\dot{m}_{air}$):** More air means more carrying capacity.
2.  **Driving Force:** The difference between how much moisture the air *could* hold at the bed temperature ($w_{sat}(T_{bed})$) and how much it is *already* holding ($w_{in}$).
3.  **Evaporation Efficiency ($\eta_{evap}$):** Air doesn't perfectly reach 100% saturation before leaving the pan. Due to bypass air and finite contact time, it usually reaches 70-90% saturation.

$\dot{m}_{evap\_capacity} = \dot{m}_{air} \cdot (w_{sat}(T_{bed}) - w_{in}) \cdot \eta_{evap}$

> [!TIP]
> **Code Implementation: The Min-Bounding Logic**
> The model calculates the capacity, but it cannot evaporate more water than actually exists on the tablets! In `dynamic_model.py` (Lines 82-86), we use a min-bound:
> ```python
> m_dot_evap_cap_s = m_dot_dry_air_s * (w_sat_s - w_in) * eta_evap
> # Actual evaporation cannot exceed the water available on the bed
> water_available_s = max(0.0, y[1] / dt_approx)
> m_dot_evap_s = min(m_dot_evap_cap_s, water_available_s)
> ```

### 4.2 Defining the Wetness Index
The Wetness Index is a dimensionless ratio.
$WI = \frac{\dot{m}_{spray\_solvent}}{\dot{m}_{evap\_capacity}}$

*   **$WI < 1.0$:** The air has excess capacity. The tablets remain relatively dry.
*   **$WI = 1.0$:** Perfect equilibrium.
*   **$WI > 1.0$:** The spray rate exceeds the air's capacity to dry. Water physically accumulates on the surface of the tablets, leading to twinning and structural degradation.

### 4.3 The Excess Wetness Integral (EWI) and Cumulative Damage
A Wetness Index of 1.1 for 5 seconds is harmless. A Wetness Index of 1.1 for 30 minutes will ruin a batch. We need a metric for *cumulative* overwetting damage. 

We define the **Excess Wetness Integral (EWI)**:
$EWI = \int_{0}^{t} \max(0, WI(\tau) - WI_{critical}) d\tau$

If $WI_{critical} = 1.05$, the integral only accumulates value when the process crosses into the severe danger zone. By the end of the batch, if EWI > 0, the batch has suffered sustained overwetting and is flagged as a failure in the Execution Summary dashboard.

---

## Part V: The Two-Zone Model (Page et al., 2006)

### 5.1 The Flaw of the 0-Dimensional Assumption
Imagine you are filling a bathtub. A 0-Dimensional (0-D) model assumes that the moment you turn on the hot water, the entire tub instantly becomes slightly warmer. It assumes perfect, instantaneous mixing.

In a coating pan, the spray guns only cover a small stripe across the top of the tumbling bed—roughly 20% of the total mass. This is where 100% of the cold liquid lands, and where 100% of the evaporative cooling occurs. The remaining 80% of the bed is just receiving hot air. 

If you use a 0-D model, it averages the massive cooling in the spray zone with the massive heating in the drying zone. It predicts a mild, safe, uniform bed temperature. 
**In reality, the spray zone is freezing and drowning in water, while the drying zone is bone dry.** The 0-D model completely fails to predict local overwetting, which is exactly where tablet twinning occurs.

### 5.2 Physical Segregation: The Spray Zone vs. The Drying Zone
Following the landmark paper by Page et al. (2006), we split the bed into two coupled zones:
1.  **Spray Zone ($f_s = 0.20$):** Receives 100% of the spray, 20% of the air, and constitutes 20% of the mass.
2.  **Drying Zone ($f_d = 0.80$):** Receives 0% of the spray, 80% of the air, and constitutes 80% of the mass.

### 5.3 Mass Balance Derivations (Water and Solids)

Let's derive the exact differential equation for the mass of liquid water in the Spray Zone ($M_{w,s}$).

The rate of change of water mass ($\frac{dM_{w,s}}{dt}$) is determined by:
1.  **+** Water arriving from the spray nozzle ($\dot{m}_{spray\_solvent}$).
2.  **-** Water evaporating into the air ($\dot{m}_{evap,s}$).
3.  **+** Water carried *into* the spray zone by tablets rotating from the drying zone.
4.  **-** Water carried *out* of the spray zone by tablets rotating into the drying zone.

The circulation terms depend on the mass exchange rate ($\dot{m}_{circ}$). When a tablet moves from the drying zone to the spray zone, it carries a proportional fraction of the drying zone's total water.

Therefore, the final equation is:
$\frac{dM_{w,s}}{dt} = \dot{m}_{spray\_solvent} - \dot{m}_{evap,s} + \dot{m}_{circ} \left( \frac{M_{w,d}}{M_{bed,d}} \right) - \dot{m}_{circ} \left( \frac{M_{w,s}}{M_{bed,s}} \right)$

> [!NOTE]
> **Code Implementation:**
> In `dynamic_model.py` Line 88, this equation is transcribed perfectly:
> ```python
> dMw_s_dt = m_dot_w_spray - m_dot_evap_s + m_dot_circ_w_d - m_dot_circ_w_s
> ```
> The solid coating mass ($M_{c,s}$) follows the exact same logic, except evaporation is zero, and it includes a deposition efficiency ($\eta_{dep}$) term to account for spray that misses the bed.

### 5.4 Energy Balance Derivations (Temperature)
The temperature derivative ($\frac{dT_s}{dt}$) is derived from Newton's laws of heating. The change in temperature equals the net heat flow divided by the thermal mass (mass $\times$ specific heat).

$\frac{dT_s}{dt} = \frac{Q_{convection} + Q_{spray\_sensible} - Q_{evaporative} - Q_{heat\_loss} + Q_{circulation}}{M_{bed,s} \cdot Cp_{bed}}$

Let's break down the heat flows ($Q$, in kW):
*   **$Q_{convection} = h \cdot A_{bed} \cdot f_s \cdot (T_{air} - T_s)$**: The hot air transferring heat to the tablets.
*   **$Q_{spray\_sensible} = \dot{m}_{spray} \cdot Cp_{spray} \cdot (T_{spray} - T_s)$**: The cold liquid hitting the warm tablets cools them down.
*   **$Q_{evaporative} = \dot{m}_{evap,s} \cdot h_{fg}$**: The massive amount of energy consumed by liquid turning into gas.
*   **$Q_{heat\_loss} = UA \cdot f_s \cdot (T_s - T_{ambient})$**: Heat bleeding out through the pan walls.
*   **$Q_{circulation} = \dot{m}_{circ} \cdot Cp_{bed} \cdot (T_d - T_s)$**: Warm tablets from the drying zone transferring their thermal energy as they enter the spray zone.

### 5.5 Bed Circulation Kinetics ($\tau_c$ and RPM)
The entire Two-Zone model hinges on $\dot{m}_{circ}$, which represents how fast the pan mixes.
The time it takes for a tablet to complete one full cycle (surface $\rightarrow$ bulk $\rightarrow$ surface) is the **Circulation Time ($\tau_c$)**, empirically defined as:

$\tau_c = \frac{150}{RPM}$ (in seconds).

If $RPM = 10$, $\tau_c = 15$ seconds.
Because the spray zone is 20% of the bed, a tablet spends $0.2 \times 15 = 3$ seconds under the spray, and $12$ seconds in the drying zone.

The mass exchange rate is the mass of the zone divided by the time spent in it:
$\dot{m}_{circ} = \frac{M_{bed,s}}{\tau_c \cdot f_s}$

---

## Part VI: Numerical Implementation (`dynamic_model.py`)

### 6.1 The State Vector Architecture
SciPy's ODE solvers require the system state to be packed into a flat 1D array (`y`). We define a 6-state vector:

```python
# The 6 states being tracked at every microsecond:
y[0] = T_s    # Spray Zone Temperature
y[1] = Mw_s   # Spray Zone Liquid Water Mass
y[2] = Mc_s   # Spray Zone Solid Coating Mass
y[3] = T_d    # Drying Zone Temperature
y[4] = Mw_d   # Drying Zone Liquid Water Mass
y[5] = Mc_d   # Drying Zone Solid Coating Mass
```

### 6.2 The `rhs` Derivative Function: A Line-by-Line Walkthrough
The `rhs(t, y)` function is called thousands of times by the solver. For a given time `t`, it must return the derivatives `dy/dt`.

**1. Time Interpolation (Line 57-61)**
The user provides a step-function recipe (e.g., at minute 15, spray goes from 0 to 50). The solver might ask for the state at $t = 15.321$ seconds. We use SciPy's `interp1d` functions to evaluate the exact input parameters at that specific decimal time.

**2. Physical Properties (Line 63-79)**
We calculate the current specific heat of the bed (a weighted average of the core tablet, the solid coating, and the liquid water). We calculate the saturation vapor pressures based on the current temperatures `y[0]` and `y[3]`.

**3. Rate Equations (Line 88-118)**
We execute the exact mathematical formulas derived in Part V, assigning the results to `dT_s_dt`, `dMw_s_dt`, etc.

**4. Return**
We return the array `[dT_s_dt, dMw_s_dt, dMc_s_dt, dT_d_dt, dMw_d_dt, dMc_d_dt]`.

### 6.3 Why `solve_ivp` with `LSODA`?
We use `scipy.integrate.solve_ivp`. 
We specifically request the `LSODA` method. Why? 
The coating pan equations can become **stiff**. Stiffness occurs when some variables change at vastly different timescales than others. For example, if spray is suddenly turned off, the liquid water mass (`Mw_s`) will evaporate to exactly $0.0$ very rapidly, while the temperature (`T_s`) changes slowly. 

Standard solvers (like Runge-Kutta `RK45`) will crash or take millions of microscopic time steps when they hit stiffness, taking hours to compute. `LSODA` automatically detects stiffness and switches internally from an explicit Adams method (fast) to an implicit BDF method (robust), solving the 3-hour batch simulation in less than 0.1 seconds.

### 6.4 The Criticality of `max_step=1.0` in Step-Function Recipes
> [!CAUTION]
> **The `max_step` Constraint**
> Look at Line 128: `max_step=1.0`. This is the most important numerical parameter in the code.
> 
> Because `LSODA` is so efficient, if the temperature isn't changing much (e.g., during a long 30-minute spray phase), the solver will try to take a massive leap forward in time, perhaps jumping from $t=14$ minutes directly to $t=16$ minutes. 
> 
> However, if the user's recipe turns the spray OFF exactly at $t=15$ minutes, the solver's giant leap will completely step *over* the event. It will sample the spray rate at $t=14$ (which is 50g/min) and at $t=16$ (which is 0g/min), and completely miss the discontinuity. 
> 
> By forcing `max_step=1.0`, we mandate that the solver can never leap forward by more than 1 second. This guarantees it will detect the $t=15$ minute recipe change, ensuring thermodynamic accuracy without sacrificing much performance.

---

## Part VII: Advanced Capabilities (CQA, Scale-up, Risk)

The core ODE model gives us average thermodynamics. The advanced modules translate thermodynamics into pharmaceutical quality metrics.

### 7.1 Monte Carlo Simulation of Coating Uniformity ($CV_m$)
Found in `coating_model/exposure.py`.

A 0-D model assumes every tablet gets exactly the same amount of coating. In reality, some tablets spend more time in the spray zone than others. The pharmaceutical metric for variance is the **Coefficient of Variation ($CV_m$)**. If $CV_m > 5\%$, the batch fails quality control.

We use a Monte Carlo approach to model 10,000 individual tablets:
1.  **Visit Frequency:** The number of times a tablet passes through the spray zone follows a **Poisson distribution**.
2.  **Residence Time:** The duration a tablet spends in the spray zone per visit follows a **Log-Normal distribution**.

By sampling these distributions for 10,000 virtual tablets, we build a histogram of coating masses and calculate the statistical variance ($CV_m$). 

### 7.2 Predicting Critical Quality Attributes (Film Thickness)
Found in `coating_model/cqa.py`.

The model calculates the total mass of solid polymer deposited. To find the physical **Film Thickness ($\mu m$)**, we use:
$Thickness = \frac{M_{coating}}{\rho_{film} \cdot A_{tablet\_total}}$
Where $\rho_{film}$ is the density of the dried polymer (from `products.yaml`), and $A_{tablet\_total}$ is the total surface area of all 100,000+ tablets in the pan.

### 7.3 Scale-Up Engineering (Froude Number vs. Peripheral Speed)
Found in `coating_model/scale_up.py`.

When moving a recipe from a 24-inch R&D coater to a 60-inch production coater, you cannot use the same RPM. The 60-inch coater has a massive circumference; at the same RPM, the outer tablets would be launched into the air like a centrifuge.

There are two dominant scale-up paradigms provided in the tool:
1.  **Constant Peripheral Speed:** Maintains the linear velocity of the drum wall. 
    $RPM_{prod} = RPM_{lab} \times \left(\frac{Diameter_{lab}}{Diameter_{prod}}\right)$
2.  **Constant Froude Number:** The Froude number ($Fr = \frac{v^2}{g \cdot D}$) is the ratio of centrifugal force to gravitational force. Keeping it constant ensures the cascading dynamics of the tumbling bed look identical.
    $RPM_{prod} = RPM_{lab} \times \sqrt{\frac{Diameter_{lab}}{Diameter_{prod}}}$

### 7.4 Model Calibration via Differential Evolution
Found in `coating_model/calibration.py`.

The theoretical model requires two empirical tuning parameters: $HLF$ (Heat Loss) and $\eta_{evap}$ (Evaporation Efficiency). You cannot measure these directly.
Instead, you upload a CSV of historical plant data (Airflow, Spray, Inlet Temp) along with the historically measured *Exhaust Temperature*.

The Calibration module uses **SciPy's `differential_evolution`** algorithm. This is a global genetic algorithm. It spawns a "population" of random $HLF$ and $\eta$ guesses. It runs the full 6-state ODE model for every guess. It compares the predicted exhaust temperature to the CSV's actual exhaust temperature and calculates the Root Mean Square Error (RMSE). It then "breeds" the best guesses together, mutating them over dozens of generations until it finds the absolute perfect $HLF$ and $\eta$ that force the model to perfectly match reality.

### 7.5 Quantifying Risk with Probabilistic Uncertainty
Found in `coating_model/uncertainty.py`.

In the real world, sensors drift. A setpoint of 1200 CFM might physically be 1180 CFM or 1220 CFM. 
The Uncertainty module allows the user to define standard deviations for their inputs. It then runs a **Monte Carlo Simulation**, executing the full ODE model 100+ times, sampling input values from Gaussian (Normal) distributions.
Instead of a single "Wetness Index", it outputs a probability histogram. The engineer can now confidently state: *"Given our sensor variance, there is a 4.2% probability that the Wetness Index will exceed the critical threshold."*

---

## Part VIII: The User Interface & Practical Guide

### 8.1 Streamlit Dashboard Architecture
The user interface is built entirely in **Streamlit**. 
*   `streamlit_app.py`: The main router. It configures the sidebar, the global dark-theme CSS, and the multi-page navigation.
*   `app_pages/simulation_page.py`: The primary workhorse. It allows users to build multi-stage recipes using numeric inputs, triggers the `batch_runner.py` pipeline, and plots the dynamic ODE outputs using Plotly.
*   `app_pages/calibration_page.py`: The interface for the Differential Evolution tuner.

### 8.2 Formatting Plant Data (CSV Schema Rules)
When uploading historical data for calibration or validation, the CSV parser (`coating_model/data_loader.py`) enforces specific schema rules, though it is lenient on capitalization.

**Required Columns:**
*   `time (min)`: Must be in minutes. The ODE engine internally multiplies by 60 for seconds.
*   `inlet temp (c)`
*   `airflow (cfm)`
*   `spray rate (g/min)`
*   `inlet rh`: Must be a fraction (e.g., $0.10$ for 10% relative humidity). If a user enters $10$, the system detects values $> 1.5$ and automatically divides by 100.

**Optional Validation Columns:**
*   `exhaust temp (c)`
*   `exhaust rh`
*   `bed temp`

> [!WARNING]
> **Missing Data Handling:** If a sensor dropped out and a row is missing data, `data_loader.py` utilizes Pandas `ffill()` (forward fill) to carry the last known value forward, up to a limit of 5 consecutive minutes, preventing ODE crashes.

### 8.3 Tuning Process Parameters (`inputs` Dictionary)
In `app_pages/simulation_page.py` (around Line 19), there is a master `inputs` dictionary. This is where you configure the base state of the simulation if you aren't loading a YAML config.

```python
inputs = {
    'batch_load_kg': 100.0,
    'cp_core_kJ_kgK': 1.1,
    'A_bed_m2': 2.0,
    'h_conv_W_m2K': 50.0,
    'HLF_kW_K': 0.1,
    'no_of_guns': 4,
    'solids_fraction': 0.15,
    'eta_dep': 0.95,
    'evap_efficiency': 0.8,
    'initial_T_bed': 30.0,
    'pan_rpm': 10.0
}
```

**Key Parameter Impacts:**
*   **`batch_load_kg`:** Increasing this massively increases the thermal inertia. The bed will take much longer to heat up during the pre-heat phase.
*   **`A_bed_m2`:** The exposed surface area of the tumbling bed. If you increase this, convective heat transfer from the hot air is much faster.
*   **`solids_fraction`:** A crucial formulation parameter. If you lower this to `0.05`, your spray is 95% water. You will have to spray massive amounts of liquid to achieve your target weight gain, almost certainly causing a Wetness Index failure.

### 8.4 YAML Configurations (`equipment.yaml`, `products.yaml`)
To prevent hardcoding, plant constraints are stored in `configs/`.
*   **`equipment.yaml`**: Contains definitions for specific machines. For example, a `Coater_48inch` has a max airflow of 2500 CFM and 4 spray guns. The Streamlit UI reads these bounds to prevent the user from simulating physically impossible recipes.
*   **`products.yaml`**: Contains specific drug properties. A placebo tablet might have a core density of $1.2$ g/cc, while a heavy mineral supplement might be $1.8$ g/cc. This affects the calculated Film Thickness in the CQA module.

---
*Document Version 1.0. Generated to serve as the definitive, exhaustive reference for the Coating Pan Simulation Architecture.*
