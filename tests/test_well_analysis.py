import pandas as pd
import pytest

from src.well_analysis import build_area_analysis


def make_dataset() -> pd.DataFrame:
    rows = []
    production = {
        101: [100.0, 80.0, 0.0, 50.0],
        202: [0.0, 20.0, 30.0, 0.0],
    }
    for well_id, oil_values in production.items():
        for month, oil in enumerate(oil_values, start=1):
            rows.append(
                {
                    "areapermisoconcesion": "AGUADA DEL CHAÑAR",
                    "idpozo": well_id,
                    "anio": 2026,
                    "mes": month,
                    "tipo_de_recurso": "NO CONVENCIONAL",
                    "prod_pet": oil,
                    "prod_gas": oil * 2,
                }
            )
    return pd.DataFrame(rows)


def test_analysis_tracks_first_production_and_events() -> None:
    result = build_area_analysis(make_dataset(), "AGUADA DEL CHAÑAR")

    monthly = result["monthly"].set_index("date")
    february = pd.Timestamp("2026-02-01")
    march = pd.Timestamp("2026-03-01")
    april = pd.Timestamp("2026-04-01")

    assert monthly.loc[february, "new_oil_wells"] == 1
    assert monthly.loc[march, "new_oil_wells"] == 0
    assert monthly.loc[april, "cumulative_oil_wells"] == 2

    events = result["events"].set_index(["date", "resource", "event"])
    assert events.loc[(march, "Oil", "Shut-in"), "wells"] == 1
    assert events.loc[(april, "Oil", "Reactivation"), "wells"] == 1
    assert events.loc[(april, "Oil", "Shut-in"), "wells"] == 1


def test_decomposition_reconciles_to_observed_monthly_change() -> None:
    result = build_area_analysis(make_dataset(), "AGUADA DEL CHAÑAR")
    decomposition = result["decomposition"]

    for (date, resource), rows in decomposition.groupby(["date", "resource"]):
        net_change = rows.loc[
            rows["component"].eq("Net production change"), "change"
        ].iloc[0]
        component_sum = rows.loc[
            ~rows["component"].eq("Net production change"), "change"
        ].sum()
        assert component_sum == pytest.approx(net_change)


def test_missing_production_is_not_counted_as_a_zero_or_shutdown() -> None:
    data = make_dataset()
    data.loc[(data["idpozo"] == 101) & (data["mes"] == 2), "prod_pet"] = pd.NA

    result = build_area_analysis(data, "AGUADA DEL CHAÑAR")

    assert (
        result["diagnostics"].set_index("Check").loc["Missing oil values", "Result"]
        == 1
    )
    missing_oil_mix = result["production_mix"].loc[
        result["production_mix"]["resource"].eq("Oil")
        & result["production_mix"]["date"].eq(pd.Timestamp("2026-02-01"))
        & result["production_mix"]["production_group"].eq("Missing production")
    ]
    assert len(missing_oil_mix) == 1
    oil_shutdowns = result["events"].loc[
        result["events"]["resource"].eq("Oil")
        & result["events"]["event"].eq("Shut-in")
    ]
    assert not oil_shutdowns["date"].eq(pd.Timestamp("2026-03-01")).any()


def test_duplicate_well_month_is_rejected() -> None:
    data = make_dataset()
    duplicated = pd.concat([data, data.iloc[[0]]], ignore_index=True)

    with pytest.raises(ValueError, match="duplicate idpozo-month"):
        build_area_analysis(duplicated, "AGUADA DEL CHAÑAR")


def test_analysis_can_be_run_for_any_selected_area() -> None:
    aguada = make_dataset()
    other_area = aguada.assign(areapermisoconcesion="MARIA INES")
    data = pd.concat([aguada, other_area], ignore_index=True)

    result = build_area_analysis(data, "  maria ines ")

    assert set(result["area_data"]["areapermisoconcesion"]) == {"MARIA INES"}
    assert result["diagnostics"].set_index("Check").loc["Unique wells", "Result"] == 2
