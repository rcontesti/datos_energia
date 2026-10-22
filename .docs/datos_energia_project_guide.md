# datos_energia — Project Overview, Engineering Guide and Roadmap

**Status:** Engineering handover / living project guide  
**Current scope:** 2026 Argentina well-level oil and gas production  
**Primary tools:** Python, pandas, PyArrow/Parquet, Streamlit, Plotly

## 1. What we are building

`datos_energia` is a reproducible data pipeline and local dashboard for analyzing monthly oil and gas production at individual-well level using public data from Argentina's Ministry of Energy.

The initial production universe is **CGC**, defined as:

1. `COMPAÑÍA GENERAL DE COMBUSTIBLES S.A.`
2. `CGC ENERGIA SAU`
3. `YPF S.A.` wells in `AGUADA DEL CHAÑAR`

The pipeline downloads the public source CSV, validates it, applies configurable filters, adds classification fields, stores the filtered well-level data in Parquet, generates summary reports, and feeds a local Streamlit dashboard.

The current project is a **production-data foundation**, not yet a revenue, cash-flow, reserves, or valuation model.

## 2. Goals

### Current goals

- Obtain reliable well-level production data.
- Keep the filtering rules explicit and auditable.
- Preserve source units and source columns.
- Keep individual-well records available for drill-down.
- Produce a compact Parquet dataset.
- Generate independently checkable CSV reports.
- Record source and run metadata.
- Build a local dashboard for exploration.
- Make the workflow understandable and debuggable by another engineer.
- Validate the manual process before introducing automation.

### Current non-goals

- Do not commit the approximately 226 MB raw CSV.
- Do not silently convert production units.
- Do not silently broaden company or area filters.
- Do not discard well-level information in the primary dataset.
- Do not interpret missing production as zero without confirming source semantics.
- Do not mix economic assumptions into the ingestion layer.
- Do not introduce scheduled GitHub Actions until the local workflow is validated.

## 3. Data source

Current source:

`http://datos.energia.gob.ar/dataset/c846e79c-026c-4040-897f-1ad3543b407c/resource/fb7a47a0-cba9-4667-a004-6f6c1c346c23/download/produccin-de-pozos-de-gas-y-petrleo-2026.csv`

Upstream repository:

`https://github.com/datosenergia/produccion-de-petroleo-y-gas-por-pozo`

Observed source characteristics:

- Year: 2026
- Approximate file size: 226 MB
- Rows: 738,993
- Original columns: 38
- Available months in the first run: January–September
- CSV encoding: UTF-8 with BOM

The row count and latest month are observations, not permanent constants. The source may be revised.

## 4. Filtering rules

Filtering is configured in `config/companies.yaml`.

Current logic:

```text
Keep row if:
    empresa == "COMPAÑÍA GENERAL DE COMBUSTIBLES S.A."
OR  empresa == "CGC ENERGIA SAU"
OR  (empresa == "YPF S.A."
     AND areapermisoconcesion == "AGUADA DEL CHAÑAR")
```

Two derived columns are added:

- `grupo = "CGC"`
- `origen_grupo`
  - `CGC_DIRECTO`
  - `YPF_AGUADA_DEL_CHAÑAR`

The original `empresa` is retained.

### Important maintenance rule

Company and area matching is currently exact string matching. If the publisher changes spelling or formatting, do not silently normalize the data. Inspect the source values, decide whether the production-universe definition should change, update configuration/tests, and document the change.

## 5. Units and interpretation

Source units are preserved:

| Field | Meaning | Unit |
|---|---|---|
| `prod_pet` | Oil production | m³ |
| `prod_gas` | Gas production | thousand m³ |
| `prod_agua` | Water production | m³ |

Monthly totals are reported monthly volumes, **not daily production rates** and not seasonally adjusted.

The processed Parquet retains all original source columns, including fields such as `observaciones` and `sub_tipo_recurso`.

## 6. Architecture

```text
Ministry of Energy CSV
        |
        v
Temporary download
        |
        v
Read with pandas
        |
        v
Validate source
        |
        v
Apply CGC filters
        |
        v
Add grupo / origen_grupo
        |
        v
Validate filtered data
        |
        +-------------------------+
        |                         |
        v                         v
Well-level Parquet          CSV reports
        |                         |
        +------------+------------+
                     |
                     v
              Streamlit dashboard
```

The layers should remain separate:

- **Configuration:** source URL, year, company/area rules.
- **Ingestion:** download and read.
- **Validation:** schema and data-quality checks.
- **Transformation:** filtering and classification.
- **Storage:** Parquet.
- **Reporting:** aggregate CSVs.
- **Dashboard:** presentation and exploration.

The dashboard should not duplicate ingestion logic.

## 7. Repository structure

```text
datos_energia/
├── README.md
├── requirements.txt
├── .gitignore
├── config/
│   └── companies.yaml
├── src/
│   ├── __init__.py
│   └── update_data.py
├── data/
│   ├── metadata.json
│   └── processed/
│       └── cgc_production_2026.parquet
├── reports/
│   ├── monthly.csv
│   ├── annual.csv
│   ├── by_area.csv
│   └── by_well.csv
├── dashboard/
│   └── app.py
└── tests/
```

Raw downloads belong in temporary storage and should not be committed.

## 8. Current pipeline

Main command:

```bash
python -m src.update_data
```

The updater:

1. Loads `config/companies.yaml`.
2. Creates a temporary directory.
3. Streams the source CSV to disk.
4. Reads it with pandas.
5. Validates required columns, year, months, and numeric production fields.
6. Applies the CGC filter.
7. Adds `grupo` and `origen_grupo`.
8. Validates the filtered universe.
9. Writes the Parquet dataset.
10. Generates summary reports.
11. Writes metadata.
12. Removes the temporary source file.

### CSV loading

The first run produced a pandas `DtypeWarning` for mixed-type source columns. Use:

```python
source = pd.read_csv(
    source_path,
    encoding="utf-8-sig",
    low_memory=False,
    dtype={
        "observaciones": "string",
        "sub_tipo_recurso": "string",
    },
)
```

A LibreSSL warning was observed in the local Python environment, but the download succeeded. Do not disable TLS verification as a workaround.

## 9. Outputs

### Primary dataset

`data/processed/cgc_production_2026.parquet`

Contains the filtered well-level dataset and all source columns plus `grupo` and `origen_grupo`. This is the dashboard's primary data source.

### Metadata

`data/metadata.json` records source URL, repository, download timestamp, source year, row counts, companies, areas, months, latest month, output path, and filter rules.

Future metadata should consider adding a source checksum, code revision, package versions, and run identifier.

### Reports

- `reports/monthly.csv` — production by month.
- `reports/annual.csv` — production by year.
- `reports/by_area.csv` — production by area and month.
- `reports/by_well.csv` — well-level grouped production.

The reports are validation/convenience outputs. Parquet remains the detailed dataset.

## 10. Baseline validation results

First successful run on 2026-10-21:

| Check | Result |
|---|---:|
| Source rows | 738,993 |
| Filtered rows | 60,552 |
| Months | Jan–Sep 2026 |
| Output columns | 40 |
| Duplicate `anio`-`mes`-`idpozo` keys | 0 |
| Missing `prod_pet` | 0 |
| Missing `prod_gas` | 0 |

Filtered rows:

| Company | Origin | Rows |
|---|---|---:|
| CGC ENERGIA SAU | CGC_DIRECTO | 12,964 |
| COMPAÑÍA GENERAL DE COMBUSTIBLES S.A. | CGC_DIRECTO | 46,895 |
| YPF S.A. | YPF_AGUADA_DEL_CHAÑAR | 693 |
| **Total** | | **60,552** |

Observed monthly totals:

| Month | Oil m³ | Gas thousand m³ |
|---|---:|---:|
| Jan | 195,741.97 | 153,067.85 |
| Feb | 180,516.46 | 138,275.89 |
| Mar | 191,956.64 | 149,473.79 |
| Apr | 173,308.96 | 140,369.19 |
| May | 172,336.89 | 139,274.12 |
| Jun | 158,685.07 | 131,996.42 |
| Jul | 161,800.57 | 128,919.80 |
| Aug | 158,709.39 | 127,349.88 |
| Sep | 152,507.77 | 126,928.20 |

These are baseline checks, not permanent expected values. Upstream revisions may change them.

## 11. Dashboard specification

The local dashboard uses Streamlit and Plotly.

Run:

```bash
source .venv/bin/activate
streamlit run dashboard/app.py
```

### First version

The dashboard should contain:

1. **KPIs:** latest oil, latest gas, oil MoM change, gas MoM change, with explicit month and units.
2. **Monthly trends:** separate oil and gas charts in original units.
3. **Origin comparison:** `CGC_DIRECTO` versus `YPF_AGUADA_DEL_CHAÑAR`.
4. **Area analysis:** area ranking for the selected period, with oil/gas clearly separated.
5. **Well table:** month, company, area, origin filters and CSV export.

### Important dashboard rule

MoM means the immediately preceding calendar month, not simply the previous month selected by the user. If that month is unavailable, display `N/A`.

The dashboard must never silently reinterpret units or use different production-universe rules from the pipeline.

## 12. Debugging guide

### Download failure

Check the source URL, HTTP status, network connectivity, TLS/certificate errors, disk space, and whether the downloaded file is actually CSV. Do not disable TLS verification.

### CSV schema/read failure

Inspect:

```python
print(source.columns.tolist())
print(source.shape)
```

Compare required columns against the source. Do not weaken validation just to make a run succeed.

### Unexpectedly few filtered rows

Inspect distinct company and YPF area values:

```python
print(source["empresa"].value_counts(dropna=False).head(30))
print(
    source.loc[source["empresa"].eq("YPF S.A."),
               "areapermisoconcesion"]
    .value_counts(dropna=False)
)
```

### Classification error

Verify direct CGC companies become `CGC_DIRECTO`, YPF becomes `YPF_AGUADA_DEL_CHAÑAR` only for the configured area, unrelated YPF records are excluded, and the original `empresa` is unchanged.

### Report mismatch

Recompute directly from Parquet:

```python
df = pd.read_parquet("data/processed/cgc_production_2026.parquet")
check = (
    df.groupby(["anio", "mes"])[["prod_pet", "prod_gas"]]
      .sum(min_count=1)
      .reset_index()
)
print(check)
print(pd.read_csv("reports/monthly.csv"))
```

First determine whether the Parquet and report files came from different runs before changing code.

### Dashboard appears blank

Check that the Parquet exists and that the app is resolving the repository root correctly:

```python
from pathlib import Path
import pandas as pd

root = Path(__file__).resolve().parents[1]
path = root / "data" / "processed" / "cgc_production_2026.parquet"
print(path, path.exists())
df = pd.read_parquet(path)
print(df.shape)
print(df.columns.tolist())
```

Also inspect the Streamlit terminal for exceptions.

## 13. Testing strategy

Before automation, add pytest tests for:

- Configuration loading.
- Direct CGC filtering.
- YPF/Aguada filtering.
- Exclusion of unrelated companies.
- `grupo` and `origen_grupo` classification.
- Missing required columns.
- Empty source and empty filtered universe.
- Invalid months.
- Non-numeric production fields.
- Duplicate well-month keys.
- Report/Parquet reconciliation.
- Dashboard behavior when Parquet is missing.

Use small synthetic DataFrames for unit tests. Do not download the 226 MB source file for every test.

Add data-quality diagnostics for row counts, month coverage, latest month, duplicate keys, null counts, unusual production values, and report reconciliation.

## 14. Roadmap

### Phase 1 — Finish and verify the dashboard

- [ ] Launch `dashboard/app.py`.
- [ ] Reconcile dashboard totals to `reports/monthly.csv`.
- [ ] Verify company, area, origin, and month filters.
- [ ] Verify MoM calculations.
- [ ] Verify CSV download.
- [ ] Fix rendering/performance issues.

### Phase 2 — Formalize quality controls

- [ ] Add pytest tests.
- [ ] Add duplicate-key validation.
- [ ] Add report reconciliation.
- [ ] Add source checksum/code-version metadata.
- [ ] Make output replacement atomic so a failed update cannot leave inconsistent outputs.

### Phase 3 — Monthly automation

Only after local validation:

- [ ] Add GitHub Actions.
- [ ] Support manual and scheduled monthly triggers.
- [ ] Run tests in CI.
- [ ] Run the same updater used locally.
- [ ] Decide whether generated Parquet/reports belong in Git, workflow artifacts, or external storage.
- [ ] Make failures visible.

### Phase 4 — Better production analytics

Potential additions:

- Daily-rate normalization with explicit assumptions.
- Production by area/company/well.
- Well rankings.
- New/inactive/producing well classification where source data permits.
- Well-level time series.
- Production contribution analysis.
- Better treatment/display of `[Sin movimientos]`.
- Multi-year comparisons.

### Phase 5 — Multi-year history

- [ ] Configure annual source files.
- [ ] Build a consistent cross-year schema.
- [ ] Document schema changes.
- [ ] Add year selection and comparisons to the dashboard.
- [ ] Track source revisions.
- [ ] Revisit storage/versioning as data grows.

## 15. Longer-term economic analysis

The production dataset is intended to become an input to a separate analytical layer.

Potential future work:

- Oil and gas price assumptions.
- Revenue estimates.
- Transport and realization assumptions.
- Lifting/operating costs.
- Workovers and maintenance capex.
- Development capex.
- Production decline analysis.
- Well/area economic scenarios.
- Stress testing.
- Asset/company cash-flow estimates.
- Comparison with reported company financials.

This layer must remain separate from ingestion.

**Production volume is not cash flow.** Economic analysis must distinguish:

1. Reported source data.
2. External market/company data.
3. Analyst assumptions.
4. Derived estimates.

Every economic metric should have a documented definition, unit, source, and assumption set.

## 16. Engineering principles

1. Preserve provenance.
2. Fail loudly when the source schema or production universe is invalid.
3. Keep filtering rules in configuration.
4. Do not silently change scope.
5. Preserve well-level detail.
6. Preserve source units.
7. Label every chart and KPI with units and period.
8. Make transformations deterministic.
9. Keep facts separate from estimates.
10. Automate only after local validation.
11. Prefer small, testable functions over monolithic code.
12. Never fix an unexpected result by weakening validation without understanding the underlying data.

## 17. Handover checklist

An engineer taking over should:

1. Read this document and `README.md`.
2. Inspect `config/companies.yaml`.
3. Activate `.venv`.
4. Run `python -m src.update_data`.
5. Inspect `data/metadata.json`.
6. Inspect the Parquet shape and columns.
7. Reconcile `reports/monthly.csv`.
8. Check duplicate well-month keys.
9. Launch the Streamlit dashboard.
10. Test filters and CSV export.
11. Add automated tests.
12. Only then implement scheduled automation.

## 18. Open decisions

- Strategy for versioning generated Parquet as the dataset grows.
- Whether multiple years should be separate annual files or one dataset.
- How to detect and document upstream revisions.
- Exact semantics of well status/inactivity.
- Definition of daily-rate metrics, if added.
- External datasets for future economic analysis.
- Storage/versioning of economic assumptions.

## 19. Bottom line

The immediate objective is **not** to build a sophisticated oil-and-gas valuation system. It is to establish a trustworthy production-data foundation.

The intended sequence is:

```text
Reliable source
    ↓
Validated filter
    ↓
Well-level Parquet
    ↓
Reconciled reports
    ↓
Tested dashboard
    ↓
Automated monthly updates
    ↓
Multi-year history
    ↓
Production analytics
    ↓
Economic / cash-flow analysis
```

Every later analytical layer should be traceable back to the original source data and explicit assumptions.
