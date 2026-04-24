#!/usr/bin/env python3
"""Refined governance-opacity scorer.

v1 flagged lots of tiny volunteer-board shelters as high-suspicion because the
'zero officer comp + zero fundraising events' pattern is structurally normal
at that scale. v2 adds discriminating signals:

  SCALE FILTER:
    Only score orgs with avg revenue >= $500K AND avg revenue <= $50M.
    At $500K+, a real DV shelter has a paid ED listed somewhere on 990.
    Above $50M is a different beast (national/state coalitions, not fraud-scale).

  NEW SIGNALS (all on avg across filings):
    F. Accumulation anomaly: net_assets_latest / avg_revenue
       Healthy shelter: 0.3-0.8x (spends what it gets, keeps some reserves)
       Suspicious: 1.2x+ (hoarding)
    G. Contribution dependency: avg_totcntrbgfts / avg_totrevenue
       Most shelters have SOME program revenue (Medicaid billing, fees).
       100% contribution-funded = can't be cross-checked against clients
    H. Salary-to-revenue outlier: avg_othrsalwages / avg_totrevenue
       Normal DV shelter: 50-70%. Very low (<20%) = suspicious where's-the-money.
    I. Program revenue absence: avg_totprgmrevnue / avg_totrevenue < 5%
       Combined with size >$500K = no billable services to clients

  COMPOSITE (out of 100):
     Base = 0.25*A + 0.15*B + 0.25*F_score + 0.15*G_score + 0.10*H_score + 0.10*I_score
     * E_duration (year multiplier)
     + 10 if D stability flag hits

Result: a ranked list where top entries are actually anomalous, not just small.
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

bmf = {}
with (ROOT / "filtered/dv-foundations-all.csv").open() as f:
    for r in csv.DictReader(f):
        bmf[r["EIN"].zfill(9)] = r

MIN_REV = 500_000
MAX_REV = 50_000_000

def to_int(v):
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0

def score(d):
    filings = sorted(d.get("filings_with_data", []), key=lambda f: f.get("tax_prd_yr", 0))
    if len(filings) < 3:
        return None

    # Compute averages and series
    revenues = [to_int(f.get("totrevenue")) for f in filings]
    avg_rev = statistics.mean(revenues) if revenues else 0
    if not (MIN_REV <= avg_rev <= MAX_REV):
        return None

    contrib = statistics.mean(to_int(f.get("totcntrbgfts")) for f in filings)
    prog = statistics.mean(to_int(f.get("totprgmrevnue")) for f in filings)
    expns = statistics.mean(to_int(f.get("totfuncexpns")) for f in filings)
    salary = statistics.mean(to_int(f.get("othrsalwages")) for f in filings)

    latest = filings[-1]
    net_assets = to_int(latest.get("totnetassetend"))

    # A: zero officer comp while staff payroll exists
    A_hits = sum(1 for f in filings if to_int(f.get("compnsatncurrofcr"))==0 and to_int(f.get("othrsalwages"))>0)
    A = 100.0 * A_hits / len(filings)

    # B: zero fundraising events while significant contributions
    B_hits = sum(1 for f in filings if to_int(f.get("grsincfndrsng"))==0 and to_int(f.get("lessdirfndrsng"))==0 and to_int(f.get("totcntrbgfts"))>50_000)
    B = 100.0 * B_hits / len(filings)

    # D: unnatural YoY revenue stability
    D_hit = False
    if len(revenues) >= 5 and statistics.mean(revenues) > 0:
        cv = statistics.stdev(revenues) / statistics.mean(revenues)
        if cv < 0.05:
            D_hit = True

    # E: duration multiplier
    E = max(0.3, min(1.0, len(filings) / 10.0))

    # F: accumulation (net_assets / avg_revenue)
    # Map: 0.3x-0.8x = 0pts; 1.0x = 30pts; 1.5x = 70pts; 2.0x+ = 100pts
    accum_ratio = net_assets / avg_rev if avg_rev else 0
    if accum_ratio < 0.8:
        F = 0
    elif accum_ratio < 1.0:
        F = 20
    elif accum_ratio < 1.5:
        F = 40 + 40 * (accum_ratio - 1.0) / 0.5
    elif accum_ratio < 2.0:
        F = 80 + 20 * (accum_ratio - 1.5) / 0.5
    else:
        F = 100

    # G: contribution dependency
    contrib_share = contrib / avg_rev if avg_rev else 0
    if contrib_share < 0.7:
        G = 0
    elif contrib_share < 0.9:
        G = 50 * (contrib_share - 0.7) / 0.2
    else:
        G = 50 + 50 * min((contrib_share - 0.9) / 0.1, 1.0)

    # H: salary-to-revenue outlier (very low = suspicious)
    salary_share = salary / avg_rev if avg_rev else 0
    if salary_share >= 0.30:
        H = 0   # normal 30-70% salary is healthy
    elif salary_share >= 0.15:
        H = 30 * (0.30 - salary_share) / 0.15
    else:
        H = 60 + 40 * (0.15 - salary_share) / 0.15

    # I: program revenue absence at scale
    prog_share = prog / avg_rev if avg_rev else 0
    if prog_share >= 0.10:
        I = 0
    elif prog_share >= 0.02:
        I = 50 * (0.10 - prog_share) / 0.08
    else:
        I = 50 + 50 * max(0, 1 - prog_share/0.02)

    composite = (0.25*A + 0.15*B + 0.25*F + 0.15*G + 0.10*H + 0.10*I) * E
    if D_hit:
        composite += 10

    return {
        "n_filings": len(filings),
        "year_range": f"{filings[0].get('tax_prd_yr','?')}-{filings[-1].get('tax_prd_yr','?')}",
        "avg_rev": int(avg_rev),
        "latest_netassets": net_assets,
        "accum_ratio": round(accum_ratio, 2),
        "contrib_share": round(contrib_share, 2),
        "prog_share": round(prog_share, 2),
        "salary_share": round(salary_share, 2),
        "expns_share": round(expns/avg_rev, 2) if avg_rev else 0,
        "A_zero_offcr_comp": round(A,1),
        "B_zero_fundrsng": round(B,1),
        "D_stability": "Y" if D_hit else "",
        "E_dur": round(E,2),
        "F_accum": round(F,1),
        "G_contrib_dep": round(G,1),
        "H_low_salary": round(H,1),
        "I_no_prog_rev": round(I,1),
        "composite": round(composite, 1),
    }

results = []
for p in sorted(PP.glob("*.json")):
    if p.name.startswith("_"):
        continue
    ein = p.stem.zfill(9)
    try:
        d = json.load(open(p))
    except Exception:
        continue
    s = score(d)
    if s is None:
        continue
    row = bmf.get(ein, {})
    base = {
        "EIN": ein,
        "NAME": d.get("organization", {}).get("name", "")[:60],
        "STATE": d.get("organization", {}).get("state", ""),
        "CITY": d.get("organization", {}).get("city", ""),
        "NTEE_CD": row.get("NTEE_CD", ""),
        "RULING": row.get("RULING", ""),
        "REVOKED": row.get("REVOKED", ""),
    }
    base.update(s)
    results.append(base)

results.sort(key=lambda r: r["composite"], reverse=True)

cols = [
    "composite", "EIN", "NAME", "STATE", "CITY", "NTEE_CD",
    "n_filings", "year_range",
    "avg_rev", "latest_netassets",
    "accum_ratio", "contrib_share", "prog_share", "salary_share", "expns_share",
    "A_zero_offcr_comp", "B_zero_fundrsng", "F_accum", "G_contrib_dep", "H_low_salary", "I_no_prog_rev",
    "D_stability", "E_dur",
    "RULING", "REVOKED",
]
out_path = OUT / "suspicion-ranked-v2.csv"
with out_path.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(results)

print(f"v2 scored: {len(results):,} orgs (after scale + min-filings filters)")

print(f"\nTop 20:")
print(f"{'#':<3}{'Score':>6}{'EIN':>12}  {'State':<3}  {'Name':<42}  {'AvgRev':>10}  {'Accum':>6}  {'Contr%':>7}  {'Prog%':>6}  {'Sal%':>6}")
print("-" * 120)
for i, r in enumerate(results[:20], 1):
    print(f"{i:<3}{r['composite']:>6}  {r['EIN']}  {r['STATE']:<3}  {r['NAME']:<42}  {r['avg_rev']:>10,}  {r['accum_ratio']:>5.2f}x  {int(r['contrib_share']*100):>6}%  {int(r['prog_share']*100):>5}%  {int(r['salary_share']*100):>5}%")
