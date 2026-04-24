"""Detector d03 — Schedule G Part II $0 direct expenses across all events.

Fires when an organization reports fundraising-event gross receipts at
or above a materiality floor but zero direct expense on every Schedule G
Part II line, sustained across multiple years.

Methodology: docs/methodology.md §Rule 3.
"""
from __future__ import annotations

import sqlite3

from ._base import Score, collect

DETECTOR_ID = "d03_zero_fundraising_events"
DESCRIPTION = "Schedule G Part II $0 direct expenses across all events."
METHODOLOGY = "docs/methodology.md#rule-3--schedule-g-part-ii-0-direct-expenses-across-all-events"

MIN_EVENT_GROSS = 50_000
MIN_QUALIFYING_YEARS = 3

_SQL = """
WITH per_year AS (
  SELECT
    ein,
    fiscal_year,
    COUNT(*) AS event_count,
    SUM(COALESCE(gross_receipts, 0)) AS total_gross,
    SUM(
      COALESCE(cash_prizes, 0) +
      COALESCE(noncash_prizes, 0) +
      COALESCE(rent_facility, 0) +
      COALESCE(food_beverages, 0) +
      COALESCE(entertainment, 0) +
      COALESCE(other_direct, 0)
    ) AS total_direct
    FROM events
   GROUP BY ein, fiscal_year
),
zero_years AS (
  SELECT ein, fiscal_year, event_count, total_gross
    FROM per_year
   WHERE total_gross >= :min_gross
     AND total_direct = 0
)
SELECT
  ein,
  COUNT(*)                          AS years_with_pattern,
  SUM(total_gross)                  AS cumulative_gross,
  MIN(fiscal_year)                  AS first_year,
  MAX(fiscal_year)                  AS last_year,
  GROUP_CONCAT(fiscal_year, ',')    AS affected_years
  FROM zero_years
 GROUP BY ein
HAVING years_with_pattern >= :min_years;
"""


def run(conn: sqlite3.Connection) -> list[Score]:
    denom = {
        r["ein"]: r["n_years"]
        for r in collect(conn, "SELECT ein, COUNT(*) AS n_years FROM filings GROUP BY ein")
    }
    rows = collect(
        conn,
        _SQL,
        min_gross=MIN_EVENT_GROSS,
        min_years=MIN_QUALIFYING_YEARS,
    )

    out: list[Score] = []
    for r in rows:
        total_years = denom.get(r["ein"], r["years_with_pattern"])
        if total_years <= 0:
            continue
        fraction = min(1.0, r["years_with_pattern"] / total_years)
        out.append(Score(
            ein=r["ein"],
            score=round(100.0 * fraction, 2),
            years_evaluated=total_years,
            detail={
                "years_with_pattern": r["years_with_pattern"],
                "cumulative_gross": r["cumulative_gross"],
                "first_year": r["first_year"],
                "last_year": r["last_year"],
                "affected_years": r["affected_years"],
                "min_event_gross_threshold": MIN_EVENT_GROSS,
            },
        ))
    return out
