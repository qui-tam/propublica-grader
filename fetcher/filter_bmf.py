#!/usr/bin/env python3
"""Filter IRS BMF to DV-adjacent NTEE codes, flag auto-revoked EINs, surface zombie shells."""
import csv
from pathlib import Path

RAW = Path.home() / "OSINT-Network/DV-Foundations/raw"
OUT = Path.home() / "OSINT-Network/DV-Foundations/filtered"
OUT.mkdir(exist_ok=True)

# NTEE I70 = Protection Against Abuse (general) — Crime/Legal tree, parent category
# NTEE I71 = Spouse Abuse, Prevention of — Crime/Legal tree
# NTEE I72 = Child Abuse, Prevention of — Crime/Legal tree
#            (DV sector treats child maltreatment in DV households as part of the continuum;
#             same governance red flags apply regardless of stated beneficiary)
# NTEE I73 = Sexual Abuse, Prevention of — Crime/Legal tree
# NTEE P43 = Family Violence Shelters and Services — Human Services tree, shelter framing
#           
NTEE_PREFIXES = ("I70", "I71", "I72", "I73", "P43")

# Manually-included EINs — orgs whose NTEE field is malformed but which belong in scope.
# Format: EIN (zero-padded 9-digit) -> reason string (written to MANUAL_INCLUDE column).
MANUAL_INCLUDES = {
    "464766274": "NTEE truncated to 'I7' in BMF; name 'She's Somebody's Daughter' indicates DV/trafficking advocacy",
    "943109034": "NTEE 'I7O' in BMF is data-entry error for I70 (zero→O); Soroptimist local chapter, women's advocacy network",
}

# Zombie-shell detection: active 501(c)(3) with zero activity over a full filing window.
# Criteria:
#   - STATUS == "01" (active unconditional exemption)
#   - ASSET_AMT == INCOME_AMT == REVENUE_AMT == 0
#   - RULING date >= 3 years old (enough time to have filed at least one 990/990-N)
ZOMBIE_RULING_CUTOFF = "202304"  # 3 years before 2026-04

# BMF STATUS codes (from IRS EO BMF documentation)
STATUS_LABELS = {
    "01": "Unconditional exemption",
    "02": "Conditional exemption",
    "12": "Trust 4947(a)(2)",
    "25": "Terminated PF status",
    "36": "501(c)(3) gross receipts < $5000",
    "40": "Status change — no longer tax-exempt",
    "71": "Church — no ruling letter",
    "72": "No ruling letter",
}

INCOME_BRACKETS = {
    "0": "$0",
    "1": "$1 - $9,999",
    "2": "$10,000 - $24,999",
    "3": "$25,000 - $99,999",
    "4": "$100,000 - $499,999",
    "5": "$500,000 - $999,999",
    "6": "$1M - $4.99M",
    "7": "$5M - $9.99M",
    "8": "$10M - $49.99M",
    "9": "$50M+",
}

# Step 1: Build revoked EIN set from data-download-revocation.txt
revoked = {}
rev_file = RAW / "revocation" / "data-download-revocation.txt"
with rev_file.open(encoding="latin-1") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        parts = line.split("|")
        if len(parts) < 11:
            continue
        ein = parts[0].strip().zfill(9)
        rev_date = parts[9].strip() if len(parts) > 9 else ""
        pub_date = parts[10].strip() if len(parts) > 10 else ""
        reinstate = parts[11].strip() if len(parts) > 11 else ""
        revoked[ein] = {
            "rev_date": rev_date,
            "pub_date": pub_date,
            "reinstate_date": reinstate,
        }

print(f"Loaded {len(revoked):,} auto-revoked EINs")

# Step 2: Filter all 4 BMF regions (NTEE prefix match OR manual-include EIN match)
rows = []
manual_seen = set()
for region in ("eo1.csv", "eo2.csv", "eo3.csv", "eo4.csv"):
    path = BMF_DIR / region
    with path.open(encoding="latin-1") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ntee = (row.get("NTEE_CD") or "").strip().upper()
            ein = row.get("EIN", "").strip().zfill(9)
            if ntee.startswith(NTEE_PREFIXES):
                row["_region"] = region
                row["MANUAL_INCLUDE"] = ""
                rows.append(row)
            elif ein in MANUAL_INCLUDES:
                row["_region"] = region
                row["MANUAL_INCLUDE"] = MANUAL_INCLUDES[ein]
                rows.append(row)
                manual_seen.add(ein)
    print(f"{region}: running total {len(rows):,} DV-adjacent orgs")

missing_manual = set(MANUAL_INCLUDES) - manual_seen
if missing_manual:
    print(f"WARNING: manual includes not found in BMF: {missing_manual}")

# Step 3: Annotate with revocation status and readable bracket labels
for row in rows:
    ein = row.get("EIN", "").strip().zfill(9)
    rev = revoked.get(ein)
    row["REVOKED"] = "Y" if rev else ""
    row["REV_DATE"] = rev["rev_date"] if rev else ""
    row["REV_PUB_DATE"] = rev["pub_date"] if rev else ""
    row["REINSTATE_DATE"] = rev["reinstate_date"] if rev else ""
    row["STATUS_LABEL"] = STATUS_LABELS.get(row.get("STATUS", "").strip(), "")
    row["INCOME_LABEL"] = INCOME_BRACKETS.get(row.get("INCOME_CD", "").strip(), "")

# Step 4: Write master filtered CSV
out_cols = [
    "EIN", "NAME", "CITY", "STATE", "ZIP", "NTEE_CD",
    "STATUS", "STATUS_LABEL", "REVOKED", "REV_DATE", "REV_PUB_DATE", "REINSTATE_DATE",
    "MANUAL_INCLUDE",
    "SUBSECTION", "CLASSIFICATION", "DEDUCTIBILITY", "FOUNDATION",
    "RULING", "TAX_PERIOD", "FILING_REQ_CD",
    "ASSET_AMT", "INCOME_AMT", "REVENUE_AMT", "INCOME_CD", "INCOME_LABEL",
    "ICO", "STREET", "_region",
]
out_path = OUT / "dv-foundations-all.csv"
with out_path.open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=out_cols, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
print(f"\nWrote {out_path} with {len(rows):,} rows")

# Step 5: Split by NTEE bucket for easier triage
for prefix in NTEE_PREFIXES:
    subset = [r for r in rows if r["NTEE_CD"].strip().upper().startswith(prefix)]
    sub_path = OUT / f"dv-foundations-{prefix}.csv"
    with sub_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=out_cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(subset)
    print(f"  {prefix}: {len(subset):,} orgs -> {sub_path.name}")

# Step 6: Summary stats
from collections import Counter
print("\n=== NTEE distribution ===")
for ntee, ct in Counter(r["NTEE_CD"].strip() for r in rows).most_common():
    print(f"  {ntee}: {ct}")

print("\n=== STATUS distribution ===")
for st, ct in Counter(r["STATUS"].strip() for r in rows).most_common():
    label = STATUS_LABELS.get(st, "?")
    print(f"  {st} ({label}): {ct}")

print("\n=== STATE (top 15) ===")
for state, ct in Counter(r["STATE"].strip() for r in rows).most_common(15):
    print(f"  {state}: {ct}")

print(f"\n=== Revoked in filtered set: {sum(1 for r in rows if r['REVOKED']):,} ===")

# Step 7: Zombie-shell detection within the DV subset.
# IMPORTANT: BMF only populates ASSET_AMT/INCOME_AMT/REVENUE_AMT reliably for FILING_REQ_CD=01
# (full 990 required). Empirically, 91% of FILING_REQ_CD=02 (990-EZ) filers show zero financials
# regardless of actual activity — measurement artifact, not dormancy. Only code-01 zeros are signal.
def is_zero(val):
    return (val or "").strip() in ("", "0")

zombies = []
unclassified_zeros = []  # FILING_REQ_CD=00 — edge case, log separately
for row in rows:
    if row.get("STATUS", "").strip() != "01":
        continue
    if row.get("REVOKED") == "Y":
        continue
    if not (is_zero(row.get("ASSET_AMT")) and is_zero(row.get("INCOME_AMT")) and is_zero(row.get("REVENUE_AMT"))):
        continue
    ruling = (row.get("RULING") or "").strip()
    if not ruling or ruling > ZOMBIE_RULING_CUTOFF:
        continue  # too new to be a zombie (may not have filed yet)
    filing = row.get("FILING_REQ_CD", "").strip()
    if filing == "01":
        zombies.append(row)
    elif filing == "00":
        unclassified_zeros.append(row)
    # skip 02/03/06/13/14 — BMF can't reliably tell us activity for those

zombie_path = OUT / "zombies.csv"
with zombie_path.open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=out_cols, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(zombies)
print(f"\n=== HIGH-SUSPICION zombies (990-required, all-zero financials, ruling ≤ {ZOMBIE_RULING_CUTOFF}): {len(zombies):,} ===")
print(f"    Wrote {zombie_path}")
for z in sorted(zombies, key=lambda r: r.get("RULING", "")):
    print(f"      ruling={z['RULING']}  {z['EIN']}  {z['NAME'][:50]:<50}  {z['CITY']}, {z['STATE']}  [{z['NTEE_CD']}]")

unclass_path = OUT / "zombies-unclassified.csv"
with unclass_path.open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=out_cols, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(unclassified_zeros)
print(f"\n=== UNCLASSIFIED-filing zeros (FILING_REQ_CD=00, ruling ≤ {ZOMBIE_RULING_CUTOFF}): {len(unclassified_zeros):,} ===")
print(f"    Wrote {unclass_path} — needs manual triage, BMF cannot classify filing obligation")
