import pandas as pd
import pytest

from src.area_production_summary import (
    OIL_CUBIC_METRES_TO_BARRELS,
    THOUSAND_CUBIC_METRES_TO_MCF,
    build_area_production_summary,
)


def make_dataset() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "areapermisoconcesion": "AREA A",
                "anio": 2026,
                "mes": 8,
                "tipo_de_recurso": "CONVENCIONAL",
                "prod_pet": 999.0,
                "prod_gas": 999.0,
            },
            {
                "areapermisoconcesion": "AREA A",
                "anio": 2026,
                "mes": 9,
                "tipo_de_recurso": "CONVENCIONAL",
                "prod_pet": 100.0,
                "prod_gas": 6.0,
            },
            {
                "areapermisoconcesion": "AREA A",
                "anio": 2026,
                "mes": 9,
                "tipo_de_recurso": "NO CONVENCIONAL",
                "prod_pet": 10.0,
                "prod_gas": 12.0,
            },
            {
                "areapermisoconcesion": "AREA A",
                "anio": 2026,
                "mes": 9,
                "tipo_de_recurso": "SIN RESERVORIO",
                "prod_pet": 500.0,
                "prod_gas": 500.0,
            },
            {
                "areapermisoconcesion": "AREA B",
                "anio": 2026,
                "mes": 9,
                "tipo_de_recurso": "CONVENCIONAL",
                "prod_pet": 1.0,
                "prod_gas": 0.0,
            },
            {
                "areapermisoconcesion": "AREA C",
                "anio": 2026,
                "mes": 8,
                "tipo_de_recurso": "NO CONVENCIONAL",
                "prod_pet": 400.0,
                "prod_gas": 0.0,
            },
        ]
    )


def test_summary_uses_latest_month_and_sorts_by_boe() -> None:
    as_of, summary = build_area_production_summary(make_dataset())

    assert as_of == pd.Timestamp("2026-09-01")
    assert summary["Permit area"].tolist() == ["AREA A", "AREA B", "AREA C"]
    assert summary.loc[0, "Total Oil Production (m³)"] == 110.0
    assert summary.loc[0, "Total Gas Production (thousand m³)"] == 18.0
    assert summary.loc[0, "Conventional Oil Production (m³)"] == 100.0
    assert summary.loc[0, "Non Conventional Gas Production (thousand m³)"] == 12.0

    expected_boe = (
        110 * OIL_CUBIC_METRES_TO_BARRELS
        + 18 * THOUSAND_CUBIC_METRES_TO_MCF / 6
    )
    assert summary.loc[0, "Total Production (BOE)"] == pytest.approx(expected_boe)


def test_area_without_latest_month_data_is_unavailable_not_stale() -> None:
    _, summary = build_area_production_summary(make_dataset())

    area_c = summary.set_index("Permit area").loc["AREA C"]
    assert area_c.filter(like="Production").isna().all()


def test_area_without_a_resource_category_gets_zero_for_that_category() -> None:
    _, summary = build_area_production_summary(make_dataset())

    area_b = summary.set_index("Permit area").loc["AREA B"]
    assert area_b["Non Conventional Oil Production (m³)"] == 0
    assert area_b["Non Conventional Gas Production (thousand m³)"] == 0


def test_missing_source_value_keeps_total_unavailable() -> None:
    data = make_dataset()
    data.loc[
        (data["areapermisoconcesion"] == "AREA A")
        & (data["mes"] == 9)
        & (data["tipo_de_recurso"] == "NO CONVENCIONAL"),
        "prod_gas",
    ] = pd.NA

    _, summary = build_area_production_summary(data)

    area_a = summary.set_index("Permit area").loc["AREA A"]
    assert pd.isna(area_a["Total Gas Production (thousand m³)"])
    assert pd.isna(area_a["Total Production (BOE)"])
