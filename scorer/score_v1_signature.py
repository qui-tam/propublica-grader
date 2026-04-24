#!/usr/bin/env python3
"""Stage 3: score the governance-opacity pattern across all orgs with
structured ProPublica data, plus write a 'gap-suspects' list for full-990 orgs
missing from ProPublica entirely.

Score components (all 0-100, higher = more opacity-pattern-matching):

  A. zero-officer-comp anomaly
     Years where compnsatncurrofcr=0 AND othrsalwages>0, as % of filings
     (opacity marker: staff exists but named officers report $0)

  B. zero-fundraising anomaly
     Years where grsincfndrsng=0 AND lessdirfndrsng=0 AND totcntrbgfts>$50K,
     as % of filings
     (opacity marker: significant contributions but no fundraising events reported)

  C. surplus accumulation
     Mean (totrevenue-totfuncexpns)/totrevenue across filings, clamped to [0,1]
     (Flags orgs banking donations instead of spending on mission)

  D. unnatural YoY revenue stability
     Flag if stdev(revenue)/mean(revenue) < 0.05 across 5+ filings
     (Template/copy-paste returns)

  E. pattern duration multiplier
     max(min(filings/10, 1.0), 0.3) — long patterns get weight

Composite = weighted sum of A,B,C with E as multiplier. D adds 10 points if hit.
"""
import csv
import json
import statistics
from pathlib import Path

import sys; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schema.paths import DATA_DIR, RAW_DIR, BMF_DIR, PROPUBLICA_DIR, USASPENDING_DIR, GUIDESTAR_DIR, XML_DIR, XML_BATCH_DIR, XML_EXTRACT_DIR, FILTERED_DIR, REPORTS_DIR
ROOT = DATA_DIR.parent  # repo-root compat for legacy refs below
PP = PROPUBLICA_DIR
OUT = REPORTS_DIR
OUT.mkdir(exist_ok=True)

# BMF lookup
bmf = {}
with (ROOT / "filtered/dv-foundations-all.csv").open() as f:
    for r in csv.DictReader(f):
        bmf[r["EIN"].zfill(9)] = r

def to_int(v):
    try:
        return int(v or 0)
    except (ValueError, TypeError):
        return 0

def score_org(d):
    filings = sorted(d.get("filings_with_data", []), key=lambda f: f.get("tax_prd_yr", 0))
    if not filings:
        return None

    # Per-year flags
    A_hits = 0
    B_hits = 0
    surplus_ratios = []
    revenues = []
    for f in filings:
        co = to_int(f.get("compnsatncurrofcr"))
        os_ = to_int(f.get("othrsalwages"))
        gf = to_int(f.get("grsincfndrsng"))
        lf = to_int(f.get("lessdirfndrsng"))
        tc = to_int(f.get("totcntrbgfts"))
        tr = to_int(f.get("totrevenue"))
        te = to_int(f.get("totfuncexpns"))

        if co == 0 and os_ > 0:
            A_hits += 1
        if gf == 0 and lf == 0 and tc > 50_000:
            B_hits += 1
        if tr > 0:
            surplus_ratios.append((tr - te) / tr)
            revenues.append(tr)

    n = len(filings)
    A_score = 100.0 * A_hits / n
    B_score = 100.0 * B_hits / n
    C_raw = statistics.mean(surplus_ratios) if surplus_ratios else 0
    C_score = max(0.0, min(1.0, C_raw)) * 100.0

    # D: unnatural stability
    D_hit = False
    if len(revenues) >= 5 and statistics.mean(revenues) > 0:
        cv = statistics.stdev(revenues) / statistics.mean(revenues)
        if cv < 0.05:
            D_hit = True

    # E: duration multiplier
    E = max(0.3, min(1.0, n / 10.0))

    # Composite: A and B are the strongest opacity signals, C moderate, D bonus
    composite = (0.45 * A_score + 0.35 * B_score + 0.20 * C_score) * E
    if D_hit:
        composite += 10

    return {
        "n_filings": n,
        "year_range": f"{filings[0].get('tax_prd_yr','?')}-{filings[-1].get('tax_prd_yr','?')}",
        "latest_revenue": to_int(filings[-1].get("totrevenue")),
        "latest_totfuncexpns": to_int(filings[-1].get("totfuncexpns")),
        "latest_othrsalwages": to_int(filings[-1].get("othrsalwages")),
        "latest_compnsatncurrofcr": to_int(filings[-1].get("compnsatncurrofcr")),
        "A_zero_officer_comp_pct": round(A_score, 1),
        "B_zero_fundraising_pct": round(B_score, 1),
        "C_surplus_pct": round(C_score, 1),
        "D_stability_flag": "Y" if D_hit else "",
        "E_duration_mult": round(E, 2),
        "composite": round(composite, 1),
    }

# Score every ProPublica JSON
results = []
no_filings = []
for p in sorted(PP.glob("*.json")):
    if p.name.startswith("_"):
        continue
    ein = p.stem.zfill(9)
    try:
        d = json.load(open(p))
    except Exception:
        continue
    s = score_org(d)
    bmf_row = bmf.get(ein, {})
    base = {
        "EIN": ein,
        "NAME": d.get("organization", {}).get("name", "")[:70],
        "STATE": d.get("organization", {}).get("state", ""),
        "CITY": d.get("organization", {}).get("city", ""),
        "NTEE_CD": bmf_row.get("NTEE_CD", ""),
        "FILING_REQ_CD": bmf_row.get("FILING_REQ_CD", ""),
        "RULING": bmf_row.get("RULING", ""),
        "REVOKED": bmf_row.get("REVOKED", ""),
        "MANUAL_INCLUDE": bmf_row.get("MANUAL_INCLUDE", ""),
    }
    if s is None:
        no_filings.append(base)
    else:
        base.update(s)
        results.append(base)

results.sort(key=lambda r: r["composite"], reverse=True)

# Write ranked CSV
cols = [
    "composite", "EIN", "NAME", "STATE", "CITY", "NTEE_CD",
    "n_filings", "year_range", "latest_revenue", "latest_totfuncexpns",
    "latest_othrsalwages", "latest_compnsatncurrofcr",
    "A_zero_officer_comp_pct", "B_zero_fundraising_pct", "C_surplus_pct",
    "D_stability_flag", "E_duration_mult",
    "FILING_REQ_CD", "RULING", "REVOKED", "MANUAL_INCLUDE",
]
out_path = OUT / "suspicion-ranked.csv"
with out_path.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(results)
print(f"Scored: {len(results):,}   |   no filings_with_data: {len(no_filings):,}")
print(f"Wrote {out_path}")



# Top-50 human-readable markdown
md = OUT / "top-50-suspicion.md"
with md.open("w") as f:
    f.write(f"# Top 50 DV 501(c)(3)s by governance-opacity signature suspicion score\n\n")
    f.write(f"Scored {len(results):,} orgs with structured ProPublica 990 data.\n\n")
    f.write(f"Top scorers surface at the top of the list.\n\n")
    f.write("Scoring components:\n")
    f.write("- **A** = % of filings with `compnsatncurrofcr=0 & othrsalwages>0` (staff exists, officers report $0)\n")
    f.write("- **B** = % of filings with `grsincfndrsng=0 & lessdirfndrsng=0 & totcntrbgfts>$50K` (has contributions, no fundraising events)\n")
    f.write("- **C** = mean surplus ratio (revenue minus expenses / revenue)\n")
    f.write("- **D** = unnatural YoY revenue stability flag (CV < 5% over 5+ years)\n")
    f.write("- **E** = duration multiplier (more filings → stronger signal)\n\n")
    f.write("| # | Score | EIN | Name | ST | Rev (latest) | Filings | A% | B% | C% | D |\n")
    f.write("|---|------:|-----|------|----|-------------:|--------:|---:|---:|---:|---|\n")
    for i, r in enumerate(results[:50], 1):
        f.write(f"| {i} | {r['composite']} | {r['EIN']} | {r['NAME']} | {r['STATE']} | ${r['latest_revenue']:,} | {r['n_filings']} | {r['A_zero_officer_comp_pct']} | {r['B_zero_fundraising_pct']} | {r['C_surplus_pct']} | {r['D_stability_flag']} |\n")
print(f"Wrote {md}")

# Gap-suspects: full-990 required but no ProPublica data AND nonzero BMF revenue
gap_rows = []
scored_eins = {r["EIN"] for r in results} | {r["EIN"] for r in no_filings}
for ein_str, row in bmf.items():
    if ein_str in scored_eins and ein_str not in {n["EIN"] for n in no_filings}:
        # Already scored, skip
        continue
    if row.get("FILING_REQ_CD") != "01":
        continue
    rev = to_int(row.get("REVENUE_AMT"))
    if rev <= 0:
        continue
    gap_rows.append({
        "EIN": ein_str, "NAME": row["NAME"], "CITY": row["CITY"], "STATE": row["STATE"],
        "NTEE_CD": row["NTEE_CD"], "REVENUE_AMT": rev, "ASSET_AMT": row["ASSET_AMT"],
        "RULING": row["RULING"], "FILING_REQ_CD": row["FILING_REQ_CD"],
        "REVOKED": row["REVOKED"], "MANUAL_INCLUDE": row.get("MANUAL_INCLUDE",""),
    })
gap_rows.sort(key=lambda r: r["REVENUE_AMT"], reverse=True)
gap_path = OUT / "gap-suspects.csv"
gap_cols = ["REVENUE_AMT","ASSET_AMT","EIN","NAME","CITY","STATE","NTEE_CD","RULING","FILING_REQ_CD","REVOKED","MANUAL_INCLUDE"]
with gap_path.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=gap_cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(gap_rows)
print(f"\nGap-suspects (no ProPublica data, full-990 required, nonzero BMF rev): {len(gap_rows)}")
print(f"Wrote {gap_path}")
