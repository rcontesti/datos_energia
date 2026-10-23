from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import plotly.express as px
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.well_analysis import render_well_analysis
from dashboard.area_summary import render_area_summary
from src.production_units import calculate_boe


DATA_PATH = ROOT / "data" / "processed" / "cgc_production_2025_2026.parquet"

PRODUCTION_COLUMNS = {
    "prod_pet": "Oil production (m³)",
    "prod_gas": "Gas production (thousand m³)",
}
ORIGIN_LABELS = {
    "CGC_DIRECTO": "Direct CGC",
    "YPF_AGUADA_DEL_CHAÑAR": "YPF — Aguada del Chañar",
}


st.set_page_config(
    page_title="CGC Oil & Gas Production",
    page_icon="🛢️",
    layout="wide",
)


@st.cache_data(show_spinner="Loading production data…")
def load_data(path: str, modified_time: float) -> pd.DataFrame:
    """Cache the Parquet dataset; modified_time invalidates the cache after updates."""
    df = pd.read_parquet(path)

    required = {
        "anio",
        "mes",
        "idpozo",
        "empresa",
        "areapermisoconcesion",
        "prod_pet",
        "prod_gas",
        "tipo_de_recurso",
        "grupo",
        "origen_grupo",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Dataset is missing required columns: {sorted(missing)}")

    df["anio"] = pd.to_numeric(df["anio"], errors="raise").astype(int)
    df["mes"] = pd.to_numeric(df["mes"], errors="raise").astype(int)

    for col in ("prod_pet", "prod_gas"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def format_number(value: float, decimals: int = 0) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{value:,.{decimals}f}"


def month_over_month(
    monthly: pd.DataFrame,
    latest_month: int,
    column: str,
) -> str:
    """Compare with the immediately preceding calendar month, if available."""
    previous_month = latest_month - 1
    current = monthly.loc[monthly["mes"].eq(latest_month), column]
    previous = monthly.loc[monthly["mes"].eq(previous_month), column]

    if current.empty or previous.empty:
        return "N/A"
    current_value = current.iloc[0]
    previous_value = previous.iloc[0]

    if pd.isna(current_value) or pd.isna(previous_value) or previous_value == 0:
        return "N/A"

    change = (current_value / previous_value - 1) * 100
    return f"{change:+.1f}%"


def production_variation(
    resource_data: pd.DataFrame,
    production: str,
    months_back: int,
    fallback_to_earliest: bool = False,
) -> tuple[str, str, str]:
    latest = resource_data.iloc[-1]
    target_date = latest["date"] - pd.DateOffset(months=months_back)
    reference = resource_data.loc[resource_data["date"].eq(target_date)]
    used_fallback = False

    if reference.empty and fallback_to_earliest:
        reference = resource_data.iloc[[0]]
        used_fallback = True

    if reference.empty:
        label = "vs last month" if months_back == 1 else "vs 12 months ago"
        return label, "N/A", f"No data available for {target_date:%b %Y}."

    reference_row = reference.iloc[0]
    reference_date = reference_row["date"]
    reference_value = reference_row[production]
    latest_value = latest[production]

    if (
        pd.isna(latest_value)
        or pd.isna(reference_value)
        or reference_value == 0
    ):
        variation = "N/A"
    else:
        variation = f"{(latest_value / reference_value - 1) * 100:+.1f}%"

    if used_fallback:
        label = "vs earliest available"
        help_text = (
            f"No data for {target_date:%b %Y}; compared with "
            f"{reference_date:%b %Y}, the earliest available month."
        )
    else:
        label = "vs last month" if months_back == 1 else "vs 12 months ago"
        help_text = f"Compared with {reference_date:%b %Y}."

    return label, variation, help_text


def quarterly_variation(
    quarterly_data: pd.DataFrame,
    production: str,
    quarters_back: int,
) -> tuple[str, str, str]:
    latest = quarterly_data.iloc[-1]
    target_date = latest["quarter_start"] - pd.DateOffset(
        months=quarters_back * 3
    )
    reference = quarterly_data.loc[
        quarterly_data["quarter_start"].eq(target_date)
    ]
    label = "vs previous quarter" if quarters_back == 1 else "vs same quarter last year"

    if reference.empty:
        target_quarter = (target_date.month - 1) // 3 + 1
        return (
            label,
            "N/A",
            f"No data available for {target_date.year} Q{target_quarter}.",
        )

    reference_row = reference.iloc[0]
    reference_value = reference_row[production]
    latest_value = latest[production]
    if (
        pd.isna(latest_value)
        or pd.isna(reference_value)
        or reference_value == 0
    ):
        variation = "N/A"
    else:
        variation = f"{(latest_value / reference_value - 1) * 100:+.1f}%"

    return (
        label,
        variation,
        f"Latest quarter compared with {reference_row['period']}.",
    )


st.title("CGC Oil & Gas Production")
st.caption(
    "2025–2026 well-level production • Original source units • "
    "Direct CGC operations plus YPF-operated wells in Aguada del Chañar"
)

df = load_data(str(DATA_PATH), DATA_PATH.stat().st_mtime)

dashboard_view = st.segmented_control(
    "Dashboard section",
    ["Production overview", "Well analysis", "Area summary"],
    default="Production overview",
    label_visibility="collapsed",
)
if dashboard_view is None:
    st.stop()
if dashboard_view == "Well analysis":
    render_well_analysis(df)
    st.stop()
if dashboard_view == "Area summary":
    render_area_summary(df)
    st.stop()

st.subheader("Monthly production by resource type")
st.caption(
    "Monthly totals by year and resource type • "
    "Oil in m³ • Gas in thousand m³"
)

resource_monthly = (
    df.groupby(
        ["anio", "mes", "tipo_de_recurso"],
        dropna=False,
    )[list(PRODUCTION_COLUMNS)]
    .sum(min_count=1)
    .unstack("tipo_de_recurso")
    .sort_index()
)
resource_types = sorted(df["tipo_de_recurso"].dropna().unique())
resource_monthly = resource_monthly.reindex(
    columns=pd.MultiIndex.from_tuples(
        [
            (production, resource_type)
            for resource_type in resource_types
            for production in PRODUCTION_COLUMNS
        ]
    )
)
resource_monthly.columns = pd.MultiIndex.from_tuples(
    [
        (resource_type, PRODUCTION_COLUMNS[production])
        for production, resource_type in resource_monthly.columns
    ]
)
resource_monthly = resource_monthly.round(2).reset_index()
resource_monthly.columns = pd.MultiIndex.from_tuples(
    [
        ("Period", "Year"),
        ("Period", "Month"),
        *resource_monthly.columns[2:],
    ]
)

st.dataframe(
    resource_monthly,
    hide_index=True,
)

st.subheader("Monthly production trends by resource type")
st.caption(
    "Each chart shows one resource type and production series. "
    "Oil is in m³; gas is in thousand m³. Percentage changes use each "
    "series' latest month as the starting point."
)

production_timeseries = (
    df.groupby(
        ["anio", "mes", "tipo_de_recurso"],
        dropna=False,
    )[list(PRODUCTION_COLUMNS)]
    .sum(min_count=1)
    .reset_index()
    .sort_values(["anio", "mes"])
)
production_timeseries["date"] = pd.to_datetime(
    {
        "year": production_timeseries["anio"],
        "month": production_timeseries["mes"],
        "day": 1,
    }
)

chart_columns = st.columns(2)
for index, resource_type in enumerate(resource_types):
    resource_data = production_timeseries.loc[
        production_timeseries["tipo_de_recurso"].eq(resource_type)
    ]
    for production, label in PRODUCTION_COLUMNS.items():
        fig = px.line(
            resource_data,
            x="date",
            y=production,
            markers=True,
            title=f"{resource_type} — {label}",
            labels={"date": "Date", production: label},
        )
        fig.update_layout(height=320, margin={"t": 55, "b": 20})
        with chart_columns[index % len(chart_columns)]:
            metric_columns = st.columns(2)
            for metric_column, months_back, fallback in (
                (metric_columns[0], 1, False),
                (metric_columns[1], 12, True),
            ):
                metric_label, variation, help_text = production_variation(
                    resource_data,
                    production,
                    months_back,
                    fallback_to_earliest=fallback,
                )
                metric_column.metric(
                    metric_label,
                    variation,
                    help=help_text,
                )
            st.plotly_chart(fig)

st.subheader("Monthly combined production")
st.caption(
    "Oil and gas converted to thousands of barrels of oil equivalent (MBOE). "
    "Oil uses 6.28981077 barrels per m³; gas uses 35.3146667 Mcf per thousand "
    "m³ and 6 Mcf per BOE."
)

monthly_combined = (
    df.groupby(["anio", "mes"])[list(PRODUCTION_COLUMNS)]
    .sum(min_count=1)
    .reset_index()
    .sort_values(["anio", "mes"])
)
monthly_combined["MBOE"] = calculate_boe(
    monthly_combined["prod_pet"],
    monthly_combined["prod_gas"],
) / 1000
monthly_combined["date"] = pd.to_datetime(
    {
        "year": monthly_combined["anio"],
        "month": monthly_combined["mes"],
        "day": 1,
    }
)
monthly_mboe_chart = px.line(
    monthly_combined,
    x="date",
    y="MBOE",
    markers=True,
    labels={"date": "Date", "MBOE": "Production (MBOE)"},
)
monthly_mboe_chart.update_layout(height=360, margin={"t": 30, "b": 20})
monthly_metric_columns = st.columns(2)
for metric_column, months_back, fallback in (
    (monthly_metric_columns[0], 1, False),
    (monthly_metric_columns[1], 12, True),
):
    metric_label, variation, help_text = production_variation(
        monthly_combined,
        "MBOE",
        months_back,
        fallback_to_earliest=fallback,
    )
    metric_column.metric(metric_label, variation, help=help_text)
st.plotly_chart(monthly_mboe_chart)

st.subheader("Quarterly production by resource type")
st.caption(
    "Quarterly totals sum the monthly volumes in each calendar quarter. "
    "Variations compare the latest available quarter with the previous quarter "
    "and the same quarter one year earlier."
)

quarterly_production = df.copy()
quarterly_production["quarter"] = (quarterly_production["mes"] - 1) // 3 + 1
quarterly_production = (
    quarterly_production.groupby(
        ["anio", "quarter", "tipo_de_recurso"],
        dropna=False,
    )[list(PRODUCTION_COLUMNS)]
    .sum(min_count=1)
    .reset_index()
    .sort_values(["anio", "quarter"])
)
quarterly_production["quarter_start"] = pd.to_datetime(
    {
        "year": quarterly_production["anio"],
        "month": (quarterly_production["quarter"] - 1) * 3 + 1,
        "day": 1,
    }
)
quarterly_production["period"] = (
    quarterly_production["anio"].astype(str)
    + " Q"
    + quarterly_production["quarter"].astype(str)
)

quarterly_chart_columns = st.columns(2)
for index, resource_type in enumerate(resource_types):
    resource_quarters = quarterly_production.loc[
        quarterly_production["tipo_de_recurso"].eq(resource_type)
    ].sort_values("quarter_start")
    for production, label in PRODUCTION_COLUMNS.items():
        fig = px.bar(
            resource_quarters,
            x="period",
            y=production,
            title=f"{resource_type} — {label}",
            labels={"period": "Quarter", production: label},
            category_orders={"period": resource_quarters["period"].tolist()},
        )
        fig.update_layout(height=320, margin={"t": 55, "b": 20})
        with quarterly_chart_columns[index % len(quarterly_chart_columns)]:
            metric_columns = st.columns(2)
            for metric_column, quarters_back in (
                (metric_columns[0], 1),
                (metric_columns[1], 4),
            ):
                metric_label, variation, help_text = quarterly_variation(
                    resource_quarters,
                    production,
                    quarters_back,
                )
                metric_column.metric(
                    metric_label,
                    variation,
                    help=help_text,
                )
            st.plotly_chart(fig)

st.subheader("Quarterly combined production")
st.caption("Quarterly oil and gas totals converted to thousands of BOE (MBOE).")

quarterly_combined = df.copy()
quarterly_combined["quarter"] = (quarterly_combined["mes"] - 1) // 3 + 1
quarterly_combined = (
    quarterly_combined.groupby(["anio", "quarter"])[list(PRODUCTION_COLUMNS)]
    .sum(min_count=1)
    .reset_index()
    .sort_values(["anio", "quarter"])
)
quarterly_combined["MBOE"] = calculate_boe(
    quarterly_combined["prod_pet"],
    quarterly_combined["prod_gas"],
) / 1000
quarterly_combined["quarter_start"] = pd.to_datetime(
    {
        "year": quarterly_combined["anio"],
        "month": (quarterly_combined["quarter"] - 1) * 3 + 1,
        "day": 1,
    }
)
quarterly_combined["period"] = (
    quarterly_combined["anio"].astype(str)
    + " Q"
    + quarterly_combined["quarter"].astype(str)
)
quarterly_mboe_chart = px.bar(
    quarterly_combined,
    x="period",
    y="MBOE",
    labels={"period": "Quarter", "MBOE": "Production (MBOE)"},
    category_orders={"period": quarterly_combined["period"].tolist()},
)
quarterly_mboe_chart.update_layout(height=360, margin={"t": 30, "b": 20})
quarterly_metric_columns = st.columns(2)
for metric_column, quarters_back in (
    (quarterly_metric_columns[0], 1),
    (quarterly_metric_columns[1], 4),
):
    metric_label, variation, help_text = quarterly_variation(
        quarterly_combined,
        "MBOE",
        quarters_back,
    )
    metric_column.metric(metric_label, variation, help=help_text)
st.plotly_chart(quarterly_mboe_chart)
