#!/usr/bin/env bash
# End-to-end pipeline runner for propublica-grader.
#
# Runs every stage in order, using defaults from schema/paths.py.
# Override with PPG_DATA_DIR and PPG_OUTPUT_DIR env vars if needed.
#
# Expected wall time on a consumer laptop: ~25 min for the DV sector.

set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== Stage 1: Download IRS BMF + filter to NTEE I70-I74 + P43 ==="
python3 fetcher/filter_bmf.py

echo ""
echo "=== Stage 2: Bulk-fetch ProPublica JSON per EIN (~15 min) ==="
python3 fetcher/fetch_propublica.py

echo ""
echo "=== Stage 3: Fetch federal subaward history by ALN (~5 min) ==="
python3 fetcher/fetch_usaspending.py

echo ""
echo "=== Stage 4: Probe Candid/GuideStar profile existence (~4 hr) ==="
echo "    (commented out by default — uncomment to run)"
# python3 fetcher/fetch_guidestar.py

echo ""
echo "=== Stage 5: Score the sector (governance-opacity signature + weighted) ==="
python3 scorer/score_v2_weighted.py

echo ""
echo "=== Stage 6: Tier into remediation-outreach segments ==="
python3 scorer/tier_leads.py

echo ""
echo "=== Done ==="
echo "Outputs in: output/reports/"
ls -la output/reports/ 2>/dev/null | head
