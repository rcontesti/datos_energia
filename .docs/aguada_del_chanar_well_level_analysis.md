# Aguada del Chañar — Well-Level Production Forensic Analysis

## Purpose

This document defines an exploratory-analysis workflow for determining **why Aguada del Chañar production changes over time**, with particular attention to the apparent decline during the last months of 2026.

The analysis should distinguish between:

1. normal decline of existing wells;
2. absence or postponement of new wells;
3. wells being shut in or partially curtailed;
4. reactivation of previously inactive wells;
5. changes in conventional vs. non-conventional production;
6. changes in gas vs. oil behavior;
7. unusual well or pad performance;
8. changes in the productivity of newer well vintages;
9. Aguada behaving differently from comparable YPF-operated Vaca Muerta assets.

The objective is **diagnosis, not causal attribution**. The production data can identify fingerprints consistent with particular explanations, but external evidence is required before concluding that YPF or CGC intentionally postponed development.

---

# 1. Expected input data

The analysis assumes a monthly well-level dataset covering:

- all of 2025;
- January–September 2026;
- Aguada del Chañar;
- ideally comparable nearby YPF-operated areas.

Minimum useful fields:

```text
well_id
month
field / area
oil
gas
development_type       # conventional / non_conventional
```

Highly desirable additional fields:

```text
pad
operator
well_name
production_days
status
formation
subformation / target
completion_date
first_production_date
latitude
longitude
```

Do not invent missing fields. If a field is unavailable, omit the corresponding analysis and document the limitation.

---

# 2. Data validation

Before doing any analysis:

```python
df["month"] = pd.to_datetime(df["month"])

df = df.sort_values(["field", "well_id", "month"])

assert df["well_id"].notna().all()
assert df["month"].notna().all()

# Check duplicate well-month observations
dupes = (
    df.groupby(["field", "well_id", "month"])
      .size()
      .reset_index(name="n")
)

assert dupes["n"].max() == 1
```

Check:

- duplicate well-month records;
- negative production;
- missing months;
- wells appearing/disappearing unexpectedly;
- unit consistency;
- oil and gas zeros versus missing values.

A zero and a missing value must **not automatically be treated as equivalent**.

---

# 3. Restrict the main analysis to Aguada

```python
aguada = df[
    df["field"].eq("Aguada del Chañar")
].copy()
```

Keep the complete dataset available because later comparisons should use other YPF/Vaca Muerta areas as controls.

---

# 4. Level 1 — Establish what is declining

Create monthly field totals:

```python
monthly = (
    aguada
    .groupby("month")
    .agg(
        oil=("oil", "sum"),
        gas=("gas", "sum"),
        wells=("well_id", "nunique")
    )
    .reset_index()
)
```

Also calculate conventional/non-conventional totals:

```python
monthly_type = (
    aguada
    .groupby(["month", "development_type"])
    .agg(
        oil=("oil", "sum"),
        gas=("gas", "sum"),
        wells=("well_id", "nunique")
    )
    .reset_index()
)
```

### Dashboard charts

Create:

1. **Total oil production — monthly line**
2. **Total gas production — monthly line**
3. **Oil by conventional/non-conventional — stacked area or stacked bars**
4. **Gas by conventional/non-conventional — stacked area or stacked bars**

The dashboard should make it immediately obvious whether the decline is concentrated in unconventional production.

---

# 5. Level 2 — Number of producing wells

Define producing wells explicitly.

For example:

```python
oil_wells = (
    aguada.assign(producing_oil=aguada["oil"] > 0)
         .groupby("month")["producing_oil"]
         .sum()
)

gas_wells = (
    aguada.assign(producing_gas=aguada["gas"] > 0)
         .groupby("month")["producing_gas"]
         .sum()
)
```

Prefer a production-status definition based on official status or production days if those fields exist.

### Key diagnostic

Compare:

```text
field production
vs.
number of producing wells
```

Interpretation:

### Production down + wells stable

Likely:

- natural decline;
- lower productivity;
- reservoir/completion performance;
- reduced operating time.

### Production down + wells down

Investigate:

- shut-ins;
- workovers;
- infrastructure;
- operational restrictions.

### Production down + no new wells

Strong evidence consistent with a development pause or sequencing effect.

---

# 6. Identify new wells

For each well, calculate first production.

```python
first_oil = (
    aguada.loc[aguada["oil"] > 0]
          .groupby("well_id")["month"]
          .min()
          .rename("first_oil_month")
)

aguada = aguada.merge(
    first_oil,
    on="well_id",
    how="left"
)
```

Then:

```python
new_wells = (
    aguada[
        aguada["month"] == aguada["first_oil_month"]
    ]
    .groupby("month")["well_id"]
    .nunique()
)
```

Do the equivalent for gas if appropriate.

### Dashboard

Show:

- **New wells per month**
- **Cumulative producing wells**
- **New-well production contribution**

This is one of the most important dashboard sections.

---

# 7. Existing-well versus new-well production

Separate monthly production into:

```text
new wells
existing wells
reactivated wells
```

A simple first implementation:

```python
aguada["well_age_months"] = (
    aguada["month"].dt.to_period("M")
    - aguada["first_oil_month"].dt.to_period("M")
).apply(lambda x: x.n)
```

Then:

```python
aguada["new_well"] = aguada["well_age_months"].eq(0)
```

Aggregate:

```python
age_groups = (
    aguada
    .groupby(["month", "new_well"])
    .agg(
        oil=("oil", "sum"),
        gas=("gas", "sum")
    )
    .reset_index()
)
```

A more complete classification should identify:

- new well;
- continuing existing well;
- reactivated well;
- shut-in well.

---

# 8. Same-well analysis

This is critical.

Do not infer well decline simply from total field production.

Identify wells that existed throughout a comparison period.

For January–September 2026:

```python
months_2026 = aguada[
    aguada["month"].between(
        "2026-01-01",
        "2026-09-01"
    )
]

stable_wells = (
    months_2026
    .groupby("well_id")["month"]
    .nunique()
)

stable_wells = stable_wells[
    stable_wells == 9
].index
```

Then calculate production from only these wells:

```python
stable = months_2026[
    months_2026["well_id"].isin(stable_wells)
]

same_well = (
    stable
    .groupby("month")
    .agg(
        oil=("oil", "sum"),
        gas=("gas", "sum")
    )
    .reset_index()
)
```

### Interpretation

If:

```text
total production       ↓↓↓
same-well production   ↓ only moderately
```

then missing production is likely related to the lack of new wells.

If:

```text
total production       ↓↓↓
same-well production   ↓↓↓
```

then existing-well performance is the main issue.

---

# 9. Identify wells going offline

Look for positive production followed by zero.

```python
aguada = aguada.sort_values(["well_id", "month"])

aguada["previous_oil"] = (
    aguada.groupby("well_id")["oil"].shift(1)
)

shutdowns = aguada[
    (aguada["previous_oil"] > 0) &
    (aguada["oil"] == 0)
]
```

Aggregate:

```python
shutdown_count = (
    shutdowns
    .groupby("month")["well_id"]
    .nunique()
)
```

Also calculate the production lost from those wells in the previous month.

Do not assume that zero means a permanent shutdown.

A well may be:

- temporarily offline;
- under workover;
- awaiting equipment;
- affected by facility constraints;
- reporting differently.

---

# 10. Identify reactivations

The opposite event is also useful.

```python
aguada["previous_oil"] = (
    aguada.groupby("well_id")["oil"].shift(1)
)

reactivations = aguada[
    (aguada["previous_oil"] == 0) &
    (aguada["oil"] > 0)
]
```

Plot reactivations alongside shutdowns.

---

# 11. Detect unusually large monthly declines

Calculate well-level month-over-month changes:

```python
aguada["oil_mom_change"] = (
    aguada.groupby("well_id")["oil"]
          .pct_change()
)
```

Flag large movements:

```python
large_declines = aguada[
    aguada["oil_mom_change"] <= -0.30
]
```

Use thresholds only as diagnostic flags, not as evidence of causation.

Recommended dashboard table:

| Month | Well | Previous oil | Current oil | MoM change |
|---|---|---:|---:|---:|
| ... | ... | ... | ... | ... |

Sort by largest declines.

---

# 12. Well decline distribution

For each well, calculate a simple three-month and six-month decline where sufficient history exists.

```python
aguada["oil_3m_change"] = (
    aguada["oil"] /
    aguada.groupby("well_id")["oil"].shift(3)
    - 1
)

aguada["oil_6m_change"] = (
    aguada["oil"] /
    aguada.groupby("well_id")["oil"].shift(6)
    - 1
)
```

Visualize the distribution of well declines.

Recommended visualization:

- histogram of 3-month declines;
- histogram of 6-month declines;
- optionally boxplots by well vintage.

The objective is to determine whether September represents:

> normal decline across many wells

or

> an unusual cluster of negative well-level events.

---

# 13. Vintage analysis

Define the well vintage as the first-production month.

```python
aguada["vintage"] = aguada["first_oil_month"]
```

Calculate production per well by age:

```python
vintage_curve = (
    aguada
    .groupby(["vintage", "well_age_months"])
    .agg(
        oil=("oil", "sum"),
        wells=("well_id", "nunique")
    )
    .reset_index()
)

vintage_curve["oil_per_well"] = (
    vintage_curve["oil"] /
    vintage_curve["wells"]
)
```

Normalize each vintage:

```python
vintage_curve["production_index"] = (
    vintage_curve["oil_per_well"] /
    vintage_curve.groupby("vintage")["oil_per_well"]
                 .transform("first")
)
```

### Dashboard

Create a **vintage decline curve**:

- x-axis: months since first production;
- y-axis: indexed production;
- one line per vintage or selected vintage cohorts.

This is particularly useful for determining whether 2026 wells are performing differently from 2025 wells.

---

# 14. Pad-level analysis

If pad information exists:

```python
pad_monthly = (
    aguada
    .groupby(["pad", "month"])
    .agg(
        oil=("oil", "sum"),
        gas=("gas", "sum"),
        wells=("well_id", "nunique")
    )
    .reset_index()
)
```

Calculate each pad's contribution to the field.

Dashboard:

1. production by pad;
2. wells by pad;
3. monthly pad growth/decline;
4. heatmap of pad production.

A sudden field decline caused by one or two pads should become immediately visible.

---

# 15. Oil/gas relationship

Calculate gas-to-oil ratio if units permit:

```python
monthly["gor"] = (
    monthly["gas"] /
    monthly["oil"]
)
```

Do not calculate this if the units are incompatible.

Track:

- oil;
- gas;
- GOR.

A divergence between oil and gas can provide clues about changes in well behavior or operating conditions.

---

# 16. Production decomposition

This should become the central analytical output.

For each month:

```text
Change in field production
=
existing-well decline
+ new-well production
+ reactivated-well production
- shutdown losses
+ residual / unexplained
```

Conceptual implementation:

```python
for month in months[1:]:

    previous_month = ...
    current_month = ...

    continuing_wells = intersection(
        wells_previous,
        wells_current
    )

    new_wells = wells_current - wells_previous
    reactivated_wells = ...
    shutdown_wells = ...

    existing_change = (
        production_current[continuing_wells]
        - production_previous[continuing_wells]
    ).sum()

    new_production = (
        production_current[new_wells]
    ).sum()

    reactivated_production = ...

    shutdown_loss = (
        production_previous[shutdown_wells]
    ).sum()

    total_change = (
        existing_change
        + new_production
        + reactivated_production
        - shutdown_loss
    )
```

Create a waterfall-style diagnostic table:

```text
June → July

Existing-well decline       -450
New wells                     +0
Reactivations                 +0
Shutdowns                    -100
Residual                      +50
--------------------------------
Net change                   -500
```

The exact decomposition must be carefully defined so components do not overlap.

---

# 17. Counterfactual decline analysis

Estimate what production would have been if existing wells had simply followed their historical decline.

Conceptually:

```python
expected_production = model_existing_well_decline(
    historical_well_production
)

actual_production = ...

gap = expected_production - actual_production
```

Start with simple empirical decline rather than an elaborate Arps model.

For example:

```python
expected = previous_month_production * historical_decline_factor
```

Later, if justified, introduce:

- exponential decline;
- hyperbolic decline;
- Arps parameters;
- vintage-specific decline curves.

The purpose is not to produce a reserve estimate. It is to identify whether recent production is materially outside the historical trajectory.

---

# 18. Compare Aguada with control areas

This is essential.

Run the same analysis for comparable YPF-operated areas, for example:

```python
comparison_fields = [
    "Aguada del Chañar",
    "La Amarga Chica",
    "Bandurria Sur",
    "Loma Campana",
    "La Angostura Sur I"
]
```

Compare:

- production growth;
- producing wells;
- new wells/month;
- production per well;
- well decline;
- vintage performance;
- conventional/non-conventional mix.

The important question is:

> Is Aguada's behavior abnormal relative to other YPF Vaca Muerta assets?

Aguada should not be analyzed in isolation.

---

# 19. Recommended dashboard structure

Build the dashboard in five sections.

## Section A — Field overview

Top KPI cards:

```text
September oil
September gas
Producing wells
New wells
MoM oil change
YoY oil change
```

Charts:

1. Oil production
2. Gas production
3. Producing wells

---

## Section B — Development activity

Charts:

1. New wells/month
2. Cumulative producing wells
3. New-well production
4. Existing-well production
5. Conventional vs non-conventional production

This section answers:

> Is the field being developed?

---

## Section C — Well performance

Charts:

1. Same-well production
2. Average production per producing well
3. Distribution of 3-month declines
4. Distribution of 6-month declines
5. Shutdowns/reactivations

Add a table of the largest individual well declines.

---

## Section D — Vintage and pad analysis

Charts:

1. Vintage decline curves
2. Production by pad
3. Pad-level monthly changes
4. New wells by vintage

This section answers:

> Are new wells worse, or are old wells simply aging?

---

## Section E — Forensic decomposition

This is the most important section.

Show:

```text
Field production change
        │
        ├── Existing-well decline
        ├── New wells
        ├── Reactivations
        ├── Shutdowns
        └── Residual
```

Charts:

1. Monthly production-change decomposition
2. Cumulative contribution of each component
3. Counterfactual vs actual production

Then provide a small automatically generated diagnostic summary:

```text
Current signal

• Existing wells: normal / elevated decline
• New wells: increasing / flat / absent
• Shutdowns: normal / elevated
• 2026 vintages: above / similar / below prior vintages
• Aguada relative to peers: stronger / similar / weaker
```

These labels should be calculated from documented thresholds, not subjective interpretation.

---

# 20. Dashboard filters

Provide:

- field;
- date range;
- oil/gas;
- conventional/non-conventional;
- well;
- pad;
- vintage.

For Aguada, default to:

```text
2025-01 → latest available month
Oil
All development types
All wells
```

---

# 21. Data architecture

Do not perform all calculations inside the dashboard code.

Recommended structure:

```text
datos_energia/
│
├── data/
│   ├── raw/
│   └── processed/
│       └── cgc_production_2026.parquet
│
├── src/
│   ├── load_data.py
│   ├── validate.py
│   ├── well_analysis.py
│   ├── decline_analysis.py
│   ├── vintage_analysis.py
│   └── field_comparison.py
│
├── reports/
│   └── aguada_analysis.md
│
└── dashboard/
    └── app.py
```

The analytical layer should produce reusable tables/dataframes.

For example:

```python
aguada_monthly
aguada_well_month
aguada_new_wells
aguada_shutdowns
aguada_reactivations
aguada_vintages
aguada_pads
aguada_decomposition
peer_comparison
```

The dashboard should consume these outputs rather than independently recreating the calculations.

---

# 22. Important methodological safeguards

### Do not confuse zero with missing

```python
oil == 0
```

does not necessarily mean:

```text
well shut down
```

unless the source data definition supports that interpretation.

### Do not use monthly totals to infer well decline

Always perform the same-well analysis.

### Do not treat new wells as immediately comparable

A new well has a partial first month. Use:

- production days if available;
- normalized first-month production;
- or exclude incomplete months from certain comparisons.

### Do not overfit

Start with descriptive statistics and simple decline measures.

### Do not infer intent

Production data can show:

> "No new wells were added."

They cannot by themselves show:

> "YPF deliberately postponed drilling."

That requires contractual, operational, or corporate evidence.

---

# 23. Minimum viable implementation

If implementation time is limited, build these first:

### Must have

1. monthly oil/gas;
2. producing wells;
3. new wells;
4. existing-well production;
5. same-well decline;
6. shutdown/reactivation detection;
7. conventional/non-conventional split;
8. vintage curves;
9. comparison with peer YPF fields;
10. production-change decomposition.

### Later

11. pad analysis;
12. counterfactual decline;
13. production-days normalization;
14. formation/landing-zone analysis;
15. spatial visualization;
16. statistical change-point detection.

---

# 24. What the analysis should ultimately answer

The final dashboard should make it possible to classify the recent decline into one of four evidence patterns:

### Pattern A — Normal decline

```text
Existing wells ↓ normally
New wells       present
Shutdowns       normal
Vintages        normal
```

Interpretation: probably ordinary field decline.

### Pattern B — Development pause

```text
Existing wells ↓ normally
New wells       ↓ / zero
Shutdowns       normal
Vintages        unavailable or unchanged
```

Interpretation: consistent with delayed development.

### Pattern C — Operational disruption

```text
Existing wells ↓ sharply
Shutdowns       ↑
Several wells/pads affected simultaneously
```

Interpretation: investigate operational/infrastructure causes.

### Pattern D — New-well performance problem

```text
Existing wells  normal
New wells       present
New-vintage productivity ↓
```

Interpretation: investigate reservoir interval, completion design, landing zone or geological performance.

The purpose of the dashboard is to determine **which of these fingerprints is actually present in the data**, before attributing it to YPF/CGC strategy or contractual decisions.
