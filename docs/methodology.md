# Methodology

A description of the eight governance-opacity detectors, the composite scoring,
and the justification for each rule drawn from the nonprofit-governance
literature, IRS guidance, and federal grant-compliance frameworks.

This document exists to be auditable. Every threshold is documented; every
field reference names a specific Form 990 line or schedule cell; every
rule-rationale cites published scholarship or regulatory guidance. A reader
should be able to reproduce any ranking and evaluate whether the underlying
logic is defensible.

## Overview

The eight detectors operate on the schema in [`schema/facts_table.sql`](../schema/facts_table.sql).
Each detector evaluates a single dimension of governance opacity against
IRS-prescribed public-filing requirements and against the normative
baselines that the nonprofit-governance literature identifies as
associated with accountable 501(c)(3) operation.

A given detector produces a score on the `[0, 100]` interval representing
the proportion of verifiable years in which the organization exhibits the
target pattern. The composite score is a weighted mean of the eight
detector scores.

No detector, in isolation, is evidence of wrongdoing. A composite score in
the upper tail of the sector distribution is evidence that an organization's
*public reporting* merits deeper examination against its *operational
documentation* — documentation held by state coalitions, state administering
agencies for federal pass-through grants, and state attorney-general
charitable-oversight offices.

## The detectors

### Rule 1 — Sustained affirmative $0 officer compensation

**What it reads.** Part VII Section A (Officers, Directors, Trustees, and Key
Employees): the "Check this box if neither the organization nor any related
organization compensated any current officer, director, or trustee"
checkbox. For the same organization-year, Part I Line 12 (total revenue)
and Part IX Line 5 (compensation of current officers in functional
expenses).

**Threshold.** Affirmatively checked for ≥3 consecutive years AND
organization revenue ≥ $500,000 in each of those years AND a principal
officer is named on the Form 990 Part II signature block.

**Why this is a signal.** The IRS's "Governance and Related Topics" guidance
(2008) identifies documented executive compensation as a core
accountability baseline. BoardSource (2021) finds that 93% of U.S. 501(c)(3)
organizations in the >$1M revenue bracket pay at least one officer. An
organization attesting that no officer received any compensation while
operating at >$500K revenue with a named principal officer represents
either: (a) a genuine volunteer-executive arrangement (rare but legitimate
at this revenue band), or (b) a compensation disclosure inconsistency.
The detector flags the pattern; downstream review determines which.

**Literature.** Fremont-Smith (2004), chapter 7; GAO-05-561T; IRS Form 990
instructions Part VII.

---

### Rule 2 — Part VII officer undercount vs Part VI voting-member count

**What it reads.** Part VI Section A Line 1a (number of voting members of
the governing body). Count of rows in Part VII Section A with any of
columns C.1 (Individual trustee or director), C.2 (Institutional
trustee), or C.3 (Officer) checked.

**Threshold.** `voting_members - officers_listed ≥ 3` for ≥2 consecutive
years. (Applies only when `voting_members ≥ 5`, to exclude micro-organizations
whose boards fit on a single table row.)

**Why this is a signal.** IRS Form 990 instructions for Part VII Section A
require listing *all* current officers, directors, and trustees
"regardless of amount of compensation." Systematic undercounting across
years is either a clerical reporting failure or a deliberate narrowing of
disclosed leadership. The former is correctable; the latter is the
signal this detector is built to find.

**Literature.** IRS Form 990 Instructions, Part VII Section A paragraph 2;
Brody (1998); Fremont-Smith (2004) chapter 4.

---

### Rule 3 — Schedule G Part II $0 direct expenses across all events

**What it reads.** Schedule G Part II Lines 4–9: cash prizes, noncash
prizes, rent/facility costs, food and beverages, entertainment, other
direct expenses. Evaluated across all events reported by the organization
in a given fiscal year.

**Threshold.** Sum of all six expense lines across all reported events =
$0 AND event gross receipts ≥ $50,000, for ≥3 consecutive years.

**Why this is a signal.** Any genuine fundraising event with gross receipts
in the five-figure range has direct costs: venue rental, food, entertainment,
materials, prizes. An annual event with zero reported direct expenses is
either a pure telephone / online solicitation that happens to be classified
as a fundraising event (legitimate but unusual), or a reporting practice
that uses the Schedule G line item as a pass-through for donations whose
event-level accounting is not being maintained. The Office for Victims of
Crime's VOCA Subrecipient Performance Measures Dictionary and the
Government Finance Officers Association's *Budgeting Best Practices for
Nonprofit Organizations* both require event-level revenue and expense
reconciliation as part of baseline nonprofit financial accountability.

**Literature.** GAO-05-561T pp. 23–29; IRS Schedule G Instructions
Part II.

---

### Rule 4 — Multi-dimensional one-year pivot

**What it reads.** Five year-over-year comparisons for each filing: (a)
mission-text length change ≥25% (Part I Line 1), (b) employee count flat
or decreased (Part I Line 5), (c) fundraising expense collapsed ≥50% or
to zero (Part IX column D Line 25), (d) Schedule G filing status changed,
(e) Part VII Section A officer roster turnover ≥50%.

**Threshold.** ≥3 of the 5 dimensions change simultaneously in a single
fiscal year.

**Why this is a signal.** The nonprofit-governance literature treats
simultaneous multi-dimensional filing changes as a reclassification event,
distinct from routine year-over-year drift. When an organization
simultaneously rewrites its mission, alters its staffing, collapses its
fundraising-expense reporting, changes its schedule filings, and turns
over its named leadership — all within 12 months — the filing is
presenting a functionally different organization under a continuous
EIN. This may reflect a legitimate organizational restructuring (merger,
leadership transition, scope expansion), or it may reflect a reporting
posture change that warrants a closer look at the underlying transactions.

**Literature.** Light (2002); Salamon (2012) *The State of Nonprofit
America* chapter on organizational transitions.

---

### Rule 5 — Part VI governance all-No

**What it reads.** Part VI Section B answers: Line 12a (written
conflict-of-interest policy), Line 13 (written whistleblower policy),
Line 14 (written document retention and destruction policy), Line 15a
(independent review of ED compensation).

**Threshold.** All four answered "No" for ≥5 consecutive years AND
organization revenue ≥ $500,000 in each year.

**Why this is a signal.** These four policies are the IRS's documented
baseline for 501(c)(3) governance accountability, as enumerated in
"Governance and Related Topics" (2008). The IRS's stated position is that
each policy should exist in writing. Their universal absence across a
multi-year window at a mid-sized organization indicates a sustained
decision to operate outside the IRS-identified accountability baseline —
not an oversight correctable by next year's filing.

**Literature.** IRS "Governance and Related Topics — 501(c)(3)
Organizations" (February 4, 2008), pp. 2–8; BoardSource (2021) index of
board practices; GAO-05-561T.

---

### Rule 6 — Schedule O verbatim-template narrative

**What it reads.** Schedule O free-text narratives for Part VI Lines 11b,
18, and 19, normalized to uppercase and collapsed whitespace.

**Threshold.** Identical normalized narrative text across ≥5 consecutive
years, combined with narratives that assert absence of review processes
(e.g., phrases matching `NO REVIEW.*CONDUCTED` or `NO DOCUMENTS AVAILABLE`).

**Why this is a signal.** Schedule O is the IRS's free-form narrative space
for an organization to explain its governance practices. Repeating an
identical template across consecutive years indicates the absence of an
actual governance practice being narrated. When the template itself
attests to the non-existence of a process (rather than describing the
process), the organization is using the free-text space to formalize the
absence of governance — a different disclosure act than either describing
a process or leaving the field blank.

**Literature.** IRS Schedule O Instructions; BoardSource survey data on
nonprofit documentation practices.

---

### Rule 7 — Capacity mismatch (revenue growth without headcount growth)

**What it reads.** Part I Line 12 (total revenue) and Part I Line 5
(employee count) paired across a five-year window.

**Threshold.** `revenue(t) ≥ 1.5 × revenue(t-5)` AND `employees(t) ≤ employees(t-5)`
AND `employees(t-5) ≥ 5`.

**Why this is a signal.** For direct-service nonprofits — which includes
every organization in the scoped NTEE codes — operational capacity scales
with staff. A nonprofit that grows its revenue by ≥50% over five years
while holding headcount flat or decreasing is either extracting
efficiency gains at the theoretical limit, or booking revenue that does
not translate into proportional service delivery. The former is rare at
sustained duration in direct-service delivery; the latter is a signal
worth examining against the organization's own program-service
accomplishment narratives in Part III.

**Literature.** Urban Institute Center on Nonprofits and Philanthropy,
*Nonprofit Sector Brief* series; NCCS human-services subsector
benchmarking studies.

---

### Rule 8 — Service-area growth without staffing growth

**What it reads.** Part I Line 1 mission-text analysis for count of named
service areas (parishes, counties, states, regions). Part I Line 5
employee count. Both evaluated year-over-year.

**Threshold.** Service-area count increases by ≥2 in a single year AND
employee count increase ≤1 in the same year.

**Why this is a signal.** Federal grant pass-through programs — VOCA,
VAWA, SSBG — distribute funds in part on declared service-area coverage.
A single-year expansion of claimed service area without a corresponding
staffing increase is a discrepancy between declared and operational
capacity. The Office for Victims of Crime's VOCA monitoring guidance
specifically flags mismatch between declared service-area coverage and
staff-hours documentation as a subgrantee risk indicator.

**Literature.** OVC VOCA Subrecipient Performance Measures Dictionary;
Federal Register notices for annual VOCA formula-grant distributions;
Violence Against Women Office Grants Financial Management Guide.

---

## Composite scoring

The composite score aggregates the eight detector outputs into a single
per-organization metric:

```
composite = Σ(weight_i × detector_score_i)  for i in 1..8
```

Detector weights:

| Detector | Weight |
|---|---|
| Rule 1 — Zero ED comp sustained    | 0.15 |
| Rule 2 — Officer undercount         | 0.10 |
| Rule 3 — Schedule G $0 expenses     | 0.15 |
| Rule 4 — Multi-dim pivot            | 0.20 |
| Rule 5 — Governance all-No          | 0.10 |
| Rule 6 — Schedule O verbatim        | 0.10 |
| Rule 7 — Capacity mismatch          | 0.10 |
| Rule 8 — Area growth w/o staff      | 0.10 |

Weights are documented and modifiable. The defaults reflect an assessment
that the multi-dimensional pivot detector (Rule 4) is the sharpest signal
because it aggregates five independent co-moving dimensions, and that the
zero-ED-comp and Schedule-G detectors are individually more
discriminating than the governance-policy detectors (which tend to have
higher sector baseline rates of "No" answers).

Sensitivity analysis: re-running with uniform weights (all 0.125) produces
substantially similar rank orderings in the upper tail, differing primarily
in the middle of the distribution where scoring is least decisive.

## Known false-positive sources

The detectors are calibrated to be conservative — i.e., to require
sustained patterns across multiple years rather than flag single-year
events. Even so, several sector subpopulations score high for structural
reasons unrelated to governance opacity:

1. **National-affiliate CASA / Children's Advocacy Center networks** use
   shared filing templates across their member organizations. Member
   affiliates tend to produce similar Schedule O language and similar Part
   VI answers by convention rather than by independent choice. This can
   elevate Rule 5 and Rule 6 scores across an entire sub-network
   simultaneously. Users should treat the CASA sub-population
   (NTEE I72 with name contains "CASA" or "Court Appointed Special
   Advocates") as a separate stratum with its own baseline.

2. **All-volunteer small organizations** (revenue near the $500K threshold
   with all-volunteer boards) legitimately score high on Rules 1 and 5.
   The detectors apply revenue-threshold floors to mitigate this, but
   borderline cases remain.

3. **Grant-dependent organizations with minimal fundraising-event
   activity** score high on Rule 3. A victim-service nonprofit primarily
   funded through VOCA pass-through grants may legitimately have no
   fundraising events requiring Schedule G. Rule 3's $50K event-gross
   floor mitigates but does not eliminate this.

4. **Recent founders and newly-established 501(c)(3)s** lack the multi-year
   history the detectors require. A three-year-old organization cannot
   fire Rule 1 (needs 3+ consecutive years) or Rule 5 (needs 5+). This is
   intended behavior — detectors operate on verified multi-year patterns,
   not on snapshot filings.

## Data sources

All data is drawn from:

1. **ProPublica Nonprofit Explorer API** (`projects.propublica.org/nonprofits/api/v2/`).
   The fetcher paginates through NTEE-filtered organization lists and
   pulls the most recent filing XML for each.
2. **IRS Exempt Organizations Business Master File** (for EIN-level
   metadata not carried in the ProPublica API response, including NTEE
   code and ruling year).

No private, leaked, or unauthorized data is used at any stage.

## References

### IRS and federal guidance
- Internal Revenue Service. *Governance and Related Topics — 501(c)(3) Organizations.* February 4, 2008.
- Internal Revenue Service. *Instructions for Form 990*, Parts I, VI, VII, IX; Schedules G and O (various years).
- U.S. Department of Justice, Office for Victims of Crime. *VOCA Subrecipient Performance Measures Dictionary.* Various years.
- U.S. Department of Justice, Office on Violence Against Women. *Grants Financial Management Guide.* Various years.

### Academic and sector-research literature
- Brody, Evelyn. "The Limits of Charity Fiduciary Law." *Maryland Law Review* 57 (1998): 1400–1501.
- Fremont-Smith, Marion R. *Governing Nonprofit Organizations: Federal and State Law and Regulation.* Harvard University Press, 2004.
- Light, Paul C. *Pathways to Nonprofit Excellence.* Brookings Institution Press, 2002.
- Salamon, Lester M. (ed.) *The State of Nonprofit America.* Brookings Institution Press, second edition, 2012.
- Urban Institute Center on Nonprofits and Philanthropy. *Nonprofit Sector Brief* series. 2019–present.
- BoardSource. *Leading with Intent: National Index of Nonprofit Board Practices.* Periodic (2012, 2015, 2017, 2021).

### Government oversight reports
- Government Accountability Office. *Tax-Exempt Sector: Governance, Transparency, and Financial Accountability.* GAO-05-561T (2005).
- Government Accountability Office. *Nonprofit Sector: Significant Federal Funds Reach the Sector Through Various Mechanisms.* GAO-09-193 (2009).
- Office of Inspector General, U.S. Department of Justice. Multiple VOCA subgrantee compliance reports (2015–2024).
