"""Get ESCO v1.2 data for the occupations in data/curated/target_occupations.csv.

Two routes, same output tables after normalising:

A) Official CSV bundle (preferred, complete). The ESCO portal only hands it out
   through a form, so it cannot be scripted. Fetch it by hand:
     https://esco.ec.europa.eu/en/use-esco/download
     Version: v1.2.0 | Content: classification | Language: en | File type: csv
   and save the zip anywhere under data/raw/esco/. This script then extracts the
   files we use into data/raw/esco/csv/.

B) ESCO Web Service API (automatic fallback, real v1.2 data, subset only):
     https://ec.europa.eu/esco/api  (selectedVersion=v1.2.0)
   Crawls the target occupations, all their essential/optional skills, and the
   skills' broader concepts up to the top of the skills pillar. Writes
   data/raw/esco_api/{occupations,skills}.jsonl (English labels only).

Licence: ESCO is published by the European Commission under the Commission's
reuse policy (Decision 2011/833/EU, attribution required).

Usage:  python data/scripts/download_esco.py [--force-api]
"""
from __future__ import annotations

import argparse
import json
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests

from _common import CURATED, RAW, ROOT, load_manifest, manual_notice, now_iso, save_manifest

API = "https://ec.europa.eu/esco/api"
VERSION = "v1.2.0"
SOURCE = f"ESCO {VERSION} (European Commission)"
CSV_DIR = RAW / "esco" / "csv"
API_DIR = RAW / "esco_api"
WANTED_CSV = [
    "occupations_en.csv", "skills_en.csv", "occupationSkillRelations_en.csv",
    "broaderRelationsSkillPillar_en.csv", "skillsHierarchy_en.csv", "ISCOGroups_en.csv",
    "greenSkillsCollection_en.csv", "digitalSkillsCollection_en.csv",
    "transversalSkillsCollection_en.csv",
]
BATCH = 20


# ---------- route A: official zip ----------
def try_zip() -> bool:
    zips = sorted((RAW / "esco").glob("*.zip")) if (RAW / "esco").exists() else []
    if not zips:
        return False
    z = zips[-1]
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(z) as zf:
        names = {Path(n).name: n for n in zf.namelist()}
        missing = [w for w in WANTED_CSV if w not in names]
        for w in WANTED_CSV:
            if w in names:
                (CSV_DIR / w).write_bytes(zf.read(names[w]))
    print(f"ESCO: extracted {len(WANTED_CSV) - len(missing)} CSVs from {z.name}")
    if missing:
        print(f"  (not in zip: {missing})")
    m = load_manifest()
    m[z.relative_to(ROOT).as_posix()] = {"source": SOURCE, "status": "ok (manual download)",
                                         "fetched_at": now_iso(), "bytes": z.stat().st_size}
    save_manifest(m)
    return True


# ---------- route B: API crawl ----------
class Esco:
    def __init__(self) -> None:
        self.s = requests.Session()
        self.calls = 0

    def get(self, path: str, params: dict) -> dict:
        params = {"language": "en", "selectedVersion": VERSION, **params}
        for attempt in range(4):
            try:
                r = self.s.get(f"{API}/{path}", params=params, timeout=60)
                self.calls += 1
                if r.status_code == 200:
                    return r.json()
                if r.status_code == 404:
                    return {}
                raise RuntimeError(f"HTTP {r.status_code}")
            except Exception as e:
                wait = 2 ** attempt
                print(f"  retry {path} in {wait}s ({e})")
                time.sleep(wait)
        raise RuntimeError(f"ESCO API failed: {path} {params}")

    def bulk(self, kind: str, uris: list[str]) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for i in range(0, len(uris), BATCH):
            chunk = uris[i:i + BATCH]
            d = self.get(f"resource/{kind}", {"uris": chunk})
            out.update(d.get("_embedded", {}))
            time.sleep(0.2)  # be polite to a public service
        return out


def en(d: dict | None) -> str | None:
    if not d:
        return None
    return d.get("en") if isinstance(d, dict) else d


def en_list(d: dict | None) -> list[str]:
    if not d:
        return []
    v = d.get("en", [])
    return v if isinstance(v, list) else [v]


def links(obj: dict, key: str) -> list[dict]:
    v = obj.get("_links", {}).get(key, [])
    return v if isinstance(v, list) else [v]


def trim_occupation(o: dict) -> dict:
    return {
        "uri": o["uri"],
        "preferred_label": o.get("title") or en(o.get("preferredLabel")),
        "code": o.get("code"),
        "description": (en(o.get("description")) or {}).get("literal")
        if isinstance(en(o.get("description")), dict) else en(o.get("description")),
        "alt_labels": en_list(o.get("alternativeLabel")),
        "isco_group": [x.get("code") for x in links(o, "broaderIscoGroup")],
        "essential_skills": [x["uri"] for x in links(o, "hasEssentialSkill")],
        "optional_skills": [x["uri"] for x in links(o, "hasOptionalSkill")],
    }


def trim_skill(s: dict) -> dict:
    desc = en(s.get("description"))
    if isinstance(desc, dict):
        desc = desc.get("literal")
    return {
        "uri": s["uri"],
        "preferred_label": s.get("title") or en(s.get("preferredLabel")),
        "description": desc,
        "alt_labels": en_list(s.get("alternativeLabel")),
        "skill_type": [x.get("title") for x in links(s, "hasSkillType")],
        "reuse_level": [x.get("title") for x in links(s, "hasReuseLevel")],
        "schemes": [{"uri": x.get("uri"), "title": x.get("title")} for x in links(s, "isInScheme")],
        "broader_skill": [x["uri"] for x in links(s, "broaderSkill")],
        "broader_hierarchy": [x["uri"] for x in links(s, "broaderHierarchyConcept")],
    }


def crawl_api(force: bool) -> None:
    occ_out = API_DIR / "occupations.jsonl"
    skill_out = API_DIR / "skills.jsonl"
    if occ_out.exists() and skill_out.exists() and not force:
        print(f"  [skip] {occ_out.relative_to(ROOT).as_posix()} present (use --force-api)")
        return
    API_DIR.mkdir(parents=True, exist_ok=True)
    targets = pd.read_csv(CURATED / "target_occupations.csv")
    esco = Esco()

    occs = esco.bulk("occupation", targets.esco_uri.tolist())
    missing = sorted(set(targets.esco_uri) - set(occs))
    if missing:
        raise SystemExit(f"ESCO API did not return these occupation URIs: {missing}")
    occ_rows = [trim_occupation(occs[u]) for u in targets.esco_uri]
    print(f"  occupations: {len(occ_rows)}")

    # skills of the occupations, then their broader concepts up to the pillar top
    skills: dict[str, dict] = {}
    frontier = sorted({u for o in occ_rows for u in o["essential_skills"] + o["optional_skills"]})
    depth = 0
    while frontier:
        got = esco.bulk("skill", frontier)
        for u, s in got.items():
            skills[u] = trim_skill(s)
        unresolved = set(frontier) - set(got)
        if unresolved:
            print(f"  (depth {depth}: {len(unresolved)} URIs not returned)")
        nxt = {b for u in got for b in skills[u]["broader_skill"] + skills[u]["broader_hierarchy"]}
        frontier = sorted(nxt - set(skills))
        print(f"  depth {depth}: {len(got)} skills fetched, {len(frontier)} broader to fetch")
        depth += 1

    with occ_out.open("w", encoding="utf-8") as f:
        for o in occ_rows:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
    with skill_out.open("w", encoding="utf-8") as f:
        for s in skills.values():
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    m = load_manifest()
    for p in (occ_out, skill_out):
        m[p.relative_to(ROOT).as_posix()] = {
            "url": f"{API}/resource/{{occupation,skill}}?selectedVersion={VERSION}",
            "source": SOURCE + " via ESCO Web Service API", "status": "ok",
            "bytes": p.stat().st_size, "fetched_at": now_iso(), "api_calls": esco.calls,
        }
    save_manifest(m)
    print(f"  wrote {len(occ_rows)} occupations, {len(skills)} skills ({esco.calls} API calls)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force-api", action="store_true", help="re-crawl the API")
    args = ap.parse_args()
    if not try_zip():
        manual_notice("https://esco.ec.europa.eu/en/use-esco/download",
                      RAW / "esco" / "ESCO dataset - v1.2.0 - classification - en - csv.zip",
                      "choose v1.2.0 / classification / en / csv. Until then we use the ESCO API subset.")
    print("ESCO API crawl (subset for target occupations):")
    crawl_api(args.force_api)


if __name__ == "__main__":
    main()
