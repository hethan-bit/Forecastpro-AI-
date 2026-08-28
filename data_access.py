# Snowpark data access with seasonal index computation from organic/incremental metrics
# Co-authored with CoCo
"""Read-only Snowpark access using the active Streamlit in Snowflake session."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*(?:\.[A-Za-z_][A-Za-z0-9_$]*){0,2}$")

REFERENCE_HISTORICAL_TABLE = (
    "ZX.ANALYTICS.ZX_ATTRIBUTION_CUMULATIVE_WEEKLY_PERFORMANCE"
)


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
    query = """
        SELECT DISTINCT ACCT_NAME, SUB_ACCOUNT, CHANNEL, EVENT, CAMPAIGN_YEAR, CAMPAIGN_QTR,
          GLOBAL_VAR_SETTINGS:"DERIVED_WEEKLY_TABLE"::STRING AS DERIVED_WEEKLY_TABLE
        FROM ZX.ANALYTICS.ATTRIBUTION_CONFIG_OBJECTS
        WHERE ACCT_NAME ILIKE ? AND CAMPAIGN_YEAR = ?
        ORDER BY ACCT_NAME, SUB_ACCOUNT
    """
    rows = _rows(
        session.sql(query, params=[f"%{account_name}%", int(campaign_year)]).collect()
    )
    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.get("DERIVED_WEEKLY_TABLE"):
            table = normalize_identifier(str(row["DERIVED_WEEKLY_TABLE"]))
            unique[table] = {**row, "DERIVED_WEEKLY_TABLE": table}
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
    """Return four-dimension dependent filters from the fixed historical source."""
    identifier = str(account_identifier or "").strip()
    if not identifier:
        return []
    filters = [
        "(ACCT_NAME ILIKE ? OR TO_VARCHAR(ACCT_ID) ILIKE ?)",
    ]
    params: list[Any] = [f"%{identifier}%", f"%{identifier}%"]
    if sub_account:
        filters.append("UPPER(TRIM(COALESCE(SUB_ACCOUNT, ''))) = UPPER(TRIM(?))")
        params.append(sub_account)
    if event:
        filters.append("UPPER(TRIM(COALESCE(EVENT, ''))) = UPPER(TRIM(?))")
        params.append(event)
    query = f"""
        SELECT DISTINCT SUB_ACCOUNT, EVENT, CHANNEL
        FROM {REFERENCE_HISTORICAL_TABLE}
        WHERE {' AND '.join(filters)}
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
    """Choose 30-day attribution when present, otherwise the largest available.

    Attribution Window is intentionally resolved after the four authoritative
    dimensions are selected; it is not a user input and campaign name is never
    considered by this lookup.
    """
    where_clause, params = _dimension_filters(
        account_name, sub_account, event, channel
    )
    query = f"""
        SELECT
            MAX(IFF(ATTRIBUTION_WINDOW = 30, 30, NULL)) AS WINDOW_30,
            MAX(ATTRIBUTION_WINDOW) AS MAX_WINDOW
        FROM {REFERENCE_HISTORICAL_TABLE}
        WHERE {where_clause}
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
    return date.fromisoformat(str(value))


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
    """Build the four authoritative historical-dimension filters."""
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
    """Add the internally resolved attribution window to the four dimensions."""
    dimension_clause, dimension_params = _dimension_filters(
        account_name, sub_account, event, channel
    )
    filters = ["ATTRIBUTION_WINDOW = ?", dimension_clause]
    params: list[Any] = [int(attribution_window), *dimension_params]

    return " AND ".join(filters), params


def historical_preview(
    session: Any,
    table_name: str,
    attribution_window: int = 30,
    account_name: str | None = None,
    sub_account: str | None = None,
    event: str | None = None,
    channel: str | None = None,
) -> list[dict[str, Any]]:
    return _latest_historical_snapshots(
        _historical_rows(
            session,
            table_name,
            attribution_window,
            account_name,
            sub_account,
            event,
            channel,
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
        _historical_rows(
            session,
            table_name,
            attribution_window,
            account_name,
            sub_account,
            event,
            channel,
        ),
        period="month",
    )


def _historical_rows(
    session: Any,
    table_name: str,
    attribution_window: int,
    account_name: str | None,
    sub_account: str | None,
    event: str | None,
    channel: str | None,
) -> list[dict[str, Any]]:
    table = normalize_identifier(table_name)
    conversion_columns = (
        ", SUM(TRT_CONVERSIONS) AS TRT_CONVERSIONS,"
        " SUM(TRT_ORDERS) AS TRT_ORDERS, SUM(TRT_REVENUE) AS TRT_REVENUE,"
        " SUM(CTR_CONVERSIONS) AS CTR_CONVERSIONS, SUM(CTR_ORDERS) AS CTR_ORDERS"
        if table == REFERENCE_HISTORICAL_TABLE
        else ""
    )
    where_clause, params = _slice_filters(
        attribution_window,
        account_name,
        sub_account,
        event,
        channel,
    )
    query = f"""
        SELECT CAMPAIGN_QUARTER, MONTH_MARKER,
          SUM(DELIVERED) AS DELIVERED,
          SUM(TRT_PROSPECTS) AS TRT_PROSPECTS,
          SUM(INC_NEW_SALES) AS INC_NEW_SALES,
          SUM(INC_REVENUE) AS INC_REVENUE{conversion_columns},
          SUM(SPEND) AS SPEND,
          MAX(CUS_MEASURE_THROUGH) AS CUS_MEASURE_THROUGH,
          DELIVERY_WEEK AS WEEK_ORDER
        FROM {table}
        WHERE {where_clause}
        GROUP BY CAMPAIGN_QUARTER, MONTH_MARKER, DELIVERY_WEEK
        ORDER BY CAMPAIGN_QUARTER, DELIVERY_WEEK
    """
    valid = []
    for source in _rows(session.sql(query, params=params).collect()):
        try:
            valid.append(_historical_row(source))
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
    """Compute quarterly and monthly organic + incremental seasonal indexes.

    Organic = TRT_CONVERSIONS + CTR_CONVERSIONS (total business conversions).
    Incremental = INC_NEW_SALES (attributed incremental customers only).

    Uses the same four-dimension historical slice as the forecast inputs.
    """
    table = normalize_identifier(table_name)
    where_clause, params = _slice_filters(
        attribution_window,
        account_name,
        sub_account,
        event,
        channel,
    )


    # Quarterly: organic (TRT + CTR) and incremental by CAMPAIGN_QUARTER
    qtr_query = f"""
        WITH latest AS (
            SELECT CAMPAIGN_QUARTER,
                   SUM(COALESCE(TRT_CONVERSIONS, 0)) + SUM(COALESCE(CTR_CONVERSIONS, 0)) AS ORGANIC,
                   SUM(COALESCE(INC_NEW_SALES, 0)) AS INCREMENTAL,
                   ROW_NUMBER() OVER (
                       PARTITION BY CAMPAIGN_QUARTER
                       ORDER BY DELIVERY_WEEK DESC
                   ) AS rn
            FROM {table}
            WHERE {where_clause}
            GROUP BY CAMPAIGN_QUARTER, DELIVERY_WEEK
        )
        SELECT CAMPAIGN_QUARTER, ORGANIC, INCREMENTAL
        FROM latest WHERE rn = 1
        ORDER BY CAMPAIGN_QUARTER
    """
    qtr_rows = _rows(
        session.sql(qtr_query, params=params).collect()
    )

    # Seasonal allocation must use one value per calendar quarter. Restrict to
    # the latest four campaign quarters before normalizing, otherwise an older
    # Q1/Q2/Q3/Q4 can remain in the denominator after its display key is replaced.
    qtr_rows = sorted(
        (
            row
            for row in qtr_rows
            if _quarter_sort(str(row.get("CAMPAIGN_QUARTER", ""))) > 0
        ),
        key=lambda row: _quarter_sort(str(row.get("CAMPAIGN_QUARTER", ""))),
        reverse=True,
    )[:4]

    # Monthly: try derived table first, then fall back to cumulative weekly
    monthly_rows = _try_monthly_from_derived(
        session, table, attribution_window, account_name, sub_account, event, channel
    )
    if not monthly_rows or all(float(r.get("ORGANIC", 0) or 0) == 0 for r in monthly_rows):
        monthly_rows = _try_monthly_from_cumulative(
            session, attribution_window, account_name, sub_account, event, channel
        )

    # Quarterly percentages
    # If fewer than 4 quarters of data, use the standard seasonal benchmarks
    # from the forecasting template (prevents 100% allocation to a single quarter)
    total_organic_qtr = sum(float(r.get("ORGANIC", 0) or 0) for r in qtr_rows)
    total_inc_qtr = sum(float(r.get("INCREMENTAL", 0) or 0) for r in qtr_rows)

    distinct_quarters = set()
    for r in qtr_rows:
        match = re.fullmatch(r"Q([1-4])\s*\d{4}", str(r.get("CAMPAIGN_QUARTER", "")).upper())
        if match:
            distinct_quarters.add(match.group(1))

    if len(distinct_quarters) < 4:
        # Standard seasonal benchmarks from the forecasting template
        quarterly_organic = {"Q1": 0.26, "Q2": 0.25, "Q3": 0.26, "Q4": 0.23}
        quarterly_incremental = {"Q1": 0.232, "Q2": 0.255, "Q3": 0.304, "Q4": 0.209}
    else:
        quarterly_organic = {}
        quarterly_incremental = {}
        for r in qtr_rows:
            qtr_label = str(r["CAMPAIGN_QUARTER"])
            match = re.fullmatch(r"Q([1-4])\s*\d{4}", qtr_label.upper())
            if match:
                q_key = f"Q{match.group(1)}"
                quarterly_organic[q_key] = (
                    float(r.get("ORGANIC", 0) or 0) / total_organic_qtr
                    if total_organic_qtr else 0.25
                )
                quarterly_incremental[q_key] = (
                    float(r.get("INCREMENTAL", 0) or 0) / total_inc_qtr
                    if total_inc_qtr else 0.25
                )

    # Monthly percentages — ALWAYS try to compute from actual data
    # regardless of how many quarters exist
    month_names = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]

    # Compute monthly from monthly_rows (derived or cumulative)
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
                monthly_organic[mo_name] = (
                    float(r.get("ORGANIC", 0) or 0) / total_organic_mo
                )
                monthly_incremental[mo_name] = (
                    float(r.get("INCREMENTAL", 0) or 0) / total_inc_mo
                    if total_inc_mo else 0.0
                )

    # If we got fewer than 6 months of data, fall back to template benchmarks
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
    for q in ["Q1", "Q2", "Q3", "Q4"]:
        quarterly_organic.setdefault(q, 0.25)
        quarterly_incremental.setdefault(q, 0.25)

    return {
        "quarterly_organic": quarterly_organic,
        "quarterly_incremental": quarterly_incremental,
        "monthly_organic": monthly_organic,
        "monthly_incremental": monthly_incremental,
    }


def _try_monthly_from_derived(
    session: Any,
    table: str,
    attribution_window: int,
    account_name: str | None = None,
    sub_account: str | None = None,
    event: str | None = None,
    channel: str | None = None,
) -> list[dict[str, Any]]:
    """Try to get monthly data from the selected four-dimension slice."""
    try:
        where_clause, params = _slice_filters(
            attribution_window,
            account_name,
            sub_account,
            event,
            channel,
        )
        query = f"""
            WITH latest AS (
                SELECT DERIVED_MONTH,
                       SUM(COALESCE(MONTHLY_TRT_CONVERSIONS, 0)) + SUM(COALESCE(MONTHLY_CTR_CONVERSIONS, 0)) AS ORGANIC,
                       SUM(COALESCE(MONTHLY_INC_NEW_SALES, 0)) AS INCREMENTAL,
                       ROW_NUMBER() OVER (
                           PARTITION BY DERIVED_MONTH
                           ORDER BY DELIVERY_WEEK DESC
                       ) AS rn
                FROM {table}
                WHERE {where_clause}
                  AND DERIVED_MONTH IS NOT NULL
                GROUP BY DERIVED_MONTH, DELIVERY_WEEK
            )
            SELECT DERIVED_MONTH AS MONTH, ORGANIC, INCREMENTAL
            FROM latest WHERE rn = 1
            ORDER BY DERIVED_MONTH
        """
        return _rows(session.sql(query, params=params).collect())
    except Exception:
        return []


def _try_monthly_from_cumulative(
    session: Any,
    attribution_window: int,
    account_name: str | None = None,
    sub_account: str | None = None,
    event: str | None = None,
    channel: str | None = None,
) -> list[dict[str, Any]]:
    """Convert cumulative weekly rows to monthly deltas within each campaign quarter."""
    try:
        where_clause, params = _slice_filters(
            attribution_window,
            account_name,
            sub_account,
            event,
            channel,
        )
        query = f"""
            WITH weekly_rollup AS (
                SELECT CAMPAIGN_QUARTER, DELIVERY_WEEK, MONTH_MARKER,
                       SUM(COALESCE(TRT_CONVERSIONS, 0)) AS TRT,
                       SUM(COALESCE(CTR_CONVERSIONS, 0)) AS CTR,
                       SUM(COALESCE(INC_NEW_SALES, 0)) AS INC
                FROM {REFERENCE_HISTORICAL_TABLE}
                WHERE {where_clause}
                GROUP BY CAMPAIGN_QUARTER, DELIVERY_WEEK, MONTH_MARKER
            ),
            weekly_diffs AS (
                SELECT CAMPAIGN_QUARTER, DELIVERY_WEEK, MONTH_MARKER, TRT, CTR, INC,
                       LAG(TRT, 1, 0)
                           OVER (PARTITION BY CAMPAIGN_QUARTER ORDER BY DELIVERY_WEEK) AS PREV_TRT,
                       LAG(CTR, 1, 0)
                           OVER (PARTITION BY CAMPAIGN_QUARTER ORDER BY DELIVERY_WEEK) AS PREV_CTR,
                       LAG(INC, 1, 0)
                           OVER (PARTITION BY CAMPAIGN_QUARTER ORDER BY DELIVERY_WEEK) AS PREV_INC
                FROM weekly_rollup
            ),
            weekly_increments AS (
                SELECT MONTH_MARKER,
                       (TRT - PREV_TRT) + (CTR - PREV_CTR) AS WEEK_ORGANIC,
                       INC - PREV_INC AS WEEK_INCREMENTAL
                FROM weekly_diffs
            )
            SELECT SPLIT_PART(MONTH_MARKER, ', ', 1) AS MONTH_NAME,
                   SUM(WEEK_ORGANIC) AS MONTHLY_ORGANIC,
                   SUM(WEEK_INCREMENTAL) AS MONTHLY_INCREMENTAL
            FROM weekly_increments
            WHERE MONTH_MARKER IS NOT NULL
            GROUP BY MONTH_NAME
            ORDER BY CASE MONTH_NAME
                WHEN 'Jan' THEN 1 WHEN 'Feb' THEN 2 WHEN 'Mar' THEN 3
                WHEN 'Apr' THEN 4 WHEN 'May' THEN 5 WHEN 'Jun' THEN 6
                WHEN 'Jul' THEN 7 WHEN 'Aug' THEN 8 WHEN 'Sep' THEN 9
                WHEN 'Oct' THEN 10 WHEN 'Nov' THEN 11 WHEN 'Dec' THEN 12
            END
        """
        rows = _rows(session.sql(query, params=params).collect())
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
    """Parse a month string to 0-based index."""
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
 

     


    # Monthly cumulative snapshots are converted to quarter-scoped month-over-month deltas.
def monthly_cumulative_deltas(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(
        rows,
        key=lambda row: (
            _quarter_sort(str(row.get("campaign_quarter") or "")),
            _monthly_sort_key(str(row.get("month_marker") or "")),
            int(row.get("source_week_order") or 0),
        ),
    )
    previous: dict[str, dict[str, Any]] = {}
    delta_fields = (
        ("incremental_customers", "monthly_incremental_customers"),
        ("incremental_revenue", "monthly_incremental_revenue"),
        ("treatment_conversions", "monthly_treatment_conversions"),
        ("control_conversions", "monthly_control_conversions"),
    )
    result: list[dict[str, Any]] = []
    for row in ordered:
        item = dict(row)
        key = str(row.get("campaign_quarter") or "")
        prior = previous.get(key)
        for source_field, delta_field in delta_fields:
            current = row.get(source_field)
            prior_value = prior.get(source_field) if prior else None
            if current is None:
                item[delta_field] = None
            elif prior_value is None:
                item[delta_field] = current
            else:
                item[delta_field] = current - prior_value
        previous[key] = row
        result.append(item)
    return result

def _monthly_sort_key(label: str) -> tuple[int, int, object]:
    for fmt in ("%Y-%m-%d", "%Y-%m", "%m/%Y", "%b %Y", "%B %Y"):
        try:
            parsed = datetime.strptime(label.strip(), fmt)
            return (0, parsed.year, parsed.month)
        except ValueError:
            continue
    return (1, 0, label.casefold())

_original_historical_monthly_preview = historical_monthly_preview
def historical_monthly_preview(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
    return monthly_cumulative_deltas(
        _original_historical_monthly_preview(*args, **kwargs)
    )


def load_actual_for_quarter(
    session: Any,
    quarter_label: str,
    attribution_window: int = 30,
    account_name: str | None = None,
    sub_account: str | None = None,
    event: str | None = None,
    channel: str | None = None,
) -> dict[str, Any] | None:
    """Load actual results for a specific quarter at its latest available week.

    Returns a dict with DELIVERED, INC_CUSTOMERS, INC_REVENUE, SPEND, MAX_WEEK
    or None if no data exists for that quarter.
    """
    where_clause, params = _slice_filters(
        attribution_window, account_name, sub_account, event, channel
    )
    query = f"""
        WITH target AS (
            SELECT CAMPAIGN_QUARTER,
                   MAX(DELIVERY_WEEK) AS MAX_WEEK
            FROM {REFERENCE_HISTORICAL_TABLE}
            WHERE {where_clause}
              AND CAMPAIGN_QUARTER = ?
            GROUP BY CAMPAIGN_QUARTER
        )
        SELECT
            d.CAMPAIGN_QUARTER,
            SUM(d.DELIVERED) AS DELIVERED,
            SUM(d.INC_NEW_SALES) AS INC_CUSTOMERS,
            SUM(d.INC_REVENUE) AS INC_REVENUE,
            SUM(d.SPEND) AS SPEND,
            t.MAX_WEEK
        FROM {REFERENCE_HISTORICAL_TABLE} d
        JOIN target t
          ON d.CAMPAIGN_QUARTER = t.CAMPAIGN_QUARTER
         AND d.DELIVERY_WEEK = t.MAX_WEEK
        WHERE {where_clause}
          AND d.CAMPAIGN_QUARTER = ?
        GROUP BY d.CAMPAIGN_QUARTER, t.MAX_WEEK
    """
    all_params = params + [quarter_label] + params + [quarter_label]
    try:
        rows = _rows(session.sql(query, params=all_params).collect())
    except Exception:
        return None
    if not rows:
        return None
    row = rows[0]
    return {
        "CAMPAIGN_QUARTER": row.get("CAMPAIGN_QUARTER"),
        "DELIVERED": float(row.get("DELIVERED", 0)),
        "INC_CUSTOMERS": float(row.get("INC_CUSTOMERS", 0)),
        "INC_REVENUE": float(row.get("INC_REVENUE", 0)),
        "SPEND": float(row.get("SPEND", 0)),
        "MAX_WEEK": int(row.get("MAX_WEEK", 0)),
    }


def load_weekly_cumulative(
    session: Any,
    quarter_labels: list[str],
    attribution_window: int = 30,
    account_name: str | None = None,
    sub_account: str | None = None,
    event: str | None = None,
    channel: str | None = None,
) -> "pd.DataFrame":
    """Load week-by-week cumulative data for given quarters.

    Returns a DataFrame with CAMPAIGN_QUARTER, DELIVERY_WEEK, DELIVERED,
    INC_NEW_SALES, INC_REVENUE, SPEND, TRT_PROSPECTS, FREQUENCY.
    """
    import pandas as pd

    if not quarter_labels:
        return pd.DataFrame()
    where_clause, params = _slice_filters(
        attribution_window, account_name, sub_account, event, channel
    )
    placeholders = ", ".join("?" for _ in quarter_labels)
    query = f"""
        SELECT CAMPAIGN_QUARTER, DELIVERY_WEEK,
               SUM(DELIVERED) AS DELIVERED,
               SUM(INC_NEW_SALES) AS INC_NEW_SALES,
               SUM(INC_REVENUE) AS INC_REVENUE,
               SUM(SPEND) AS SPEND,
               SUM(TRT_PROSPECTS) AS TRT_PROSPECTS,
               CASE WHEN SUM(TRT_PROSPECTS) > 0
                    THEN SUM(DELIVERED) * 1.0 / SUM(TRT_PROSPECTS)
                    ELSE 0 END AS FREQUENCY
        FROM {REFERENCE_HISTORICAL_TABLE}
        WHERE {where_clause}
          AND CAMPAIGN_QUARTER IN ({placeholders})
          AND DELIVERY_WEEK <= 12
        GROUP BY CAMPAIGN_QUARTER, DELIVERY_WEEK
        ORDER BY CAMPAIGN_QUARTER, DELIVERY_WEEK
    """
    all_params = params + list(quarter_labels)
    try:
        return session.sql(query, params=all_params).to_pandas()
    except Exception:
        return pd.DataFrame()
