"""Central configuration: paths, source URLs and reference mappings.

Every other module imports paths from here so the project works the same
on Windows and Linux (pathlib handles the separators).
"""
from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------- paths
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
LOG_DIR = ROOT / "logs"
OUTPUT_DIR = ROOT / "outputs"
CHART_DIR = OUTPUT_DIR / "charts"
PHOTO_DIR = DATA_DIR / "photos"

RAW_SNAPSHOT = RAW_DIR / "vitap_faculty_raw.json"
EXTRACTED_JSON = PROCESSED_DIR / "faculty_extracted.json"
FACULTY_JSON = DATA_DIR / "faculty.json"
FACULTY_CSV = DATA_DIR / "faculty.csv"
FACULTY_DB = DATA_DIR / "faculty.db"
QUALITY_REPORT = PROCESSED_DIR / "data_quality_report.json"
ISSUES_CSV = PROCESSED_DIR / "data_quality_issues.csv"

# ---------------------------------------------------------------- source
BASE_URL = "https://vitap.ac.in"
DIRECTORY_URL = f"{BASE_URL}/allfaculty"
ROBOTS_URL = f"{BASE_URL}/robots.txt"
# The directory page loads its records from this CMS endpoint (observed in
# the browser's network log). We never call it ourselves with credentials;
# the scraper only records what the rendered page itself loads.
CMS_ENDPOINT_PATTERN = "cms.vitap.ac.in/api/faculty-profiles"
USER_AGENT = (
    "VITbutAP-ATSMA-Lab/1.0 (student academic project; CSE 4039; "
    "contact via VIT-AP)"
)
REQUEST_DELAY_SECONDS = 1.5

# ---------------------------------------------------------------- reference data
# School names exactly as the official directory filter lists them.
SCHOOLS = {
    "SCOPE": "School of Computer Science and Engineering",
    "SENSE": "School of Electronics Engineering",
    "SMEC": "School of Mechanical Engineering",
    "SAS": "School of Advanced Science",
    "VSB": "School of Business",
    "VSL": "School of Law",
    "VISH": "School of Social Science and Humanities",
    "SBST": "School of Bio Sciences and Technology",
}

# sub_department codes used by the CMS -> readable department names.
# Codes DDSE/DSSE/DNS/DAIML appear as filter tabs on the site; their long
# names come from the "Head, Dept. of ..." designations in the same data.
SUB_DEPARTMENTS = {
    "MATHS": "Mathematics",
    "MATHEMATICS": "Mathematics",
    "PHYSICS": "Physics",
    "CHEMISTRY": "Chemistry",
    "DSSE": "Software and Systems Engineering",
    "DDSE": "Data Science and Engineering",
    "DNS": "Networking and Security",
    "DAIML": "Artificial Intelligence and Machine Learning",
}

# Canonical academic ranks, ordered from senior to junior for charts.
RANK_ORDER = [
    "Professor",
    "Professor of Practice",
    "Emeritus Professor",
    "Associate Professor",
    "Assistant Professor",
    "Adjunct Faculty",
    "Not stated",
]

# Fields used to compute the profile completeness score.
COMPLETENESS_FIELDS = [
    "photograph_url",
    "designation",
    "official_email",
    "office_location",
    "specialisation",
    "education_ug",
    "education_pg",
    "education_phd",
    "google_scholar",
    "orcid",
    "scopus",
    "linkedin",
]


def ensure_dirs() -> None:
    """Create every output directory the pipeline writes to."""
    for d in (RAW_DIR, PROCESSED_DIR, LOG_DIR, CHART_DIR, PHOTO_DIR):
        d.mkdir(parents=True, exist_ok=True)
