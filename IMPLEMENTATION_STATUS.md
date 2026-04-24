# Implementation Status

**Last updated:** 2026-04-24

The [README](README.md) describes the target architecture: eight governance-opacity
indicators across every filing in NTEE I70–I74 and P43. This file tracks what is
actually implemented in-tree today versus what remains as scaffolding.

## Implemented

### Fetcher — fully working (`fetcher/`)

| Module | What it does | Data source |
|--------|--------------|-------------|
| `filter_bmf.py` | Downloads IRS BMF (4 regional CSVs) + Auto-Revocation List; filters to DV-sector NTEE codes (I70/I71/I72/I73 + P43). Writes `data/filtered/dv-foundations-all.csv`. | [IRS EO BMF Extract](https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf) + [IRS Auto-Revocation List](https://apps.irs.gov/pub/epostcard/data-download-revocation.zip) |
| `fetch_propublica.py` | Bulk-fetches one JSON per EIN from ProPublica Nonprofit Explorer v2 API. Resumable. 5 concurrent workers, 1s/worker throttle (~5 req/s). ~15 min for 4,000 orgs. | [ProPublica Nonprofit Explorer API](https://projects.propublica.org/nonprofits/api/v2/) |
| `fetch_usaspending.py` | Bulk-fetches federal subawards by ALN (CFDA) code: VOCA (16.575), VAWA (16.588), Rural DV (16.589), Arrest Policies (16.590), Legal Assistance (16.524), FVPSA (93.671). Polite single-worker pacing. | [USASpending Search API](https://api.usaspending.gov/api/v2/search/spending_by_award/) |
| `fetch_guidestar.py` | Probes public Candid/GuideStar profile pages for existence + Seal of Transparency level. Conservative 4s/req with abort-on-consecutive-errors backoff. | [guidestar.org/profile/{EIN}](https://www.guidestar.org/) |
| `extract_990_xml.py` | Extracts individual 990 XMLs from IRS e-file batch ZIPs. Indexes by EIN + tax-period via `index_YYYY.csv`. | [IRS e-file 990 XML batches](https://apps.irs.gov/pub/epostcard/990/xml/) |

### Scorer — partial (`scorer/`)

| Module | Indicators implemented | Reference in README's 8-indicator schema |
|--------|------------------------|------------------------------------------|
| `score_v1_signature.py` | Zero officer comp; zero fundraising; surplus accumulation; YoY stability | Indicators #1, #3 (and orthogonal signals) |
| `score_v2_weighted.py` | v1 signals + revenue-scale filter + accumulation ratio + contribution dependency + salary-share anomaly + program-revenue absence | Indicators #1, #3, #7 (partial) + 4 orthogonal signals |
| `tier_leads.py` | Reframes scored output as a tiered lead/watchlist (Tier A-D): which orgs are likely yeses for remediation vs. likely refusers. Refusers become AG-referral candidates. | Not in 8-indicator schema — a separate practical output layer |

### Docs (`docs/`)

- `state-ag-feasibility.md` — per-state map of U.S. charitable-registration registry access (downloadable vs. scrape vs. unavailable). Covers top 15 states by DV-org count.

## Not yet implemented (scaffolded only)

### Detectors (`detectors/` — empty directory)

The README's indicator framework treats each indicator as a standalone detector
module. That factoring is cleaner than the current monolithic `scorer/score_v*.py`
files. Still to do:

- `d01_zero_officer_comp.py` — sustained affirmative $0 officer comp
- `d02_officer_undercount.py` — Part VII rows < Part VI voting members
- `d03_zero_fundraising_events.py` — Schedule G Part II $0 direct expenses
- `d04_pivot_year.py` — multi-dimensional one-year pivot
- `d05_governance_all_no.py` — Part VI 11b/12a/13/14/15a all "No"
- `d06_schedule_o_template.py` — verbatim-template detection via n-gram hashing
  (caveat: the common "NO REVIEW WAS OR WILL BE CONDUCTED" boilerplate appears in
  ~28k filings and is NOT by itself a fraud signal; detector must focus on
  unusual verbatim matches, not well-known boilerplate)
- `d07_capacity_mismatch.py` — revenue/headcount divergence
- `d08_growth_without_staffing.py` — revenue growth without Part I L5 growth

Detectors #1, #3, #5 can be extracted from `scorer/score_v2_weighted.py`. The
remaining five require additional fetcher work to pull Part VII officer tables,
Part VI question answers, and Part IX line-item detail from the XML.

### Schema (`schema/` — only `paths.py`)

- `sqlite_schema.sql` — target schema for parsed 990 facts
- `parse.py` — XML → SQLite loader using the schema

### Tests (`tests/` — only `fixtures/` empty)

- Unit tests for each detector against fixture XMLs
- End-to-end test running the full pipeline against 5 known-pattern orgs

### Examples (`examples/` — empty)

- `basic_queries.sql` — sample SQLite queries on parsed facts
- `run_pipeline.sh` — end-to-end pipeline runner

## How to contribute

Each unimplemented detector is independent. Pick one from the list above, read
its row in the README for data-source references, and implement it as a module
conforming to the (to-be-written) `detectors/base.py` interface. Add fixture
data and a test, then submit a PR.
