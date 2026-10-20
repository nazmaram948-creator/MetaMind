"""Download O*NET 31.0 task statements, task ratings and occupation titles,
plus O*NET's official ESCO <-> O*NET-SOC crosswalk.

Source:  https://www.onetcenter.org/database.html   (CC BY 4.0, O*NET 31.0)
Saves to data/raw/onet/

Usage:  python data/scripts/download_onet.py [--force]
"""
from __future__ import annotations

import argparse

from _common import RAW, ManualDownloadNeeded, download, manual_notice

ONET_VERSION = "31_0"
BASE = f"https://www.onetcenter.org/dl_files/database/db_{ONET_VERSION}_csv"
SOURCE = "O*NET 31.0 Database (U.S. DOL/ETA, CC BY 4.0)"

FILES = {
    f"{BASE}/task_statements.csv": "task_statements.csv",
    f"{BASE}/task_ratings.csv": "task_ratings.csv",
    f"{BASE}/occupation_data.csv": "occupation_data.csv",
    "https://www.onetcenter.org/crosswalks/esco/ESCO_to_ONET-SOC.xlsx": "ESCO_to_ONET-SOC.xlsx",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    print(f"O*NET {ONET_VERSION}: {len(FILES)} files -> data/raw/onet/")
    for url, name in FILES.items():
        dest = RAW / "onet" / name
        try:
            download(url, dest, source=SOURCE, force=args.force)
        except ManualDownloadNeeded:
            manual_notice(url, dest)


if __name__ == "__main__":
    main()
