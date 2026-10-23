"""Check every course URL in data/curated/courses.csv against the live page.

For each course it records whether the link is a specific course page or only a
provider homepage, the HTTP status, and the total hours the page states. A
course's hours count as verified (in courses_v2.csv) only when one of these is
found on the page, and the method is recorded:

  page_header_total         "Flexible schedule 7 hours to complete" (course header)
  page_program_hours        "includes over 180 hours of instruction"
  sum_of_course_durations   "Course 1 • 19 hours", "Course 2 • 22 hours", ...
  sum_of_module_durations   "Module 1 • 3 hours to complete", ...

Weekly effort ("10 hours a week") is never turned into a total, because the
number of weeks is the learner's choice. Page text is treated as data: we only
pattern-match duration phrases. Pages are cached in data/raw/course_pages/.

Output: data/curated/course_page_checks.csv
Usage:  python data/scripts/check_course_pages.py [--refresh]
"""
from __future__ import annotations

import argparse
import csv
import html
import re
import time
from datetime import date
from urllib.parse import urlparse

import requests

from _common import BROWSER_UA, CURATED, RAW

OUT = CURATED / "course_page_checks.csv"
CACHE = RAW / "course_pages"

HEADER_TOTAL = re.compile(r"Flexible schedule\s+(?:Approx\.?\s*)?(\d+(?:\.\d+)?)\s+hours?\s+to\s+complete", re.I)
PROGRAM_HOURS = re.compile(r"includes\s+(?:over\s+|about\s+|approximately\s+)?(\d+(?:\.\d+)?)\s+hours\s+of\s+instruction", re.I)
PART = re.compile(r"\b(Course|Module|Week)\s+(\d+)\s*[•·]\s*(?:(\d+(?:\.\d+)?)\s*hours?)?\s*(?:(\d+)\s*minutes?)?", re.I)
ANY_DURATION = re.compile(
    r"[^.<>\n]{0,30}\b\d+(?:\.\d+)?\s*(?:-|–|to)?\s*\d*\s*(?:hours?|hrs?|weeks?|months?)\b[^.<>\n]{0,30}",
    re.I,
)


def is_homepage(url: str) -> bool:
    segments = [s for s in urlparse(url).path.split("/") if s]
    return len(segments) < 2


def page_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(raw))


def stated_total(text: str) -> tuple[str, str]:
    """Return (hours, method) stated on the page, or ("", "").

    The first header / programme statement is the page's own course (later ones
    belong to "recommended courses" blocks). A sum of parts is accepted only when
    every part numbered 1..n on the page carries a duration, so a partly listed
    programme is never under-counted.
    """
    for pattern, method in ((HEADER_TOTAL, "page_header_total"), (PROGRAM_HOURS, "page_program_hours")):
        m = pattern.search(text)
        if m and float(m.group(1)) > 0:
            return m.group(1), method
    candidates = []  # (number of parts, total, method); the kind with most parts wins
    for kind, method in (("course", "sum_of_course_durations"), ("module", "sum_of_module_durations"),
                         ("week", "sum_of_module_durations")):
        mentioned: set[int] = set()
        parts: dict[int, float] = {}
        for m in PART.finditer(text):
            if m.group(1).lower() != kind:
                continue
            n = int(m.group(2))
            mentioned.add(n)
            if m.group(3) or m.group(4):
                parts.setdefault(n, float(m.group(3) or 0) + float(m.group(4) or 0) / 60)
        complete = mentioned and set(parts) == mentioned == set(range(1, max(mentioned) + 1))
        total = sum(parts.values())
        if complete and total >= 1:
            candidates.append((len(parts), total, method))
    if candidates:
        _, total, method = max(candidates, key=lambda c: c[0])
        return f"{total:.1f}".rstrip("0").rstrip("."), method
    return "", ""


def fetch(course_id: str, url: str, s: requests.Session, refresh: bool) -> tuple[int, str, str]:
    """Return (status, final_url, html) using the local cache when possible."""
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / f"{course_id}.html"
    meta = CACHE / f"{course_id}.meta"
    if cached.exists() and meta.exists() and not refresh:
        status, final = meta.read_text(encoding="utf-8").split("\n", 1)
        return int(status), final, cached.read_text(encoding="utf-8")
    r = s.get(url, timeout=30, headers={"User-Agent": BROWSER_UA})
    body = r.content.decode("utf-8", errors="replace")
    cached.write_text(body, encoding="utf-8")
    meta.write_text(f"{r.status_code}\n{r.url}", encoding="utf-8")
    time.sleep(1.5)  # polite crawl
    return r.status_code, r.url, body


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="refetch pages instead of using the cache")
    args = ap.parse_args()
    with (CURATED / "courses.csv").open(encoding="utf-8-sig", newline="") as f:
        courses = list(csv.DictReader(f))
    today = date.today().isoformat()
    s = requests.Session()
    rows = []
    for c in courses:
        url = c["url"].strip()
        row = {"course_id": c["course_id"], "url": url, "url_kind": "", "http_status": "",
               "final_url": "", "hours_total_on_page": "", "hours_method": "",
               "duration_phrases": "", "checked_on": today}
        if is_homepage(url):
            row["url_kind"] = "homepage_only"
            rows.append(row)
            print(f"  {c['course_id']}: homepage only ({url})")
            continue
        try:
            status, final, body = fetch(c["course_id"], url, s, args.refresh)
            row["http_status"] = status
            row["final_url"] = final
            row["url_kind"] = "course_page" if status == 200 else "broken"
            if status == 200:
                text = page_text(body)
                row["hours_total_on_page"], row["hours_method"] = stated_total(text)
                phrases = []
                for m in ANY_DURATION.finditer(text):
                    p = m.group(0).strip()
                    if p not in phrases:
                        phrases.append(p)
                row["duration_phrases"] = " | ".join(phrases[:5])
        except requests.RequestException as e:
            row["url_kind"] = "error"
            row["http_status"] = type(e).__name__
        rows.append(row)
        print(f"  {c['course_id']}: {row['url_kind']} {row['http_status']} "
              f"page={row['hours_total_on_page'] or '-'} [{row['hours_method'] or 'not found'}] "
              f"(sheet says {c['hours']})")

    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {OUT.name}: {len(rows)} rows")


if __name__ == "__main__":
    main()
