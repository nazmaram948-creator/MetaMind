# data/raw

Downloads land here and are **not committed** (large, re-fetchable). Only
`MANIFEST.json` (url, size, sha256, fetch time per file) and this note are tracked.

Fetch everything:

```bash
python data/scripts/download_aei.py
python data/scripts/download_onet.py
python data/scripts/download_esco.py
python data/scripts/download_crosswalk.py
python data/scripts/inspect_schemas.py   # regenerates docs/data_schemas.md
```

Two sources cannot be scripted. Fetch them in a browser:

| File | Where to get it | Save as |
|---|---|---|
| ESCO v1.2.0 CSV bundle | https://esco.ec.europa.eu/en/use-esco/download → Version v1.2.0, Content classification, Language en, File type csv | `data/raw/esco/<any name>.zip` |
| BLS SOC↔ISCO-08 crosswalk | https://www.bls.gov/soc/ISCO_SOC_Crosswalk.xls | `data/raw/crosswalk/ISCO_SOC_Crosswalk.xls` |

Without them the pipeline still runs. ESCO comes from the ESCO Web Service API (same
v1.2.0 data, limited to our target occupations), and O*NET↔ESCO links come from
O*NET's official `ESCO_to_ONET-SOC.xlsx`.
