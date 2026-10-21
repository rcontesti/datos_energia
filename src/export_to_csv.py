from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "processed" / "cgc_production_2026.parquet"
DEFAULT_OUTPUT = DEFAULT_INPUT.with_suffix(".csv")


def export_to_csv(input_path: Path, output_path: Path) -> None:
    df = pd.read_parquet(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8")
    print(f"Exported {len(df):,} rows to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export the CGC production Parquet dataset to CSV."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Input Parquet file (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output CSV file (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()
    export_to_csv(args.input, args.output)


if __name__ == "__main__":
    main()
