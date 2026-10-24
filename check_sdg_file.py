"""Check an SDG map CSV before sending it to the team.

Usage (PowerShell or terminal):
    python check_sdg_file.py                      -> checks data/curated/sdg_map_v2.csv
    python check_sdg_file.py path\\to\\your_file.csv  -> checks that file

Uses only the Python standard library.
Exit code 0 = ready to send, 1 = problems found.
"""
import csv
import json
import re
import sys
import urllib.request
from collections import Counter
from pathlib import Path

# Columns the engine expects (keep every one, same spelling).
ORIGINAL_COLUMNS = [
    "key_type", "key", "occ_id", "isco_code", "esco_uri",
    "sdg_ids", "targets", "reason", "evidence", "basis", "status",
]
# Columns needed for source/date badges in the app.
METADATA_COLUMNS = ["source", "date_published"]

# Fallback if the full occupation list can't be loaded.
KNOWN_SIX = {
    "billing_clerk": "Billing clerk",
    "budget_analyst": "Budget analyst",
    "debt_collector": "Debt collector",
    "insurance_clerk": "Insurance clerk",
    "procurement_support_officer": "Procurement support officer",
    "receptionist": "Receptionist",
}

problems = []
warnings = []


def fail(msg):
    problems.append(msg)
    print("  FAIL  " + msg)


def warn(msg):
    warnings.append(msg)
    print("  WARN  " + msg)


def ok(msg):
    print("  PASS  " + msg)


def short(items, n=8):
    items = list(items)
    text = ", ".join(str(i) for i in items[:n])
    return text + (" ... (+%d more)" % (len(items) - n) if len(items) > n else "")


def find_repo_root():
    here = Path(__file__).resolve()
    for p in [Path.cwd().resolve(), *Path.cwd().resolve().parents, *here.parents]:
        if (p / "engine" / "build.py").exists():
            return p
    return None


def load_occupations():
    """Return ({occ_id: title}, source_name) or (None, None)."""
    root = find_repo_root()
    if root is not None:
        try:
            sys.path.insert(0, str(root))
            from engine.build import occupations  # type: ignore

            records = occupations().to_dict("records")
            return {str(r["occ_id"]): str(r["title"]) for r in records}, "engine data"
        except Exception:
            pass
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/api/occupations", timeout=3) as resp:
            data = json.load(resp)
        return {str(o["occ_id"]): str(o["title"]) for o in data}, "running backend"
    except Exception:
        return None, None


def read_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        header = [h.strip() for h in (reader.fieldnames or [])]
        rows, wide = [], []
        for i, raw in enumerate(reader, start=2):
            if None in raw:
                wide.append(i)
            rows.append({(k or "").strip(): (v or "").strip() for k, v in raw.items() if k is not None})
    return header, rows, wide


def main():
    default = Path("data/curated/sdg_map_v2.csv")
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    print("Checking: %s\n" % path)

    if not path.exists():
        print("  FAIL  File not found: %s" % path)
        print("\nNOT READY TO SEND: file not found")
        return 1
    try:
        header, rows, wide = read_rows(path)
    except Exception as e:
        print("  FAIL  Could not read the file as CSV: %s" % e)
        print("\nNOT READY TO SEND: unreadable file")
        return 1

    # 1. Header
    print("1. Columns")
    missing = [c for c in ORIGINAL_COLUMNS if c not in header]
    if "reasoning" in header and "reason" not in header:
        fail('Column "reasoning" must be named "reason" (the engine reads "reason")')
    if missing:
        fail("Missing columns: " + short(missing))
    else:
        ok("All %d expected columns are present" % len(ORIGINAL_COLUMNS))
    miss_meta = [c for c in METADATA_COLUMNS if c not in header]
    if miss_meta:
        warn("No %s column (needed for SDG source/date badges)" % " / ".join(miss_meta))
    else:
        ok("source and date_published columns are present")
    if wide:
        fail("Rows with more values than columns (check commas in text): lines " + short(wide))
    if missing:
        print("\nNOT READY TO SEND: fix the columns first")
        return 1

    # 2. Row types
    print("\n2. Rows")
    types = Counter(r["key_type"] for r in rows)
    print("        %d rows: %s" % (len(rows), ", ".join("%s=%d" % kv for kv in types.items())))
    occ_rows = [r for r in rows if r["key_type"] == "occupation"]
    if not occ_rows:
        fail('No rows with key_type "occupation"')
        print("\nNOT READY TO SEND: no occupation rows")
        return 1
    dup = [k for k, n in Counter((r["key_type"], r["key"]) for r in rows).items() if n > 1]
    if dup:
        fail("Duplicate rows: " + short("%s/%s" % d for d in dup))
    else:
        ok("No duplicate rows")

    # 3. Occupation list
    occ_map, source = load_occupations()
    if occ_map:
        print("\n   (compared against %d occupations from %s)" % (len(occ_map), source))
    else:
        print("\n   (full occupation list not available, running a limited check)")

    # 4. Row quality
    print("\n3. Occupation rows")
    bad = {"no_id": [], "dup_id": [], "sdg": [], "target": [], "reason": [],
           "status": [], "title": [], "unknown_id": []}
    id_counts = Counter(r["occ_id"] for r in occ_rows if r["occ_id"])
    for r in occ_rows:
        name = r["key"] or "(blank key)"
        if not r["occ_id"]:
            bad["no_id"].append(name)
        elif id_counts[r["occ_id"]] > 1:
            bad["dup_id"].append(r["occ_id"])
        elif occ_map is not None and r["occ_id"] not in occ_map:
            bad["unknown_id"].append(r["occ_id"])

        sdgs = [s.strip() for s in re.split(r"[;,]", r["sdg_ids"]) if s.strip()]
        if not sdgs or not all(s.isdigit() and 1 <= int(s) <= 17 for s in sdgs):
            bad["sdg"].append("%s (%s)" % (name, r["sdg_ids"] or "empty"))
        else:
            for t in [t.strip() for t in re.split(r"[;,]", r["targets"]) if t.strip()]:
                if not re.match(r"^\d{1,2}\.(\d{1,2}|[a-z])$", t):
                    bad["target"].append("%s: %s" % (name, t))
                elif t.split(".")[0] not in sdgs:
                    bad["target"].append("%s: target %s is not under SDG %s" % (name, t, "/".join(sdgs)))

        if len(r["reason"]) < 25:
            bad["reason"].append(name)
        if not r["status"]:
            bad["status"].append(name)
        if occ_map and r["occ_id"] in occ_map and r["key"] != occ_map[r["occ_id"]]:
            bad["title"].append('%s (should be "%s")' % (r["key"], occ_map[r["occ_id"]]))

    def report(key, problem_label, ok_label, hard=True):
        if bad[key]:
            (fail if hard else warn)("%s: %s" % (problem_label, short(bad[key])))
        else:
            ok(ok_label)

    report("no_id", "occ_id is empty", "Every row has an occ_id")
    report("dup_id", "occ_id is used twice", "Every occ_id is unique")
    report("unknown_id", "occ_id not in the occupation list", "Every occ_id is a real occupation", hard=False)
    report("sdg", "sdg_ids is empty or not a number from 1 to 17", "sdg_ids are valid (1 to 17)")
    report("target", "targets is wrong", "targets match their SDG")
    report("title", "key does not match the occupation title", "key matches the occupation title")
    report("reason", "reason is empty or too short (under 25 characters)", "Every row has a reason")
    report("status", "status is empty", "Every row has a status")

    # 5. Quality hints
    print("\n4. Quality hints")
    same_reason = [k for k, n in Counter(r["reason"] for r in occ_rows if r["reason"]).items() if n > 1]
    if same_reason:
        warn("Identical reason text on several rows: " + short(same_reason, 3))
    same_target = [k for k, n in Counter(r["targets"] for r in occ_rows if r["targets"]).items() if n >= 5]
    if same_target:
        warn("5+ rows share the same target (%s). Check they are specific." % short(same_target))
    verified_no_evidence = [r["key"] for r in occ_rows
                            if r["status"].lower() == "verified" and not r["evidence"]]
    if verified_no_evidence:
        warn('status "Verified" with empty evidence: ' + short(verified_no_evidence))
    if not (same_reason or same_target or verified_no_evidence):
        ok("No generic or unsupported rows spotted")
    print('        Reminder: use status "Verified" only if someone really reviewed the row.')

    # 6. Coverage
    print("\n5. Coverage")
    have = {r["occ_id"] for r in occ_rows if r["occ_id"]}
    have_titles = {r["key"] for r in occ_rows}
    if occ_map:
        gone = [t for i, t in occ_map.items() if i not in have and t not in have_titles]
        if gone:
            fail("%d of %d occupations have no SDG row: %s" % (len(gone), len(occ_map), short(gone)))
        else:
            ok("All %d occupations have an SDG row" % len(occ_map))
    else:
        gone = [t for i, t in KNOWN_SIX.items() if i not in have]
        if gone:
            fail("These roles have no row with the right occ_id: " + short(gone))
        else:
            ok("The 6 roles that were missing are present with the right occ_id")
        print("        (start the backend or run from the repo folder for a full check)")

    # Result
    print("\n" + "=" * 50)
    if problems:
        print("NOT READY TO SEND: %d problem(s), %d warning(s)" % (len(problems), len(warnings)))
        return 1
    print("READY TO SEND (%d warning(s) to read above)" % len(warnings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
