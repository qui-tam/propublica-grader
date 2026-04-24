# State AG Charitable Registration — Feasibility Map

**Goal:** cross-reference DV 501(c)(3) EINs against state-level charitable solicitation registries. An org soliciting in a state without being registered = separate violation layer beyond IRS.

**Top-15 states cover 62.9% of the dataset (2,494 / 3,967 orgs).**

| Rank | State | DV orgs | Registry name | Data access | Complexity |
|-----:|-------|--------:|---------------|-------------|------------|
| 1 | CA | 476 | Registry of Charitable Trusts (AG) | **Downloadable CSV** at oag.ca.gov/charities/registry — full registry dump, includes status (active/suspended/revoked/delinquent) | **Low** — one download, join by EIN |
| 2 | TX | 343 | **No state charitable registration.** TX only regulates charitable trusts (Texas Business Organizations Code §252). Most 501(c)(3)s don't need to register. | N/A | N/A — skip this state |
| 3 | FL | 236 | Department of Agriculture — "Gift Givers Guide" | **Downloadable** at fdacs.gov — includes registration status, financial data, exec compensation, fundraiser contracts | **Low** |
| 4 | GA | 169 | Secretary of State — Charities Division | Search-only (corpgasos.state.ga.us). No bulk download. Individual HTML lookups. | **Medium** — scrape |
| 5 | NC | 143 | Secretary of State — Charitable Solicitation Licensing | Search at sosnc.gov/csl. HTML scrape only. | **Medium** |
| 6 | IL | 138 | AG Charitable Trust Bureau | **Downloadable** AG990-IL filings + annual registration data. Often behind FOIA but some aggregated. | **Medium** |
| 7 | MI | 137 | AG Charitable Trust Section | Search at michigan.gov/ag. HTML scrape. | **Medium** |
| 8 | NY | 135 | AG Charities Bureau | **CHAR500 filings public** at charitiesnys.com — downloadable dataset with audited financials, board detail. | **Low** — high-value |
| 9 | PA | 127 | Dept of State — Charitable Organizations | Search at dos.pa.gov. HTML scrape. Financial reports attached. | **Medium** |
| 10 | VA | 114 | Dept of Agriculture — Office of Charitable and Regulatory Programs | Search at vdacs.virginia.gov. HTML scrape. | **Medium** |
| 11 | OR | 101 | AG Charitable Activities Section | **Downloadable CT-12 filings** at justice.oregon.gov | **Low** |
| 12 | OH | 98 | AG Charitable Law Section | Search at charitableregistration.ohioago.gov. HTML scrape. | **Medium** |
| 13 | WA | 96 | Secretary of State | Search at sos.wa.gov/charities. HTML scrape. | **Medium** |
| 14 | NJ | 92 | Div of Consumer Affairs | Search at njconsumeraffairs.gov/charities. HTML scrape. | **Medium** |
| 15 | AZ | 89 | No state charitable solicitation registration | N/A | Skip |

## Recommended approach (tiered)

### Tier 1 — Quick wins (downloadable bulk data):
- **CA (476)**, **FL (236)**, **NY (135)**, **OR (101)** — total 948 orgs (24% of dataset)
- Each is a single download + join by EIN. ~1 day of work.
- NY is especially high-value: CHAR500 includes audited board compensation, matching our scoring signals.

### Tier 2 — Scrape targets (medium complexity, high volume):
- **GA (169)**, **NC (143)**, **IL (138)**, **MI (137)**, **PA (127)**, **VA (114)**, **OH (98)**, **WA (96)**, **NJ (92)** — 1,114 orgs (28%)
- Each needs a one-off scraper. Rate-limit risk.
- Write once per state, reusable.

### Tier 3 — Manual or skip:
- **TX (343)**, **AZ (89)**: no state-level registration for most 501(c)(3)s. Can't enrich here.
- Remaining states (37% of dataset): varied, most have registration but low volume per state.

## Minimal viable next step

Pull the **4 Tier-1 downloadables** (CA + FL + NY + OR) — covers 24% of the dataset and doesn't require scraping. 
That gives us a `STATE_AG_STATUS` column populated for ~948 orgs including flags like:
- `registered_active`
- `registered_delinquent` (missed annual filing)
- `suspended` or `revoked`
- `not_registered_despite_soliciting` (org has CA zip code but no CA AG registration)

The 4th status is the scammer signal — soliciting contributions without state registration is a violation in its own right.

## Outstanding questions before execution

1. **Cross-state solicitation**: An org based in LA but soliciting in CA must register in CA too. Scope = just "home state" or "all states where solicited"? The latter multiplies work by ~10x.
2. **Historical data**: Most registries only show current status. For the fraud-pattern analysis, we'd want historical "went delinquent in FY20" records. Most states don't expose this publicly.
3. **Louisiana note:** Louisiana has Department of Justice Consumer Protection — but no centralized charitable solicitation registry. Louisiana Secretary of State business registration is the closest analog.
