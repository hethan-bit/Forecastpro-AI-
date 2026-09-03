"""Read approved planning inputs from the Snowflake planning-input table."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

PLANNING_INPUT_TABLE = "ZX.ANALYTICS.FORECASTING_INPUTS"


def planning_quarters(
    session: Any,
    account_name: str,
    sub_account: str,
    channel: str,
) -> list[str]:
    """Return planning quarters available for one account/sub-account/channel slice."""
    rows = session.sql(
        f"""
        SELECT DISTINCT QUARTER
        FROM {PLANNING_INPUT_TABLE}
        WHERE QUARTER IS NOT NULL
          AND UPPER(TRIM(ACCOUNT_NAME)) = UPPER(TRIM(?))
          AND UPPER(TRIM(COALESCE(SUB_ACCOUNT, ''))) = UPPER(TRIM(?))
          AND UPPER(TRIM(COALESCE(CHANNEL, ''))) = UPPER(TRIM(?))
        ORDER BY QUARTER
        """,
        params=[account_name, sub_account, channel],
    ).collect()
    return [str(row["QUARTER"]).strip() for row in rows if row["QUARTER"]]

def planning_input(
    session: Any,
    quarter: str,
    account_name: str,
    sub_account: str,
    channel: str,
) -> dict[str, Decimal]:
    """Return the one planning row for the selected historical slice.

    Event intentionally is not a key here: it is not present in the approved
    planning table. The table's unique grain is quarter/account/sub-account/channel.
    """
    query = f"""
        SELECT CAMPAIGN_BUDGET, CPM, PLANNED_CAMPAIGN_REACH,
               MAXIMUM_REACH_TO_MAINTAIN_PERFORMANCE,
               SIGNAL_UTILIZATION, FREQUENCY
        FROM {PLANNING_INPUT_TABLE}
        WHERE UPPER(TRIM(QUARTER)) = UPPER(TRIM(?))
          AND UPPER(TRIM(ACCOUNT_NAME)) = UPPER(TRIM(?))
          AND UPPER(TRIM(COALESCE(SUB_ACCOUNT, ''))) = UPPER(TRIM(?))
          AND UPPER(TRIM(COALESCE(CHANNEL, ''))) = UPPER(TRIM(?))
    """
    rows = session.sql(
        query, params=[quarter, account_name, sub_account, channel]
    ).collect()
    if not rows:
        raise ValueError(
            "No planning inputs match the selected quarter, account, sub account, and channel."
        )
    if len(rows) > 1:
        raise ValueError(
            "More than one planning row matches the selected quarter, account, sub account, and channel."
        )
    row = rows[0]
    return {
        "campaign_budget": Decimal(str(row["CAMPAIGN_BUDGET"])),
        "cpm": Decimal(str(row["CPM"])),
        "planned_reach": Decimal(str(row["PLANNED_CAMPAIGN_REACH"])),
        "maximum_reach": Decimal(
            str(row["MAXIMUM_REACH_TO_MAINTAIN_PERFORMANCE"])
        ),
        # FORECASTING_INPUTS stores percent points (for example, 100 for 100%).
        # ForecastPro calculations and percent formatting use decimal fractions.
        "signal_utilization": Decimal(str(row["SIGNAL_UTILIZATION"])) / Decimal("100"),
        "frequency_at_max": Decimal(str(row["FREQUENCY"])),
    }
