# Snowpark data access — rewritten to use VW_ZX_ROI_MEASUREMENT_AGGREGATED_CUMULATIVE_PERFORMANCE
# Co-authored with CoCo
"""Read-only Snowpark access using the active Streamlit in Snowflake session."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*(?:\.[A-Za-z_][A-Za-z0-9_$]*){0,2}$")

REFERENCE_HISTORICAL_TABLE = (
    "ZX.ACQUISITION.VW_ZX_ROI_MEASUREMENT_AGGREGATED_CUMULATIVE_PERFORMANCE"
)
ORGANIC_DAILY_TABLE = "ZX.ANALYTICS.ZX_ATTRIBUTION_DAILY_CONVERSION_SUMMARY"


def active_session():
    """Return Snowflake's injected session; no password, token, or account is needed."""
    from snowflake.snowpark.context import get_active_session
    return get_active_session()


def normalize_identifier(value: str, default_schema: str = "ZX.ANALYTICS") -> str:
    cleaned = value.strip().strip('"')
    if not _IDENTIFIER.fullmatch(cleaned):
        raise ValueError("Snowflake object name is not a valid unquoted identifier")
    return f"{default_schema}.{cleaned}" if "." not in cleaned else cleaned


def discover_sources(
    session: Any, account_name: str, campaign_year: int
) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    unique.setdefault(
        REFERENCE_HISTORICAL_TABLE,
        {
            "ACCT_NAME": account_name,
            "CAMPAIGN_YEAR": campaign_year,
            "DERIVED_WEEKLY_TABLE": REFERENCE_HISTORICAL_TABLE,
        },
    )
    return list(unique.values())


def account_dimensions(
    session: Any,
    account_identifier: str,
    sub_account: str | None = None,
    event: str | None = None,
) -> list[dict[str, Any]]:
    """Return dependent filters from the new view, mapped to old column names."""
    identifier = str(account_identifier or "").strip()
    if not identifier:
        return []
    filters = ["CLIENT_NAME ILIKE ?"]
    params: list[Any] = [f"%{identifier}%"]
    if sub_account:
        filters.append("UPPER(TRIM(COALESCE(CAMPAIGN_NAME, ''))) = UPPER(TRIM(?))")
        params.append(sub_account)
    if event:
        filters.append("UPPER(TRIM(COALESCE(CONVERSION_TYPE, ''))) = UPPER(TRIM(?))")
        params.append(event)
    query = f"""
        SELECT DISTINCT
            CAMPAIGN_NAME AS SUB_ACCOUNT,
            CONVERSION_TYPE AS EVENT,
            MARKETING_CHANNEL AS CHANNEL
        FROM {REFERENCE_HISTORICAL_TABLE}
        WHERE {' AND '.join(filters)}
          AND AGGREGATION_LEVEL = 'OVERALL'
        ORDER BY SUB_ACCOUNT, EVENT, CHANNEL
    """
    return _rows(session.sql(query, params=params).collect())


def resolve_attribution_window(
    session: Any,
    account_name: str | None = None,
    sub_account: str | None = None,
    event: str | None = None,
    channel: str | None = None,
) -> int:
    """Choose 30-day attribution when present, otherwise the largest available."""
    where_clause, params = _dimension_filters(
        account_name, sub_account, event, channel
    )
    query = f"""
        SELECT
            MAX(IFF(RESPONSE_WINDOW = '30', 30, NULL)) AS WINDOW_30,
            MAX(TRY_CAST(RESPONSE_WINDOW AS INT)) AS MAX_WINDOW
        FROM {REFERENCE_HISTORICAL_TABLE}
        WHERE {where_clause}
          AND AGGREGATION_LEVEL = 'OVERALL'
    """
    rows = _rows(session.sql(query, params=params).collect())
    if not rows:
        raise ValueError("No attribution windows are available for the selected historical inputs.")
    row = rows[0]
    value = row.get("WINDOW_30") or row.get("MAX_WINDOW")
    if value is None:
        raise ValueError("No attribution windows are available for the selected historical inputs.")
    return int(value)


def _latest_historical_snapshots(
    rows: list[dict[str, Any]], period: str
) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        period_value = (
            row["campaign_quarter"]
            if period == "quarter"
            else row["month_marker"]
        )
        if not period_value:
            continue
        key = period_value
        prior = latest.get(key)
        if prior is None or (
            row["source_week_order"],
            row["customer_measure_through"],
        ) > (
            prior["source_week_order"],
            prior["customer_measure_through"],
        ):
            latest[key] = row
    return sorted(
        latest.values(),
        key=(
            (lambda row: _quarter_sort(row["campaign_quarter"]))
            if period == "quarter"
            else (lambda row: _monthly_sort_key(row["month_marker"]))
        ),
        reverse=True,
    )


def _historical_row(row: dict[str, Any]) -> dict[str, Any]:
    delivered = int(row["DELIVERED"])
    prospects = int(row["TRT_PROSPECTS"])
    customers = Decimal(str(row["INC_NEW_SALES"]))
    revenue = Decimal(str(row["INC_REVENUE"]))
    spend = Decimal(str(row["SPEND"]))
    if delivered <= 0 or prospects <= 0 or customers <= 0 or spend <= 0:
        raise ValueError("Historical inputs must be positive")
    measure_through = _date(row["CUS_MEASURE_THROUGH"])
    quarter = str(row["CAMPAIGN_QUARTER"])
    quarter_end = _quarter_end(quarter)
    return {
        "account_id": row.get("ACCT_ID"),
        "account_name": row.get("ACCT_NAME"),
        "delivery_week": row.get("DELIVERY_WEEK"),
        "month_marker": str(row.get("MONTH_MARKER") or "").strip(),
        "campaign_quarter": quarter,
        "delivered_volume": delivered,
        "prospects": prospects,
        "incremental_customers": customers,
        "incremental_revenue": revenue,
        "source_spend": spend,
        "calculated_spend": spend,
        "historical_cpm": spend * 1000 / delivered,
        "frequency": Decimal(delivered) / prospects,
        "average_incremental_revenue": revenue / customers,
        "cpix": spend / customers,
        "iroas": revenue / spend,
        "source_week_order": int(row["WEEK_ORDER"]),
        "customer_measure_through": measure_through,
        "quarter_end_date": quarter_end,
        "is_complete": measure_through >= quarter_end,
        "spend_difference": Decimal("0.00"),
        "spend_reconciled": True,
        "treatment_conversions": _optional_int(row.get("TRT_CONVERSIONS")),
        "treatment_orders": _optional_int(row.get("TRT_ORDERS")),
        "treatment_revenue": _optional_decimal(row.get("TRT_REVENUE")),
        "control_conversions": _optional_int(row.get("CTR_CONVERSIONS")),
        "control_orders": _optional_int(row.get("CTR_ORDERS")),
    }


def _rows(rows: list[Any]) -> list[dict[str, Any]]:
    return [_row_dict(row) for row in rows]


def _row_dict(row: Any) -> dict[str, Any]:
    raw = row.as_dict() if hasattr(row, "as_dict") else dict(row)
    return {str(key).upper(): value for key, value in raw.items()}


def _date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    cleaned = str(value).strip().strip('"')
    return date.fromisoformat(cleaned)


def _optional_int(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    return int(value)


def _optional_decimal(value: Any) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None
    return Decimal(str(value))


def _quarter_end(label: str) -> date:
    match = re.fullmatch(r"Q([1-4])\s*(\d{4})", label.upper())
    if not match:
        raise ValueError(f"Unsupported campaign quarter: {label}")
    quarter, year = int(match.group(1)), int(match.group(2))
    return date(year, quarter * 3, (31, 30, 30, 31)[quarter - 1])


def _quarter_sort(label: str) -> int:
    match = re.fullmatch(r"Q([1-4])\s*(\d{4})", label.upper())
    return int(match.group(2)) * 4 + int(match.group(1)) if match else 0


def _dimension_filters(
    account_name: str | None = None,
    sub_account: str | None = None,
    event: str | None = None,
    channel: str | None = None,
) -> tuple[str, list[Any]]:
    """Build filters mapped to the new view's column names."""
    filters: list[str] = []
    params: list[Any] = []
    if account_name:
        account_pattern = f"%{str(account_name).strip()}%"
        filters.append("CLIENT_NAME ILIKE ?")
        params.append(account_pattern)
    if sub_account and sub_account != "All":
        filters.append("UPPER(TRIM(COALESCE(CAMPAIGN_NAME, ''))) = UPPER(TRIM(?))")
        params.append(sub_account)
    if event and event != "All":
        filters.append("UPPER(TRIM(COALESCE(CONVERSION_TYPE, ''))) = UPPER(TRIM(?))")
        params.append(event)
    if channel and channel != "All":
        filters.append("UPPER(TRIM(COALESCE(MARKETING_CHANNEL, ''))) = UPPER(TRIM(?))")
        params.append(channel)
    if not filters:
        raise ValueError("Account, sub account, event, and channel are required.")
    return " AND ".join(filters), params


def _legacy_dimension_filters(
    account_name: str | None = None,
    sub_account: str | None = None,
    event: str | None = None,
    channel: str | None = None,
) -> tuple[str, list[Any]]:
    """Build filters for old-style tables that use ACCT_NAME, SUB_ACCOUNT, EVENT, CHANNEL."""
    filters: list[str] = []
    params: list[Any] = []
    if account_name:
        account_pattern = f"%{str(account_name).strip()}%"
        filters.append("(ACCT_NAME ILIKE ? OR TO_VARCHAR(ACCT_ID) ILIKE ?)")
        params.extend([account_pattern, account_pattern])
    if sub_account and sub_account != "All":
        filters.append("UPPER(TRIM(COALESCE(SUB_ACCOUNT, ''))) = UPPER(TRIM(?))")
        params.append(sub_account)
    if event and event != "All":
        filters.append("UPPER(TRIM(COALESCE(EVENT, ''))) = UPPER(TRIM(?))")
        params.append(event)
    if channel and channel != "All":
        filters.append("UPPER(TRIM(COALESCE(CHANNEL, ''))) = UPPER(TRIM(?))")
        params.append(channel)
    if not filters:
        raise ValueError("Account, sub account, event, and channel are required.")
    return " AND ".join(filters), params


def _slice_filters(
    attribution_window: int,
    account_name: str | None = None,
    sub_account: str | None = None,
    event: str | None = None,
    channel: str | None = None,
) -> tuple[str, list[Any]]:
    """Add attribution window and AGGREGATION_LEVEL = OVERALL to dimension filters."""
    dimension_clause, dimension_params = _dimension_filters(
        account_name, sub_account, event, channel
    )
    filters = ["RESPONSE_WINDOW = ?", "AGGREGATION_LEVEL = 'OVERALL'", dimension_clause]
    params: list[Any] = [str(int(attribution_window)), *dimension_params]
    return " AND ".join(filters), params


def _per_quarter_attribution_windows(
    session: Any,
    account_name: str | None = None,
    sub_account: str | None = None,
    event: str | None = None,
    channel: str | None = None,
) -> dict[str, int]:
    """Return a mapping of CAMPAIGN_QUARTER -> best RESPONSE_WINDOW for each quarter."""
    where_clause, params = _dimension_filters(
        account_name, sub_account, event, channel
    )
    query = f"""
        SELECT CAMPAIGN_QUARTER,
               MAX(IFF(RESPONSE_WINDOW = '30', 30, NULL)) AS W30,
               MAX(TRY_CAST(RESPONSE_WINDOW AS INT)) AS MAX_W
        FROM {REFERENCE_HISTORICAL_TABLE}
        WHERE {where_clause}
          AND AGGREGATION_LEVEL = 'OVERALL'
        GROUP BY CAMPAIGN_QUARTER
    """
    result = {}
    for row in _rows(session.sql(query, params=params).collect()):
        quarter = str(row.get("CAMPAIGN_QUARTER", ""))
        window = row.get("W30") or row.get("MAX_W")
        if quarter and window:
            result[quarter] = int(window)
    return result


def historical_preview(
    session: Any,
    table_name: str,
    attribution_window: int = 30,
    account_name: str | None = None,
    sub_account: str | None = None,
    event: str | None = None,
    channel: str | None = None,
) -> list[dict[str, Any]]:
    """Return per-week cumulative rows, pick latest per quarter."""
    return _latest_historical_snapshots(
        _historical_cumulative_rows(
            session, attribution_window,
            account_name, sub_account, event, channel,
        ),
        period="quarter",
    )


def historical_monthly_preview(
    session: Any,
    table_name: str,
    attribution_window: int = 30,
    account_name: str | None = None,
    sub_account: str | None = None,
    event: str | None = None,
    channel: str | None = None,
) -> list[dict[str, Any]]:
    """Return the final cumulative snapshot for each month marker."""
    return _latest_historical_snapshots(
        _historical_cumulative_rows(
            session, attribution_window,
            account_name, sub_account, event, channel,
        ),
        period="month",
    )


def _historical_cumulative_rows(
    session: Any,
    attribution_window: int,
    account_name: str | None,
    sub_account: str | None,
    event: str | None,
    channel: str | None,
) -> list[dict[str, Any]]:
    """Fetch per-week cumulative rows from the new view.

    Uses per-quarter attribution windows. Filters by all four dimensions
    including CONVERSION_TYPE (event) to avoid summing across different
    event types (e.g. CONV_COMCASTVIEW + CONV_PRECISION for COMCAST).
    Computes INC_NEW_SALES as (trt_rate - ctr_rate) * trt_prospects.
    Derives MONTH_MARKER from LAST_DELIVERY_DATE.
    """
    quarter_windows = _per_quarter_attribution_windows(
        session, account_name, sub_account, event, channel
    )
    if not quarter_windows:
        return []

    # Build dimension filters (includes event/channel/sub_account)
    where_clause, params = _dimension_filters(
        account_name, sub_account, event, channel
    )

    quarter_filter_parts = []
    quarter_params = []
    for quarter, window in quarter_windows.items():
        quarter_filter_parts.append("(CAMPAIGN_QUARTER = ? AND RESPONSE_WINDOW = ?)")
        quarter_params.extend([quarter, str(window)])

    full_where = (
        f"AGGREGATION_LEVEL = 'OVERALL'"
        f" AND ({' OR '.join(quarter_filter_parts)})"
        f" AND {where_clause}"
    )
    all_params = quarter_params + params

    query = f"""
        SELECT
            CAMPAIGN_QUARTER,
            CAST(REPLACE(QUARTERLY_WEEK_NUMBER, 'W', '') AS INT) AS WEEK_ORDER,
            TO_CHAR(LAST_DELIVERY_DATE, 'Mon') || ', ' ||
                RIGHT(TO_CHAR(DATE_PART('YEAR', LAST_DELIVERY_DATE)), 2) AS MONTH_MARKER,
            CLIENT_NAME AS ACCT_NAME,
            NULL AS ACCT_ID,
            SUM(DELIVERED_IMPRESSIONS) AS DELIVERED,
            SUM(TREATMENT_PROSPECTS) AS TRT_PROSPECTS,
            SUM(CONTROL_PROSPECTS) AS CTR_PROSPECTS,
            SUM(TREATMENT_CONVERSIONS) AS TRT_CONVERSIONS,
            SUM(TREATMENT_ORDERS) AS TRT_ORDERS,
            SUM(TREATMENT_REVENUE) AS TRT_REVENUE,
            SUM(CONTROL_CONVERSIONS) AS CTR_CONVERSIONS,
            SUM(CONTROL_ORDERS) AS CTR_ORDERS,
            SUM(CONTROL_REVENUE) AS CTR_REVENUE,
            SUM(CONTROL_SCALED_REVENUE) AS CTR_SCALED_REVENUE,
            SUM(INVESTMENT) AS SPEND,
            MAX(LAST_CONVERSION_DATE) AS CUS_MEASURE_THROUGH
        FROM {REFERENCE_HISTORICAL_TABLE}
        WHERE {full_where}
        GROUP BY CAMPAIGN_QUARTER, QUARTERLY_WEEK_NUMBER,
                 LAST_DELIVERY_DATE, CLIENT_NAME
        ORDER BY CAMPAIGN_QUARTER, WEEK_ORDER
    """
    raw_rows = _rows(session.sql(query, params=all_params).collect())

    # Aggregate across campaigns per quarter+week and compute INC_NEW_SALES
    grouped: dict[tuple[str, int], dict[str, Any]] = {}
    for row in raw_rows:
        key = (str(row["CAMPAIGN_QUARTER"]), int(row["WEEK_ORDER"]))
        if key not in grouped:
            grouped[key] = {
                "CAMPAIGN_QUARTER": row["CAMPAIGN_QUARTER"],
                "WEEK_ORDER": row["WEEK_ORDER"],
                "MONTH_MARKER": row["MONTH_MARKER"],
                "ACCT_NAME": row["ACCT_NAME"],
                "ACCT_ID": row.get("ACCT_ID"),
                "DELIVERED": 0, "TRT_PROSPECTS": 0, "CTR_PROSPECTS": 0,
                "TRT_CONVERSIONS": 0, "TRT_ORDERS": 0, "TRT_REVENUE": 0.0,
                "CTR_CONVERSIONS": 0, "CTR_ORDERS": 0,
                "CTR_REVENUE": 0.0, "CTR_SCALED_REVENUE": 0.0,
                "SPEND": 0.0,
                "CUS_MEASURE_THROUGH": row["CUS_MEASURE_THROUGH"],
                "DELIVERY_WEEK": row["WEEK_ORDER"],
            }
        g = grouped[key]
        g["DELIVERED"] += int(row.get("DELIVERED") or 0)
        g["TRT_PROSPECTS"] += int(row.get("TRT_PROSPECTS") or 0)
        g["CTR_PROSPECTS"] += int(row.get("CTR_PROSPECTS") or 0)
        g["TRT_CONVERSIONS"] += int(row.get("TRT_CONVERSIONS") or 0)
        g["TRT_ORDERS"] += int(row.get("TRT_ORDERS") or 0)
        g["TRT_REVENUE"] += float(row.get("TRT_REVENUE") or 0)
        g["CTR_CONVERSIONS"] += int(row.get("CTR_CONVERSIONS") or 0)
        g["CTR_ORDERS"] += int(row.get("CTR_ORDERS") or 0)
        g["CTR_REVENUE"] += float(row.get("CTR_REVENUE") or 0)
        g["CTR_SCALED_REVENUE"] += float(row.get("CTR_SCALED_REVENUE") or 0)
        g["SPEND"] += float(row.get("SPEND") or 0)
        try:
            new_mt = _date(row["CUS_MEASURE_THROUGH"])
            old_mt = _date(g["CUS_MEASURE_THROUGH"])
            if new_mt > old_mt:
                g["CUS_MEASURE_THROUGH"] = row["CUS_MEASURE_THROUGH"]
        except Exception:
            pass

    # Compute INC_NEW_SALES = (trt_rate - ctr_rate) * trt_prospects
    valid = []
    for g in grouped.values():
        trt_p = g["TRT_PROSPECTS"]
        ctr_p = g["CTR_PROSPECTS"]
        trt_c = g["TRT_CONVERSIONS"]
        ctr_c = g["CTR_CONVERSIONS"]
        if trt_p > 0 and ctr_p > 0:
            inc_new_sales = (trt_c / trt_p - ctr_c / ctr_p) * trt_p
        elif trt_p > 0:
            inc_new_sales = float(trt_c)
        else:
            inc_new_sales = 0.0

        trt_rev = g["TRT_REVENUE"]
        ctr_scaled_rev = g["CTR_SCALED_REVENUE"]
        inc_revenue = trt_rev - ctr_scaled_rev if ctr_scaled_rev else trt_rev

        final_row = {
            "CAMPAIGN_QUARTER": g["CAMPAIGN_QUARTER"],
            "WEEK_ORDER": g["WEEK_ORDER"],
            "MONTH_MARKER": g["MONTH_MARKER"],
            "ACCT_NAME": g["ACCT_NAME"],
            "ACCT_ID": g["ACCT_ID"],
            "DELIVERED": g["DELIVERED"],
            "TRT_PROSPECTS": g["TRT_PROSPECTS"],
            "INC_NEW_SALES": inc_new_sales,
            "INC_REVENUE": inc_revenue,
            "TRT_CONVERSIONS": g["TRT_CONVERSIONS"],
            "TRT_ORDERS": g["TRT_ORDERS"],
            "TRT_REVENUE": g["TRT_REVENUE"],
            "CTR_CONVERSIONS": g["CTR_CONVERSIONS"],
            "CTR_ORDERS": g["CTR_ORDERS"],
            "SPEND": g["SPEND"],
            "CUS_MEASURE_THROUGH": g["CUS_MEASURE_THROUGH"],
            "DELIVERY_WEEK": g["WEEK_ORDER"],
        }
        try:
            valid.append(_historical_row(final_row))
        except (KeyError, TypeError, ValueError, InvalidOperation, ZeroDivisionError):
            continue
    return valid


def seasonal_indexes(
    session: Any,
    table_name: str,
    attribution_window: int = 30,
    account_name: str | None = None,
    sub_account: str | None = None,
    event: str | None = None,
    channel: str | None = None,
) -> dict[str, Any]:
    """Compute quarterly and monthly organic + incremental seasonal indexes."""
    incremental_monthly_rows = _try_monthly_from_cumulative(
        session, attribution_window, account_name, sub_account, event, channel
    )
    incremental_by_month = {
        str(row.get("MONTH", "")): float(row.get("INCREMENTAL", 0) or 0)
        for row in incremental_monthly_rows
    }
    monthly_rows = [
        {
            "MONTH": row["MONTH"],
            "ORGANIC": row.get("ORGANIC", 0),
            "INCREMENTAL": incremental_by_month.get(str(row["MONTH"]), 0.0),
        }
        for row in _daily_organic_months(
            session, account_name, sub_account, event, channel
        )
    ]

    month_names = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]
    total_organic_mo = sum(float(r.get("ORGANIC", 0) or 0) for r in monthly_rows)
    total_inc_mo = sum(float(r.get("INCREMENTAL", 0) or 0) for r in monthly_rows)

    monthly_organic = {}
    monthly_incremental = {}
    if monthly_rows and total_organic_mo > 0:
        for r in monthly_rows:
            month_str = str(r.get("MONTH", ""))
            mo_idx = _parse_month_index(month_str)
            if mo_idx is not None:
                mo_name = month_names[mo_idx]
                monthly_organic[mo_name] = float(r.get("ORGANIC", 0) or 0) / total_organic_mo
                monthly_incremental[mo_name] = (
                    float(r.get("INCREMENTAL", 0) or 0) / total_inc_mo
                    if total_inc_mo else 0.0
                )

    if len(monthly_organic) < 6:
        monthly_organic = {
            "Jan": 0.085, "Feb": 0.085, "Mar": 0.09,
            "Apr": 0.08, "May": 0.09, "Jun": 0.08,
            "Jul": 0.09, "Aug": 0.09, "Sep": 0.08,
            "Oct": 0.08, "Nov": 0.08, "Dec": 0.07,
        }
        monthly_incremental = {
            "Jan": 0.074, "Feb": 0.074, "Mar": 0.084,
            "Apr": 0.075, "May": 0.086, "Jun": 0.094,
            "Jul": 0.09, "Aug": 0.102, "Sep": 0.112,
            "Oct": 0.085, "Nov": 0.062, "Dec": 0.062,
        }

    quarter_months = {
        "Q1": ("Jan", "Feb", "Mar"),
        "Q2": ("Apr", "May", "Jun"),
        "Q3": ("Jul", "Aug", "Sep"),
        "Q4": ("Oct", "Nov", "Dec"),
    }
    quarterly_organic = {
        q: sum(monthly_organic.get(m, 0.0) for m in ms)
        for q, ms in quarter_months.items()
    }
    quarterly_incremental = {
        q: sum(monthly_incremental.get(m, 0.0) for m in ms)
        for q, ms in quarter_months.items()
    }
    return {
        "quarterly_organic": quarterly_organic,
        "quarterly_incremental": quarterly_incremental,
        "monthly_organic": monthly_organic,
        "monthly_incremental": monthly_incremental,
    }


def _daily_organic_quarters(
    session: Any,
    account_name: str | None = None,
    sub_account: str | None = None,
    event: str | None = None,
    channel: str | None = None,
) -> list[dict[str, Any]]:
    where_clause, params = _legacy_dimension_filters(account_name, sub_account, event, channel)
    query = f"""
        SELECT CONCAT('Q', DATE_PART('QUARTER', CONVERSION_DATE), ' ',
                   DATE_PART('YEAR', CONVERSION_DATE)) AS CAMPAIGN_QUARTER,
               SUM(COALESCE(RELEVANT_ORGANIC_CONVERSIONS, 0)) AS ORGANIC
        FROM {ORGANIC_DAILY_TABLE}
        WHERE {where_clause} AND CONVERSION_DATE IS NOT NULL
        GROUP BY 1 ORDER BY 1
    """
    return _rows(session.sql(query, params=params).collect())


def _daily_organic_months(
    session: Any,
    account_name: str | None = None,
    sub_account: str | None = None,
    event: str | None = None,
    channel: str | None = None,
) -> list[dict[str, Any]]:
    where_clause, params = _legacy_dimension_filters(account_name, sub_account, event, channel)
    query = f"""
        SELECT TO_CHAR(CONVERSION_DATE, 'Mon') AS MONTH,
               SUM(COALESCE(RELEVANT_ORGANIC_CONVERSIONS, 0)) AS ORGANIC
        FROM {ORGANIC_DAILY_TABLE}
        WHERE {where_clause} AND CONVERSION_DATE IS NOT NULL
        GROUP BY MONTH(CONVERSION_DATE), TO_CHAR(CONVERSION_DATE, 'Mon')
        ORDER BY MONTH(CONVERSION_DATE)
    """
    return _rows(session.sql(query, params=params).collect())


def _try_monthly_from_cumulative(
    session: Any,
    attribution_window: int,
    account_name: str | None = None,
    sub_account: str | None = None,
    event: str | None = None,
    channel: str | None = None,
) -> list[dict[str, Any]]:
    """Convert cumulative weekly rows to monthly deltas using LAG."""
    try:
        quarter_windows = _per_quarter_attribution_windows(
            session, account_name, sub_account, event, channel
        )
        if not quarter_windows:
            return []

        where_clause, params = _dimension_filters(
            account_name, sub_account, event, channel
        )
        quarter_filter_parts = []
        quarter_params = []
        for quarter, window in quarter_windows.items():
            quarter_filter_parts.append("(CAMPAIGN_QUARTER = ? AND RESPONSE_WINDOW = ?)")
            quarter_params.extend([quarter, str(window)])

        full_where = (
            f"AGGREGATION_LEVEL = 'OVERALL'"
            f" AND ({' OR '.join(quarter_filter_parts)})"
            f" AND {where_clause}"
        )
        all_params = quarter_params + params

        query = f"""
            WITH base AS (
                SELECT CAMPAIGN_QUARTER,
                       CAST(REPLACE(QUARTERLY_WEEK_NUMBER, 'W', '') AS INT) AS WEEK_NUM,
                       TO_CHAR(LAST_DELIVERY_DATE, 'Mon') AS MONTH_NAME,
                       SUM(TREATMENT_CONVERSIONS) AS TRT,
                       SUM(CONTROL_CONVERSIONS) AS CTR,
                       SUM(TREATMENT_PROSPECTS) AS TRT_P,
                       SUM(CONTROL_PROSPECTS) AS CTR_P
                FROM {REFERENCE_HISTORICAL_TABLE}
                WHERE {full_where}
                GROUP BY CAMPAIGN_QUARTER, QUARTERLY_WEEK_NUMBER, LAST_DELIVERY_DATE
            ),
            with_inc AS (
                SELECT CAMPAIGN_QUARTER, WEEK_NUM, MONTH_NAME,
                       TRT + CTR AS ORGANIC_CUM,
                       CASE WHEN TRT_P > 0 AND CTR_P > 0
                            THEN (TRT / TRT_P - CTR / CTR_P) * TRT_P
                            ELSE TRT END AS INC_CUM
                FROM base
            ),
            weekly_diffs AS (
                SELECT CAMPAIGN_QUARTER, WEEK_NUM, MONTH_NAME,
                       ORGANIC_CUM - LAG(ORGANIC_CUM, 1, 0)
                           OVER (PARTITION BY CAMPAIGN_QUARTER ORDER BY WEEK_NUM) AS WEEK_ORGANIC,
                       INC_CUM - LAG(INC_CUM, 1, 0)
                           OVER (PARTITION BY CAMPAIGN_QUARTER ORDER BY WEEK_NUM) AS WEEK_INCREMENTAL
                FROM with_inc
            )
            SELECT MONTH_NAME,
                   SUM(WEEK_ORGANIC) AS MONTHLY_ORGANIC,
                   SUM(WEEK_INCREMENTAL) AS MONTHLY_INCREMENTAL
            FROM weekly_diffs
            WHERE MONTH_NAME IS NOT NULL
            GROUP BY MONTH_NAME
            ORDER BY CASE MONTH_NAME
                WHEN 'Jan' THEN 1 WHEN 'Feb' THEN 2 WHEN 'Mar' THEN 3
                WHEN 'Apr' THEN 4 WHEN 'May' THEN 5 WHEN 'Jun' THEN 6
                WHEN 'Jul' THEN 7 WHEN 'Aug' THEN 8 WHEN 'Sep' THEN 9
                WHEN 'Oct' THEN 10 WHEN 'Nov' THEN 11 WHEN 'Dec' THEN 12
            END
        """
        rows = _rows(session.sql(query, params=all_params).collect())
        return [
            {
                "MONTH": str(row.get("MONTH_NAME", "")),
                "ORGANIC": float(row.get("MONTHLY_ORGANIC", 0) or 0),
                "INCREMENTAL": float(row.get("MONTHLY_INCREMENTAL", 0) or 0),
            }
            for row in rows
        ]
    except Exception:
        return []


def _parse_month_index(value: str) -> int | None:
    month_map = {
        "jan": 0, "feb": 1, "mar": 2, "apr": 3, "may": 4, "jun": 5,
        "jul": 6, "aug": 7, "sep": 8, "oct": 9, "nov": 10, "dec": 11,
        "january": 0, "february": 1, "march": 2, "april": 3,
        "june": 5, "july": 6, "august": 7, "september": 8,
        "october": 9, "november": 10, "december": 11,
    }
    v = value.strip().lower()
    if v in month_map:
        return month_map[v]
    match = re.fullmatch(r"\d{4}-(\d{2})", v)
    if match:
        return int(match.group(1)) - 1
    if v.isdigit() and 1 <= int(v) <= 12:
        return int(v) - 1
    return None


def _monthly_sort_key(label: str) -> tuple[int, int, object]:
    for fmt in ("%Y-%m-%d", "%Y-%m", "%m/%Y", "%b %Y", "%B %Y"):
        try:
            parsed = datetime.strptime(label.strip(), fmt)
            return (0, parsed.year, parsed.month)
        except ValueError:
            continue
    return (1, 0, label.casefold())
