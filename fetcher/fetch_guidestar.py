#!/usr/bin/env python3
"""Bulk-probe GuideStar/Candid profiles for every EIN in DV dataset.

For each EIN:
  - GET https://www.guidestar.org/profile/{EIN-dashed}
  - Record HTTP status, title, meta description, and any seal-of-transparency signal

Resumable, rate-limited (1 worker, 2s/req = ~0.5 req/sec; 3,969 orgs = ~2.2 hrs).
Writes raw/guidestar/results.csv (append-only) + _errors.txt for retries.
"""
import csv
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

import sys; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schema.paths import DATA_DIR, RAW_DIR, BMF_DIR, PROPUBLICA_DIR, USASPENDING_DIR, GUIDESTAR_DIR, XML_DIR, XML_BATCH_DIR, XML_EXTRACT_DIR, FILTERED_DIR, REPORTS_DIR
ROOT = DATA_DIR.parent  # repo-root compat for legacy refs below
OUT = GUIDESTAR_DIR
OUT.mkdir(parents=True, exist_ok=True)
RESULTS = OUT / "results.csv"
ERRORS = OUT / "_errors.txt"
LOG = OUT / "_progress.log"

URL = "https://www.guidestar.org/profile/{ein}"
UA = "Mozilla/5.0 (compatible; osint-dv-research/1.0)"
SLEEP = 4.0                     # 0.25 req/sec — conservative, 4.4hr for 3,969
CONSECUTIVE_ERROR_PAUSE = 5     # trigger long pause after N errors in a row
LONG_PAUSE_SEC = 300            # 5 min cool-down if pattern breaks
ABORT_AFTER_CONSECUTIVE = 15    # stop entirely if this many errors stack up

TITLE_RE = re.compile(r"<title>([^<]{1,400})</title>", re.I)
DESC_RE = re.compile(r'<meta\s+name="description"\s+content="([^"]{0,400})"', re.I)
SEAL_RE = re.compile(r"(Platinum|Gold|Silver|Bronze)\s+Transparency\s+(\d{4})", re.I)
CLAIMED_RE = re.compile(r"(claim(ed)? (this|your) (non)?profile|manage (this|your) profile)", re.I)


def format_ein(ein: str) -> str:
    e = str(ein).zfill(9)
    return f"{e[:2]}-{e[2:]}"


def probe(ein: str):
    url = URL.format(ein=format_ein(ein))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            status = r.status
            body = r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return {
            "ein": ein,
            "http_status": e.code,
            "title": "",
            "description": "",
            "seal_level": "",
            "seal_year": "",
            "claim_indicator": "",
        }

    title = (TITLE_RE.search(body).group(1).strip() if TITLE_RE.search(body) else "").replace("\n", " ")
    desc = (DESC_RE.search(body).group(1).strip() if DESC_RE.search(body) else "").replace("\n", " ")
    seal_m = SEAL_RE.search(body)
    claim_m = CLAIMED_RE.search(body)

    return {
        "ein": ein,
        "http_status": status,
        "title": title[:300],
        "description": desc[:300],
        "seal_level": seal_m.group(1) if seal_m else "",
        "seal_year": seal_m.group(2) if seal_m else "",
        "claim_indicator": "present" if claim_m else "",
    }


def main():
    orgs = []
    with (ROOT / "filtered/dv-foundations-all.csv").open() as f:
        for r in csv.DictReader(f):
            orgs.append(r["EIN"].zfill(9))
    print(f"Loaded {len(orgs):,} EINs")

    done = set()
    if RESULTS.exists():
        with RESULTS.open() as f:
            r = csv.DictReader(f)
            for row in r:
                done.add(row["ein"].zfill(9))
    todo = [e for e in orgs if e not in done]
    print(f"Already done: {len(done):,}   Todo: {len(todo):,}")
    if not todo:
        return

    cols = ["ein", "http_status", "title", "description", "seal_level", "seal_year", "claim_indicator"]
    file_is_new = not RESULTS.exists()
    with RESULTS.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        if file_is_new:
            w.writeheader()
        counters = {"ok": 0, "404": 0, "err": 0}
        consec_err = 0
        start = time.time()
        for i, ein in enumerate(todo, 1):
            for attempt in range(3):
                try:
                    row = probe(ein)
                    break
                except Exception as e:
                    if attempt < 2:
                        time.sleep(10 * (attempt + 1))  # 10s, 20s
                        continue
                    row = {
                        "ein": ein, "http_status": "err",
                        "title": "", "description": "",
                        "seal_level": "", "seal_year": "", "claim_indicator": "",
                    }
                    with ERRORS.open("a") as fp:
                        fp.write(f"{ein}\t{repr(e)}\n")
                    counters["err"] += 1
                    break

            if row["http_status"] == 200:
                counters["ok"] += 1
                consec_err = 0
            elif row["http_status"] == 404:
                counters["404"] += 1
                consec_err = 0
            else:
                consec_err += 1

            w.writerow(row)
            f.flush()

            # Rate-limit defense
            if consec_err >= ABORT_AFTER_CONSECUTIVE:
                msg = f"[{time.strftime('%H:%M:%S')}] ABORT: {consec_err} consecutive errors. Quitting to avoid further damage."
                print(msg, flush=True)
                with LOG.open("a") as fp:
                    fp.write(msg + "\n")
                return
            if consec_err >= CONSECUTIVE_ERROR_PAUSE:
                msg = f"[{time.strftime('%H:%M:%S')}] Pausing {LONG_PAUSE_SEC}s after {consec_err} consecutive errors"
                print(msg, flush=True)
                with LOG.open("a") as fp:
                    fp.write(msg + "\n")
                time.sleep(LONG_PAUSE_SEC)
            else:
                time.sleep(SLEEP)

            if i % 50 == 0:
                elapsed = time.time() - start
                rate = i / elapsed
                eta = (len(todo) - i) / rate
                msg = (
                    f"[{time.strftime('%H:%M:%S')}] {i:,}/{len(todo):,}  "
                    f"ok={counters['ok']:,} 404={counters['404']:,} err={counters['err']:,}  "
                    f"rate={rate:.2f}/s eta={eta/60:.1f}min"
                )
                print(msg, flush=True)
                with LOG.open("a") as fp:
                    fp.write(msg + "\n")


if __name__ == "__main__":
    main()
