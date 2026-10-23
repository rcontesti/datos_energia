from __future__ import annotations

import pandas as pd

from src.production_units import (
    MCF_PER_BOE,
    OIL_CUBIC_METRES_TO_BARRELS,
    THOUSAND_CUBIC_METRES_TO_MCF,
    calculate_boe,
)


AREA_COLUMN = "areapermisoconcesion"
TYPE_COLUMN = "tipo_de_recurso"
OIL_COLUMN = "prod_pet"
GAS_COLUMN = "prod_gas"

CONVENTIONAL = "CONVENCIONAL"
NON_CONVENTIONAL = "NO CONVENCIONAL"

SUMMARY_COLUMNS = [
    "Permit area",
    "Conventional Oil Production (m³)",
    "Conventional Gas Production (thousand m³)",
    "Non Conventional Oil Production (m³)",
    "Non Conventional Gas Production (thousand m³)",
    "Total Oil Production (m³)",
    "Total Gas Production (thousand m³)",
    "Total Production (BOE)",
]

REQUIRED_COLUMNS = {
    AREA_COLUMN,
    TYPE_COLUMN,
    "anio",
    "mes",
    OIL_COLUMN,
    GAS_COLUMN,
}


def build_area_production_summary(
    df: pd.DataFrame,
) -> tuple[pd.Timestamp, pd.DataFrame]:
    """Summarize conventional and non-conventional area production for latest month."""
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Dataset is missing required columns: {sorted(missing)}")

    area_names = df[AREA_COLUMN].astype("string").str.strip()
    valid_area = area_names.notna() & area_names.ne("")
    if not valid_area.any():
        raise ValueError("Dataset contains no permit-area values.")

    data = df.loc[valid_area].copy()
    data[AREA_COLUMN] = area_names.loc[valid_area]
    data["date"] = pd.to_datetime(
        {
            "year": pd.to_numeric(data["anio"], errors="raise"),
            "month": pd.to_numeric(data["mes"], errors="raise"),
            "day": 1,
        },
        errors="raise",
    )
    data[TYPE_COLUMN] = (
        data[TYPE_COLUMN].astype("string").str.strip().str.upper()
    )
    for column in (OIL_COLUMN, GAS_COLUMN):
        data[column] = pd.to_numeric(data[column], errors="coerce")

    as_of = data["date"].max()
    latest = data.loc[data["date"].eq(as_of)]
    area_names = sorted(data[AREA_COLUMN].unique().tolist(), key=str.casefold)
    areas_with_latest_data = set(latest[AREA_COLUMN].unique())

    grouped = (
        latest.loc[latest[TYPE_COLUMN].isin([CONVENTIONAL, NON_CONVENTIONAL])]
        .groupby([AREA_COLUMN, TYPE_COLUMN])[[OIL_COLUMN, GAS_COLUMN]]
        .agg(lambda values: values.sum(min_count=1))
    )

    records: list[dict[str, object]] = []
    for area_name in area_names:
        if area_name not in areas_with_latest_data:
            conventional_oil = float("nan")
            conventional_gas = float("nan")
            non_conventional_oil = float("nan")
            non_conventional_gas = float("nan")
        else:
            conventional = (
                grouped.loc[(area_name, CONVENTIONAL)]
                if (area_name, CONVENTIONAL) in grouped.index
                else None
            )
            non_conventional = (
                grouped.loc[(area_name, NON_CONVENTIONAL)]
                if (area_name, NON_CONVENTIONAL) in grouped.index
                else None
            )
            conventional_oil = (
                float(conventional[OIL_COLUMN])
                if conventional is not None
                else 0.0
            )
            conventional_gas = (
                float(conventional[GAS_COLUMN])
                if conventional is not None
                else 0.0
            )
            non_conventional_oil = (
                float(non_conventional[OIL_COLUMN])
                if non_conventional is not None
                else 0.0
            )
            non_conventional_gas = (
                float(non_conventional[GAS_COLUMN])
                if non_conventional is not None
                else 0.0
            )

        category_values = (
            conventional_oil,
            conventional_gas,
            non_conventional_oil,
            non_conventional_gas,
        )
        if all(pd.notna(value) for value in category_values):
            total_oil = conventional_oil + non_conventional_oil
            total_gas = conventional_gas + non_conventional_gas
            boe = calculate_boe(
                pd.Series([total_oil]),
                pd.Series([total_gas]),
            ).iloc[0]
        else:
            total_oil = float("nan")
            total_gas = float("nan")
            boe = float("nan")

        records.append(
            {
                SUMMARY_COLUMNS[0]: area_name,
                SUMMARY_COLUMNS[1]: conventional_oil,
                SUMMARY_COLUMNS[2]: conventional_gas,
                SUMMARY_COLUMNS[3]: non_conventional_oil,
                SUMMARY_COLUMNS[4]: non_conventional_gas,
                SUMMARY_COLUMNS[5]: total_oil,
                SUMMARY_COLUMNS[6]: total_gas,
                SUMMARY_COLUMNS[7]: boe,
            }
        )

    summary = pd.DataFrame.from_records(records, columns=SUMMARY_COLUMNS)
    summary = summary.sort_values(
        SUMMARY_COLUMNS[-1],
        ascending=False,
        na_position="last",
        ignore_index=True,
    )
    return as_of, summary
