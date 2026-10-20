"""Download the BLS SOC 2010 <-> ISCO-08 crosswalk (links O*NET -> ISCO -> ESCO/MASCO).

Source:  https://www.bls.gov/soc/soccrosswalks.htm  (U.S. public domain)
Saves to data/raw/crosswalk/ISCO_SOC_Crosswalk.xls

bls.gov answers scripted clients with HTTP 403, so this usually ends with a
manual-download notice. Until the file is there, the normaliser links O*NET to
ESCO with O*NET's own ESCO_to_ONET-SOC.xlsx (fetched by download_onet.py) and
takes ISCO codes from ESCO; the BLS file is then only used as a cross-check.

Usage:  python data/scripts/download_crosswalk.py [--force]
"""
from __future__ import annotations

import argparse

from _common import RAW, ManualDownloadNeeded, download, manual_notice

URL = "https://www.bls.gov/soc/ISCO_SOC_Crosswalk.xls"
SOURCE = "BLS SOC 2010 to ISCO-08 crosswalk"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    dest = RAW / "crosswalk" / "ISCO_SOC_Crosswalk.xls"
    print("BLS SOC<->ISCO crosswalk:")
    try:
        download(URL, dest, source=SOURCE, force=args.force)
    except ManualDownloadNeeded as e:
        print(f"  blocked: {e}")
        manual_notice(URL, dest, "open in a normal browser and save the .xls unchanged "
                                 "(linked from https://www.bls.gov/soc/soccrosswalks.htm)")


if __name__ == "__main__":
    main()
