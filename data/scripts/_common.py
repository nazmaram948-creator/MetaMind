"""Shared helpers for the data download / normalise scripts.

Every download is recorded in data/raw/MANIFEST.json (url, bytes, sha256,
fetched_at, status) so the API can report where each number came from.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
# Raw downloads can live outside the checkout (shared cache, CI, second worktree).
RAW = Path(os.environ.get("SKILLSHIFT_RAW", DATA / "raw")).resolve()
CURATED = DATA / "curated"
FIXTURES = DATA / "fixtures"
EXTRACTS = DATA / "extracts"
MANIFEST = RAW / "MANIFEST.json"

# Some hosts (BLS) reject non-browser clients; a plain browser UA is enough elsewhere.
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)


def rel(path: Path) -> str:
    """Stable key for logs and the manifest: 'data/raw/...' even when RAW is elsewhere."""
    path = path.resolve()
    if path.is_relative_to(RAW):
        return "data/raw/" + path.relative_to(RAW).as_posix()
    if path.is_relative_to(ROOT):
        return path.relative_to(ROOT).as_posix()
    return path.as_posix()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {}


def save_manifest(m: dict) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(m, indent=2, sort_keys=True), encoding="utf-8")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class ManualDownloadNeeded(Exception):
    pass


def download(url: str, dest: Path, *, source: str, force: bool = False,
             retries: int = 3, timeout: int = 120) -> Path:
    """Stream `url` to `dest`. Skips if already present (unless force).

    Raises ManualDownloadNeeded if the host refuses us (403/401/429), so callers
    can print the exact URL for a human to fetch.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    rel_path = rel(dest)
    manifest = load_manifest()
    if dest.exists() and dest.stat().st_size > 0 and not force:
        print(f"  [skip] {rel_path} already present ({dest.stat().st_size:,} bytes)")
        return dest

    tmp = dest.with_suffix(dest.suffix + ".part")
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, stream=True, timeout=timeout,
                              headers={"User-Agent": BROWSER_UA}) as r:
                if r.status_code in (401, 403, 429):
                    raise ManualDownloadNeeded(f"HTTP {r.status_code} from {url}")
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                done = 0
                with tmp.open("wb") as f:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        f.write(chunk)
                        done += len(chunk)
                        if total > 20_000_000:
                            print(f"\r  {rel_path}: {done/1e6:,.0f}/{total/1e6:,.0f} MB",
                                  end="", file=sys.stderr)
                if total > 20_000_000:
                    print(file=sys.stderr)
            tmp.replace(dest)
            break
        except ManualDownloadNeeded:
            manifest[rel_path] = {"url": url, "source": source, "status": "manual_download_needed",
                             "checked_at": now_iso()}
            save_manifest(manifest)
            raise
        except Exception as e:  # network hiccup: retry with backoff
            last_err = e
            print(f"  attempt {attempt} failed: {e}", file=sys.stderr)
            time.sleep(2 * attempt)
    else:
        raise RuntimeError(f"download failed after {retries} attempts: {url}") from last_err

    manifest[rel_path] = {
        "url": url,
        "source": source,
        "status": "ok",
        "bytes": dest.stat().st_size,
        "sha256": sha256(dest),
        "fetched_at": now_iso(),
    }
    save_manifest(manifest)
    print(f"  [ok]   {rel_path} ({dest.stat().st_size:,} bytes)")
    return dest


def manual_notice(url: str, dest: Path, extra: str = "") -> None:
    rel_path = rel(dest)
    print("\n  !! MANUAL DOWNLOAD NEEDED")
    print(f"     open:    {url}")
    print(f"     save to: {rel_path}")
    if extra:
        print(f"     note:    {extra}")
    print()
