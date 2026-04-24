"""Governance-opacity detectors.

Each detector is a module that exports:
    DETECTOR_ID : str
    DESCRIPTION : str
    METHODOLOGY : str         (anchor to docs/methodology.md)
    def run(conn) -> list[Score]

The REGISTRY list below is the canonical ordering — downstream composite
scoring iterates this list to produce a per-organization aggregate.
"""
from __future__ import annotations

from ._base import Score, collect, connect, today
from . import (
    d01_zero_officer_comp,
    d02_officer_undercount,
    d03_zero_fundraising_events,
    d04_pivot_year,
    d05_governance_all_no,
    d06_schedule_o_template,
    d07_capacity_mismatch,
    d08_growth_without_staffing,
)

REGISTRY = [
    d01_zero_officer_comp,
    d02_officer_undercount,
    d03_zero_fundraising_events,
    d04_pivot_year,
    d05_governance_all_no,
    d06_schedule_o_template,
    d07_capacity_mismatch,
    d08_growth_without_staffing,
]

# Default weights for the composite score — see docs/methodology.md §Composite.
WEIGHTS: dict[str, float] = {
    "d01_zero_officer_comp":       0.15,
    "d02_officer_undercount":      0.10,
    "d03_zero_fundraising_events": 0.15,
    "d04_pivot_year":              0.20,
    "d05_governance_all_no":       0.10,
    "d06_schedule_o_template":     0.10,
    "d07_capacity_mismatch":       0.10,
    "d08_growth_without_staffing": 0.10,
}

__all__ = [
    "REGISTRY",
    "WEIGHTS",
    "Score",
    "collect",
    "connect",
    "today",
]
