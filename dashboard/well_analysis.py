from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.well_analysis import AREA_COLUMN, build_area_analysis


def _format_change(current: float, previous: float) -> str:
    if pd.isna(current) or pd.isna(previous) or previous == 0:
        return "N/A"
    return f"{(current / previous - 1) * 100:+.1f}%"


def render_well_analysis(df: pd.DataFrame) -> None:
    st.caption(
        "Monthly well-level production by permit area • Oil in m³ • "
        "Gas in thousand m³ • "
        "Descriptive signals, not causal conclusions"
    )

    areas = sorted(
        df[AREA_COLUMN].dropna().astype("string").str.strip().unique().tolist(),
        key=str.casefold,
    )
    default_area = next(
        (area for area in areas if area.casefold() == "aguada del chañar"),
        areas[0] if areas else None,
    )
    if not areas or default_area is None:
        st.error("The dataset has no permit-area values to analyze.")
        return
    selected_area = st.selectbox(
        "Permit area",
        areas,
        index=areas.index(default_area),
    )
    st.header(f"{selected_area} — Well analysis")

    try:
        analysis = build_area_analysis(df, selected_area)
    except ValueError as error:
        st.error(f"Unable to build the analysis for {selected_area}: {error}")
        return

    area_data = analysis["area_data"]
    data_start = analysis["monthly"]["date"].min()
    data_end = analysis["monthly"]["date"].max()

    filter_columns = st.columns([2, 2, 3])
    with filter_columns[0]:
        selected_period = st.date_input(
            "Production period",
            value=(data_start.date(), data_end.date()),
            min_value=data_start.date(),
            max_value=data_end.date(),
        )
    resource_types = sorted(area_data["tipo_de_recurso"].dropna().unique())
    type_options = ["All", *resource_types]
    with filter_columns[1]:
        selected_types = st.multiselect(
            "Development type",
            type_options,
            default=["All"],
        )
    with filter_columns[2]:
        selected_wells = st.multiselect(
            "Focus wells (optional)",
            sorted(area_data["idpozo"].unique().tolist()),
            help="Restricts the individual-well decline table only.",
        )

    if not selected_types:
        st.warning("Select at least one development type.")
        return
    if not isinstance(selected_period, tuple) or len(selected_period) != 2:
        st.info("Select both a start and end date to display the analysis.")
        return

    start_date = pd.Timestamp(selected_period[0]).to_period("M").to_timestamp()
    end_date = pd.Timestamp(selected_period[1]).to_period("M").to_timestamp()
    filtered_source = (
        area_data
        if "All" in selected_types
        else area_data.loc[area_data["tipo_de_recurso"].isin(selected_types)]
    )
    analysis = build_area_analysis(filtered_source, selected_area)
    monthly = analysis["monthly"].loc[
        analysis["monthly"]["date"].between(start_date, end_date)
    ].copy()
    if monthly.empty:
        st.warning("No monthly production is available for the selected period.")
        return

    latest = monthly.iloc[-1]
    previous = monthly.iloc[-2] if len(monthly) > 1 else None
    metrics = st.columns(5)
    metrics[0].metric("Latest oil", f"{latest['oil']:,.0f} m³")
    metrics[1].metric("Latest gas", f"{latest['gas']:,.0f} thousand m³")
    metrics[2].metric("Oil-producing wells", int(latest["oil_wells"]))
    metrics[3].metric(
        "First oil production in data", int(latest["new_oil_wells"])
    )
    metrics[4].metric(
        "Oil change",
        _format_change(latest["oil"], previous["oil"])
        if previous is not None
        else "N/A",
        help="Compared with the previous available month in the selected period.",
    )

    st.subheader("Field production and development mix")
    monthly_charts = st.columns(2)
    for column, production, title, unit in (
        (monthly_charts[0], "oil", "Monthly oil production", "m³"),
        (
            monthly_charts[1],
            "gas",
            "Monthly gas production",
            "thousand m³",
        ),
    ):
        figure = px.line(
            monthly,
            x="date",
            y=production,
            markers=True,
            title=title,
            labels={"date": "Month", production: f"Production ({unit})"},
        )
        figure.update_layout(height=350, margin={"t": 55, "b": 20})
        column.plotly_chart(figure, use_container_width=True)

    by_type = analysis["by_type"].loc[
        analysis["by_type"]["date"].between(start_date, end_date)
    ]
    type_charts = st.columns(2)
    for column, production, title, unit in (
        (type_charts[0], "oil", "Oil by development type", "m³"),
        (
            type_charts[1],
            "gas",
            "Gas by development type",
            "thousand m³",
        ),
    ):
        figure = px.area(
            by_type,
            x="date",
            y=production,
            color="tipo_de_recurso",
            title=title,
            labels={
                "date": "Month",
                production: f"Production ({unit})",
                "tipo_de_recurso": "Development type",
            },
        )
        figure.update_layout(height=350, margin={"t": 55, "b": 20})
        column.plotly_chart(figure, use_container_width=True)

    development_charts = st.columns(2)
    producing = monthly.melt(
        id_vars="date",
        value_vars=["oil_wells", "gas_wells"],
        var_name="resource",
        value_name="producing_wells",
    )
    producing["resource"] = producing["resource"].map(
        {"oil_wells": "Oil", "gas_wells": "Gas"}
    )
    figure = px.line(
        producing,
        x="date",
        y="producing_wells",
        color="resource",
        markers=True,
        title="Producing wells",
        labels={"date": "Month", "producing_wells": "Wells"},
    )
    figure.update_layout(height=350, margin={"t": 55, "b": 20})
    development_charts[0].plotly_chart(figure, use_container_width=True)

    new_wells = monthly.melt(
        id_vars="date",
        value_vars=["new_oil_wells", "new_gas_wells"],
        var_name="resource",
        value_name="new_wells",
    )
    new_wells["resource"] = new_wells["resource"].map(
        {"new_oil_wells": "Oil", "new_gas_wells": "Gas"}
    )
    figure = px.bar(
        new_wells,
        x="date",
        y="new_wells",
        color="resource",
        barmode="group",
        title="First producing month observed",
        labels={"date": "Month", "new_wells": "Wells"},
    )
    figure.update_layout(height=350, margin={"t": 55, "b": 20})
    development_charts[1].plotly_chart(figure, use_container_width=True)

    monthly["oil_per_well"] = monthly["oil"].div(
        monthly["oil_wells"].where(monthly["oil_wells"].gt(0))
    )
    monthly["gas_per_well"] = monthly["gas"].div(
        monthly["gas_wells"].where(monthly["gas_wells"].gt(0))
    )
    monthly["gas_oil_ratio"] = monthly["gas"].div(
        monthly["oil"].where(monthly["oil"].gt(0))
    )
    per_well_charts = st.columns(2)
    for column, production, title, unit in (
        (
            per_well_charts[0],
            "oil_per_well",
            "Average oil per oil-producing well",
            "m³ per well",
        ),
        (
            per_well_charts[1],
            "gas_per_well",
            "Average gas per gas-producing well",
            "thousand m³ per well",
        ),
    ):
        figure = px.line(
            monthly,
            x="date",
            y=production,
            markers=True,
            title=title,
            labels={"date": "Month", production: unit},
        )
        figure.update_layout(height=320, margin={"t": 55, "b": 20})
        column.plotly_chart(figure, use_container_width=True)
    st.caption(
        "Average monthly production per producing well is not normalized for "
        "production days. The gas/oil ratio is shown in source units "
        "(thousand m³ gas per m³ oil)."
    )
    figure = px.line(
        monthly,
        x="date",
        y="gas_oil_ratio",
        markers=True,
        title="Gas-to-oil ratio",
        labels={
            "date": "Month",
            "gas_oil_ratio": "thousand m³ gas per m³ oil",
        },
    )
    figure.update_layout(height=320, margin={"t": 55, "b": 20})
    st.plotly_chart(figure, use_container_width=True)

    cumulative = monthly.melt(
        id_vars="date",
        value_vars=["cumulative_oil_wells", "cumulative_gas_wells"],
        var_name="resource",
        value_name="cumulative_wells",
    )
    cumulative["resource"] = cumulative["resource"].map(
        {"cumulative_oil_wells": "Oil", "cumulative_gas_wells": "Gas"}
    )
    figure = px.line(
        cumulative,
        x="date",
        y="cumulative_wells",
        color="resource",
        markers=True,
        title="Cumulative wells with production",
        labels={"date": "Month", "cumulative_wells": "Wells"},
    )
    figure.update_layout(height=350, margin={"t": 55, "b": 20})
    st.plotly_chart(figure, use_container_width=True)

    mix = analysis["production_mix"].loc[
        analysis["production_mix"]["date"].between(start_date, end_date)
    ]
    mix_charts = st.columns(2)
    for column, resource, unit in (
        (mix_charts[0], "Oil", "m³"),
        (mix_charts[1], "Gas", "thousand m³"),
    ):
        figure = px.bar(
            mix.loc[mix["resource"].eq(resource)],
            x="date",
            y="production",
            color="production_group",
            title=f"{resource} production by first-production cohort",
            labels={
                "date": "Month",
                "production": f"Production ({unit})",
                "production_group": "Well cohort",
            },
        )
        figure.update_layout(height=350, margin={"t": 55, "b": 20})
        column.plotly_chart(figure, use_container_width=True)

    st.subheader("Same-well performance and well-level changes")
    same_well = analysis["same_well"].loc[
        analysis["same_well"]["date"].between(start_date, end_date)
    ]
    if same_well.empty:
        st.info("There are no wells observed in every month of the latest year.")
    else:
        st.caption(
            f"Same-well cohort: {int(same_well['stable_wells'].iloc[0])} wells "
            f"recorded in every available month of {int(same_well['year'].iloc[0])}."
        )
        same_well_charts = st.columns(2)
        for column, production, field_column, title, unit in (
            (
                same_well_charts[0],
                "oil",
                "field_oil",
                "Oil: field vs same wells",
                "m³",
            ),
            (
                same_well_charts[1],
                "gas",
                "field_gas",
                "Gas: field vs same wells",
                "thousand m³",
            ),
        ):
            chart_data = same_well.melt(
                id_vars="date",
                value_vars=[field_column, production],
                var_name="series",
                value_name="production",
            )
            chart_data["series"] = chart_data["series"].map(
                {field_column: "All wells", production: "Same-well cohort"}
            )
            figure = px.line(
                chart_data,
                x="date",
                y="production",
                color="series",
                markers=True,
                title=title,
                labels={
                    "date": "Month",
                    "production": f"Production ({unit})",
                    "series": "",
                },
            )
            figure.update_layout(height=350, margin={"t": 55, "b": 20})
            column.plotly_chart(figure, use_container_width=True)

    well_month = analysis["well_month"]
    selected_well_rows = well_month.loc[
        well_month["date"].between(start_date, end_date)
    ]
    if selected_wells:
        selected_well_rows = selected_well_rows.loc[
            selected_well_rows["idpozo"].isin(selected_wells)
        ]
    decline_columns = st.columns(2)
    for column, change_column, title in (
        (decline_columns[0], "oil_3m_change", "Oil change over 3 months"),
        (decline_columns[1], "oil_6m_change", "Oil change over 6 months"),
    ):
        decline_data = analysis["declines"].loc[
            analysis["declines"]["date"].between(start_date, end_date)
        ]
        if selected_wells:
            decline_data = decline_data.loc[
                decline_data["idpozo"].isin(selected_wells)
            ]
        decline_data = decline_data.loc[
            decline_data[change_column].notna()
        ]
        figure = px.histogram(
            decline_data,
            x=change_column,
            nbins=30,
            title=title,
            labels={change_column: "Production change"},
        )
        figure.update_layout(height=320, margin={"t": 55, "b": 20})
        column.plotly_chart(figure, use_container_width=True)

    events = analysis["events"].loc[
        analysis["events"]["date"].between(start_date, end_date)
        & analysis["events"]["resource"].eq("Oil")
    ]
    figure = px.bar(
        events,
        x="date",
        y="wells",
        color="event",
        barmode="group",
        title="Oil-well shut-ins and reactivations",
        labels={"date": "Month", "wells": "Wells"},
    )
    figure.update_layout(height=330, margin={"t": 55, "b": 20})
    st.plotly_chart(figure, use_container_width=True)

    decline_table = selected_well_rows.loc[
        selected_well_rows["oil_mom_change"].notna(),
        [
            "date",
            "idpozo",
            "previous_oil",
            "prod_pet",
            "oil_mom_change",
        ],
    ].copy()
    decline_table["oil_mom_change_pct"] = decline_table["oil_mom_change"] * 100
    large_declines = decline_table.loc[
        decline_table["oil_mom_change"].le(-0.30)
    ].sort_values("oil_mom_change")
    st.markdown("**Largest month-over-month oil declines (at least 30%)**")
    st.dataframe(
        large_declines[
            [
                "date",
                "idpozo",
                "previous_oil",
                "prod_pet",
                "oil_mom_change_pct",
            ]
        ].rename(
            columns={
                "date": "Month",
                "idpozo": "Well ID",
                "previous_oil": "Previous oil (m³)",
                "prod_pet": "Current oil (m³)",
                "oil_mom_change_pct": "Change (%)",
            }
        ),
        hide_index=True,
        use_container_width=True,
    )

    st.subheader("Vintage decline curves")
    vintage = analysis["vintage"]
    vintage = vintage.loc[
        vintage["well_age_months"].between(0, 18)
    ]
    if vintage.empty:
        st.info("Not enough post-baseline oil production history for vintage curves.")
    else:
        figure = px.line(
            vintage,
            x="well_age_months",
            y="production_index",
            color="vintage",
            markers=True,
            hover_data=["wells", "oil_per_well"],
            title="Indexed oil production by first-production year",
            labels={
                "well_age_months": "Months since first oil production",
                "production_index": "Oil production index (age 0 = 1)",
                "vintage": "First-production year",
            },
        )
        figure.update_layout(height=380, margin={"t": 55, "b": 20})
        st.plotly_chart(figure, use_container_width=True)

    st.subheader("Monthly production-change decomposition")
    resource = st.selectbox("Resource", ["Oil", "Gas"])
    decomposition = analysis["decomposition"].loc[
        analysis["decomposition"]["date"].between(start_date, end_date)
        & analysis["decomposition"]["resource"].eq(resource)
        & ~analysis["decomposition"]["component"].eq("Net production change")
    ]
    if decomposition.empty:
        st.info("No consecutive months are available for decomposition.")
    else:
        figure = px.bar(
            decomposition,
            x="date",
            y="change",
            color="component",
            title=f"{resource} production-change components",
            labels={
                "date": "Month",
                "change": (
                    "Change (m³)" if resource == "Oil" else "Change (thousand m³)"
                ),
            },
        )
        figure.update_layout(height=380, margin={"t": 55, "b": 20})
        st.plotly_chart(figure, use_container_width=True)
        st.caption(
            "Existing wells compare positive production in consecutive recorded "
            "months. First production in the data and reactivations require a "
            "recorded zero in "
            "the prior month. Unassigned change includes absent records and "
            "missing production values; it is not treated as shut-in production."
        )

    with st.expander("Data quality and analysis limitations"):
        st.dataframe(analysis["diagnostics"], hide_index=True)
        st.markdown(
            """
            - A zero is a reported value; a missing value or absent well-month
              record is not converted to zero.
            - "First production" means first positive monthly production found in
              this 2025–2026 file. Wells already producing in the first data month
              have unknown prior vintage and are excluded from new-well counts and
              vintage curves.
            - A reported zero after a positive month is a temporary shut-in signal,
              not proof of a permanent shutdown.
            - The file has no pad, completion date, production-days, or status
              history sufficient for pad performance, normalized rates, or
              confirmed operating-status analysis. It also does not provide the
              comparable YPF Vaca Muerta peer set in the procedure.
            - Monthly totals are source volumes, not daily rates. No intent or
              causal attribution is inferred.
            """
        )
