# propublica-grader

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19724234.svg)](https://doi.org/10.5281/zenodo.19724234)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A reproducible detector for governance-opacity patterns in IRS Form 990 filings,
targeted at domestic-violence and abuse-victim-service 501(c)(3) organizations
(NTEE codes I70–I74 and P43).

Consumes the publicly available IRS e-file 990 data surfaced by the
[ProPublica Nonprofit Explorer](https://projects.propublica.org/nonprofits/).
Produces a per-organization score on eight independent governance indicators
drawn from the IRS Form 990 itself and from the nonprofit-governance
literature. No private or non-public data is used at any stage.

---

## Scope

The tool evaluates filings for organizations in six NTEE categories that
together span the U.S. domestic-violence and family-abuse service sector:

| Code | Category                                                        |
|------|-----------------------------------------------------------------|
| P43  | Family Violence Shelters and Services                           |
| I70  | Protection Against, Prevention of Neglect, Abuse, Exploitation  |
| I71  | Spouse Abuse, Prevention of                                     |
| I72  | Child Abuse, Prevention of                                      |
| I73  | Sexual Abuse, Prevention of                                     |
| I74  | Rape Victim Services                                            |

This cross-NTEE sweep avoids the common error of restricting sector analysis
to a single code. Operationally similar organizations self-classify across
both major groups I (Crime & Legal-Related) and P (Human Services)
depending on founding framing and grant-eligibility considerations.

## What it computes

For each organization in the sector, the scanner computes a composite score
(0–100) over eight indicators of governance opacity. Each indicator is
documented with (a) the specific Form 990 field it reads, (b) the threshold
at which it fires, and (c) the governance-literature basis for treating the
pattern as a potential opacity signal.

| # | Indicator                                              | 990 fields consulted                   |
|---|--------------------------------------------------------|----------------------------------------|
| 1 | Sustained affirmative $0 officer compensation          | Part VII §A; Part IX L5; Part I L12    |
| 2 | Part VII officer undercount vs Part VI voting members  | Part VI L1a; Part VII §A row count     |
| 3 | Schedule G Part II $0 direct expenses across all events | Schedule G Part II L4–9                |
| 4 | Multi-dimensional one-year pivot                        | Part I L1, L5; Part IX D L25; Sch G    |
| 5 | Part VI governance all-No                               | Part VI L11b, 12a, 13, 14, 15a         |
| 6 | Schedule O verbatim-template narrative                  | Schedule O §1                          |
| 7 | Capacity mismatch (revenue/headcount divergence)        | Part I L5, L12; year-over-year         |
| 8 | Service-area growth without staffing growth             | Part I L1 mission text; Part I L5      |

Detailed rule documentation, including the governance-literature basis for
each, is in [`docs/methodology.md`](docs/methodology.md).

## Output

The scanner emits two files per run:

- `output/scored.csv` — one row per organization, all scored indicators,
  composite score, basic metadata (EIN, name, state, NTEE, revenue).
- `output/gaps.csv` — organizations with BMF revenue above the reporting
  threshold but no indexed Form 990 in ProPublica's database (paper-filed,
  late-filed, or IRS-processing delay). Separate output because these
  represent a different class of anomaly than the scored cohort.

No commentary or interpretation is added to the output. Downstream review of
any specific high-scoring organization is left to the user, and should
consult the organization's primary filings before drawing conclusions from
the score alone.

## Installation

```bash
git clone https://github.com/qui-tam/propublica-grader.git
cd propublica-grader
pip install -r requirements.txt
```

Python 3.10+ recommended. Depends on `requests`, `pandas`, and the Python
standard `sqlite3` module (stdlib).

## Usage

```bash
# 1. Fetch the NTEE-filtered organization list and recent 990 XML data
python -m fetcher.fetch_sector --output data/sector.db

# 2. Parse fetched XML into the facts schema
python -m fetcher.parse --input data/sector.db

# 3. Run detectors and emit composite scores
python -m scorer.run --input data/sector.db --output output/

# 4. Inspect results
sqlite3 data/sector.db < examples/basic_queries.sql
```

Total wall time: approximately 15 minutes on a consumer laptop for the full
sector (about 4,000 organizations at the time of release).

## Scope of claims

This tool detects patterns. It does not assert wrongdoing. Each of the eight
indicators has a benign explanation in some subset of the sector: small
nonprofits with volunteer executive directors, organizations receiving
primarily direct grants (no fundraising events), and filings prepared by
under-resourced staff using templated narratives. A high composite score is
best read as an indication that an organization's *public reporting*
warrants closer examination against its *operational documentation* held at
state DV coalitions, state administering agencies (for VOCA/VAWA
subgrantees), and state attorney-general charitable-oversight offices.

The scorer's role is to reduce a sector of several thousand organizations to
a shorter shortlist. What happens at the shortlist stage is a matter for
investigative journalists, academic researchers, state regulators, and
federal grant-oversight bodies — all of whom have tools and authorities this
software does not.

## Reproducibility

All data sources are public. All detection thresholds are documented. All
rule implementations are version-controlled and unit-tested against
fixture data checked into this repository. Any two users running the
scanner on the same IRS e-file snapshot should obtain identical output.

The scanner does not maintain or update a hosted result table. Users
generate their own results by running the pipeline on current ProPublica
data at the time of their inquiry.

## License

MIT. See [LICENSE](LICENSE).

## Citation

If this tool supports published research, journalism, or regulatory
analysis, please cite:

> qui-tam. (2026). *propublica-grader: A governance-opacity detector for
> domestic-violence and abuse-victim-service 501(c)(3) organizations*
> (Version 0.1.0) [Software]. Zenodo.
> https://doi.org/10.5281/zenodo.19724234

**DOI:** [10.5281/zenodo.19724234](https://doi.org/10.5281/zenodo.19724234)
**Repository:** <https://github.com/qui-tam/propublica-grader>
**License:** MIT

Every tagged GitHub release produces a new archived Zenodo snapshot with
its own DOI. Cite the specific version used, not the repository URL, for
reproducible attribution.

## References

The detection rules draw on the following literature:

- Internal Revenue Service. *Governance and Related Topics — 501(c)(3) Organizations.* February 4, 2008.
- BoardSource. *Leading with Intent: National Index of Nonprofit Board Practices.* 2021.
- Fremont-Smith, Marion R. *Governing Nonprofit Organizations: Federal and State Law and Regulation.* Harvard University Press, 2004.
- Light, Paul C. *Pathways to Nonprofit Excellence.* Brookings Institution Press, 2002.
- Brody, Evelyn. "The Limits of Charity Fiduciary Law." *Maryland Law Review* 57 (1998).
- Government Accountability Office. *Tax-Exempt Sector: Governance, Transparency, and Financial Accountability.* GAO-05-561T (2005).
- Office for Victims of Crime. *VOCA Subrecipient Performance Measures Dictionary.* U.S. Department of Justice, various years.

Full citation list with methodological notes: [`docs/methodology.md`](docs/methodology.md#references).
