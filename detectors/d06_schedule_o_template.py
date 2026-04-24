"""Detector d06 — Schedule O verbatim-template narrative.

Important false-positive guardrail:
  Common boilerplate phrasing like "NO REVIEW WAS OR WILL BE CONDUCTED"
  appears in tens of thousands of Form 990 filings across unrelated
  organizations — it is *not*, by itself, evidence of anything but a
  preparer's standard template. This detector therefore fires only on
  patterns that are unusual:

    (a) identical narrative text across multiple years for the SAME
        organization (the org uses the same template year over year
        rather than describing an actual evolving process), AND/OR

    (b) narrative text shared across a suspiciously wide set of
        unrelated organizations (preparer-template fingerprinting —
        different orgs with different structure using verbatim-identical
        Schedule O text strongly suggests a shared preparer copy-pasting
        boilerplate rather than documenting real practice).

Methodology: docs/methodology.md §Rule 6.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
from collections import defaultdict

from ._base import Score, collect

DETECTOR_ID = "d06_schedule_o_template"
DESCRIPTION = "Verbatim-identical Schedule O narrative across years or across orgs."
METHODOLOGY = "docs/methodology.md#rule-6--schedule-o-verbatim-template-narrative"

MIN_WITHIN_ORG_YEARS = 5          # same text >= this many years within one org
MAX_CROSS_ORG_FREQ = 50           # if shared across more orgs than this, likely IRS-template boilerplate (not a fingerprint)
MIN_CROSS_ORG_FREQ = 3            # shared across at least this many orgs to be "template-like"
MIN_TEXT_LENGTH = 40              # ignore trivially short narratives

_WS = re.compile(r"\s+")


def _normalize(text: str | None) -> str | None:
    if not text:
        return None
    t = _WS.sub(" ", text).strip().upper()
    if len(t) < MIN_TEXT_LENGTH:
        return None
    return t


def _hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def run(conn: sqlite3.Connection) -> list[Score]:
    rows = collect(
        conn,
        """
        SELECT ein, fiscal_year,
               schedule_o_review_narr AS review_narr,
               schedule_o_public_narr AS public_narr
          FROM filings
         WHERE schedule_o_review_narr IS NOT NULL
            OR schedule_o_public_narr IS NOT NULL
        """,
    )

    # Build (hash -> set(eins)) and (ein -> {hash: years})
    hash_to_eins: dict[str, set[str]] = defaultdict(set)
    ein_hash_years: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))

    for r in rows:
        for field in ("review_narr", "public_narr"):
            norm = _normalize(r[field])
            if norm is None:
                continue
            h = _hash(norm)
            hash_to_eins[h].add(r["ein"])
            ein_hash_years[r["ein"]][h].append(r["fiscal_year"])

    # Preparer-template candidates: hashes shared by a small-but-meaningful
    # set of orgs. (Hashes shared by huge populations are IRS-common boilerplate.)
    template_hashes = {
        h
        for h, eins in hash_to_eins.items()
        if MIN_CROSS_ORG_FREQ <= len(eins) <= MAX_CROSS_ORG_FREQ
    }

    denom = {
        r["ein"]: r["n_years"]
        for r in collect(conn, "SELECT ein, COUNT(*) AS n_years FROM filings GROUP BY ein")
    }

    out: list[Score] = []
    for ein, hashes in ein_hash_years.items():
        total_years = denom.get(ein, 0)
        if total_years <= 0:
            continue

        within_org_max_years = max(len(years) for years in hashes.values())
        within_org_fraction = min(1.0, within_org_max_years / total_years)

        template_match = any(h in template_hashes for h in hashes.keys())
        template_signal = 1.0 if template_match else 0.0

        # Scoring: within-org repetition is the primary signal; cross-org
        # preparer-template match is a secondary multiplier.
        within_component = 100.0 * within_org_fraction if within_org_max_years >= MIN_WITHIN_ORG_YEARS else 0.0
        template_component = 20.0 * template_signal

        total = min(100.0, within_component + template_component)
        if total <= 0:
            continue

        out.append(Score(
            ein=ein,
            score=round(total, 2),
            years_evaluated=total_years,
            detail={
                "within_org_max_identical_years": within_org_max_years,
                "within_org_fraction": round(within_org_fraction, 3),
                "matched_cross_org_template": template_match,
                "min_within_org_years_threshold": MIN_WITHIN_ORG_YEARS,
                "cross_org_frequency_window": [MIN_CROSS_ORG_FREQ, MAX_CROSS_ORG_FREQ],
            },
        ))
    return out
