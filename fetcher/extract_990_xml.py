#!/usr/bin/env python3
"""Extract 990 XMLs for top-20 suspicion orgs from downloaded IRS batches,
then compare Schedule O language across orgs to detect boilerplate reuse.
"""
import csv
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import sys; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schema.paths import DATA_DIR, RAW_DIR, BMF_DIR, PROPUBLICA_DIR, USASPENDING_DIR, GUIDESTAR_DIR, XML_DIR, XML_BATCH_DIR, XML_EXTRACT_DIR, FILTERED_DIR, REPORTS_DIR
ROOT = DATA_DIR.parent  # repo-root compat for legacy refs below
BATCHES_DIR = XML_BATCH_DIR
MAIN_ZIP = ROOT / "raw/990-pdfs/batch_2024_TEOS_XML_11A.zip"
EXTRACT_DIR = XML_EXTRACT_DIR
EXTRACT_DIR.mkdir(exist_ok=True)
NS = {"": "http://www.irs.gov/efile"}

# Build top-20 EIN → (OBJECT_ID, XML_BATCH_ID)
with (ROOT / "reports/suspicion-ranked-v2.csv").open() as f:
    top20 = list(csv.DictReader(f))[:20]

idx = {}
with (ROOT / "raw/990-pdfs/index_2024.csv").open() as f:
    for row in csv.DictReader(f):
        ein = row["EIN"].zfill(9)
        tp = row["TAX_PERIOD"]
        if ein not in idx or tp > idx[ein]["TAX_PERIOD"]:
            idx[ein] = row

targets = []
for i, r in enumerate(top20, 1):
    ein = r["EIN"]
    match = idx.get(ein)
    if match:
        obj_id = match["OBJECT_ID"]
        # Normalize batch id — use UPPERCASE final letter since that's the real filename
        batch_id = match["XML_BATCH_ID"]
        batch_id_upper = batch_id[:-1] + batch_id[-1].upper()
        targets.append({
            "rank": i,
            "score": r["composite"],
            "ein": ein,
            "name": r["NAME"],
            "state": r["STATE"],
            "obj_id": obj_id,
            "batch_id_idx": batch_id,
            "batch_id_fs": batch_id_upper,
        })

print(f"Targets to extract: {len(targets)}\n")

# Extract from each batch
def extract_xml(obj_id, batch_id):
    """Extract single XML from a batch zip."""
    # Try main zip first (11A was downloaded separately)
    if batch_id == "2024_TEOS_XML_11A" and MAIN_ZIP.exists():
        zip_path = MAIN_ZIP
    else:
        zip_path = BATCHES_DIR / f"{batch_id}.zip"
    if not zip_path.exists():
        return None, f"batch not found: {zip_path.name}"
    out_path = EXTRACT_DIR / f"{obj_id}_public.xml"
    if out_path.exists():
        return out_path, "cached"
    try:
        with zipfile.ZipFile(zip_path) as zf:
            # The internal path is e.g. "2024_TEOS_XML_11A/202443179349302964_public.xml"
            # Or potentially with lowercase trailing letter like "2024_TEOS_XML_05a/..."
            for name in zf.namelist():
                if obj_id in name and name.endswith("_public.xml"):
                    out_path.write_bytes(zf.read(name))
                    return out_path, "extracted"
            return None, "obj_id not in batch"
    except zipfile.BadZipFile as e:
        return None, f"bad zip: {e}"

for t in targets:
    path, status = extract_xml(t["obj_id"], t["batch_id_fs"])
    t["xml_path"] = str(path) if path else None
    t["status"] = status
    print(f"#{t['rank']:<3}{t['ein']:<11}{t['name'][:40]:<40}  {status}")

print()

# Parse each extracted XML for Schedule O narrative + key facts
def parse_so(xml_path):
    if not xml_path:
        return None
    try:
        tree = ET.parse(xml_path)
    except Exception as e:
        return {"err": str(e)}
    root = tree.getroot()
    hdr = root.find("ReturnHeader", NS)
    rdata = root.find("ReturnData", NS)
    f990 = rdata.find("IRS990", NS) if rdata is not None else None

    out = {"schedule_o_items": []}
    so = rdata.find("IRS990ScheduleO", NS) if rdata is not None else None
    if so is not None:
        for item in so.iter():
            tag = item.tag.split("}")[-1]
            if tag == "ExplanationTxt":
                # find the prior sibling's FormAndLineReferenceDesc (in same group)
                parent = item.find("..", NS)
                # safer: walk upward — just record the explanation text
                t = (item.text or "").strip()
                if t:
                    out["schedule_o_items"].append(t)

    # Preparer
    if hdr is not None:
        pfirm = hdr.find("PreparerFirmGrp", NS)
        pperson = hdr.find("PreparerPersonGrp", NS)
        if pfirm is not None:
            n = pfirm.find("PreparerFirmName/BusinessNameLine1Txt", NS)
            e = pfirm.find("PreparerFirmEIN", NS)
            out["preparer_firm"] = (n.text.strip() if n is not None and n.text else "")
            out["preparer_firm_ein"] = (e.text.strip() if e is not None and e.text else "")
        if pperson is not None:
            pn = pperson.find("PreparerPersonNm", NS)
            pt = pperson.find("PTIN", NS)
            out["preparer_person"] = (pn.text.strip() if pn is not None and pn.text else "")
            out["preparer_ptin"] = (pt.text.strip() if pt is not None and pt.text else "")

    # Governance answers
    if f990 is not None:
        for q, tag in [
            ("form990_to_gov_body", "Form990ProvidedToGvrnBodyInd"),
            ("whistleblower", "WhistleblowerPolicyInd"),
            ("doc_retention", "DocumentRetentionPolicyInd"),
            ("comp_process_ceo", "CompensationProcessCEOInd"),
            ("coi_monitoring", "RegularMonitoringEnfrcInd"),
        ]:
            el = f990.find(tag, NS)
            out[q] = (el.text.strip() if el is not None and el.text else "")
    return out


print(f"\n{'='*70}")
print("PARSING + COMPARING SCHEDULE O LANGUAGE")
print(f"{'='*70}\n")

BOILERPLATE_PHRASE1 = "NO REVIEW WAS OR WILL BE CONDUCTED"
BOILERPLATE_PHRASE2_RE = re.compile(r"NO DOCUMENTS? AVAILABLE TO THE PUBLIC", re.I)

for t in targets:
    parsed = parse_so(t["xml_path"])
    if parsed is None:
        continue
    if "err" in parsed:
        print(f"#{t['rank']} ERROR: {parsed['err']}")
        continue
    t["parsed"] = parsed
    so_items = parsed.get("schedule_o_items", [])
    has_p1 = any(BOILERPLATE_PHRASE1 in (it or "").upper() for it in so_items)
    has_p2 = any(BOILERPLATE_PHRASE2_RE.search(it or "") for it in so_items)
    t["boilerplate_p1"] = has_p1
    t["boilerplate_p2"] = has_p2

# Summary table
print(f"{'#':<3}{'Score':>6}  {'EIN':<11}{'State':<3}  {'Name':<38}  {'NoReview':<9}{'NoDocs':<8}{'Preparer':<40}")
print("-" * 130)
for t in targets:
    if t.get("status") not in ("extracted", "cached"):
        print(f"#{t['rank']:<3}{t['score']:>6}  {t['ein']}  {t['state']:<3}  {t['name'][:36]:<38}  --[{t['status']}]")
        continue
    p = t.get("parsed", {})
    p1 = "YES" if t.get("boilerplate_p1") else ""
    p2 = "YES" if t.get("boilerplate_p2") else ""
    prep = p.get("preparer_firm", "")[:38]
    print(f"#{t['rank']:<3}{t['score']:>6}  {t['ein']}  {t['state']:<3}  {t['name'][:36]:<38}  {p1:<9}{p2:<8}{prep:<40}")

# Boilerplate stats
bp1_count = sum(1 for t in targets if t.get("boilerplate_p1"))
bp2_count = sum(1 for t in targets if t.get("boilerplate_p2"))
print(f"\n'NO REVIEW WAS OR WILL BE CONDUCTED': {bp1_count}/{len(targets)} orgs")
print(f"'NO DOCUMENTS AVAILABLE TO THE PUBLIC': {bp2_count}/{len(targets)} orgs")

# Preparer concentration
from collections import Counter
prep_counts = Counter(t.get("parsed", {}).get("preparer_firm", "(unknown)") for t in targets if t.get("parsed"))
print(f"\nPreparer firm concentration (top 10):")
for firm, ct in prep_counts.most_common(10):
    print(f"  {ct:>3}  {firm}")
