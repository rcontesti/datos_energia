from __future__ import annotations

import pandas as pd
import streamlit as st

from src.area_production_summary import SUMMARY_COLUMNS, build_area_production_summary


def render_area_summary(df: pd.DataFrame) -> None:
    st.header("Permit area production summary")
    st.caption(
        "Production for the latest month available in the dataset, "
        "sorted by total production in barrels of oil equivalent (BOE)."
    )

    try:
        as_of, summary = build_area_production_summary(df)
    except ValueError as error:
        st.error(f"Unable to build the permit-area production summary: {error}")
        return

    st.subheader(as_of.strftime("%B %Y"))
    st.dataframe(
        summary,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Permit area": st.column_config.TextColumn("Permit area"),
            **{
                column: st.column_config.NumberColumn(
                    column,
                    format="%.0f",
                )
                for column in SUMMARY_COLUMNS[1:]
            },
        },
    )
    st.caption(
        "Oil is reported in m³ and gas in thousand m³. BOE is calculated as "
        "oil m³ × 6.28981077 barrels/m³ + gas thousand m³ × "
        "35.3146667 Mcf/(thousand m³) ÷ 6 Mcf/BOE. "
        "Only conventional and non-conventional production is included; "
        "SIN RESERVORIO is excluded. Areas without records for the displayed "
        "month show unavailable values rather than prior-month production."
    )
