from __future__ import annotations

import pandas as pd


AREA_COLUMN = "areapermisoconcesion"
WELL_COLUMN = "idpozo"
PRODUCTION_COLUMNS = {
    "Oil": "prod_pet",
    "Gas": "prod_gas",
}

REQUIRED_COLUMNS = {
    AREA_COLUMN,
    WELL_COLUMN,
    "anio",
    "mes",
    "tipo_de_recurso",
    *PRODUCTION_COLUMNS.values(),
}


def _next_month(date: pd.Timestamp) -> pd.Timestamp:
    return date + pd.offsets.MonthBegin(1)


def build_area_analysis(
    df: pd.DataFrame,
    area_name: str,
) -> dict[str, pd.DataFrame]:
    """Build descriptive well-level tables for one permit area."""
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Dataset is missing required columns: {sorted(missing)}")

    area = df[AREA_COLUMN].astype("string").str.strip().str.casefold()
    area_data = df.loc[area.eq(area_name.strip().casefold())].copy()
    if area_data.empty:
        raise ValueError(f"Dataset has no records for permit area {area_name!r}.")
    if area_data[WELL_COLUMN].isna().any():
        raise ValueError(f"Permit area {area_name!r} contains missing idpozo values.")

    area_data["date"] = pd.to_datetime(
        {
            "year": pd.to_numeric(area_data["anio"], errors="raise"),
            "month": pd.to_numeric(area_data["mes"], errors="raise"),
            "day": 1,
        },
        errors="raise",
    )
    area_data[WELL_COLUMN] = area_data[WELL_COLUMN].astype("int64")

    duplicate_count = int(area_data.duplicated([WELL_COLUMN, "date"]).sum())
    if duplicate_count:
        raise ValueError(
            f"Permit area {area_name!r} has duplicate idpozo-month records "
            f"({duplicate_count} duplicates)."
        )

    for column in PRODUCTION_COLUMNS.values():
        area_data[column] = pd.to_numeric(area_data[column], errors="coerce")

    area_data = area_data.sort_values([WELL_COLUMN, "date"])
    first_month = area_data["date"].min()
    last_month = area_data["date"].max()

    first_production: dict[str, pd.Series] = {}
    for resource, column in PRODUCTION_COLUMNS.items():
        first_production[resource] = (
            area_data.loc[area_data[column].gt(0)]
            .groupby(WELL_COLUMN)["date"]
            .min()
        )
        area_data[f"first_{resource.lower()}_month"] = area_data[WELL_COLUMN].map(
            first_production[resource]
        )

    monthly = (
        area_data.groupby("date")
        .agg(
            oil=("prod_pet", lambda values: values.sum(min_count=1)),
            gas=("prod_gas", lambda values: values.sum(min_count=1)),
            observed_wells=(WELL_COLUMN, "nunique"),
            oil_wells=("prod_pet", lambda values: int(values.gt(0).sum())),
            gas_wells=("prod_gas", lambda values: int(values.gt(0).sum())),
        )
        .reset_index()
        .sort_values("date")
    )

    by_type = (
        area_data.groupby(["date", "tipo_de_recurso"], dropna=False)
        .agg(
            oil=("prod_pet", lambda values: values.sum(min_count=1)),
            gas=("prod_gas", lambda values: values.sum(min_count=1)),
            wells=(WELL_COLUMN, "nunique"),
        )
        .reset_index()
        .sort_values(["date", "tipo_de_recurso"])
    )

    well_month = area_data[
        [
            WELL_COLUMN,
            "date",
            "tipo_de_recurso",
            "prod_pet",
            "prod_gas",
            "first_oil_month",
            "first_gas_month",
        ]
    ].copy()

    well_month["new_oil_well"] = (
        well_month["first_oil_month"].eq(well_month["date"])
        & well_month["date"].gt(first_month)
    )
    well_month["new_gas_well"] = (
        well_month["first_gas_month"].eq(well_month["date"])
        & well_month["date"].gt(first_month)
    )

    for resource, column in PRODUCTION_COLUMNS.items():
        well_month[f"previous_{resource.lower()}"] = well_month.groupby(
            WELL_COLUMN
        )[column].shift()
        well_month[f"previous_date_{resource.lower()}"] = well_month.groupby(
            WELL_COLUMN
        )["date"].shift()
        previous_date = well_month[f"previous_date_{resource.lower()}"]
        consecutive = previous_date.map(
            lambda date: _next_month(date) if pd.notna(date) else pd.NaT
        ).eq(well_month["date"])
        previous = well_month[f"previous_{resource.lower()}"]
        current = well_month[column]
        well_month[f"{resource.lower()}_mom_change"] = (
            current.div(previous).sub(1).where(previous.gt(0) & consecutive)
        )

    monthly["new_oil_wells"] = (
        well_month.loc[well_month["new_oil_well"]]
        .groupby("date")[WELL_COLUMN]
        .nunique()
        .reindex(monthly["date"], fill_value=0)
        .to_numpy()
    )
    monthly["new_gas_wells"] = (
        well_month.loc[well_month["new_gas_well"]]
        .groupby("date")[WELL_COLUMN]
        .nunique()
        .reindex(monthly["date"], fill_value=0)
        .to_numpy()
    )
    monthly["cumulative_oil_wells"] = (
        monthly["date"].map(
            lambda date: int(
                first_production["Oil"]
                .loc[first_production["Oil"].le(date)]
                .index.nunique()
            )
        )
    )
    monthly["cumulative_gas_wells"] = (
        monthly["date"].map(
            lambda date: int(
                first_production["Gas"]
                .loc[first_production["Gas"].le(date)]
                .index.nunique()
            )
        )
    )

    mix_rows: list[pd.DataFrame] = []
    for resource, column in PRODUCTION_COLUMNS.items():
        first_column = f"first_{resource.lower()}_month"
        vintage_type = pd.Series(
            "Previously producing",
            index=well_month.index,
            dtype="string",
        )
        vintage_type.loc[well_month[column].eq(0)] = "Reported zero"
        vintage_type.loc[well_month[column].isna()] = "Missing production"
        vintage_type.loc[
            well_month[first_column].eq(first_month)
            & well_month["date"].eq(first_month)
        ] = "Age unknown at data start"
        vintage_type.loc[
            well_month[first_column].eq(well_month["date"])
            & well_month["date"].gt(first_month)
        ] = "First production in data"
        mix_rows.append(
            pd.DataFrame(
                {
                    "date": well_month["date"],
                    "resource": resource,
                    "production_group": vintage_type,
                    "production": well_month[column],
                }
            )
        )
    production_mix = (
        pd.concat(mix_rows, ignore_index=True)
        .groupby(["date", "resource", "production_group"], dropna=False)
        ["production"]
        .sum(min_count=1)
        .reset_index()
    )

    event_frames: list[pd.DataFrame] = []
    for resource, column in PRODUCTION_COLUMNS.items():
        lower = resource.lower()
        previous = well_month[f"previous_{lower}"]
        current = well_month[column]
        previous_date = well_month[f"previous_date_{lower}"]
        consecutive = previous_date.map(
            lambda date: _next_month(date) if pd.notna(date) else pd.NaT
        ).eq(well_month["date"])
        valid = consecutive & previous.notna() & current.notna()
        positive_after_zero = valid & previous.le(0) & current.gt(0)
        first_producing_month = well_month[f"first_{lower}_month"]

        event_type = pd.Series(pd.NA, index=well_month.index, dtype="string")
        event_type.loc[
            positive_after_zero & first_producing_month.eq(well_month["date"])
        ] = "First production in data"
        event_type.loc[
            positive_after_zero & first_producing_month.lt(well_month["date"])
        ] = "Reactivation"
        event_type.loc[valid & previous.gt(0) & current.eq(0)] = "Shut-in"

        event_frames.append(
            pd.DataFrame(
                {
                    "date": well_month["date"],
                    "resource": resource,
                    "event": event_type,
                    WELL_COLUMN: well_month[WELL_COLUMN],
                    "production_impact": current.where(
                        event_type.isin(
                            ["First production in data", "Reactivation"]
                        ),
                        -previous.where(event_type.eq("Shut-in")),
                    ),
                }
            ).dropna(subset=["event"])
        )
    events = pd.concat(event_frames, ignore_index=True)
    events = (
        events.groupby(["date", "resource", "event"])
        .agg(
            wells=(WELL_COLUMN, "nunique"),
            production_impact=("production_impact", "sum"),
        )
        .reset_index()
    )

    decline_rows = well_month.copy()
    for resource, column in PRODUCTION_COLUMNS.items():
        lower = resource.lower()
        for months in (3, 6):
            old_production = decline_rows.groupby(WELL_COLUMN)[column].shift(months)
            old_date = decline_rows.groupby(WELL_COLUMN)["date"].shift(months)
            expected_date = decline_rows["date"].map(
                lambda date: date - pd.DateOffset(months=months)
            )
            decline_rows[f"{lower}_{months}m_change"] = (
                decline_rows[column].div(old_production).sub(1).where(
                    old_production.gt(0) & old_date.eq(expected_date)
                )
            )

    latest_year = int(monthly["date"].max().year)
    comparison_months = monthly.loc[
        monthly["date"].dt.year.eq(latest_year), "date"
    ]
    stable_ids = (
        well_month.loc[well_month["date"].isin(comparison_months)]
        .groupby(WELL_COLUMN)["date"]
        .nunique()
    )
    stable_ids = stable_ids.loc[
        stable_ids.eq(comparison_months.nunique())
    ].index
    same_well = (
        well_month.loc[
            well_month[WELL_COLUMN].isin(stable_ids)
            & well_month["date"].isin(comparison_months)
        ]
        .groupby("date")
        .agg(
            oil=("prod_pet", lambda values: values.sum(min_count=1)),
            gas=("prod_gas", lambda values: values.sum(min_count=1)),
        )
        .reset_index()
    )
    same_well["stable_wells"] = len(stable_ids)
    same_well["year"] = latest_year
    same_well = same_well.merge(
        monthly[["date", "oil", "gas"]].rename(
            columns={"oil": "field_oil", "gas": "field_gas"}
        ),
        on="date",
        how="left",
        validate="one_to_one",
    )

    eligible_vintage = well_month.loc[
        well_month["first_oil_month"].notna()
        & well_month["first_oil_month"].gt(first_month)
        & well_month["date"].ge(well_month["first_oil_month"])
    ].copy()
    eligible_vintage["vintage"] = eligible_vintage["first_oil_month"].dt.year
    eligible_vintage["well_age_months"] = (
        (eligible_vintage["date"].dt.year - eligible_vintage["first_oil_month"].dt.year)
        * 12
        + eligible_vintage["date"].dt.month
        - eligible_vintage["first_oil_month"].dt.month
    )
    vintage = (
        eligible_vintage.groupby(["vintage", "well_age_months"])
        .agg(
            oil=("prod_pet", lambda values: values.sum(min_count=1)),
            wells=(WELL_COLUMN, "nunique"),
        )
        .reset_index()
        .sort_values(["vintage", "well_age_months"])
    )
    vintage["oil_per_well"] = vintage["oil"].div(vintage["wells"])
    vintage["production_index"] = vintage["oil_per_well"].div(
        vintage.groupby("vintage")["oil_per_well"].transform("first")
    )

    monthly_totals = monthly.set_index("date")
    decomposition_rows: list[dict[str, object]] = []
    dates = monthly["date"].tolist()
    for previous_date, date in zip(dates, dates[1:]):
        if _next_month(previous_date) != date:
            continue
        previous_rows = well_month.loc[
            well_month["date"].eq(previous_date)
        ].set_index(WELL_COLUMN)
        current_rows = well_month.loc[
            well_month["date"].eq(date)
        ].set_index(WELL_COLUMN)
        paired = previous_rows[
            ["prod_pet", "prod_gas"]
        ].join(
            current_rows[["prod_pet", "prod_gas", "first_oil_month", "first_gas_month"]],
            how="inner",
            lsuffix="_previous",
            rsuffix="_current",
        )
        components = {
            resource: {
                "Existing producing wells": 0.0,
                "First production in data": 0.0,
                "Reactivations": 0.0,
                "Shut-ins": 0.0,
            }
            for resource in PRODUCTION_COLUMNS
        }
        for resource, column in PRODUCTION_COLUMNS.items():
            previous = paired[f"{column}_previous"]
            current = paired[f"{column}_current"]
            valid = previous.notna() & current.notna()
            prior_positive = valid & previous.gt(0)
            current_positive = valid & current.gt(0)
            components[resource]["Existing producing wells"] = float(
                (current - previous).loc[prior_positive & current_positive].sum()
            )
            first_column = f"first_{resource.lower()}_month"
            first_months = paired[first_column]
            started = valid & previous.le(0) & current_positive
            is_new = started & first_months.eq(date) & (date > first_month)
            is_reactivated = started & first_months.lt(date)
            components[resource]["First production in data"] = float(
                current.loc[is_new].sum()
            )
            components[resource]["Reactivations"] = float(
                current.loc[is_reactivated].sum()
            )
            components[resource]["Shut-ins"] = float(
                -previous.loc[valid & previous.gt(0) & current.eq(0)].sum()
            )

        for resource, column in PRODUCTION_COLUMNS.items():
            total_column = resource.lower()
            net_change = float(
                monthly_totals.loc[date, total_column]
                - monthly_totals.loc[previous_date, total_column]
            )
            classified = sum(components[resource].values())
            for component, value in components[resource].items():
                decomposition_rows.append(
                    {
                        "date": date,
                        "previous_date": previous_date,
                        "resource": resource,
                        "component": component,
                        "change": value,
                    }
                )
            decomposition_rows.append(
                {
                    "date": date,
                    "previous_date": previous_date,
                    "resource": resource,
                    "component": "Unassigned / data gap",
                    "change": net_change - classified,
                }
            )
            decomposition_rows.append(
                {
                    "date": date,
                    "previous_date": previous_date,
                    "resource": resource,
                    "component": "Net production change",
                    "change": net_change,
                }
            )
    decomposition = pd.DataFrame(decomposition_rows)

    expected_observations = area_data.groupby(WELL_COLUMN)["date"].agg(
        first="min", last="max", observed="nunique"
    )
    expected_observations["expected"] = (
        (expected_observations["last"].dt.year - expected_observations["first"].dt.year)
        * 12
        + expected_observations["last"].dt.month
        - expected_observations["first"].dt.month
        + 1
    )
    diagnostics = pd.DataFrame(
        [
            ("Area records", len(area_data)),
            ("Unique wells", area_data[WELL_COLUMN].nunique()),
            ("Duplicate well-months", duplicate_count),
            ("Missing well IDs", int(area_data[WELL_COLUMN].isna().sum())),
            ("Missing oil values", int(area_data["prod_pet"].isna().sum())),
            ("Missing gas values", int(area_data["prod_gas"].isna().sum())),
            ("Negative oil values", int(area_data["prod_pet"].lt(0).sum())),
            ("Negative gas values", int(area_data["prod_gas"].lt(0).sum())),
            (
                "Missing well-month records within observed well spans",
                int((expected_observations["expected"] - expected_observations["observed"]).sum()),
            ),
            ("First month in dataset", first_month.strftime("%b %Y")),
            ("Latest month in dataset", last_month.strftime("%b %Y")),
        ],
        columns=["Check", "Result"],
    )

    return {
        "area_data": area_data,
        "monthly": monthly,
        "by_type": by_type,
        "well_month": well_month,
        "production_mix": production_mix,
        "events": events,
        "declines": decline_rows,
        "same_well": same_well,
        "vintage": vintage,
        "decomposition": decomposition,
        "diagnostics": diagnostics,
    }
