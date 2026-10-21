"""Structural validation of data/faculty.json.

    python scripts/validate_dataset.py

Checks: required keys, unique IDs and e-mails, every record traceable to an
official source URL on vitap.ac.in, photo URLs well-formed, allowed values
for school codes and quality status, no phone numbers stored.
Exit code 0 = valid.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config, storage  # noqa: E402

REQUIRED = ["faculty_id", "name", "designation", "school_code", "school", "department",
            "specialisation", "photograph_url", "official_email", "profile_url",
            "source_urls", "last_verified", "data_quality_status", "completeness"]
TEXT_FIELDS = ["name", "designation_raw", "office_location", "specialisation_text",
               "education_ug", "education_pg", "education_phd", "education_other"]
PHONE_RE = re.compile(r"(?<!\d)(?:\+91[\s-]?)?[6-9]\d{9}(?!\d)")


def validate(path: Path = config.FACULTY_JSON) -> list[str]:
    problems: list[str] = []
    recs = storage.load_records(path)
    if not recs:
        return ["dataset is empty"]
    for k in REQUIRED:
        missing = [r.get("faculty_id", "?") for r in recs if k not in r]
        if missing:
            problems.append(f"{len(missing)} records lack key '{k}'")
    ids = Counter(r["faculty_id"] for r in recs)
    problems += [f"duplicate faculty_id {i}" for i, n in ids.items() if n > 1]
    emails = Counter(r["official_email"] for r in recs if r.get("official_email"))
    problems += [f"duplicate email {e}" for e, n in emails.items() if n > 1]
    for r in recs:
        fid = r["faculty_id"]
        srcs = r.get("source_urls") or []
        if not srcs:
            problems.append(f"{fid}: no source_urls")
        for u in srcs:
            if urlparse(u).netloc != "vitap.ac.in":
                problems.append(f"{fid}: non-official source url {u}")
        if r.get("photograph_url") and urlparse(r["photograph_url"]).scheme != "https":
            problems.append(f"{fid}: malformed photo url")
        if r.get("school_code") not in config.SCHOOLS:
            problems.append(f"{fid}: unknown school {r.get('school_code')}")
        if r.get("data_quality_status") not in {"complete", "partial", "minimal"}:
            problems.append(f"{fid}: bad status")
        if not 0 <= float(r.get("completeness", -1)) <= 1:
            problems.append(f"{fid}: completeness out of range")
        if "Contact_No" in r or "contact_no" in r:
            problems.append(f"{fid}: phone field present")
        # scan free-text fields only: URLs legitimately contain long numeric
        # IDs (Scopus author IDs, LinkedIn slugs) that look like phone numbers
        for k in TEXT_FIELDS:
            v = r.get(k)
            if isinstance(v, str) and PHONE_RE.search(v):
                problems.append(f"{fid}: possible phone number in field '{k}'")
    return problems


if __name__ == "__main__":
    probs = validate()
    recs = storage.load_records()
    print(f"Records: {len(recs)}")
    print(f"With profile URL: {sum(1 for r in recs if r.get('profile_url'))}")
    print(f"With photo URL:   {sum(1 for r in recs if r.get('photograph_url'))}")
    if probs:
        print(f"{len(probs)} problem(s):")
        for p in probs[:50]:
            print("  -", p)
        sys.exit(1)
    print("Dataset valid.")
