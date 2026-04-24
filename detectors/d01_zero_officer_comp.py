"""Detector d01 — Sustained affirmative $0 officer compensation.

Fires when an organization answers "yes" to the Part VII Section A
no-compensation checkbox for three or more consecutive years, at a
revenue scale where a paid officer would ordinarily be expected.

Methodology: docs/methodology.md §Rule 1.
"""
from __future__ import annotations

import sqlite3

from ._base import Score, collect

DETECTOR_ID = "d01_zero_officer_comp"
DESCRIPTION = "Sustained affirmative $0 officer compensation."
METHODOLOGY = "docs/methodology.md#rule-1--sustained-affirmative-0-officer-compensation"

MIN_CONSECUTIVE_YEARS = 3
MIN_REVENUE = 500_000

_SQL_RUNS = """
WITH qualified AS (
  SELECT ein, fiscal_year, signer_name
    FROM filings
   WHERE no_officer_comp_box = 1
     AND total_revenue >= :min_revenue
     AND signer_name IS NOT NULL
),
streaks AS (
  SELECT
    ein,
    fiscal_year,
    fiscal_year - ROW_NUMBER() OVER (PARTITION BY ein ORDER BY fiscal_year) AS grp
    FROM qualified
)
SELECT
  ein,
  MIN(fiscal_year) AS run_start,
  MAX(fiscal_year) AS run_end,
  COUNT(*)          AS run_length
  FROM streaks
 GROUP BY ein, grp
 HAVING run_length >= :min_years
 ORDER BY run_length DESC;
"""


def run(conn: sqlite3.Connection) -> list[Score]:
    # How many filing-years per EIN exist in the facts table — used for
    # denominator so the score is "fraction of years exhibiting the pattern".
    denom_rows = collect(
        conn,
        "SELECT ein, COUNT(*) AS n_years FROM filings GROUP BY ein",
    )
    denom = {r["ein"]: r["n_years"] for r in denom_rows}

    rows = collect(
        conn,
        _SQL_RUNS,
        min_revenue=MIN_REVENUE,
        min_years=MIN_CONSECUTIVE_YEARS,
    )

    # Collapse multiple runs per EIN to the longest.
    longest: dict[str, sqlite3.Row] = {}
    for r in rows:
        cur = longest.get(r["ein"])
        if cur is None or r["run_length"] > cur["run_length"]:
            longest[r["ein"]] = r

    scores: list[Score] = []
    for ein, r in longest.items():
        total_years = denom.get(ein, r["run_length"])
        if total_years <= 0:
            continue
        fraction = min(1.0, r["run_length"] / total_years)
        scores.append(Score(
            ein=ein,
            score=round(100.0 * fraction, 2),
            years_evaluated=total_years,
            detail={
                "run_start": r["run_start"],
                "run_end": r["run_end"],
                "run_length": r["run_length"],
                "min_consecutive_years_threshold": MIN_CONSECUTIVE_YEARS,
                "min_revenue_threshold": MIN_REVENUE,
            },
        ))
    return scores
