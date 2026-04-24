"""Detector d08 — Service-area growth without staffing growth.

Fires when the count of named service areas (parishes, counties,
regions) in the Part I mission statement increases materially in a
single year while reported employee count stays flat.

This detector requires a service-area count field on the filings table.
The fetcher-parser is responsible for extracting named geographic units
from Part I Line 1 mission text and persisting the count. In the absence
of that pre-computation, the detector reports zero rather than guessing.

Methodology: docs/methodology.md §Rule 8.
"""
from __future__ import annotations

import re
import sqlite3

from ._base import Score, collect

DETECTOR_ID = "d08_growth_without_staffing"
DESCRIPTION = "Service-area count grew while employee count stayed flat."
METHODOLOGY = "docs/methodology.md#rule-8--service-area-growth-without-staffing-growth"

MIN_AREAS_ADDED = 2
MAX_EMPLOYEE_DELTA = 1

# Naive fallback area extractor for mission text if num_service_areas is not
# pre-populated. Counts commas in a section that looks like a named list of
# geographic units ("parishes of X, Y, Z, and W" or "counties of X, Y and Z").
_LIST_RE = re.compile(
    r"(?:parishes|counties|regions|districts)\s+of\s+([^.]+)",
    flags=re.IGNORECASE,
)


def _derive_area_count(mission: str | None) -> int | None:
    if not mission:
        return None
    m = _LIST_RE.search(mission)
    if not m:
        return None
    tail = m.group(1)
    # Split on comma and "and" conjunction; filter empties.
    parts = [p.strip() for p in re.split(r",|\band\b", tail, flags=re.IGNORECASE)]
    parts = [p for p in parts if p]
    return len(parts) or None


def _schema_has_num_areas(conn: sqlite3.Connection) -> bool:
    cur = conn.execute("PRAGMA table_info(filings)")
    return any(row[1] == "num_service_areas" for row in cur.fetchall())


_SQL_WITH_COL = """
SELECT
  f1.ein,
  f1.fiscal_year   AS pivot_year,
  f0.num_service_areas AS prior_areas,
  f1.num_service_areas AS current_areas,
  f0.employees     AS prior_employees,
  f1.employees     AS current_employees
  FROM filings f1
  JOIN filings f0
    ON f0.ein = f1.ein
   AND f0.fiscal_year = f1.fiscal_year - 1
 WHERE f0.num_service_areas IS NOT NULL
   AND f1.num_service_areas IS NOT NULL
   AND f0.employees IS NOT NULL
   AND f1.employees IS NOT NULL;
"""

_SQL_FALLBACK = """
SELECT
  f1.ein,
  f1.fiscal_year   AS pivot_year,
  f0.mission_text  AS prior_mission,
  f1.mission_text  AS current_mission,
  f0.employees     AS prior_employees,
  f1.employees     AS current_employees
  FROM filings f1
  JOIN filings f0
    ON f0.ein = f1.ein
   AND f0.fiscal_year = f1.fiscal_year - 1
 WHERE f0.employees IS NOT NULL
   AND f1.employees IS NOT NULL;
"""


def run(conn: sqlite3.Connection) -> list[Score]:
    denom = {
        r["ein"]: r["n_years"]
        for r in collect(conn, "SELECT ein, COUNT(*) AS n_years FROM filings GROUP BY ein")
    }

    if _schema_has_num_areas(conn):
        rows = collect(conn, _SQL_WITH_COL)
        pairs = [
            (r["ein"], r["pivot_year"], r["prior_areas"], r["current_areas"],
             r["prior_employees"], r["current_employees"])
            for r in rows
        ]
    else:
        rows = collect(conn, _SQL_FALLBACK)
        pairs = []
        for r in rows:
            prior_n = _derive_area_count(r["prior_mission"])
            curr_n = _derive_area_count(r["current_mission"])
            if prior_n is None or curr_n is None:
                continue
            pairs.append((r["ein"], r["pivot_year"], prior_n, curr_n,
                          r["prior_employees"], r["current_employees"]))

    per_ein: dict[str, list[dict]] = {}
    for ein, yr, prior_a, curr_a, prior_e, curr_e in pairs:
        if curr_a <= prior_a:
            continue
        areas_added = curr_a - prior_a
        employee_delta = curr_e - prior_e
        if areas_added < MIN_AREAS_ADDED:
            continue
        if employee_delta > MAX_EMPLOYEE_DELTA:
            continue
        per_ein.setdefault(ein, []).append({
            "pivot_year": yr,
            "prior_areas": prior_a,
            "current_areas": curr_a,
            "areas_added": areas_added,
            "prior_employees": prior_e,
            "current_employees": curr_e,
            "employee_delta": employee_delta,
        })

    out: list[Score] = []
    for ein, events in per_ein.items():
        total_years = denom.get(ein, len(events))
        if total_years <= 0:
            continue
        # Score scales with magnitude of the largest single-year area jump.
        max_added = max(e["areas_added"] for e in events)
        # Cap the magnitude component at 5 areas added → full score.
        magnitude = min(1.0, max_added / 5.0)
        recency = min(1.0, len(events) / total_years + 0.5)
        score = min(100.0, 100.0 * magnitude * recency)
        out.append(Score(
            ein=ein,
            score=round(score, 2),
            years_evaluated=total_years,
            detail={
                "pivot_events": events,
                "min_areas_added_threshold": MIN_AREAS_ADDED,
                "max_employee_delta_threshold": MAX_EMPLOYEE_DELTA,
            },
        ))
    return out
