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



def _floor_match(value: Decimal, thresholds: tuple[Decimal, ...]) -> int:
    if not thresholds or value < thresholds[0]:
        raise ValueError("Signal utilization falls outside configured curve thresholds")
    index = 0
    for candidate, threshold in enumerate(thresholds):
        if threshold > value:
            break
        index = candidate
    return index
