
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "companies.yaml"
DATA_DIR = ROOT / "data" / "processed"
REPORTS_DIR = ROOT / "reports"
METADATA_PATH = ROOT / "data" / "metadata.json"

REQUIRED_COLUMNS = {
    "anio",
    "mes",
    "idpozo",
    "empresa",
    "areapermisoconcesion",
    "prod_pet",
    "prod_gas",
    "fecha_data",
}


def load_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def download_source(url: str, destination: Path) -> None:
    """Stream the source to disk rather than holding its bytes in RAM."""
    with requests.get(url, stream=True, timeout=(30, 300)) as response:
        response.raise_for_status()
        with destination.open("wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)


def filter_production(
    df: pd.DataFrame, config: dict
) -> pd.DataFrame:
    group_config = config["groups"]["CGC"]
    companies = group_config["companies"]

    direct_mask = df["empresa"].isin(companies)

    partnership_mask = pd.Series(False, index=df.index)
    for rule in group_config.get("additional_filters", []):
        partnership_mask |= (
            df["empresa"].eq(rule["company"])
            & df["areapermisoconcesion"].eq(rule["area"])
        )

    result = df.loc[direct_mask | partnership_mask].copy()

    result["grupo"] = "CGC"
    result["origen_grupo"] = "CGC_DIRECTO"
    result.loc[partnership_mask.loc[result.index], "origen_grupo"] = (
        "YPF_AGUADA_DEL_CHAÑAR"
    )

    return result


def validate_source(df: pd.DataFrame, year: int) -> None:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Source is missing required columns: {sorted(missing)}")

    if df.empty:
        raise ValueError("Source CSV is empty.")

    years = set(df["anio"].dropna().astype(int).unique())
    if years != {year}:
        raise ValueError(f"Expected only {year} data; found years: {sorted(years)}")

    months = df["mes"].dropna()
    if not months.between(1, 12).all():
        raise ValueError("Source contains invalid month values.")

    for column in ("prod_pet", "prod_gas"):
        df[column] = pd.to_numeric(df[column], errors="raise")


def validate_filtered(df: pd.DataFrame, year: int) -> None:
    if df.empty:
        raise ValueError(
            "No records matched the configured filters. "
            "Check company and area names before proceeding."
        )

    if not df["empresa"].isin(
        ["COMPAÑÍA GENERAL DE COMBUSTIBLES S.A.",
         "CGC ENERGIA SAU", "YPF S.A."]
    ).all():
        raise ValueError("Unexpected company found in filtered data.")

    if not df["anio"].eq(year).all():
        raise ValueError(f"Filtered data contains records outside {year}.")

    expected_origin = (
        df["empresa"].eq("YPF S.A.")
        & df["areapermisoconcesion"].eq("AGUADA DEL CHAÑAR")
    )
    if (
        df.loc[expected_origin, "origen_grupo"]
        .ne("YPF_AGUADA_DEL_CHAÑAR")
        .any()
    ):
        raise ValueError("Partnership classification failed.")


def generate_reports(df: pd.DataFrame) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    production = ["prod_pet", "prod_gas"]

    df.groupby(["anio", "mes"], dropna=False)[production].sum(
        min_count=1
    ).reset_index().to_csv(REPORTS_DIR / "monthly.csv", index=False)

    df.groupby(["anio"], dropna=False)[production].sum(
        min_count=1
    ).reset_index().to_csv(REPORTS_DIR / "annual.csv", index=False)

    df.groupby(
        ["anio", "mes", "areapermisoconcesion"],
        dropna=False,
    )[production].sum(min_count=1).reset_index().to_csv(
        REPORTS_DIR / "by_area.csv", index=False
    )

    well_keys = [
        "anio", "mes", "idpozo", "sigla", "empresa",
        "grupo", "origen_grupo", "areapermisoconcesion",
        "areayacimiento", "cuenca", "provincia",
    ]
    well_keys = [c for c in well_keys if c in df.columns]

    df.groupby(well_keys, dropna=False)[production].sum(
        min_count=1
    ).reset_index().to_csv(REPORTS_DIR / "by_well.csv", index=False)


def main() -> None:
    config = load_config()
    year = int(config["source_year"])

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temp_dir:
        source_path = Path(temp_dir) / f"source_{year}.csv"
        print("Downloading source CSV...")
        download_source(config["source_url"], source_path)

        print("Reading CSV with pandas...")
        # source = pd.read_csv(source_path, encoding="utf-8-sig")
        source = pd.read_csv(
            source_path,
            encoding="utf-8-sig",
            low_memory=False,
            dtype={
                "observaciones": "string",
                "sub_tipo_recurso": "string",
            },
        )
        source_rows = len(source)

        validate_source(source, year)

        print(f"Source rows: {source_rows:,}")
        print("Filtering CGC production universe...")
        filtered = filter_production(source, config)
        validate_filtered(filtered, year)

    # Save the dataset and reports only after validation succeeds.
    output_path = DATA_DIR / f"cgc_production_{year}.parquet"
    filtered.to_parquet(output_path, index=False, engine="pyarrow")
    generate_reports(filtered)

    metadata = {
        "source_url": config["source_url"],
        "source_repository": config["source_repository"],
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "source_year": year,
        "rows_source": source_rows,
        "rows_filtered": len(filtered),
        "companies_retained": sorted(
            filtered["empresa"].dropna().unique().tolist()
        ),
        "areas_retained": sorted(
            filtered["areapermisoconcesion"].dropna().unique().tolist()
        ),
        "months_retained": sorted(
            filtered["mes"].dropna().astype(int).unique().tolist()
        ),
        "latest_month": int(filtered["mes"].max()),
        "output_file": str(output_path.relative_to(ROOT)),
        "filter_rules": config["groups"]["CGC"],
    }

    METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    METADATA_PATH.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("\nUpdate completed.")
    print(f"Source rows:   {source_rows:,}")
    print(f"Retained rows: {len(filtered):,}")
    print(f"Months:        {metadata['months_retained']}")
    print(f"Parquet:       {output_path.relative_to(ROOT)}")
    print(f"Reports:       {REPORTS_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
