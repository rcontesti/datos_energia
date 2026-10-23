from __future__ import annotations

import pandas as pd


OIL_CUBIC_METRES_TO_BARRELS = 6.28981077
THOUSAND_CUBIC_METRES_TO_MCF = 35.3146667
MCF_PER_BOE = 6


def calculate_boe(
    oil_cubic_metres: pd.Series,
    gas_thousand_cubic_metres: pd.Series,
) -> pd.Series:
    """Convert oil and gas volumes to barrels of oil equivalent."""
    return (
        oil_cubic_metres * OIL_CUBIC_METRES_TO_BARRELS
        + gas_thousand_cubic_metres * THOUSAND_CUBIC_METRES_TO_MCF / MCF_PER_BOE
    )
