"""Detector d04 — Multi-dimensional one-year pivot.

Fires when three or more of five independent dimensions co-move in a
single fiscal year: mission-text change, employee-count flat-or-down,
fundraising-expense collapse, Schedule G filing flip, officer-roster
turnover.

Methodology: docs/methodology.md §Rule 4.
"""
from __future__ import annotations

import sqlite3

from ._base import Score, collect

DETECTOR_ID = "d04_pivot_year"
DESCRIPTION = "Simultaneous multi-dimensional filing changes in a single fiscal year."
METHODOLOGY = "docs/methodology.md#rule-4--multi-dimensional-one-year-pivot"

MISSION_TEXT_DELTA = 0.25          # >=25% length change
FUNDRAISING_COLLAPSE_FLOOR = 1_000 # only flag if prior year was >= this
FUNDRAISING_COLLAPSE_RATIO = 0.5   # current year <= 50% of prior
OFFICER_TURNOVER_RATIO = 0.5       # >=50% of current officers are new names
DIMENSIONS_NEEDED = 3

_SQL = """
WITH yoy AS (
  SELECT
    f1.ein,
    f1.fiscal_year,
    f1.org_name,
    f0.mission_text           AS prior_mission,
    f1.mission_text           AS current_mission,
    f0.employees              AS prior_employees,
    f1.employees              AS current_employees,
    f0.fundraising_expenses_d25 AS prior_fund,
    f1.fundraising_expenses_d25 AS current_fund,
    f0.schedule_g_filed       AS prior_sched_g,
    f1.schedule_g_filed       AS current_sched_g
    FROM filings f1
    JOIN filings f0
      ON f0.ein = f1.ein
     AND f0.fiscal_year = f1.fiscal_year - 1
),
turnover AS (
  SELECT
    o1.ein,
    o1.fiscal_year,
    COUNT(*) FILTER (
      WHERE NOT EXISTS (
        SELECT 1 FROM officers o0
         WHERE o0.ein = o1.ein
           AND o0.fiscal_year = o1.fiscal_year - 1
           AND o0.name = o1.name
      )
    ) * 1.0 / NULLIF(COUNT(*), 0) AS new_fraction
    FROM officers o1
   GROUP BY o1.ein, o1.fiscal_year
)
SELECT
  yoy.*,
  turnover.new_fraction
  FROM yoy
  LEFT JOIN turnover
    ON turnover.ein = yoy.ein
   AND turnover.fiscal_year = yoy.fiscal_year;
"""


def _mission_changed(prior: str | None, current: str | None) -> bool:
    if not prior or not current:
        return False
    p, c = len(prior), len(current)
    if p == 0:
        return False
    return abs(c - p) / p >= MISSION_TEXT_DELTA


def _employees_flat_or_down(prior: int | None, current: int | None) -> bool:
    if prior is None or current is None:
        return False
    return current <= prior


def _fundraising_collapsed(prior: int | None, current: int | None) -> bool:
    if prior is None or current is None:
        return False
    if prior < FUNDRAISING_COLLAPSE_FLOOR:
        return False
    if current == 0:
        return True
    return current / prior <= FUNDRAISING_COLLAPSE_RATIO


def _schedule_g_flipped(prior: int | None, current: int | None) -> bool:
    if prior is None or current is None:
        return False
    return prior != current


def _officer_turnover_high(new_fraction: float | None) -> bool:
    if new_fraction is None:
        return False
    return new_fraction >= OFFICER_TURNOVER_RATIO


def run(conn: sqlite3.Connection) -> list[Score]:
    denom = {
        r["ein"]: r["n_years"]
        for r in collect(conn, "SELECT ein, COUNT(*) AS n_years FROM filings GROUP BY ein")
    }
    rows = collect(conn, _SQL)
    per_ein: dict[str, list[dict]] = {}

    for r in rows:
        flags = {
            "mission_changed":        _mission_changed(r["prior_mission"], r["current_mission"]),
            "employees_flat_or_down": _employees_flat_or_down(r["prior_employees"], r["current_employees"]),
            "fundraising_collapsed":  _fundraising_collapsed(r["prior_fund"], r["current_fund"]),
            "schedule_g_flipped":     _schedule_g_flipped(r["prior_sched_g"], r["current_sched_g"]),
            "officer_turnover_high":  _officer_turnover_high(r["new_fraction"]),
        }
        dim_count = sum(1 for v in flags.values() if v)
        if dim_count >= DIMENSIONS_NEEDED:
            per_ein.setdefault(r["ein"], []).append({
                "fiscal_year": r["fiscal_year"],
                "dimensions_changed": dim_count,
                "flags": flags,
            })

    out: list[Score] = []
    for ein, pivots in per_ein.items():
        total_years = denom.get(ein, len(pivots))
        if total_years <= 0:
            continue
        # Score: fraction of years exhibiting a pivot, scaled by max dimensions seen.
        frac = min(1.0, len(pivots) / total_years)
        max_dims = max(p["dimensions_changed"] for p in pivots)
        score = 100.0 * frac * (max_dims / 5.0)
        out.append(Score(
            ein=ein,
            score=round(score, 2),
            years_evaluated=total_years,
            detail={
                "pivot_years": pivots,
                "dimensions_threshold": DIMENSIONS_NEEDED,
            },
        ))
    return out
