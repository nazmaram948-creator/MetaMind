"""Turn the ESCO crawl (data/raw/esco_api/*.jsonl) into small committed CSVs.

Outputs in data/extracts/ (tracked in git so Replit and CI need no downloads):
  esco_occupations.csv   uri, preferred_label, code, isco_group, description
  esco_skills.csv        uri, preferred_label, skill_type, reuse_level,
                         is_green, is_digital, is_transversal, alt_labels, description
  esco_occ_skill.csv     occupation_uri, skill_uri, relation (essential|optional)
  esco_skill_broader.csv skill_uri, broader_uri, kind (skill|hierarchy)
  esco_meta.json         source, version, fetched_at

TODO: when the official ESCO CSV bundle is in data/raw/esco/csv/, read that
instead (same output columns).

Usage:  python data/scripts/extract_esco.py
"""
from __future__ import annotations

import csv
import json

from _common import EXTRACTS, RAW, load_manifest

API_DIR = RAW / "esco_api"
GREEN = "http://data.europa.eu/esco/concept-scheme/green"
DIGITAL = "http://data.europa.eu/esco/concept-scheme/6c930acd-c104-4ece-acf7-f44fd7333036"
TRANSVERSAL = "http://data.europa.eu/esco/concept-scheme/skill-transversal-groups"


def read_jsonl(name: str) -> list[dict]:
    with (API_DIR / name).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def write_csv(name: str, header: list[str], rows: list[list]) -> None:
    EXTRACTS.mkdir(parents=True, exist_ok=True)
    with (EXTRACTS / name).open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"  {name}: {len(rows)} rows")


def main() -> None:
    occs = read_jsonl("occupations.jsonl")
    skills = read_jsonl("skills.jsonl")
    print("ESCO extracts -> data/extracts/")

    write_csv("esco_occupations.csv", ["uri", "preferred_label", "code", "isco_group", "description"],
              [[o["uri"], o["preferred_label"], o["code"], ";".join(o["isco_group"]),
                o["description"] or ""] for o in occs])

    rows = []
    for s in sorted(skills, key=lambda s: s["uri"]):
        schemes = {x["uri"] for x in s["schemes"]}
        rows.append([
            s["uri"], s["preferred_label"], ";".join(s["skill_type"]), ";".join(s["reuse_level"]),
            int(GREEN in schemes), int(DIGITAL in schemes), int(TRANSVERSAL in schemes),
            "|".join(s["alt_labels"]), s["description"] or "",
        ])
    write_csv("esco_skills.csv", ["uri", "preferred_label", "skill_type", "reuse_level", "is_green",
                                  "is_digital", "is_transversal", "alt_labels", "description"], rows)

    rel = [[o["uri"], u, "essential"] for o in occs for u in o["essential_skills"]]
    rel += [[o["uri"], u, "optional"] for o in occs for u in o["optional_skills"]]
    write_csv("esco_occ_skill.csv", ["occupation_uri", "skill_uri", "relation"], rel)

    br = [[s["uri"], b, "skill"] for s in skills for b in s["broader_skill"]]
    br += [[s["uri"], b, "hierarchy"] for s in skills for b in s["broader_hierarchy"]]
    write_csv("esco_skill_broader.csv", ["skill_uri", "broader_uri", "kind"], br)

    m = load_manifest().get("data/raw/esco_api/skills.jsonl", {})
    meta = {"source": "ESCO v1.2.0, European Commission (ESCO Web Service API)",
            "source_url": "https://esco.ec.europa.eu/", "version": "v1.2.0",
            "licence": "European Commission reuse policy (Decision 2011/833/EU); attribution required",
            "fetched_at": m.get("fetched_at")}
    (EXTRACTS / "esco_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
