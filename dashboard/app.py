from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "processed" / "cgc_production_2026.parquet"

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


def month_label(month: int) -> str:
    return f"2026-{int(month):02d}"


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


st.title("CGC Oil & Gas Production")
st.caption(
    "2026 well-level production • Original source units • "
    "Direct CGC operations plus YPF-operated wells in Aguada del Chañar"
)
