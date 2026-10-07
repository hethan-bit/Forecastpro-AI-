"""Read exact planning inputs from approved and analyst-created Snowflake rows."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

PLANNING_INPUT_TABLE = "ZX.ANALYTICS.FORECASTING_INPUTS"
PLANNING_INPUT_TEST_TABLE = "ZX.ANALYTICS.FORECASTING_INPUTS_TEST"


def planning_mappings(session: Any) -> list[dict[str, str]]:
    """Return planning dimensions from approved and analyst-created rows."""
    rows = session.sql(
        f"""
        SELECT DISTINCT ACCOUNT_NAME, SUB_ACCOUNT, CONVERSION_EVENT, CHANNEL
        FROM (
            SELECT TRIM(ACCOUNT_NAME) AS ACCOUNT_NAME,
                   TRIM(COALESCE(SUB_ACCOUNT, '')) AS SUB_ACCOUNT,
                   TRIM(COALESCE(CONVERSION_EVENT, '')) AS CONVERSION_EVENT,
                   TRIM(COALESCE(CHANNEL, '')) AS CHANNEL
            FROM {PLANNING_INPUT_TEST_TABLE}
            UNION ALL
            SELECT TRIM(ACCOUNT_NAME) AS ACCOUNT_NAME,
                   TRIM(COALESCE(SUB_ACCOUNT, '')) AS SUB_ACCOUNT,
                   '' AS CONVERSION_EVENT,
                   TRIM(COALESCE(CHANNEL, '')) AS CHANNEL
            FROM {PLANNING_INPUT_TABLE}
        )
        WHERE ACCOUNT_NAME IS NOT NULL AND TRIM(ACCOUNT_NAME) <> ''
        ORDER BY ACCOUNT_NAME, SUB_ACCOUNT, CONVERSION_EVENT, CHANNEL
        """
    ).collect()
    return [
        {
            "ACCOUNT_NAME": str(row["ACCOUNT_NAME"]).strip(),
            "SUB_ACCOUNT": str(row["SUB_ACCOUNT"] or "").strip(),
            "CONVERSION_EVENT": str(row["CONVERSION_EVENT"] or "").strip(),
            "CHANNEL": str(row["CHANNEL"] or "").strip(),
        }
        for row in rows
    ]


def planning_quarters(
    session: Any,
    account_name: str,
    sub_account: str,
    event: str,
    channel: str,
) -> list[str]:
    """Return quarters without ever falling back to a different account slice."""
    rows = session.sql(
        f"""
        SELECT DISTINCT TRIM(QUARTER) AS QUARTER
        FROM (
            SELECT QUARTER
            FROM {PLANNING_INPUT_TEST_TABLE}
            WHERE UPPER(TRIM(ACCOUNT_NAME)) = UPPER(TRIM(?))
              AND UPPER(TRIM(COALESCE(SUB_ACCOUNT, ''))) = UPPER(TRIM(?))
              AND UPPER(TRIM(COALESCE(CONVERSION_EVENT, ''))) = UPPER(TRIM(?))
              AND UPPER(TRIM(COALESCE(CHANNEL, ''))) = UPPER(TRIM(?))
            UNION ALL
            SELECT QUARTER
            FROM {PLANNING_INPUT_TABLE}
            WHERE UPPER(TRIM(ACCOUNT_NAME)) = UPPER(TRIM(?))
              AND UPPER(TRIM(COALESCE(SUB_ACCOUNT, ''))) = UPPER(TRIM(?))
              AND UPPER(TRIM(COALESCE(CHANNEL, ''))) = UPPER(TRIM(?))
        )
        WHERE QUARTER IS NOT NULL
        ORDER BY QUARTER
        """,
        params=[
            account_name, sub_account, event, channel,
            account_name, sub_account, channel,
        ],
    ).collect()
    return [str(row["QUARTER"]).strip() for row in rows if row["QUARTER"]]


def planning_input(
    session: Any,
    quarter: str,
    account_name: str,
    sub_account: str,
    event: str,
    channel: str,
) -> dict[str, Decimal]:
    """Prefer an exact TEST event row, then the same approved legacy slice."""
    rows = session.sql(
        f"""
        SELECT CAMPAIGN_BUDGET, CPM, PLANNED_CAMPAIGN_REACH,
               MAXIMUM_REACH_TO_MAINTAIN_PERFORMANCE,
               SIGNAL_UTILIZATION, FREQUENCY
        FROM (
            SELECT CAMPAIGN_BUDGET, CPM, PLANNED_CAMPAIGN_REACH,
                   MAXIMUM_REACH_TO_MAINTAIN_PERFORMANCE,
                   SIGNAL_UTILIZATION, FREQUENCY,
                   UPDATED_AT, 0 AS SOURCE_PRIORITY
            FROM {PLANNING_INPUT_TEST_TABLE}
            WHERE UPPER(TRIM(QUARTER)) = UPPER(TRIM(?))
              AND UPPER(TRIM(ACCOUNT_NAME)) = UPPER(TRIM(?))
              AND UPPER(TRIM(COALESCE(SUB_ACCOUNT, ''))) = UPPER(TRIM(?))
              AND UPPER(TRIM(COALESCE(CONVERSION_EVENT, ''))) = UPPER(TRIM(?))
              AND UPPER(TRIM(COALESCE(CHANNEL, ''))) = UPPER(TRIM(?))
            UNION ALL
            SELECT CAMPAIGN_BUDGET, CPM, PLANNED_CAMPAIGN_REACH,
                   MAXIMUM_REACH_TO_MAINTAIN_PERFORMANCE,
                   SIGNAL_UTILIZATION, FREQUENCY,
                   NULL AS UPDATED_AT, 1 AS SOURCE_PRIORITY
            FROM {PLANNING_INPUT_TABLE}
            WHERE UPPER(TRIM(QUARTER)) = UPPER(TRIM(?))
              AND UPPER(TRIM(ACCOUNT_NAME)) = UPPER(TRIM(?))
              AND UPPER(TRIM(COALESCE(SUB_ACCOUNT, ''))) = UPPER(TRIM(?))
              AND UPPER(TRIM(COALESCE(CHANNEL, ''))) = UPPER(TRIM(?))
        )
        ORDER BY SOURCE_PRIORITY, UPDATED_AT DESC NULLS LAST
        LIMIT 1
        """,
        params=[
            quarter, account_name, sub_account, event, channel,
            quarter, account_name, sub_account, channel,
        ],
    ).collect()
    if not rows:
        raise ValueError(
            "No Forecasting Inputs match the selected quarter, account, campaign, "
            "conversion event, and marketing channel."
        )
    row = rows[0]
    return {
        "campaign_budget": Decimal(str(row["CAMPAIGN_BUDGET"])),
        "cpm": Decimal(str(row["CPM"])),
        "planned_reach": Decimal(str(row["PLANNED_CAMPAIGN_REACH"])),
        "maximum_reach": Decimal(
            str(row["MAXIMUM_REACH_TO_MAINTAIN_PERFORMANCE"])
        ),
        "signal_utilization": Decimal(str(row["SIGNAL_UTILIZATION"])) / Decimal("100"),
        "frequency_at_max": Decimal(str(row["FREQUENCY"])),
    }
