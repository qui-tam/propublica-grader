#!/usr/bin/env python3
"""Pull all USASpending subawards under DV-sector Assistance Listing Numbers (ALN/CFDA).

Much more efficient than per-org name queries: 6 ALN codes × years × pages ≈ a few
hundred requests instead of 3,969. Writes one JSON file per (ALN, year).

Resumable; respects rate limits (2s/req, 1 worker).
"""
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import sys; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schema.paths import DATA_DIR, RAW_DIR, BMF_DIR, PROPUBLICA_DIR, USASPENDING_DIR, GUIDESTAR_DIR, XML_DIR, XML_BATCH_DIR, XML_EXTRACT_DIR, FILTERED_DIR, REPORTS_DIR
ROOT = DATA_DIR.parent  # repo-root compat for legacy refs below
OUT = USASPENDING_DIR
OUT.mkdir(parents=True, exist_ok=True)
LOG = OUT / "_progress.log"

URL = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
UA = "osint-dv-research/1.0"
SLEEP = 2.0

# DV-sector Assistance Listing Numbers
ALN_CODES = {
    "16.575": "Crime Victim Assistance (VOCA)",
    "16.588": "Violence Against Women Formula Grants",
    "16.589": "Rural Domestic Violence, Dating Violence, Sexual Assault, and Stalking Assistance",
    "16.590": "Grants to Encourage Arrest Policies and Enforcement of Protection Orders",
    "16.524": "Legal Assistance for Victims",
    "93.671": "Family Violence Prevention and Services / Domestic Violence Shelter & Supportive Services",
}

# Time window: USASpending search API requires start >= 2007-10-01
YEARS = list(range(2008, 2027))  # full years only; pull per-FY


def http_post(payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(URL, data=data, headers={
        "Content-Type": "application/json", "User-Agent": UA,
    })
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def pull(aln, year, subawards=True):
    out_path = OUT / f"{aln}_{year}_{'sub' if subawards else 'prime'}.json"
    if out_path.exists():
        return ("cached", out_path)

    fields_sub = [
        "Sub-Award ID", "Sub-Awardee Name", "Sub-Award Amount",
        "Prime Award ID", "Prime Recipient Name", "Awarding Agency",
        "Action Date",
    ]
    fields_prime = [
        "Award ID", "Recipient Name", "Award Amount",
        "Awarding Agency", "Awarding Sub Agency", "Start Date", "End Date",
        "Award Type", "recipient_id",
    ]
    fields = fields_sub if subawards else fields_prime

    all_results = []
    page = 1
    while True:
        payload = {
            "filters": {
                "program_numbers": [aln],
                "award_type_codes": ["02", "03", "04", "05"],
                "time_period": [{"start_date": f"{year}-01-01", "end_date": f"{year}-12-31"}],
            },
            "fields": fields,
            "limit": 100,
            "page": page,
            "subawards": subawards,
        }
        for attempt in range(4):
            try:
                resp = http_post(payload)
                break
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")[:200]
                if e.code in (429, 502, 503, 504) and attempt < 3:
                    time.sleep(15 * (attempt + 1))
                    continue
                raise RuntimeError(f"HTTP {e.code}: {body}")
            except Exception as e:
                if attempt < 3:
                    time.sleep(10)
                    continue
                raise
        else:
            raise RuntimeError("retries exhausted")

        hits = resp.get("results", [])
        if not hits:
            break
        all_results.extend(hits)
        has_next = resp.get("page_metadata", {}).get("hasNext", False)
        if not has_next:
            break
        page += 1
        time.sleep(SLEEP)
        if page > 100:
            break  # safety

    out_path.write_text(json.dumps({
        "aln": aln, "year": year, "subawards": subawards,
        "count": len(all_results), "results": all_results,
    }))
    return (f"{len(all_results)} rows", out_path)


def main():
    start = time.time()
    total = 0
    for aln, name in ALN_CODES.items():
        print(f"\n=== {aln} — {name} ===")
        for year in YEARS:
            for kind in ("sub", "prime"):
                is_sub = kind == "sub"
                try:
                    status, path = pull(aln, year, is_sub)
                except Exception as e:
                    msg = f"  {aln} {year} {kind}: ERROR {e}"
                    print(msg, flush=True)
                    with LOG.open("a") as fp:
                        fp.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
                    time.sleep(30)
                    continue
                if "rows" in status:
                    cnt = int(status.split()[0])
                    total += cnt
                    msg = f"  {aln} {year} {kind}: {status}  total={total:,}"
                    print(msg, flush=True)
                    with LOG.open("a") as fp:
                        fp.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
                    time.sleep(SLEEP)
                else:
                    print(f"  {aln} {year} {kind}: cached")
    print(f"\nDone. total awards pulled: {total:,}   time: {(time.time()-start)/60:.1f} min")


if __name__ == "__main__":
    main()
