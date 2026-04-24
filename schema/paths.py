"""Shared path configuration for propublica-grader.

All scripts locate data via REPO_ROOT (the repo directory) unless overridden
with the PPG_DATA_DIR and PPG_OUTPUT_DIR environment variables.

Layout:
    data/
      raw/
        bmf/                 IRS BMF regional CSVs + revocation
        propublica/          per-EIN ProPublica JSON
        usaspending/         per-(ALN,year) USASpending JSON
        guidestar/           GuideStar probe results
        990-xml/
          batches/           IRS e-file batch ZIPs
          extracted/         per-filing XML pulled from batches
      filtered/              NTEE-filtered org lists
    output/
      reports/               scored CSVs + analysis outputs
"""
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR   = Path(os.environ.get("PPG_DATA_DIR",   REPO_ROOT / "data"))
OUTPUT_DIR = Path(os.environ.get("PPG_OUTPUT_DIR", REPO_ROOT / "output"))

RAW_DIR        = DATA_DIR / "raw"
BMF_DIR        = RAW_DIR / "bmf"
PROPUBLICA_DIR = RAW_DIR / "propublica"
USASPENDING_DIR = RAW_DIR / "usaspending"
GUIDESTAR_DIR  = RAW_DIR / "guidestar"
XML_DIR        = RAW_DIR / "990-xml"
XML_BATCH_DIR  = XML_DIR / "batches"
XML_EXTRACT_DIR = XML_DIR / "extracted"

FILTERED_DIR   = DATA_DIR / "filtered"
REPORTS_DIR    = OUTPUT_DIR / "reports"

for d in (BMF_DIR, PROPUBLICA_DIR, USASPENDING_DIR, GUIDESTAR_DIR,
          XML_BATCH_DIR, XML_EXTRACT_DIR, FILTERED_DIR, REPORTS_DIR):
    d.mkdir(parents=True, exist_ok=True)
