"""Detector d02 — Part VII officer undercount vs Part VI voting-member count.

Fires when the number of officers listed in Part VII Section A is
materially fewer than the voting-member count reported in Part VI
Line 1a, sustained across multiple years.

Methodology: docs/methodology.md §Rule 2.
"""
from __future__ import annotations

import sqlite3

from ._base import Score, collect

DETECTOR_ID = "d02_officer_undercount"
DESCRIPTION = "Part VII Section A officer count below Part VI voting-member count."
METHODOLOGY = "docs/methodology.md#rule-2--part-vii-officer-undercount-vs-part-vi-voting-member-count"

MIN_GAP = 3                 # voting_members - officers_listed
MIN_VOTING_MEMBERS = 5      # below this we're in micro-org territory
MIN_QUALIFYING_YEARS = 2

_SQL = """
WITH per_year AS (
  SELECT
    f.ein,
    f.fiscal_year,
    f.org_name,
    f.voting_members,
    COUNT(o.name) AS officers_listed,
    (f.voting_members - COUNT(o.name)) AS gap
    FROM filings f
    LEFT JOIN officers o
      ON o.ein = f.ein
     AND o.fiscal_year = f.fiscal_year
   WHERE f.voting_members >= :min_voting
   GROUP BY f.ein, f.fiscal_year, f.org_name, f.voting_members
)
SELECT
  ein,
  COUNT(*)                           AS years_with_gap,
  ROUND(AVG(gap), 2)                 AS avg_gap,
  MIN(fiscal_year)                   AS first_year,
  MAX(fiscal_year)                   AS last_year,
  GROUP_CONCAT(fiscal_year, ',')     AS affected_years
  FROM per_year
 WHERE gap >= :min_gap
 GROUP BY ein
HAVING years_with_gap >= :min_years;
"""


def run(conn: sqlite3.Connection) -> list[Score]:
    denom = {
        r["ein"]: r["n_years"]
        for r in collect(conn, "SELECT ein, COUNT(*) AS n_years FROM filings GROUP BY ein")
    }
    rows = collect(
        conn,
        _SQL,
        min_voting=MIN_VOTING_MEMBERS,
        min_gap=MIN_GAP,
        min_years=MIN_QUALIFYING_YEARS,
    )

    out: list[Score] = []
    for r in rows:
        total_years = denom.get(r["ein"], r["years_with_gap"])
        if total_years <= 0:
            continue
        fraction = min(1.0, r["years_with_gap"] / total_years)
        out.append(Score(
            ein=r["ein"],
            score=round(100.0 * fraction, 2),
            years_evaluated=total_years,
            detail={
                "years_with_gap": r["years_with_gap"],
                "avg_members_missing": r["avg_gap"],
                "first_year": r["first_year"],
                "last_year": r["last_year"],
                "affected_years": r["affected_years"],
                "gap_threshold": MIN_GAP,
            },
        ))
    return out
