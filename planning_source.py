"""Read the approved Q2 planning export bundled with the Snowflake app."""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

DEFAULT_PLANNING_SOURCE = Path(__file__).with_name("FORECASTING_Q2_2026.csv")


def planning_campaigns(
    account_name: str,
    quarter: str = "Q2 2026",
    source_path: Path = DEFAULT_PLANNING_SOURCE,
) -> list[str]:
    """Return Q2 campaign keys that match the selected ForecastPro account."""
    account = _match_text(account_name)
    matches = []
    for row in _rows(source_path):
        if _match_text(row.get("Quarter")) != _match_text(quarter):
            continue
        searchable = " ".join(
            str(row.get(column) or "")
            for column in (
                "Client",
                "New Client",
                "Client + Campaign + Channel",
                "CLIENT_CODE",
            )
        )
        campaign_key = str(row.get("Client + Campaign + Channel") or "").strip()
        if campaign_key and account in _match_text(searchable):
            matches.append(campaign_key)
    return sorted(dict.fromkeys(matches), key=str.casefold)


def planning_input(
    campaign_key: str,
    quarter: str = "Q2 2026",
    source_path: Path = DEFAULT_PLANNING_SOURCE,
) -> dict[str, Decimal]:
    """Return the five planning fields used by the forecast draft."""
    for row in _rows(source_path):
        if (
            _match_text(row.get("Quarter")) == _match_text(quarter)
            and str(row.get("Client + Campaign + Channel") or "").strip()
            == campaign_key
        ):
            return {
                "campaign_budget": _decimal(row, "Campaign Budget"),
                "cpm": _decimal(row, "CPM"),
                "planned_reach": _decimal(row, "Planned Campaign Reach"),
                "maximum_reach": _decimal(
                    row, "Maximum Reach to Maintain Performance"
                ),
                "signal_utilization": _decimal(
                    row, "Signal Utilization (to total signals available)"
                ),
                "frequency_at_max": _decimal(row, "Frequency"),
            }
    raise ValueError(
        "Selected campaign was not found in the approved Q2 forecast sheet"
    )


def _rows(source_path: Path) -> list[dict[str, str]]:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            with source_path.open(encoding=encoding, newline="") as handle:
                return [
                    {
                        (key or "").replace("\u00a0", " ").strip():
                        (value or "").replace("\u00a0", " ").strip()
                        for key, value in row.items()
                    }
                    for row in csv.DictReader(handle)
                ]
        except UnicodeDecodeError:
            continue
    raise ValueError("The approved Q2 forecast sheet has an unsupported encoding")


def _match_text(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def _decimal(row: dict[str, str], column: str) -> Decimal:
    value = (
        str(row.get(column) or "")
        .replace(",", "")
        .replace("$", "")
        .replace("\u00a0", "")
        .strip()
    )
    if not value:
        raise ValueError(f"Q2 forecast sheet is missing {column}")
    if value.endswith("%"):
        return Decimal(value[:-1]) / Decimal("100")
    return Decimal(value)
