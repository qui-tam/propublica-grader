#!/usr/bin/env python3
"""Bulk-fetch ProPublica Nonprofit Explorer JSON for every EIN in the DV dataset.

Resumable: skips EINs whose file already exists.
Rate-limited: 5 concurrent workers, each sleeping 1s between calls (~5 req/sec).
Error handling: 404s get logged to missing.txt (not in ProPublica), 429s exponential-backoff.
"""
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

import sys; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schema.paths import DATA_DIR, RAW_DIR, BMF_DIR, PROPUBLICA_DIR, USASPENDING_DIR, GUIDESTAR_DIR, XML_DIR, XML_BATCH_DIR, XML_EXTRACT_DIR, FILTERED_DIR, REPORTS_DIR
ROOT = DATA_DIR.parent  # repo-root compat for legacy refs below
OUT = PROPUBLICA_DIR
OUT.mkdir(parents=True, exist_ok=True)
MISSING_FILE = OUT / "_missing.txt"
ERROR_FILE = OUT / "_errors.txt"
PROGRESS_FILE = OUT / "_progress.log"

API = "https://projects.propublica.org/nonprofits/api/v2/organizations/{ein}.json"
WORKERS = 5
PER_WORKER_SLEEP = 1.0  # seconds between each worker's requests

# Load EINs
with (ROOT / "filtered/dv-foundations-all.csv").open() as f:
    eins = sorted({row["EIN"].zfill(9) for row in csv.DictReader(f) if row.get("EIN")})
print(f"Loaded {len(eins):,} unique EINs from filtered dataset")

# Resume: skip EINs already fetched or known-missing
done = {p.stem for p in OUT.glob("*.json")}
if MISSING_FILE.exists():
    done |= {ln.strip() for ln in MISSING_FILE.read_text().splitlines() if ln.strip()}
todo = [e for e in eins if e not in done]
print(f"Already done: {len(done):,}  ->  Todo: {len(todo):,}")

if not todo:
    print("Nothing to do. Exit.")
    sys.exit(0)

lock = Lock()
counters = {"ok": 0, "404": 0, "err": 0}
start = time.time()


def log_progress(force=False):
    total_done = counters["ok"] + counters["404"] + counters["err"]
    if total_done == 0:
        return
    if not force and total_done % 50 != 0:
        return
    elapsed = time.time() - start
    rate = total_done / elapsed if elapsed else 0
    remain = (len(todo) - total_done) / rate if rate else 0
    msg = (
        f"[{time.strftime('%H:%M:%S')}] done={total_done:,}/{len(todo):,} "
        f"ok={counters['ok']:,} 404={counters['404']:,} err={counters['err']:,} "
        f"rate={rate:.1f}/s eta={remain/60:.1f}min"
    )
    print(msg, flush=True)
    with PROGRESS_FILE.open("a") as fp:
        fp.write(msg + "\n")


def fetch(ein: str) -> tuple[str, str, str]:
    url = API.format(ein=ein)
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "osint-dv-research/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
                # Validate JSON before writing
                json.loads(data)
                (OUT / f"{ein}.json").write_bytes(data)
                time.sleep(PER_WORKER_SLEEP)
                return (ein, "ok", "")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                time.sleep(PER_WORKER_SLEEP)
                return (ein, "404", "not in ProPublica")
            if e.code == 429:
                backoff = 2 ** attempt * 5
                time.sleep(backoff)
                continue
            time.sleep(PER_WORKER_SLEEP)
            return (ein, "err", f"HTTP {e.code}")
        except Exception as e:
            if attempt < 4:
                time.sleep(2 ** attempt)
                continue
            return (ein, "err", repr(e))
    return (ein, "err", "max retries")


with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    futures = {ex.submit(fetch, ein): ein for ein in todo}
    for fut in as_completed(futures):
        ein, status, detail = fut.result()
        with lock:
            counters[status] += 1
            if status == "404":
                with MISSING_FILE.open("a") as fp:
                    fp.write(f"{ein}\n")
            elif status == "err":
                with ERROR_FILE.open("a") as fp:
                    fp.write(f"{ein}\t{detail}\n")
            log_progress()

log_progress(force=True)
print(f"\nDone. ok={counters['ok']:,} 404={counters['404']:,} err={counters['err']:,}")
print(f"  Time: {(time.time()-start)/60:.1f} min")
