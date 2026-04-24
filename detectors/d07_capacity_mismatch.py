"""Detector d07 — Capacity mismatch (revenue growth without headcount growth).

Fires when total revenue grows by at least 50% over a five-year window
while reported employee count stays flat or decreases — a divergence
between reported financial scale and reported operational capacity.

Methodology: docs/methodology.md §Rule 7.
"""
from __future__ import annotations

import sqlite3

from ._base import Score, collect

DETECTOR_ID = "d07_capacity_mismatch"
DESCRIPTION = "Revenue grew ≥50% over 5 years while employees stayed flat or decreased."
METHODOLOGY = "docs/methodology.md#rule-7--capacity-mismatch-revenue-growth-without-headcount-growth"

WINDOW_YEARS = 5
REVENUE_GROWTH_MULTIPLE = 1.5
MIN_START_EMPLOYEES = 5
MIN_START_REVENUE = 100_000

_SQL = """
SELECT
  f1.ein,
  f0.fiscal_year        AS start_year,
  f1.fiscal_year        AS end_year,
  f0.total_revenue      AS start_revenue,
  f1.total_revenue      AS end_revenue,
  f0.employees          AS start_employees,
  f1.employees          AS end_employees
  FROM filings f1
  JOIN filings f0
    ON f0.ein = f1.ein
   AND f0.fiscal_year = f1.fiscal_year - :window
 WHERE f0.total_revenue IS NOT NULL
   AND f1.total_revenue IS NOT NULL
   AND f0.employees IS NOT NULL
   AND f1.employees IS NOT NULL
   AND f0.total_revenue >= :min_rev
   AND f0.employees >= :min_emp
   AND f1.total_revenue >= :growth_mult * f0.total_revenue
   AND f1.employees <= f0.employees;
"""


def run(conn: sqlite3.Connection) -> list[Score]:
    denom = {
        r["ein"]: r["n_years"]
        for r in collect(conn, "SELECT ein, COUNT(*) AS n_years FROM filings GROUP BY ein")
    }
    rows = collect(
        conn,
        _SQL,
        window=WINDOW_YEARS,
        min_rev=MIN_START_REVENUE,
        min_emp=MIN_START_EMPLOYEES,
        growth_mult=REVENUE_GROWTH_MULTIPLE,
    )

    per_ein: dict[str, list[sqlite3.Row]] = {}
    for r in rows:
        per_ein.setdefault(r["ein"], []).append(r)

    out: list[Score] = []
    for ein, recs in per_ein.items():
        total_years = denom.get(ein, len(recs))
        if total_years <= 0:
            continue
        # Use the window with the largest revenue growth multiple.
        best = max(recs, key=lambda r: r["end_revenue"] / max(r["start_revenue"], 1))
        growth_mult = best["end_revenue"] / max(best["start_revenue"], 1)
        # Scale score by growth magnitude (capped at 3x → 100).
        score = min(100.0, (growth_mult - REVENUE_GROWTH_MULTIPLE) / (3.0 - REVENUE_GROWTH_MULTIPLE) * 100.0 + 50.0)
        out.append(Score(
            ein=ein,
            score=round(score, 2),
            years_evaluated=total_years,
            detail={
                "start_year": best["start_year"],
                "end_year": best["end_year"],
                "start_revenue": best["start_revenue"],
                "end_revenue": best["end_revenue"],
                "revenue_growth_multiple": round(growth_mult, 2),
                "start_employees": best["start_employees"],
                "end_employees": best["end_employees"],
                "employee_delta": best["end_employees"] - best["start_employees"],
                "window_years": WINDOW_YEARS,
            },
        ))
    return out
