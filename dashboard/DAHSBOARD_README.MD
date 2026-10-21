
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

The dashboard reads `data/processed/cgc_production_2026.parquet`; it does not
download or modify source data itself. After running the data updater, refresh
the dashboard page to view the updated data.

## Dashboard contents

- Latest selected month's oil and gas production, plus month-over-month change.
- Monthly oil and gas trends in separate charts because they use different units.
- Production split by direct CGC operations and YPF-operated Aguada del Chañar wells.
- Area rankings for the selected period.
- Filterable well-level records and a CSV download containing all filtered columns.

## Units and interpretation

- Oil (`prod_pet`): cubic metres (m³).
- Gas (`prod_gas`): thousands of cubic metres (thousand m³).
- Water (`prod_agua`): retained in the data but not plotted in this first version.
- Figures are source monthly totals, not daily rates or seasonally adjusted values.
