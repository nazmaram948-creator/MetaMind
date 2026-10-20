"""Download Anthropic Economic Index (AEI) files from Hugging Face.

Source:  https://huggingface.co/datasets/Anthropic/EconomicIndex  (data: CC-BY)
Saves to data/raw/aei/<release>/...

Default set = the files needed for our snapshots:
  * release_2025_03_27   per-task usage share + collaboration pattern split (small CSVs)
  * release_2026_01_15   long-format "raw" file, Claude.ai, 2025-11-13..2025-11-20
  * release_2026_06_26   long-format file with O*NET task IDs, Claude.ai, Apr-May 2026
  * labor_market_impacts observed exposure per SOC / task penetration (cross-check)
--all also fetches release_2026_03_24 and the 1P API files (large).

Usage:  python data/scripts/download_aei.py [--all] [--force]
"""
from __future__ import annotations

import argparse

from _common import RAW, download

HF = "https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main"
SOURCE = "Anthropic Economic Index (Hugging Face: Anthropic/EconomicIndex)"

CORE = [
    "README.md",
    "release_2025_03_27/README.md",
    "release_2025_03_27/task_pct_v1.csv",
    "release_2025_03_27/task_pct_v2.csv",
    "release_2025_03_27/automation_vs_augmentation_by_task.csv",
    "release_2025_03_27/automation_vs_augmentation_v2.csv",
    "release_2025_03_27/onet_task_statements.csv",
    "release_2026_01_15/data_documentation.md",
    "release_2026_01_15/data/intermediate/aei_raw_claude_ai_2025-11-13_to_2025-11-20.csv",
    "release_2026_06_26/data_documentation.md",
    "release_2026_06_26/data/aei_claude_ai_2026-06-26.csv",
    "labor_market_impacts/job_exposure.csv",
    "labor_market_impacts/task_penetration.csv",
]

EXTRA = [
    "release_2026_03_24/data_documentation.md",
    "release_2026_03_24/data/aei_raw_claude_ai_2026-02-05_to_2026-02-12.csv",
    "release_2026_01_15/data/intermediate/aei_raw_1p_api_2025-11-13_to_2025-11-20.csv",
    "release_2026_06_26/data/aei_1p_api_2026-06-26.csv",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="also fetch large optional files")
    ap.add_argument("--force", action="store_true", help="re-download even if present")
    args = ap.parse_args()

    files = CORE + (EXTRA if args.all else [])
    print(f"AEI: {len(files)} files -> data/raw/aei/")
    for f in files:
        download(f"{HF}/{f}", RAW / "aei" / f, source=SOURCE, force=args.force)


if __name__ == "__main__":
    main()
