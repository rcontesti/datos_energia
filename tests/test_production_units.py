import pandas as pd
import pytest

from src.production_units import calculate_boe


def test_calculate_boe_combines_oil_and_gas_and_preserves_missing_values() -> None:
    oil = pd.Series([1000.0, 1000.0, None])
    gas = pd.Series([0.0, 6.0, 6.0])

    boe = calculate_boe(oil, gas)

    assert boe.iloc[0] == pytest.approx(1000 * 6.28981077)
    assert boe.iloc[1] == pytest.approx(1000 * 6.28981077 + 35.3146667)
    assert pd.isna(boe.iloc[2])
