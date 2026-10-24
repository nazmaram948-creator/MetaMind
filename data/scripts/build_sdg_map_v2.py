"""Build data/curated/sdg_map_v2.csv: SDG links for our 42 target occupations.

Every link has a stated basis and evidence taken from ESCO v1.2:

1. Collection rules (project brief): skills in ESCO's Green collection -> SDG 7, 12, 13;
   skills in ESCO's Digital collection -> SDG 9. An occupation gets the goal when
   the share of its skills in that collection (essential = 1, optional = 0.5)
   reaches COLLECTION_MIN_SHARE.
2. Skill -> SDG target rules: an occupation that has one of these ESCO skills
   (essential or optional) gets the named target. Labels are checked against
   the ESCO extract; an unknown label stops the script.
3. Team rows (data/curated/sdg_team_v2.csv, from the team's SDG list): a row whose
   title matches one of our occupations is merged into that occupation (goals
   combined, both reasons kept); the other team rows are kept unchanged, without
   an occ_id, so the build ignores them for matching.

Output columns follow the team file (incl. source, date_published). The output is
a seed for team review (status column), not a final judgement.

Usage:  python data/scripts/build_sdg_map_v2.py
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict

from _common import CURATED, EXTRACTS

COLLECTION_MIN_SHARE = 0.10
RULES_SOURCE = "SkillShift rules on ESCO v1.2 (Green/Digital collections, skill->SDG target rules)"
COLUMNS = ["key_type", "key", "occ_id", "isco_code", "esco_uri", "sdg_ids", "targets", "reason",
           "evidence", "basis", "status", "source", "date_published"]
GREEN_SCHEME = "http://data.europa.eu/esco/concept-scheme/green"
DIGITAL_SCHEME = "http://data.europa.eu/esco/concept-scheme/6c930acd-c104-4ece-acf7-f44fd7333036"

# ESCO skill label -> (SDG goal, target, short target text)
SKILL_TARGETS = {
    "implement sustainable procurement": (12, "12.7", "sustainable procurement practices"),
    "global standards for sustainability reporting": (12, "12.6", "companies integrate sustainability information into reporting"),
    "lead the sustainability reporting process": (12, "12.6", "companies integrate sustainability information into reporting"),
    "corporate social responsibility": (12, "12.6", "companies adopt sustainable practices"),
    "circular economy": (12, "12.5", "reduce waste through prevention, reduction, recycling and reuse"),
    "advise on carbon emissions reduction": (13, "13.2", "integrate climate measures into policies and planning"),
    "environmental policy": (13, "13.2", "integrate climate measures into policies and planning"),
    "develop environmental policy": (13, "13.2", "integrate climate measures into policies and planning"),
    "energy efficiency": (7, "7.3", "improve energy efficiency"),
    "conduct energy audit": (7, "7.3", "improve energy efficiency"),
    "green logistics": (13, "13.2", "integrate climate measures into planning"),
    "human resource management": (8, "8.5", "full and productive employment and decent work"),
    "negotiate employment agreements": (8, "8.8", "protect labour rights"),
    "train employees": (4, "4.4", "adults with relevant skills for employment"),
    "adapt training to labour market": (4, "4.4", "adults with relevant skills for employment"),
    "apply credit risk policy": (8, "8.10", "expand access to banking and financial services"),
    "financial products": (8, "8.10", "expand access to banking and financial services"),
    "calculate tax": (17, "17.1", "improve domestic capacity for tax collection"),
    "prepare tax returns forms": (17, "17.1", "improve domestic capacity for tax collection"),
}


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def norm(title: str) -> str:
    return "".join(title.casefold().split())


def main() -> None:
    targets = read(CURATED / "target_occupations.csv")
    team_path = CURATED / "sdg_team_v2.csv"
    team = read(team_path) if team_path.exists() else []
    team_by_title = {norm(r["key"]): r for r in team}
    meta = json.loads((EXTRACTS / "esco_meta.json").read_text(encoding="utf-8"))
    rules_date = (meta.get("fetched_at") or "")[:10]
    skills = {s["uri"]: s for s in read(EXTRACTS / "esco_skills.csv")}
    by_label = {s["preferred_label"]: u for u, s in skills.items()}
    unknown = [lbl for lbl in SKILL_TARGETS if lbl not in by_label]
    if unknown:
        raise SystemExit(f"labels not in ESCO extract: {unknown}")

    occ_skills = defaultdict(list)  # occupation uri -> [(skill uri, weight)]
    for r in read(EXTRACTS / "esco_occ_skill.csv"):
        occ_skills[r["occupation_uri"]].append((r["skill_uri"], 1.0 if r["relation"] == "essential" else 0.5))

    rows = [
        {"key_type": "skill_collection", "key": GREEN_SCHEME, "occ_id": "", "isco_code": "",
         "esco_uri": GREEN_SCHEME, "sdg_ids": "7;12;13", "targets": "",
         "reason": "ESCO Green collection: skills for the green transition (project rule: green -> SDG 7/12/13)",
         "evidence": f"{sum(s['is_green'] == '1' for s in skills.values())} green skills in extract",
         "basis": "collection_rule", "status": "seed - team to review",
         "source": RULES_SOURCE, "date_published": rules_date},
        {"key_type": "skill_collection", "key": DIGITAL_SCHEME, "occ_id": "", "isco_code": "",
         "esco_uri": DIGITAL_SCHEME, "sdg_ids": "9", "targets": "",
         "reason": "ESCO Digital collection (project rule: digital -> SDG 9)",
         "evidence": f"{sum(s['is_digital'] == '1' for s in skills.values())} digital skills in extract",
         "basis": "collection_rule", "status": "seed - team to review",
         "source": RULES_SOURCE, "date_published": rules_date},
    ]

    for t in targets:
        pairs = occ_skills[t["esco_uri"]]
        total = sum(w for _, w in pairs) or 1.0
        green = sum(w for u, w in pairs if skills.get(u, {}).get("is_green") == "1") / total
        digital = sum(w for u, w in pairs if skills.get(u, {}).get("is_digital") == "1") / total
        goals: set[int] = set()
        tgt: list[str] = []
        reasons: list[str] = []
        evidence = [f"green share {green:.0%}", f"digital share {digital:.0%}"]

        if green >= COLLECTION_MIN_SHARE:
            goals |= {7, 12, 13}
            reasons.append(f"{green:.0%} of its ESCO skills are in the Green collection")
        if digital >= COLLECTION_MIN_SHARE:
            goals.add(9)
            reasons.append(f"{digital:.0%} of its ESCO skills are in the Digital collection")
        have = {skills[u]["preferred_label"] for u, _ in pairs if u in skills}
        for label, (goal, target, text) in SKILL_TARGETS.items():
            if label in have:
                goals.add(goal)
                if target not in tgt:
                    tgt.append(target)
                reasons.append(f"skill '{label}' -> target {target} ({text})")
                evidence.append(f"has '{label}'")

        row = {
            "key_type": "occupation", "key": t["title"], "occ_id": t["occ_id"],
            "isco_code": t["isco_code"], "esco_uri": t["esco_uri"],
            "sdg_ids": ";".join(str(g) for g in sorted(goals)),
            "targets": ";".join(sorted(tgt, key=lambda x: [int(p) if p.isdigit() else p for p in x.split(".")])),
            "reason": "; ".join(reasons),
            "evidence": "; ".join(evidence),
            "basis": "collection_rule+skill_rule" if reasons else "",
            "status": "seed - team to review",
            "source": RULES_SOURCE if reasons else "",
            "date_published": rules_date if reasons else "",
        }
        mate = team_by_title.pop(norm(t["title"]), None)
        if mate:  # team row for this occupation: combine goals, keep both reasons and sources
            goals |= {int(g) for g in mate["sdg_ids"].split(";") if g.strip().isdigit()}
            row["sdg_ids"] = ";".join(str(g) for g in sorted(goals))
            row["reason"] = "; ".join(filter(None, [row["reason"], f"team: {mate['reason']}"]))
            row["evidence"] = "; ".join(filter(None, [row["evidence"], f"team: {mate['evidence']}"]))
            row["basis"] = "+".join(filter(None, [row["basis"], mate["basis"] or "team"]))
            row["status"] = f"team: {mate['status']}; rules: seed - team to review" if reasons else mate["status"]
            row["source"] = "; ".join(filter(None, [row["source"], mate["source"]]))
            row["date_published"] = mate["date_published"] or row["date_published"]
        if not row["sdg_ids"]:
            row["reason"] = "no SDG-linked skills found in ESCO profile and no team row"
            row["basis"], row["status"] = "none", "needs team input"
        rows.append(row)

    # team rows for job titles outside our catalogue: kept as supplied (no occ_id)
    rows += [{c: r.get(c, "") for c in COLUMNS} for r in team_by_title.values()]

    out = CURATED / "sdg_map_v2.csv"
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    ours = [r for r in rows if r["occ_id"]]
    print(f"wrote {out.name}: {len(ours)} target occupations ({sum(bool(r['sdg_ids']) for r in ours)} with an SDG), "
          f"{len(rows) - len(ours) - 2} other team rows")
    for r in ours:
        print(f"  {r['occ_id']:28} SDG {r['sdg_ids'] or '-':10} {r['basis']:32} {r['status'][:40]}")


if __name__ == "__main__":
    main()
