"""Extraction stage: map raw CMS records to a flat, documented schema.

This stage only *renames and restructures* fields; it does not judge or
rewrite their content (that is ``cleaner.py``'s job). Keeping the two apart
means the cleaning rules can be re-run and audited against the extracted
values at any time.
"""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

from . import config

log = logging.getLogger(__name__)

# raw CMS key -> extracted key. Keys not listed here are preserved under
# ``extra_fields`` so nothing the site publishes is silently discarded.
FIELD_MAP = {
    "Name": "name",
    "Designation": "designation_raw",
    "Department": "school_raw",
    "sub_department": "sub_department_raw",
    "EMAIL": "official_email",
    "Office_Address": "office_location",
    "Research_area_of_specialization": "specialisation_raw",
    "Education_UG": "education_ug",
    "Education_PG": "education_pg",
    "Education_PHD": "education_phd",
    "Education_other": "education_other",
    "Professonal_Membership": "professional_memberships_raw",  # sic, CMS spelling
    "Research_google_schloar": "google_scholar",  # sic, CMS spelling
    "Research_orchid": "orcid",  # sic
    "Research_Scopus_Id": "scopus",
    "Research_Research_Gate": "researchgate",
    "Research_DBLP": "dblp",
    "Research_vidwan": "vidwan",
    "LinkedIn": "linkedin",
    "Website": "personal_website",
    "Photo": "photograph_url",
    "createdAt": "cms_created_at",
    "updatedAt": "cms_updated_at",
    "publishedAt": "cms_published_at",
}
LIST_FIELDS = {
    "Patents": ("patents", "patent"),
    "Projects": ("projects", "project"),
    "Awards_and_Recognitions": ("awards", "award_or_recognition_name"),
}
DROPPED_FIELDS = {"Contact_No"}  # personal phone numbers: never stored


def parse_employee_id(value: Any) -> tuple[int | None, str | None]:
    """Split the CMS ``Employee_Id`` into (listing_order, employee_code).

    The site stores values such as ``6.70009``: the integer part controls the
    order cards appear in (leaders first) and the fractional part matches the
    staff number embedded in photo file names (``..._70009_...``). Floats lose
    trailing zeros (``1.7001`` really means ``1.70010``), so the fractional
    part is right-padded to five digits. Plain integers (``70709``) carry no
    ordering prefix.
    """
    if value is None or value == "":
        return None, None
    text = str(value).strip()
    if "." in text:
        whole, frac = text.split(".", 1)
        frac = frac.ljust(5, "0")
        try:
            return int(whole), frac
        except ValueError:
            return None, text
    return None, text


def photo_url(value: Any) -> str | None:
    """Return the original photo URL from either a URL string or the nested
    Strapi media object (``{"data": {"attributes": {"url": ...}}}``)."""
    if not value:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        data = value.get("data") or {}
        attrs = data.get("attributes", data) if isinstance(data, dict) else {}
        url = attrs.get("url") if isinstance(attrs, dict) else None
        return url.strip() if isinstance(url, str) and url.strip() else None
    return None


def build_profile_url(school_raw: str | None, email: str | None) -> str | None:
    """Rebuild the official profile URL exactly as the directory page does:
    ``/<Department>/faculty/<email local part>``, with SBST shortened to its
    code. Returns None when the e-mail (the page's key) is missing."""
    if not email or "@" not in email or not school_raw:
        return None
    segment = "SBST" if school_raw == "School of Bio Sciences and Technology (SBST)" else school_raw
    local = email.strip().split("@")[0]
    return f"{config.BASE_URL}/{quote(segment, safe='()')}/faculty/{quote(local, safe='.')}"


def _list_items(raw: Any, key: str) -> list[str]:
    items = []
    if isinstance(raw, list):
        for it in raw:
            if isinstance(it, dict):
                txt = it.get(key)
            else:
                txt = it
            if isinstance(txt, str) and txt.strip():
                items.append(txt.strip())
    return items


def extract_record(raw: dict[str, Any], *, source_page: str = config.DIRECTORY_URL,
                   captured_at: str | None = None) -> dict[str, Any]:
    """Convert one raw CMS record into the extracted schema."""
    rec: dict[str, Any] = {}
    for src, dst in FIELD_MAP.items():
        val = raw.get(src)
        if src == "Photo":
            val = photo_url(val)
        rec[dst] = val
    for src, (dst, key) in LIST_FIELDS.items():
        rec[dst] = _list_items(raw.get(src), key)

    order, code = parse_employee_id(raw.get("Employee_Id"))
    rec["listing_order"] = order
    rec["employee_code"] = code
    rec["profile_url"] = build_profile_url(raw.get("Department"), raw.get("EMAIL"))
    rec["record_origin"] = "cms_api" if "createdAt" in raw else "page_bundle"
    rec["source_urls"] = [u for u in (source_page, rec["profile_url"]) if u]
    rec["captured_at"] = captured_at

    known = set(FIELD_MAP) | set(LIST_FIELDS) | DROPPED_FIELDS | {"Employee_Id"}
    extra = {k: v for k, v in raw.items() if k not in known and v not in (None, "", [])}
    rec["extra_fields"] = extra
    return rec


def extract_all(snapshot: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Extract every record in a snapshot.

    Returns ``(records, failures)``; a record that raises is logged in
    ``failures`` and skipped rather than aborting the run.
    """
    out, failures = [], []
    src = snapshot.get("source_page", config.DIRECTORY_URL)
    ts = snapshot.get("captured_at")
    for i, raw in enumerate(snapshot.get("records", [])):
        try:
            if not isinstance(raw, dict) or not raw.get("Name"):
                raise ValueError("record has no Name")
            out.append(extract_record(raw, source_page=src, captured_at=ts))
        except Exception as exc:  # noqa: BLE001
            log.warning("Extraction failed for record %d: %s", i, exc)
            failures.append({"index": str(i), "error": str(exc)})
    log.info("Extracted %d records (%d failures)", len(out), len(failures))
    return out, failures
