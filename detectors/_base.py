"""Common interface for governance-opacity detectors.

Each detector module exposes:

    DETECTOR_ID : str         Stable short identifier.
    DESCRIPTION : str         One-line human-readable description.
    METHODOLOGY : str         Section anchor in docs/methodology.md.

    def run(conn) -> list[Score]:
        Query the facts schema and return one Score per EIN that
        the detector fires on. EINs not returned score zero for
        this detector.

The canonical schema the detectors query lives in schema/facts_table.sql.
The scorer aggregates per-detector results into a composite.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Any, Callable


@dataclass
class Score:
    """A per-EIN result emitted by a single detector."""
    ein: str
    score: float                       # 0.0-100.0
    years_evaluated: int = 0
    detail: dict[str, Any] = field(default_factory=dict)

    def to_row(self, detector_id: str, run_date: str) -> dict:
        return {
            "ein": self.ein,
            "detector_id": detector_id,
            "score": round(self.score, 2),
            "years_evaluated": self.years_evaluated,
            "run_date": run_date,
            "detail_json": _json_safe(self.detail),
        }


def _json_safe(value: Any) -> str:
    import json
    return json.dumps(value, default=str, sort_keys=True)


def today() -> str:
    return date.today().isoformat()


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def collect(conn: sqlite3.Connection, sql: str, **params) -> list[sqlite3.Row]:
    cur = conn.execute(sql, params)
    return cur.fetchall()


# -----------------------------------------------------------------------------
# Helpers used by multiple detectors
# -----------------------------------------------------------------------------

def years_for(conn: sqlite3.Connection, ein: str) -> list[int]:
    rows = collect(
        conn,
        "SELECT fiscal_year FROM filings WHERE ein = :ein ORDER BY fiscal_year",
        ein=ein,
    )
    return [r["fiscal_year"] for r in rows]


def longest_run(years: list[int], predicate: Callable[[int], bool]) -> tuple[int, int, int]:
    """Longest consecutive run in `years` where `predicate(year)` is truthy.

    Returns (start_year, end_year, length). Returns (0, 0, 0) if no run.
    """
    best: tuple[int, int, int] = (0, 0, 0)
    current_start: int | None = None
    last_year: int | None = None

    for y in sorted(years):
        if predicate(y):
            if current_start is None:
                current_start = y
            last_year = y
            length = (last_year - current_start) + 1
            if length > best[2]:
                best = (current_start, last_year, length)
        else:
            current_start = None
            last_year = None
    return best
