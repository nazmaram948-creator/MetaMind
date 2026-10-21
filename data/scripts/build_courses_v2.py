"""Build data/curated/courses_v2.csv from the team's courses.csv (left unchanged).

Inputs
  data/curated/courses.csv            team catalogue (v1): ids, titles, urls, hours
  data/curated/course_skill_map_v2.csv course -> ESCO skill labels (hand-curated)
  data/curated/course_page_checks.csv  live page checks (check_course_pages.py)
  data/extracts/esco_skills.csv, esco_occ_skill.csv

What changes versus v1
  * skill_ids like "ESCO-DA-01" (not real ESCO identifiers) are replaced by ESCO
    v1.2 skill URIs. Labels are resolved against the ESCO extract; an unknown or
    ambiguous label stops the script, so no ID can be invented.
  * hours_verified is true only when the course page states the hours
    (see check_course_pages.py); `hours` is then the page value. Otherwise the
    team's figure is kept in hours_claimed_v1 and hours_verified is false.
  * relevant_to_targets: the course teaches at least one skill of our 42 target
    occupations.

Usage:  python data/scripts/build_courses_v2.py
"""
from __future__ import annotations

import csv
from collections import defaultdict

from _common import CURATED, EXTRACTS

CONF_RANK = {"high": 3, "medium": 2, "low": 1}


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def resolver():
    skills = read(EXTRACTS / "esco_skills.csv")
    linked = {r["skill_uri"] for r in read(EXTRACTS / "esco_occ_skill.csv")}
    by_label = defaultdict(list)
    for s in skills:
        by_label[s["preferred_label"]].append(s["uri"])

    def resolve(label: str) -> str:
        uris = by_label.get(label, [])
        if len(uris) > 1:  # prefer the concept linked to our occupations
            uris = [u for u in uris if u in linked] or uris
        if len(uris) != 1:
            raise SystemExit(f"ESCO label {label!r} resolves to {len(uris)} skills: {uris}")
        return uris[0]

    return resolve, linked


def main() -> None:
    resolve, linked = resolver()
    v1 = read(CURATED / "courses.csv")
    mapping = defaultdict(list)
    for m in read(CURATED / "course_skill_map_v2.csv"):
        mapping[m["course_id"]].append(m)
    unknown = set(mapping) - {c["course_id"] for c in v1}
    if unknown:
        raise SystemExit(f"course_skill_map_v2.csv has unknown course_ids: {sorted(unknown)}")
    checks_path = CURATED / "course_page_checks.csv"
    checks = {r["course_id"]: r for r in read(checks_path)} if checks_path.exists() else {}

    out = []
    for c in v1:
        maps = mapping.get(c["course_id"], [])
        uris = [resolve(m["esco_skill_label"]) for m in maps]
        chk = checks.get(c["course_id"], {})
        page_hours = chk.get("hours_total_on_page", "")
        verified = chk.get("url_kind") == "course_page" and page_hours != ""

        notes = []
        if not maps:
            notes.append("no skill of the 42 target occupations matches this course")
        if chk.get("url_kind") == "homepage_only":
            notes.append("url is a provider homepage, not a course page: hours cannot be checked")
        elif chk and not verified:
            notes.append("page does not state total hours: check by hand")
        if verified and abs(float(page_hours) - float(c["hours"])) > 0.5:
            notes.append(f"team sheet said {c['hours']} h; page states {page_hours} h")

        out.append({
            "id": c["course_id"],
            "title": c["course_title"],
            "provider": c["provider"],
            "url": c["url"],
            "url_kind": chk.get("url_kind", "not_checked"),
            "hours": page_hours if verified else c["hours"],
            "hours_verified": "true" if verified else "false",
            "hours_method": chk.get("hours_method", "") if verified else "",
            "hours_claimed_v1": c["hours"],
            "cost_myr": c["cost"],
            "hrd_claimable": "unknown",
            "esco_skill_uris": ";".join(uris),
            "esco_skill_labels": ";".join(m["esco_skill_label"] for m in maps),
            "mapping_confidence": min((m["confidence"] for m in maps), key=CONF_RANK.get, default=""),
            "relevant_to_targets": "true" if any(u in linked for u in uris) else "false",
            "checked_on": chk.get("checked_on", ""),
            "status": "UNVERIFIED - team to check skill mapping, cost (assumed MYR) and HRD Corp claimability",
            "notes": "; ".join(notes),
            "original_skill_ids_v1": c["skill_ids"],
        })

    path = CURATED / "courses_v2.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    n_rel = sum(r["relevant_to_targets"] == "true" for r in out)
    n_ver = sum(r["hours_verified"] == "true" for r in out)
    print(f"wrote {path.name}: {len(out)} courses, {n_rel} teach a target-role skill, "
          f"{n_ver} with hours verified on the course page")


if __name__ == "__main__":
    main()
