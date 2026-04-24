"""Detector d05 — Part VI governance all-No sustained.

Fires when all four baseline governance-policy questions in Part VI
Section B are answered "No" for five or more consecutive years at a
revenue scale where written policies are the IRS-identified norm.

Methodology: docs/methodology.md §Rule 5.
"""
from __future__ import annotations

import sqlite3

from ._base import Score, collect

DETECTOR_ID = "d05_governance_all_no"
DESCRIPTION = "All four Part VI governance-policy answers 'No' across consecutive years."
METHODOLOGY = "docs/methodology.md#rule-5--part-vi-governance-all-no"

MIN_CONSECUTIVE_YEARS = 5
MIN_REVENUE = 500_000

_SQL = """
WITH qualified AS (
  SELECT ein, fiscal_year
    FROM filings
   WHERE coi_policy = 0
     AND whistleblower_policy = 0
     AND doc_retention_policy = 0
     AND ed_comp_review = 0
     AND total_revenue >= :min_revenue
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
 HAVING run_length >= :min_years;
"""


def run(conn: sqlite3.Connection) -> list[Score]:
    denom = {
        r["ein"]: r["n_years"]
        for r in collect(conn, "SELECT ein, COUNT(*) AS n_years FROM filings GROUP BY ein")
    }
    rows = collect(
        conn,
        _SQL,
        min_revenue=MIN_REVENUE,
        min_years=MIN_CONSECUTIVE_YEARS,
    )

    longest: dict[str, sqlite3.Row] = {}
    for r in rows:
        cur = longest.get(r["ein"])
        if cur is None or r["run_length"] > cur["run_length"]:
            longest[r["ein"]] = r

    out: list[Score] = []
    for ein, r in longest.items():
        total_years = denom.get(ein, r["run_length"])
        if total_years <= 0:
            continue
        fraction = min(1.0, r["run_length"] / total_years)
        out.append(Score(
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
    return out
