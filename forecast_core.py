# ForecastPro calculation engine with extended scale tier for high-utilization accounts
# Co-authored with CoCo
"""ForecastPro calculation engine, packaged for Streamlit in Snowflake.

The formulas intentionally mirror ``backend/app``.  This copy keeps the deployable
Snowflake artifact self-contained and leaves the existing FastAPI application alone.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path


@dataclass(frozen=True)
class HistoricalPerformance:
    campaign_quarter: str
    cpix: Decimal
    average_incremental_revenue: Decimal


@dataclass(frozen=True)
class InvestmentTier:
    label: str
    investment: Decimal


@dataclass(frozen=True)
class SignalUtilizationCurve:
    current_utilization_thresholds: tuple[Decimal, ...]
    target_utilization_thresholds: tuple[Decimal, ...]
    adjustments: tuple[tuple[Decimal, ...], ...]

    def adjustment(self, current: Decimal, target: Decimal) -> Decimal:
        return self.adjustments[
            _floor_match(current, self.current_utilization_thresholds)
        ][_floor_match(target, self.target_utilization_thresholds)]

    def validate(self) -> None:
        if len(self.adjustments) != len(self.current_utilization_thresholds):
            raise ValueError(
                "Curve row count must match current-utilization thresholds"
            )
        if any(
            len(row) != len(self.target_utilization_thresholds)
            for row in self.adjustments
        ):
            raise ValueError("Every curve row must match target-utilization thresholds")


@dataclass(frozen=True)
class ForecastScenarioInput:
    current_budget: Decimal
    cpm: Decimal
    historical_prospect_frequency: Decimal
    current_signal_utilization: Decimal
    max_reach: Decimal
    frequency_at_max_reach: Decimal
    tiers: tuple[InvestmentTier, ...]
    historical_performance: tuple[HistoricalPerformance, ...]
    signal_utilization_curve: SignalUtilizationCurve


@dataclass(frozen=True)
class TierProjection:
    historical_quarter: str
    tier_label: str
    investment: Decimal
    delivered_volume: Decimal
    prospects: Decimal
    incremental_customers: Decimal
    incremental_revenue: Decimal
    cpix: Decimal
    iroas: Decimal
    marginal_cpix: Decimal | None
    marginal_iroas: Decimal | None
    marginal_incremental_customers: Decimal | None
    new_signal_utilization: Decimal
    adjustment_factor: Decimal


@dataclass(frozen=True)
class ValueRange:
    minimum: Decimal
    maximum: Decimal


@dataclass(frozen=True)
class TierForecastRange:
    tier_label: str
    investment: Decimal
    delivered_volume: Decimal
    prospects: Decimal
    incremental_customers: ValueRange
    incremental_revenue: ValueRange
    cpix: ValueRange
    iroas: ValueRange


@dataclass(frozen=True)
class ImprovementProjection:
    historical_quarter: str
    tier_label: str
    investment: Decimal
    incremental_customers: Decimal
    incremental_revenue: Decimal
    cpix: Decimal
    iroas: Decimal
    marginal_cpix: Decimal | None
    marginal_iroas: Decimal | None


def load_curve(path: Path | None = None) -> tuple[str, SignalUtilizationCurve]:
    curve_path = path or Path(__file__).with_name("signal_utilization_curve.json")
    payload = json.loads(curve_path.read_text(encoding="utf-8"))
    curve = SignalUtilizationCurve(
        tuple(map(Decimal, payload["current_utilization_thresholds"])),
        tuple(map(Decimal, payload["target_utilization_thresholds"])),
        tuple(tuple(map(Decimal, row)) for row in payload["adjustments"]),
    )
    curve.validate()
    return str(payload["version"]), curve


def calculate_standard_projections(
    scenario: ForecastScenarioInput,
) -> list[TierProjection]:
    _validate_scenario(scenario)
    calculated_sustainable = (
        scenario.max_reach
        * scenario.frequency_at_max_reach
        / Decimal("1000")
        * scenario.cpm
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # A manually entered Sustainable Scale is the authoritative standard-tier
    # ceiling. At 100% utilization, Current Budget is already Sustainable.
    configured_sustainable = next(
        (
            tier.investment
            for tier in scenario.tiers
            if tier.label.strip().casefold() == "sustainable scale"
        ),
        None,
    )
    if scenario.current_signal_utilization >= Decimal("1"):
        sustainable = scenario.current_budget
        standard_tiers = (InvestmentTier("Sustainable Scale", sustainable),)
    else:
        sustainable = configured_sustainable or calculated_sustainable
        standard_tiers = _standard_tiers(scenario.tiers, sustainable)

    # Extension tiers beyond Sustainable Scale — always all 5 regardless of utilization.
    extension_tiers = tuple(
        InvestmentTier(label, sustainable * factor)
        for label, factor in (
            ("Incremental Reach (+5%)", Decimal("1.05")),
            ("Incremental Reach (+10%)", Decimal("1.10")),
            ("Incremental Reach (+15%)", Decimal("1.15")),
            ("Incremental Reach (+20%)", Decimal("1.20")),
            ("Maximum Scale (+25%)", Decimal("1.25")),
        )
    )

    tiers = standard_tiers + extension_tiers
    result: list[TierProjection] = []
    for historical in scenario.historical_performance:
        previous = None
        for tier in tiers:
            current = _calculate_tier(scenario, historical, tier, sustainable, previous)
            result.append(current)
            previous = current
    return result


def forecast_ranges(
    projections: list[TierProjection], adjustment: Decimal
) -> tuple[str, list[TierForecastRange]]:
    quarters = {row.historical_quarter for row in projections}
    if len(quarters) == 1:
        if adjustment < 0 or adjustment >= 1:
            raise ValueError(
                "Forecast range adjustment must be at least zero and below one"
            )

        def symmetric(value: Decimal) -> ValueRange:
            return ValueRange(value * (1 - adjustment), value * (1 + adjustment))

        return "one-quarter-adjustment", [
            TierForecastRange(
                p.tier_label,
                p.investment,
                p.delivered_volume,
                p.prospects,
                symmetric(p.incremental_customers),
                symmetric(p.incremental_revenue),
                ValueRange(p.cpix / (1 + adjustment), p.cpix / (1 - adjustment)),
                symmetric(p.iroas),
            )
            for p in projections
        ]
    grouped: dict[tuple[str, Decimal], list[TierProjection]] = defaultdict(list)
    for row in projections:
        grouped[(row.tier_label, row.investment)].append(row)

    def bounds(rows: list[TierProjection], field: str) -> ValueRange:
        values = [getattr(row, field) for row in rows]
        return ValueRange(min(values), max(values))

    ranges = [
        TierForecastRange(
            label,
            investment,
            rows[0].delivered_volume,
            rows[0].prospects,
            bounds(rows, "incremental_customers"),
            bounds(rows, "incremental_revenue"),
            bounds(rows, "cpix"),
            bounds(rows, "iroas"),
        )
        for (label, investment), rows in grouped.items()
    ]
    return "multi-quarter-min-max", sorted(ranges, key=lambda row: row.investment)


def apply_improvement_factor(
    projections: list[TierProjection], factor: Decimal
) -> list[ImprovementProjection]:
    if factor < 0:
        raise ValueError("Improvement factor cannot be negative")
    multiplier = 1 + factor
    previous: dict[str, ImprovementProjection] = {}
    result = []
    for row in projections:
        customers = (row.incremental_customers * multiplier).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
        revenue = (row.incremental_revenue * multiplier).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
        prior = previous.get(row.historical_quarter)
        delta_investment = row.investment - prior.investment if prior else None
        delta_customers = customers - prior.incremental_customers if prior else None
        item = ImprovementProjection(
            row.historical_quarter,
            row.tier_label,
            row.investment,
            customers,
            revenue,
            row.investment / customers,
            revenue / row.investment,
            delta_investment / delta_customers
            if delta_investment and delta_customers
            else None,
            (revenue - prior.incremental_revenue) / delta_investment
            if prior and delta_investment
            else None,
        )
        previous[row.historical_quarter] = item
        result.append(item)
    return result


def _standard_tiers(
    configured: tuple[InvestmentTier, ...], sustainable: Decimal
) -> tuple[InvestmentTier, ...]:
    if any(t.investment <= 0 for t in configured):
        raise ValueError("Investment tiers must be positive")
    # Allow tiers above sustainable — they'll be treated as extension tiers
    # and get the appropriate CPIx penalty from the utilization curve
    tiers = list(configured)
    if not any(t.investment == sustainable for t in tiers):
        tiers.append(InvestmentTier("Sustainable Scale", sustainable))
    return tuple(sorted(tiers, key=lambda t: t.investment))


def _calculate_tier(
    scenario: ForecastScenarioInput,
    historical: HistoricalPerformance,
    tier: InvestmentTier,
    sustainable: Decimal,
    previous: TierProjection | None,
) -> TierProjection:
    if tier.investment > sustainable:
        # Expansion tiers use absolute targets: 105%, 110%, ..., 125%.
        utilization = tier.investment / sustainable
    elif sustainable == scenario.current_budget:
        utilization = scenario.current_signal_utilization
    elif tier.investment >= scenario.current_budget:
        utilization = scenario.current_signal_utilization + (
            (tier.investment - scenario.current_budget)
            / (sustainable - scenario.current_budget)
        ) * (1 - scenario.current_signal_utilization)
    else:
        utilization = (
            scenario.current_signal_utilization
            * tier.investment
            / scenario.current_budget
        )
    factor = 1 + scenario.signal_utilization_curve.adjustment(
        scenario.current_signal_utilization, utilization
    )
    cpix = historical.cpix * factor
    customers = tier.investment / cpix
    revenue = customers * historical.average_incremental_revenue
    delivered = tier.investment * 1000 / scenario.cpm
    prospects = delivered / scenario.historical_prospect_frequency
    if previous is None:
        marginal_cpix, marginal_iroas, marginal_customers = (
            cpix,
            revenue / tier.investment,
            None,
        )
    else:
        investment_delta = tier.investment - previous.investment
        customer_delta = customers - previous.incremental_customers
        marginal_cpix = (
            investment_delta / customer_delta
            if investment_delta and customer_delta
            else None
        )
        marginal_iroas = (
            (revenue - previous.incremental_revenue) / investment_delta
            if investment_delta
            else None
        )
        marginal_customers = customer_delta
    return TierProjection(
        historical.campaign_quarter,
        tier.label,
        tier.investment,
        delivered,
        prospects,
        customers,
        revenue,
        cpix,
        revenue / tier.investment,
        marginal_cpix,
        marginal_iroas,
        marginal_customers,
        utilization,
        factor,
    )


def _validate_scenario(scenario: ForecastScenarioInput) -> None:
    if (
        min(
            scenario.current_budget,
            scenario.cpm,
            scenario.historical_prospect_frequency,
        )
        <= 0
    ):
        raise ValueError(
            "Current budget, CPM, and historical prospect frequency must be positive"
        )
    if not Decimal("0") < scenario.current_signal_utilization <= 1:
        raise ValueError("Current signal utilization must be between zero and one")
    if min(scenario.max_reach, scenario.frequency_at_max_reach) <= 0:
        raise ValueError("Maximum reach and frequency must be positive")
    if not scenario.historical_performance:
        raise ValueError("At least one historical quarter is required")
    scenario.signal_utilization_curve.validate()


@dataclass(frozen=True)
class MonthlyProjection:
    month: str
    tier_label: str
    investment: Decimal
    delivered_volume: Decimal
    incremental_customers: Decimal
    incremental_revenue: Decimal


def monthly_projections(
    tier_ranges: list,
    target_quarter: str,
    monthly_organic_index: dict[str, float],
    monthly_incremental_index: dict[str, float],
) -> list[MonthlyProjection]:
    """Break quarterly forecast ranges into monthly projections using seasonal indexes.

    Uses monthly_organic_index for investment/delivered and monthly_incremental_index
    for customers/revenue, matching the Excel's Qtr Proj logic:
      Monthly Budget = Quarterly Budget × (Monthly Organic Index / Quarterly Organic Index)
    """
    import re as _re

    match = _re.fullmatch(r"Q([1-4])\s*(\d{4})", target_quarter.upper())
    if not match:
        return []

    q_num = int(match.group(1))
    quarter_months_map = {
        1: ["Jan", "Feb", "Mar"],
        2: ["Apr", "May", "Jun"],
        3: ["Jul", "Aug", "Sep"],
        4: ["Oct", "Nov", "Dec"],
    }
    months = quarter_months_map[q_num]

    # Get quarterly totals for normalization (sum of 3 months in target quarter)
    qtr_organic_total = sum(monthly_organic_index.get(m, 1 / 12) for m in months)
    qtr_inc_total = sum(monthly_incremental_index.get(m, 1 / 12) for m in months)

    result = []
    for row in tier_ranges:
        # Use midpoint for ranges, or direct value
        investment = (
            row.investment
            if hasattr(row, "investment")
            else Decimal("0")
        )
        delivered = (
            row.delivered_volume
            if hasattr(row, "delivered_volume")
            else Decimal("0")
        )
        customers_mid = (
            (row.incremental_customers.minimum + row.incremental_customers.maximum) / 2
            if hasattr(row.incremental_customers, "minimum")
            else row.incremental_customers
        )
        revenue_mid = (
            (row.incremental_revenue.minimum + row.incremental_revenue.maximum) / 2
            if hasattr(row.incremental_revenue, "minimum")
            else row.incremental_revenue
        )

        for month in months:
            organic_pct = Decimal(
                str(monthly_organic_index.get(month, 1 / 12) / qtr_organic_total)
            ) if qtr_organic_total else Decimal("0.333333")
            inc_pct = Decimal(
                str(monthly_incremental_index.get(month, 1 / 12) / qtr_inc_total)
            ) if qtr_inc_total else Decimal("0.333333")

            result.append(MonthlyProjection(
                month=month,
                tier_label=row.tier_label,
                investment=(investment * organic_pct).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                delivered_volume=(delivered * organic_pct).quantize(Decimal("1"), rounding=ROUND_HALF_UP),
                incremental_customers=(customers_mid * inc_pct).quantize(Decimal("1"), rounding=ROUND_HALF_UP),
                incremental_revenue=(revenue_mid * inc_pct).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            ))
    return result


def _floor_match(value: Decimal, thresholds: tuple[Decimal, ...]) -> int:
    if not thresholds or value < thresholds[0]:
        raise ValueError("Signal utilization falls outside configured curve thresholds")
    index = 0
    for candidate, threshold in enumerate(thresholds):
        if threshold > value:
            break
        index = candidate
    return index


# =========================================================================
# Full monthly tables matching template (Tables 3a.1 - 3a.5, 3b.1 - 3b.5)
# =========================================================================

QUARTER_MONTHS = {
    1: ["Jan", "Feb", "Mar"],
    2: ["Apr", "May", "Jun"],
    3: ["Jul", "Aug", "Sep"],
    4: ["Oct", "Nov", "Dec"],
}


@dataclass(frozen=True)
class MonthlyTableRow:
    month: str
    seasonal_index: float
    values_by_tier: dict  # tier_label -> value (str range or number)


def quarterly_monthly_tables(
    tier_ranges: list[TierForecastRange],
    monthly_organic_index: dict[str, float],
    monthly_incremental_index: dict[str, float],
    improvement_factor: Decimal | None = None,
) -> dict[str, dict[int, list[dict]]]:
    """Generate all 5 monthly table types for all 4 quarters.

    Returns structure:
    {
        "investment": {1: [...rows...], 2: [...], 3: [...], 4: [...]},
        "customers": {1: [...], ...},
        "revenue": {1: [...], ...},
        "cpix": {1: [...], ...},
        "iroas": {1: [...], ...},
    }

    Each row is: {"month": str, "index": float, tier_label: value, ...}
    """
    tables = {
        "investment": {},
        "customers": {},
        "revenue": {},
        "cpix": {},
        "iroas": {},
    }

    for q_num in range(1, 5):
        months = QUARTER_MONTHS[q_num]

        # Normalize organic/incremental indexes within this quarter
        org_sum = sum(monthly_organic_index.get(m, 1 / 12) for m in months)
        inc_sum = sum(monthly_incremental_index.get(m, 1 / 12) for m in months)

        inv_rows = []
        cust_rows = []
        rev_rows = []
        cpix_rows = []
        iroas_rows = []

        for month in months:
            org_pct = monthly_organic_index.get(month, 1 / 12) / org_sum if org_sum else 1 / 3
            inc_pct = monthly_incremental_index.get(month, 1 / 12) / inc_sum if inc_sum else 1 / 3

            inv_row = {"month": month, "index": round(org_pct, 4)}
            cust_row = {"month": month, "index": round(inc_pct, 4)}
            rev_row = {"month": month, "index": round(inc_pct, 4)}
            cpix_row = {"month": month, "index": round(inc_pct, 4)}
            iroas_row = {"month": month, "index": round(org_pct, 4)}

            for r in tier_ranges:
                label = r.tier_label

                # Investment (organic index)
                monthly_inv = float(r.investment) * org_pct
                inv_row[label] = round(monthly_inv, 2)

                # Customers (incremental index) — show range
                if improvement_factor is not None:
                    factor = 1 + float(improvement_factor)
                    cust_min = float(r.incremental_customers.minimum) * factor * inc_pct
                    cust_max = float(r.incremental_customers.maximum) * factor * inc_pct
                    rev_min = float(r.incremental_revenue.minimum) * factor * inc_pct
                    rev_max = float(r.incremental_revenue.maximum) * factor * inc_pct
                else:
                    cust_min = float(r.incremental_customers.minimum) * inc_pct
                    cust_max = float(r.incremental_customers.maximum) * inc_pct
                    rev_min = float(r.incremental_revenue.minimum) * inc_pct
                    rev_max = float(r.incremental_revenue.maximum) * inc_pct

                cust_row[label] = _format_range(cust_min, cust_max)
                rev_row[label] = _format_money_range(rev_min, rev_max)

                # CPIx = Investment / Customers
                cpix_min = monthly_inv / cust_max if cust_max > 0 else 0
                cpix_max = monthly_inv / cust_min if cust_min > 0 else 0
                cpix_row[label] = _format_dollar_range(cpix_min, cpix_max)

                # iROAS = Revenue / Investment
                iroas_min = rev_min / monthly_inv if monthly_inv > 0 else 0
                iroas_max = rev_max / monthly_inv if monthly_inv > 0 else 0
                iroas_row[label] = _format_decimal_range(iroas_min, iroas_max)

            inv_rows.append(inv_row)
            cust_rows.append(cust_row)
            rev_rows.append(rev_row)
            cpix_rows.append(cpix_row)
            iroas_rows.append(iroas_row)

        # Add quarterly total row
        inv_total = {"month": f"Q{q_num} Total", "index": 1.0}
        cust_total = {"month": f"Q{q_num} Total", "index": 1.0}
        rev_total = {"month": f"Q{q_num} Total", "index": 1.0}
        cpix_total = {"month": f"Q{q_num} Total", "index": 1.0}
        iroas_total = {"month": f"Q{q_num} Total", "index": 1.0}

        for r in tier_ranges:
            label = r.tier_label
            inv_total[label] = round(float(r.investment), 2)

            if improvement_factor is not None:
                factor = 1 + float(improvement_factor)
                cust_total[label] = _format_range(
                    float(r.incremental_customers.minimum) * factor,
                    float(r.incremental_customers.maximum) * factor)
                rev_total[label] = _format_money_range(
                    float(r.incremental_revenue.minimum) * factor,
                    float(r.incremental_revenue.maximum) * factor)
            else:
                cust_total[label] = _format_range(
                    float(r.incremental_customers.minimum),
                    float(r.incremental_customers.maximum))
                rev_total[label] = _format_money_range(
                    float(r.incremental_revenue.minimum),
                    float(r.incremental_revenue.maximum))

            cpix_total[label] = _format_dollar_range(
                float(r.cpix.minimum), float(r.cpix.maximum))
            iroas_total[label] = _format_decimal_range(
                float(r.iroas.minimum), float(r.iroas.maximum))

        inv_rows.append(inv_total)
        cust_rows.append(cust_total)
        rev_rows.append(rev_total)
        cpix_rows.append(cpix_total)
        iroas_rows.append(iroas_total)

        tables["investment"][q_num] = inv_rows
        tables["customers"][q_num] = cust_rows
        tables["revenue"][q_num] = rev_rows
        tables["cpix"][q_num] = cpix_rows
        tables["iroas"][q_num] = iroas_rows

    return tables


def _format_range(low: float, high: float) -> str:
    if low >= 1000:
        return f"{low/1000:.1f}K - {high/1000:.1f}K"
    return f"{low:.0f} - {high:.0f}"


def _format_money_range(low: float, high: float) -> str:
    if abs(low) >= 1_000_000:
        return f"${low/1_000_000:.1f}M - ${high/1_000_000:.1f}M"
    if abs(low) >= 1000:
        return f"${low/1000:.1f}K - ${high/1000:.1f}K"
    return f"${low:.0f} - ${high:.0f}"


def _format_dollar_range(low: float, high: float) -> str:
    return f"${low:.0f} - ${high:.0f}"


def _format_decimal_range(low: float, high: float) -> str:
    return f"{low:.2f} - {high:.2f}"
