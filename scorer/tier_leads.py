#!/usr/bin/env python3
"""Tier the scored DV 501(c)(3) dataset into remediation-outreach lead segments.

Orgs with governance gaps are qualified leads for a remediation-service offering;
the whole value prop of such a service is closing those gaps. Orgs that refuse
remediation outreach self-select into AG-referral territory — their own 990
filings already document the pattern.

Tiers (A = most likely to accept outreach, D = most likely to refuse):

  A — "Image-conscious professionalize"
      Medium org ($500K-$2M rev), governance gaps (no whistleblower / no doc
      retention), moderate accumulation (0.3-1.2x), normal fundraising events,
      functioning operations. Pitch: policy package for funder credibility.

  B — "Grant-dependent formalize"
      $250K-$5M rev, 80%+ contribution-dependent, missing multiple governance
      policies but running real programs. Pitch: federal funder readiness ahead
      of next VOCA/FVPSA cycle.

  C — "Mixed signal"
      Larger or smaller than A/B, partial signal overlap with the opacity
      pattern but not extreme. Outreach with soft pitch; measure response.

  D — "Opacity-pattern high-resistance / AG candidate"
      Extreme accumulation (1.5x+), zero officer comp persisting 10+ years on
      an org with meaningful revenue, explicit governance-refusal language in
      Schedule O, no audit committee, no board review of 990. If they refuse
      remediation outreach, they become the AG-referral cohort.

Pitch angles are computed per-org based on which specific signals are present.
"""
import csv
import json
import statistics
from pathlib import Path

import sys; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schema.paths import DATA_DIR, RAW_DIR, BMF_DIR, PROPUBLICA_DIR, USASPENDING_DIR, GUIDESTAR_DIR, XML_DIR, XML_BATCH_DIR, XML_EXTRACT_DIR, FILTERED_DIR, REPORTS_DIR
ROOT = DATA_DIR.parent  # repo-root compat for legacy refs below
PP = PROPUBLICA_DIR
OUT = REPORTS_DIR / "lead-candidates.csv"

bmf = {}
with (ROOT / "filtered/dv-foundations-all.csv").open() as f:
    for r in csv.DictReader(f):
        bmf[r["EIN"].zfill(9)] = r


def to_int(v):
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def profile(d):
    filings = sorted(d.get("filings_with_data", []), key=lambda f: f.get("tax_prd_yr", 0))
    if len(filings) < 3:
        return None
    revenues = [to_int(f.get("totrevenue")) for f in filings]
    avg_rev = statistics.mean(revenues) if revenues else 0
    if avg_rev < 100_000 or avg_rev > 50_000_000:
        return None

    contrib = statistics.mean(to_int(f.get("totcntrbgfts")) for f in filings)
    prog = statistics.mean(to_int(f.get("totprgmrevnue")) for f in filings)
    expns = statistics.mean(to_int(f.get("totfuncexpns")) for f in filings)
    salary = statistics.mean(to_int(f.get("othrsalwages")) for f in filings)

    latest = filings[-1]
    net_assets = to_int(latest.get("totnetassetend"))

    A_hits = sum(1 for f in filings if to_int(f.get("compnsatncurrofcr"))==0 and to_int(f.get("othrsalwages"))>0)
    B_hits = sum(1 for f in filings if to_int(f.get("grsincfndrsng"))==0 and to_int(f.get("lessdirfndrsng"))==0 and to_int(f.get("totcntrbgfts"))>50_000)

    return {
        "n_filings": len(filings),
        "avg_rev": int(avg_rev),
        "contrib_share": contrib / avg_rev if avg_rev else 0,
        "prog_share": prog / avg_rev if avg_rev else 0,
        "salary_share": salary / avg_rev if avg_rev else 0,
        "accum_ratio": net_assets / avg_rev if avg_rev else 0,
        "zero_offcr_comp_pct": 100 * A_hits / len(filings),
        "zero_fundrsng_pct": 100 * B_hits / len(filings),
        "latest_netassets": net_assets,
    }


def tier_and_pitch(p):
    """Assign lead tier + pitch angle."""
    tier = "?"
    reasons = []
    pitch = []

    # D — opacity-pattern high-resistance
    if (p["accum_ratio"] >= 1.5 and p["zero_offcr_comp_pct"] >= 80 and p["avg_rev"] >= 500_000):
        tier = "D"
        reasons.append(f"accum {p['accum_ratio']:.1f}x + {int(p['zero_offcr_comp_pct'])}% zero-officer-comp")
        pitch.append("High refusal risk — treat as AG-candidate if remediation outreach is refused")
    # A — image-conscious professionalize
    elif (500_000 <= p["avg_rev"] <= 2_000_000
          and 0.3 <= p["accum_ratio"] <= 1.2
          and p["zero_fundrsng_pct"] < 50):
        tier = "A"
        reasons.append(f"mid-size ($500K-$2M), healthy accum ({p['accum_ratio']:.1f}x), runs fundraising")
        pitch.append("Professionalize governance for next funder review cycle")
        if p["zero_offcr_comp_pct"] > 50:
            pitch.append("Compensation process documentation (Part VI 15a/15b)")
    # B — grant-dependent formalize
    elif (250_000 <= p["avg_rev"] <= 5_000_000
          and p["contrib_share"] >= 0.80):
        tier = "B"
        reasons.append(f"${p['avg_rev']:,} rev, {int(p['contrib_share']*100)}% contribution-dependent")
        pitch.append("Federal funder readiness — document policies before next VOCA/FVPSA cycle")
    # C — mixed
    else:
        tier = "C"
        reasons.append("mixed signals")
        pitch.append("Soft outreach, measure response")

    # Universal pitch angles
    if p["zero_offcr_comp_pct"] > 60:
        pitch.append("Board comp disclosure workflow")
    if p["zero_fundrsng_pct"] > 60:
        pitch.append("Schedule G event-tracking system")
    if p["accum_ratio"] > 1.2:
        pitch.append("Reserve-policy documentation (explain the why to funders)")
    if p["prog_share"] < 0.05 and p["avg_rev"] > 500_000:
        pitch.append("Earned-revenue pathway development")

    return tier, " | ".join(reasons), " | ".join(pitch)


rows = []
for p in sorted(PP.glob("*.json")):
    if p.name.startswith("_"):
        continue
    ein = p.stem.zfill(9)
    try:
        d = json.load(open(p))
    except Exception:
        continue
    prof = profile(d)
    if prof is None:
        continue
    tier, reasons, pitch = tier_and_pitch(prof)
    bmf_r = bmf.get(ein, {})
    rows.append({
        "lead_tier": tier,
        "EIN": ein,
        "NAME": d.get("organization", {}).get("name", "")[:60],
        "STATE": d.get("organization", {}).get("state", ""),
        "CITY": d.get("organization", {}).get("city", ""),
        "NTEE_CD": bmf_r.get("NTEE_CD", ""),
        "avg_rev": prof["avg_rev"],
        "accum_ratio": round(prof["accum_ratio"], 2),
        "contrib_share": round(prof["contrib_share"], 2),
        "prog_share": round(prof["prog_share"], 2),
        "zero_offcr_comp_pct": round(prof["zero_offcr_comp_pct"], 0),
        "zero_fundrsng_pct": round(prof["zero_fundrsng_pct"], 0),
        "n_filings": prof["n_filings"],
        "tier_reasons": reasons,
        "pitch_angles": pitch,
        "REVOKED": bmf_r.get("REVOKED", ""),
    })

# Sort: D first (priority outreach + AG-pipeline), then A (easy wins), B, C
tier_order = {"D": 0, "A": 1, "B": 2, "C": 3}
rows.sort(key=lambda r: (tier_order[r["lead_tier"]], -r["avg_rev"]))

cols = [
    "lead_tier", "EIN", "NAME", "STATE", "CITY", "NTEE_CD",
    "avg_rev", "accum_ratio", "contrib_share", "prog_share",
    "zero_offcr_comp_pct", "zero_fundrsng_pct", "n_filings",
    "tier_reasons", "pitch_angles", "REVOKED",
]
with OUT.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)

# Stats
from collections import Counter
tier_counts = Counter(r["lead_tier"] for r in rows)
print(f"Scored: {len(rows):,}")
print()
print("lead tier distribution:")
for t in ("D","A","B","C"):
    c = tier_counts.get(t, 0)
    pct = 100*c/len(rows) if rows else 0
    label = {
        "D": "opacity-pattern, AG-pipeline if remediation refused",
        "A": "Image-conscious — easy yes",
        "B": "Grant-dependent — formalize pitch",
        "C": "Mixed — soft outreach",
    }[t]
    print(f"  {t}: {c:>4} ({pct:.1f}%)  — {label}")

print(f"\nWrote {OUT}")

# Top 20 Tier-D (AG candidates if remediation refused)
print(f"\n=== Top 20 Tier-D (AG pipeline if remediation refused) ===")
tier_d = [r for r in rows if r["lead_tier"] == "D"][:20]
print(f"{'#':<3}{'State':<3}{'EIN':<11}{'Name':<40}{'AvgRev':>12}{'Accum':>7}{'ZeroComp%':>10}")
for i, r in enumerate(tier_d, 1):
    print(f"{i:<3}{r['STATE']:<3}  {r['EIN']}  {r['NAME'][:38]:<40}{r['avg_rev']:>12,}  {r['accum_ratio']:>5.2f}x  {int(r['zero_offcr_comp_pct']):>9}%")

# Top 20 Tier-A (easy yes outreach)
print(f"\n=== Top 20 Tier-A (easy remediation yes — professionalize pitch) ===")
tier_a = [r for r in rows if r["lead_tier"] == "A"][:20]
print(f"{'#':<3}{'State':<3}{'EIN':<11}{'Name':<40}{'AvgRev':>12}{'Accum':>7}")
for i, r in enumerate(tier_a, 1):
    print(f"{i:<3}{r['STATE']:<3}  {r['EIN']}  {r['NAME'][:38]:<40}{r['avg_rev']:>12,}  {r['accum_ratio']:>5.2f}x")
