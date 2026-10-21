"""Optional: cache official faculty photographs locally for offline demos.

    python scripts/download_photos.py            # all photos, 1.5 s apart
    python scripts/download_photos.py --limit 20

Photos stay at their original official URLs in the dataset; this script
only makes a local copy in data/photos/<faculty_id>.<ext> (ignored by git
and not redistributed in the submission ZIP). The app uses the local copy
when it exists, otherwise the official URL, otherwise an initials avatar.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config, storage  # noqa: E402
from src.scraper import fetch_with_retry  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    config.ensure_dirs()
    recs = [r for r in storage.load_records() if r.get("photograph_url")][: args.limit]
    ok = fail = skip = 0
    for r in recs:
        url = r["photograph_url"]
        ext = Path(url.split("?")[0]).suffix.lower() or ".jpg"
        dest = config.PHOTO_DIR / f"{r['faculty_id']}{ext}"
        if dest.exists():
            skip += 1
            continue
        resp = fetch_with_retry(url, retries=2)
        if resp is not None and resp.status_code == 200 and resp.content:
            dest.write_bytes(resp.content)
            ok += 1
        else:
            fail += 1
            print("failed:", r["faculty_id"], url)
        time.sleep(config.REQUEST_DELAY_SECONDS)
    print(f"downloaded {ok}, skipped {skip}, failed {fail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
