# CGC production dashboard

## Install dependencies

From the repository root:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Refresh the processed dataset

If the processed Parquet file does not exist yet, or you want to refresh it:

```bash
python -m src.update_data
```

The updater downloads the source CSV to a temporary directory, filters it, and
writes the processed Parquet file and reports.

## Run the dashboard

From the repository root:

```bash
streamlit run dashboard/app.py
```

Streamlit will print a local URL, usually `http://localhost:8501`.

The dashboard reads `data/processed/cgc_production_2025_2026.parquet`; it does not
download or modify source data itself. After running the data updater, refresh
the dashboard page to view the updated data.

## Dashboard contents

- Section tabs for the production overview, permit-area well analysis, and area
  production summary.
- Monthly oil and gas totals by year, month, and resource type for 2025 and 2026.
- Separate monthly oil and gas trend charts for each resource type across both years.
- Combined monthly oil and gas production in MBOE, with month-over-month and
  year-over-year variation.
- Percentage changes versus the previous month and versus 12 months earlier
  (using the earliest available month when that 12-month comparison is unavailable).
- Quarterly oil and gas bar charts by resource type, with quarter-over-quarter
  and year-over-year variation for the latest available quarter.
- Combined quarterly oil and gas production in MBOE, with quarter-over-quarter
  and year-over-year variation.
- Latest selected month's oil and gas production, plus month-over-month change.
- Production split by direct CGC operations and YPF-operated Aguada del Chañar wells.
- Area rankings for the selected period.
- Filterable well-level records and a CSV download containing all filtered columns.
- Permit-area well analysis, with Aguada del Chañar selected by default:
  production by conventional/non-conventional type,
  producing and first-producing wells, same-well trends, shut-in/reactivation
  signals, well decline distributions, vintage curves, and monthly change
  decomposition.
- Latest-month permit-area production table with conventional/non-conventional
  oil and gas, combined oil/gas totals, and BOE totals sorted descending.

The well analysis uses `idpozo` and the selected `areapermisoconcesion` value
from the processed dataset. It treats missing values and absent well-month rows
as unknown rather than zero, and flags the first month in the source period as a
baseline with unknown well vintage.
Pad, completion-date, production-days, and comparable-peer analyses are not
shown because those inputs are not present in this processed dataset. Other
permit areas can be analyzed individually from the selector, but cross-area
peer comparison is not currently calculated.

The area production summary uses the latest month present in the dataset. Areas
without records in that month display unavailable values rather than stale data.
BOE uses 6.28981077 barrels per m³ of oil and 35.3146667 Mcf per thousand m³ of
gas, divided by 6 Mcf per BOE. It includes conventional and non-conventional
production only; `SIN RESERVORIO` is excluded.

## Units and interpretation

- Oil (`prod_pet`): cubic metres (m³).
- Gas (`prod_gas`): thousands of cubic metres (thousand m³).
- Combined production is shown in MBOE (thousands of barrels of oil equivalent):
  oil is converted at 6.28981077 barrels per m³; gas is converted at 35.3146667
  Mcf per thousand m³ and 6 Mcf per BOE.
- Water (`prod_agua`): retained in the data but not plotted in this first version.
- Figures are source monthly totals, not daily rates or seasonally adjusted values.
