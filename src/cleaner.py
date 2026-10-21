"""Cleaning stage: normalise, validate, deduplicate and score records.

Input is the output of ``extractor.extract_all``; output is the cleaned
dataset written to ``data/faculty.json`` / ``.csv`` / ``.db``.

Rules are deliberately conservative: values are tidied (whitespace, case,
URL schemes) and *classified*, but never invented. Anything that cannot be
interpreted is kept as published and flagged in ``quality_issues``.
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from . import config

log = logging.getLogger(__name__)

PLACEHOLDERS = {"", "-", "--", "---", ".", "na", "n/a", "nil", "null", "none",
                "not available", "nan", "_"}
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
ORCID_RE = re.compile(r"(\d{4}-\d{4}-\d{4}-\d{3}[\dXx])")
SCOPUS_RE = re.compile(r"authorI[dD]=(\d+)")
SCHOLAR_USER_RE = re.compile(r"[?&]user=([\w-]{12})")
SCHOLAR_BARE_RE = re.compile(r"^[\w-]{12}$")
SCHOOL_RE = re.compile(r"^(.*?)\s*\(([A-Z]+)\)\s*$")


# ---------------------------------------------------------------- primitives
def clean_text(value: Any) -> str | None:
    """Collapse whitespace; map empty strings and placeholders to None."""
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    text = re.sub(r"\s+", " ", value.replace(" ", " ")).strip()
    text = text.strip(" ,;")
    return None if text.lower() in PLACEHOLDERS else text


def clean_name(value: Any) -> tuple[str | None, str | None]:
    """Return (display_name, honorific). Fixes ``Dr.Name`` / ``Dr Name``."""
    text = clean_text(value)
    if not text:
        return None, None
    m = re.match(r"^(Dr|Mr|Ms|Mrs|Prof)\.?\s*(.*)$", text, flags=re.I)
    if m and m.group(2):
        hon = m.group(1).capitalize() + "."
        rest = m.group(2).strip()
        return f"{hon} {rest}", hon
    return text, None


def split_list(value: Any, seps: str = r"[,;\n|•]+") -> list[str]:
    """Split a free-text list into unique, tidy items (order preserved)."""
    text = clean_text(value)
    if not text:
        return []
    items, seen = [], set()
    for part in re.split(seps, text):
        part = clean_text(part.strip(" .:-"))
        if not part or len(part) < 2:
            continue
        key = part.lower()
        if key not in seen:
            seen.add(key)
            items.append(part)
    return items


def normalise_url(value: Any) -> str | None:
    """Add a missing ``https://`` scheme; return None for non-URLs."""
    text = clean_text(value)
    if not text:
        return None
    if text.lower().startswith(("http://", "https://")):
        return text
    if re.match(r"^(www\.|[a-z0-9-]+\.[a-z]{2,})", text, flags=re.I) and " " not in text:
        return "https://" + text
    return None


# ---------------------------------------------------------------- domain rules
def parse_school(value: Any) -> tuple[str | None, str | None]:
    """``'School of Law (VSL)'`` -> (``'VSL'``, ``'School of Law'``)."""
    text = clean_text(value)
    if not text:
        return None, None
    m = SCHOOL_RE.match(text)
    if m:
        code = m.group(2).upper()
        return code, config.SCHOOLS.get(code, m.group(1).strip())
    for code, name in config.SCHOOLS.items():
        if text.lower() == name.lower() or text.upper() == code:
            return code, name
    return None, text


def normalise_department(sub_department: Any, school_code: str | None,
                         school_name: str | None) -> tuple[str | None, str]:
    """Return (department, level). Uses the CMS sub-department where present,
    otherwise falls back to the school (level = 'school')."""
    text = clean_text(sub_department)
    if text:
        key = re.sub(r"[^A-Z]", "", text.upper())
        return config.SUB_DEPARTMENTS.get(key, text), "department"
    return school_name, "school"


_GRADE_FIXES = [
    (r"\bsr\.?\b", "senior"),
    (r"grade\s*-\s*", "grade "),
    (r"grade(\d)", r"grade \1"),
    (r"grade\s+ii\b", "grade 2"),
    (r"grade\s+i\b", "grade 1"),
]


def parse_designation(value: Any) -> dict[str, str | None]:
    """Split a designation into administrative role, rank and grade.

    Examples::

        'Dean, SAS, Professor HAG' -> role 'Dean, SAS', rank 'Professor', grade 'HAG'
        'Assistant Professor Sr Grade 1' -> rank 'Assistant Professor', grade 'Senior Grade 1'
    """
    text = clean_text(value)
    out = {"designation": text, "admin_role": None, "admin_role_type": None,
           "academic_rank": "Not stated", "grade": None}
    if not text:
        return out
    # split on commas, and on '. ' directly before a rank word
    parts = [p.strip() for p in re.split(r",|\.\s+(?=(?:Assistant|Associate|Professor))", text) if p.strip()]
    rank_idx = None
    for i, p in enumerate(parts):
        if re.search(r"professor|adjunct|faculty", p, flags=re.I):
            rank_idx = i
    rank_part = parts[rank_idx] if rank_idx is not None else ""
    admin_parts = [p for i, p in enumerate(parts) if i != rank_idx]
    if admin_parts:
        role = re.sub(r"\s+", " ", ", ".join(admin_parts)).strip()
        out["admin_role"] = role
        low = role.lower()
        if "vice chancellor" in low:
            out["admin_role_type"] = "Vice Chancellor"
        elif "registrar" in low:
            out["admin_role_type"] = "Registrar"
        elif "associate" in low and "dean" in low:
            out["admin_role_type"] = "Associate Dean"
        elif "assistant" in low and "dean" in low:
            out["admin_role_type"] = "Assistant Dean"
        elif "dean" in low:
            out["admin_role_type"] = "Dean"
        elif "head" in low:
            out["admin_role_type"] = "Head of Department"
        else:
            out["admin_role_type"] = "Other"

    r = rank_part.lower()
    for pat, rep in _GRADE_FIXES:
        r = re.sub(pat, rep, r)
    r = re.sub(r"\s+", " ", r).strip()
    rank, rest = "Not stated", ""
    if "emeritus" in r:
        rank, rest = "Emeritus Professor", ""
    elif "professor of practice" in r:
        rank, rest = "Professor of Practice", ""
    elif "adjunct" in r:
        rank, rest = "Adjunct Faculty", ""
    elif "assistant professor" in r:
        rank, rest = "Assistant Professor", r.split("assistant professor", 1)[1]
    elif "associate professor" in r:
        rank, rest = "Associate Professor", r.split("associate professor", 1)[1]
    elif "professor" in r:
        rank, rest = "Professor", r.split("professor", 1)[1]
    out["academic_rank"] = rank
    rest = rest.strip(" .-")
    if rest:
        out["grade"] = "HAG" if rest == "hag" else " ".join(
            w.upper() if w == "hag" else w.capitalize() for w in rest.split())
    out["designation"] = (rank + (" " + out["grade"] if out["grade"] else "")) \
        if rank != "Not stated" else text
    return out


PHD_CATEGORIES = [
    ("IISER", [r"\biiser\b", r"indian institute of science education"]),
    ("IIIT", [r"\biiit", r"indian institute of information technology"]),
    ("IISc", [r"\biisc\b", r"indian institute of science\b(?! education)"]),
    ("IIT", [r"\biit\b", r"\biit[\s-]", r"indian institute of technology"]),
    ("NIT", [r"\bnit\b", r"\bnit[\s-]", r"\bnitk\b", r"national institute of technology"]),
    ("BITS", [r"\bbits\b", r"birla institute of technology and science"]),
    ("VIT", [r"\bvit\b", r"vellore institute of technology"]),
]
FOREIGN_MARKERS = [
    "usa", "u.s.a", "united states", "uk", "united kingdom", "england", "germany",
    "france", "korea", "japan", "taiwan", "china", "italy", "spain", "israel",
    "australia", "canada", "singapore", "netherlands", "sweden", "portugal",
    "malaysia", "switzerland", "belgium", "austria", "ireland", "finland",
    "norway", "denmark", "poland", "russia", "saudi", "new zealand", "hong kong",
    "czech", "brazil", "south africa", "thailand", "turkey", "iran",
]


def classify_phd(value: Any) -> str:
    """Rule-based classification of the PhD institution text.

    Returns one of IIT, NIT, IISc, IISER, IIIT, BITS, VIT, Foreign, Pursuing,
    Other / unclassified, or Not stated.
    """
    text = clean_text(value)
    if not text:
        return "Not stated"
    low = text.lower()
    if re.search(r"pursuing|ongoing|submitted|thesis under", low):
        return "Pursuing"
    for cat, pats in PHD_CATEGORIES:
        if any(re.search(p, low) for p in pats):
            return cat
    for marker in FOREIGN_MARKERS:
        if re.search(r"(?<![a-z])" + re.escape(marker) + r"(?![a-z])", low):
            return "Foreign"
    return "Other / unclassified"


def parse_office_building(value: Any) -> str | None:
    """Extract the building code from an office address such as
    ``'145, AB-1'`` -> ``'AB-1'`` or ``'1013-P, CB'`` -> ``'CB'``."""
    text = clean_text(value)
    if not text:
        return None
    text = re.sub(r"central block", "CB", text, flags=re.I)
    text = re.sub(r"academic block\s*-?\s*(\d)", r"AB-\1", text, flags=re.I)
    m = re.search(r"\b(AB|CB|LH|MH|SJT|TT)\s*-?\s*(\d)?\b", text.upper())
    if not m:
        return None
    return m.group(1) + (f"-{m.group(2)}" if m.group(2) else "")


def canonical_orcid(value: Any) -> tuple[str | None, bool]:
    text = clean_text(value)
    if not text:
        return None, True
    m = ORCID_RE.search(text)
    if m:
        return f"https://orcid.org/{m.group(1).upper()}", True
    return normalise_url(text), False


def canonical_scopus(value: Any) -> tuple[str | None, bool]:
    text = clean_text(value)
    if not text:
        return None, True
    m = SCOPUS_RE.search(text)
    if m:
        return f"https://www.scopus.com/authid/detail.uri?authorId={m.group(1)}", True
    if re.fullmatch(r"\d{8,12}", text):
        return f"https://www.scopus.com/authid/detail.uri?authorId={text}", True
    return normalise_url(text), False


def canonical_scholar(value: Any) -> tuple[str | None, bool]:
    text = clean_text(value)
    if not text:
        return None, True
    m = SCHOLAR_USER_RE.search(text)
    if m:
        return f"https://scholar.google.com/citations?user={m.group(1)}", True
    if SCHOLAR_BARE_RE.match(text):
        return f"https://scholar.google.com/citations?user={text}", True
    return normalise_url(text), False


# ---------------------------------------------------------------- record level
def clean_record(rec: dict[str, Any]) -> dict[str, Any]:
    """Apply every cleaning rule to one extracted record."""
    issues: list[str] = []
    name, honorific = clean_name(rec.get("name"))
    school_code, school = parse_school(rec.get("school_raw"))
    if school_code not in config.SCHOOLS:
        issues.append("unknown_school")
    department, dept_level = normalise_department(rec.get("sub_department_raw"), school_code, school)
    des = parse_designation(rec.get("designation_raw"))
    if des["academic_rank"] == "Not stated":
        issues.append("rank_not_stated")

    email = clean_text(rec.get("official_email"))
    email = email.lower() if email else None
    if email and not EMAIL_RE.match(email):
        issues.append("invalid_email")
        email = None
    if not email:
        issues.append("missing_email")
    elif not email.endswith("@vitap.ac.in"):
        issues.append("non_institutional_email")

    specs = split_list(rec.get("specialisation_raw"))
    if not specs:
        issues.append("missing_specialisation")

    scholar, ok = canonical_scholar(rec.get("google_scholar"))
    if not ok:
        issues.append("scholar_not_profile_link")
    orcid, ok = canonical_orcid(rec.get("orcid"))
    if not ok:
        issues.append("orcid_unparsed")
    scopus, ok = canonical_scopus(rec.get("scopus"))
    if not ok:
        issues.append("scopus_unparsed")

    photo = normalise_url(rec.get("photograph_url"))
    if not photo:
        issues.append("missing_photo")
    if not rec.get("profile_url"):
        issues.append("no_profile_url")

    out = {
        "faculty_id": None,  # assigned after deduplication
        "name": name,
        "honorific": honorific,
        "designation": des["designation"],
        "designation_raw": clean_text(rec.get("designation_raw")),
        "academic_rank": des["academic_rank"],
        "grade": des["grade"],
        "admin_role": des["admin_role"],
        "admin_role_type": des["admin_role_type"],
        "school_code": school_code,
        "school": school,
        "department": department,
        "department_level": dept_level,
        "specialisation": specs,
        "specialisation_text": clean_text(rec.get("specialisation_raw")),
        "education_ug": clean_text(rec.get("education_ug")),
        "education_pg": clean_text(rec.get("education_pg")),
        "education_phd": clean_text(rec.get("education_phd")),
        "education_other": clean_text(rec.get("education_other")),
        "phd_institution_category": classify_phd(rec.get("education_phd")),
        "professional_memberships": split_list(rec.get("professional_memberships_raw")),
        "official_email": email,
        "office_location": clean_text(rec.get("office_location")),
        "office_building": parse_office_building(rec.get("office_location")),
        "photograph_url": photo,
        "google_scholar": scholar,
        "orcid": orcid,
        "scopus": scopus,
        "researchgate": normalise_url(rec.get("researchgate")),
        "dblp": normalise_url(rec.get("dblp")),
        "vidwan": normalise_url(rec.get("vidwan")),
        "linkedin": normalise_url(rec.get("linkedin")),
        "personal_website": normalise_url(rec.get("personal_website")),
        "patents": [clean_text(p) for p in rec.get("patents", []) if clean_text(p)],
        "projects": [clean_text(p) for p in rec.get("projects", []) if clean_text(p)],
        "awards": [clean_text(p) for p in rec.get("awards", []) if clean_text(p)],
        "publications": None,  # not published in the directory data
        "experience": None,    # not published in the directory data
        "listing_order": rec.get("listing_order"),
        "employee_code": rec.get("employee_code"),
        "profile_url": rec.get("profile_url"),
        "source_urls": rec.get("source_urls", []),
        "record_origin": rec.get("record_origin"),
        "cms_updated_at": rec.get("cms_updated_at"),
        "last_verified": rec.get("captured_at"),
        "extra_fields": rec.get("extra_fields", {}),
    }
    out["n_patents"] = len(out["patents"])
    out["n_projects"] = len(out["projects"])
    out["n_awards"] = len(out["awards"])
    filled = sum(1 for f in config.COMPLETENESS_FIELDS if out.get(f) not in (None, "", []))
    out["completeness"] = round(filled / len(config.COMPLETENESS_FIELDS), 3)
    out["quality_issues"] = issues
    out["data_quality_status"] = quality_status(out["completeness"], issues)
    return out


def quality_status(completeness: float, issues: list[str]) -> str:
    """Bucket a record: 'complete' (>= 75 % of tracked fields and no blocking
    issue), 'partial' (>= 40 %), else 'minimal'."""
    blocking = {"missing_email", "unknown_school", "no_profile_url"}
    if completeness >= 0.75 and not blocking.intersection(issues):
        return "complete"
    if completeness >= 0.40:
        return "partial"
    return "minimal"


def dedupe_key(rec: dict[str, Any]) -> str:
    """E-mail if present, otherwise the honorific-free lower-cased name."""
    if rec.get("official_email"):
        return "email:" + rec["official_email"]
    name = re.sub(r"^(dr|mr|ms|mrs|prof)\.?\s*", "", (rec.get("name") or "").lower())
    return "name:" + re.sub(r"[^a-z]", "", name)


def deduplicate(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Keep the most complete record per key; return (kept, duplicates)."""
    best: dict[str, dict[str, Any]] = {}
    dups: list[dict[str, Any]] = []
    for rec in records:
        key = dedupe_key(rec)
        if key in best:
            loser, winner = sorted([best[key], rec], key=lambda r: r["completeness"])
            dups.append({"key": key, "kept": winner["name"], "dropped": loser["name"]})
            best[key] = winner
        else:
            best[key] = rec
    # second pass: same normalised name but different e-mail -> flag only
    names = Counter(dedupe_key({"name": r["name"]}) for r in best.values())
    for r in best.values():
        if names[dedupe_key({"name": r["name"]})] > 1:
            r["quality_issues"].append("possible_duplicate_name")
    return list(best.values()), dups


def assign_ids(records: list[dict[str, Any]]) -> None:
    """``VITAP-<employee_code>`` when unique, else a sequential fallback."""
    codes = Counter(r.get("employee_code") for r in records)
    for i, r in enumerate(records, start=1):
        code = r.get("employee_code")
        if code and codes[code] == 1 and re.fullmatch(r"\d+", code):
            r["faculty_id"] = f"VITAP-{code}"
        else:
            r["faculty_id"] = f"VITAP-X{i:04d}"
            r["quality_issues"].append("fallback_id")


def clean_records(extracted: list[dict[str, Any]], *, discovered: int | None = None,
                  extraction_failures: int = 0) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the full cleaning pipeline and return (records, quality_report)."""
    cleaned = [clean_record(r) for r in extracted]
    kept, dups = deduplicate(cleaned)
    kept.sort(key=lambda r: (r["listing_order"] if r["listing_order"] is not None else 10**6,
                             r["employee_code"] or "", r["name"] or ""))
    assign_ids(kept)
    issue_counts = Counter(i for r in kept for i in r["quality_issues"])
    coverage = {}
    track = config.COMPLETENESS_FIELDS + ["education_other", "professional_memberships",
                                          "researchgate", "dblp", "vidwan",
                                          "personal_website", "patents", "projects", "awards"]
    for f in track:
        n = sum(1 for r in kept if r.get(f) not in (None, "", []))
        coverage[f] = {"count": n, "pct": round(100 * n / max(len(kept), 1), 1)}
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profiles_discovered": discovered if discovered is not None else len(extracted),
        "extraction_failures": extraction_failures,
        "profiles_extracted": len(extracted),
        "duplicates_removed": len(dups),
        "duplicates": dups,
        "profiles_processed": len(kept),
        "issue_counts": dict(issue_counts.most_common()),
        "field_coverage": coverage,
        "status_counts": dict(Counter(r["data_quality_status"] for r in kept)),
        "fields_not_published": ["publications", "experience"],
    }
    log.info("Cleaned %d records (%d duplicates removed)", len(kept), len(dups))
    return kept, report
