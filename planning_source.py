"""Read the latest MailOps inputs from the approved Forecasting Inputs table."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

PLANNING_INPUT_TABLE = "ZX.ANALYTICS.FORECASTING_INPUTS"


def _quarter_value(label: str) -> int:
    match = re.fullmatch(r"Q([1-4])\s+(\d{4})", str(label or "").strip(), re.I)
    return int(match.group(2)) * 4 + int(match.group(1)) if match else 0


def _quarter_label(value: int) -> str:
    year, offset = divmod(value - 1, 4)
    return f"Q{offset + 1} {year}"


def _all_inputs_sql(columns: str) -> str:
    return f"""
        SELECT {columns}, 0 AS SOURCE_PRIORITY
        FROM {PLANNING_INPUT_TABLE}
    """


def planning_mappings(session: Any) -> list[dict[str, str]]:
    rows = session.sql(
        f"""
        WITH ALL_INPUTS AS (
            {_all_inputs_sql("QUARTER, ACCOUNT_NAME, SUB_ACCOUNT, CHANNEL, UPDATED_AT, TIMERANK")}
        )
        SELECT ACCOUNT_NAME, SUB_ACCOUNT, CHANNEL
        FROM ALL_INPUTS
        WHERE ACCOUNT_NAME IS NOT NULL
          AND TRIM(ACCOUNT_NAME) <> ''
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY
                UPPER(TRIM(QUARTER)),
                UPPER(TRIM(ACCOUNT_NAME)),
                UPPER(TRIM(COALESCE(SUB_ACCOUNT, ''))),
                UPPER(TRIM(COALESCE(CHANNEL, '')))
            ORDER BY
                SOURCE_PRIORITY ASC,
                CASE WHEN UPDATED_AT IS NOT NULL THEN 0 ELSE 1 END ASC,
                UPDATED_AT DESC NULLS LAST,
                TIMERANK ASC NULLS LAST
        ) = 1
        ORDER BY ACCOUNT_NAME, SUB_ACCOUNT, CHANNEL
        """
    ).collect()
    return [
        {
            "ACCOUNT_NAME": str(row["ACCOUNT_NAME"]).strip(),
            "SUB_ACCOUNT": str(row["SUB_ACCOUNT"] or "").strip(),
            "CONVERSION_EVENT": "",
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
    """Return actual source quarters for the selected MailOps slice."""
    rows = session.sql(
        f"""
        WITH ALL_INPUTS AS (
            {_all_inputs_sql("QUARTER, ACCOUNT_NAME, SUB_ACCOUNT, CHANNEL, UPDATED_AT, TIMERANK")}
        )
        SELECT TRIM(QUARTER) AS QUARTER
        FROM ALL_INPUTS
        WHERE UPPER(TRIM(ACCOUNT_NAME)) = UPPER(TRIM(?))
          AND UPPER(TRIM(COALESCE(SUB_ACCOUNT, ''))) = UPPER(TRIM(?))
          AND UPPER(TRIM(COALESCE(CHANNEL, ''))) = UPPER(TRIM(?))
          AND QUARTER IS NOT NULL
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY
                UPPER(TRIM(QUARTER)),
                UPPER(TRIM(ACCOUNT_NAME)),
                UPPER(TRIM(COALESCE(SUB_ACCOUNT, ''))),
                UPPER(TRIM(COALESCE(CHANNEL, '')))
            ORDER BY
                SOURCE_PRIORITY ASC,
                CASE WHEN UPDATED_AT IS NOT NULL THEN 0 ELSE 1 END ASC,
                UPDATED_AT DESC NULLS LAST,
                TIMERANK ASC NULLS LAST
        ) = 1
        ORDER BY QUARTER
        """,
        params=[account_name, sub_account, channel],
    ).collect()
    return sorted(
        {str(row["QUARTER"]).strip() for row in rows if row["QUARTER"]},
        key=_quarter_value,
    )


def planning_projection_quarters(session: Any) -> list[str]:
    """Return global projection horizon: earliest source + 1 through latest + 1."""
    rows = session.sql(
        f"""
        WITH ALL_INPUTS AS (
            {_all_inputs_sql("QUARTER, ACCOUNT_NAME, SUB_ACCOUNT, CHANNEL, UPDATED_AT, TIMERANK")}
        )
        SELECT DISTINCT TRIM(QUARTER) AS QUARTER
        FROM ALL_INPUTS
        WHERE QUARTER IS NOT NULL
          AND TRIM(QUARTER) <> ''
        """
    ).collect()
    values = sorted(
        {_quarter_value(str(row["QUARTER"]).strip()) for row in rows if row["QUARTER"]}
        - {0}
    )
    if not values:
        return []
    return [_quarter_label(value) for value in range(values[0] + 1, values[-1] + 2)]


def planning_input(
    session: Any,
    quarter: str,
    account_name: str,
    sub_account: str,
    event: str,
    channel: str,
) -> dict[str, Decimal]:
    """Return the latest row from the approved Forecasting Inputs table."""
    rows = session.sql(
        f"""
        WITH ALL_INPUTS AS (
            {_all_inputs_sql("QUARTER, ACCOUNT_NAME, SUB_ACCOUNT, CHANNEL, CAMPAIGN_BUDGET, CPM, PLANNED_CAMPAIGN_REACH, MAXIMUM_REACH_TO_MAINTAIN_PERFORMANCE, SIGNAL_UTILIZATION, FREQUENCY, UPDATED_AT, TIMERANK")}
        )
        SELECT
            CAMPAIGN_BUDGET,
            CPM,
            PLANNED_CAMPAIGN_REACH,
            MAXIMUM_REACH_TO_MAINTAIN_PERFORMANCE,
            SIGNAL_UTILIZATION,
            FREQUENCY
        FROM ALL_INPUTS
        WHERE UPPER(TRIM(QUARTER)) = UPPER(TRIM(?))
          AND UPPER(TRIM(ACCOUNT_NAME)) = UPPER(TRIM(?))
          AND UPPER(TRIM(COALESCE(SUB_ACCOUNT, ''))) = UPPER(TRIM(?))
          AND UPPER(TRIM(COALESCE(CHANNEL, ''))) = UPPER(TRIM(?))
        ORDER BY
            SOURCE_PRIORITY ASC,
            CASE WHEN UPDATED_AT IS NOT NULL THEN 0 ELSE 1 END ASC,
            UPDATED_AT DESC NULLS LAST,
            TIMERANK ASC NULLS LAST
        LIMIT 1
        """,
        params=[quarter, account_name, sub_account, channel],
    ).collect()
    if not rows:
        raise ValueError(
            "No Forecasting Inputs match the selected quarter, account, "
            "campaign, and marketing channel."
        )
    row = rows[0]
    return {
        "campaign_budget": Decimal(str(row["CAMPAIGN_BUDGET"] or 0)),
        "cpm": Decimal(str(row["CPM"] or 0)),
        "planned_reach": Decimal(str(row["PLANNED_CAMPAIGN_REACH"] or 0)),
        "maximum_reach": Decimal(
            str(row["MAXIMUM_REACH_TO_MAINTAIN_PERFORMANCE"] or 0)
        ),
        "signal_utilization": Decimal(str(row["SIGNAL_UTILIZATION"] or 0)) / Decimal("100"),
        "frequency_at_max": Decimal(str(row["FREQUENCY"] or 0)),
    }
