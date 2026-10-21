"""Shared fixtures: small synthetic records shaped like the real CMS data.

The synthetic people below are invented test fixtures (names like
'Dr. Test Alpha'); they never appear in the real dataset.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import cleaner, extractor, storage  # noqa: E402


def raw(name, email, dept, desig, spec, sub=None, photo=True, emp="1.70001", **kw):
    rec = {
        "Name": name, "Employee_Id": emp, "Designation": desig, "Department": dept,
        "sub_department": sub, "EMAIL": email, "Office_Address": "101-A, CB",
        "Contact_No": "9876543210",
        "Research_area_of_specialization": spec,
        "Education_UG": "B.Tech, Some University", "Education_PG": "M.Tech, NIT Trichy",
        "Education_PHD": "Ph.D, IIT Madras", "Education_other": None,
        "Professonal_Membership": "IEEE, ACM", "Research_google_schloar": None,
        "Research_orchid": None, "Research_Scopus_Id": None, "Research_Research_Gate": None,
        "Research_DBLP": None, "Research_vidwan": None, "LinkedIn": None, "Website": None,
        "Photo": ({"data": {"id": 1, "attributes": {"url": f"https://img.example/{emp}.avif"}}}
                  if photo else {"data": None}),
        "Patents": [], "Projects": [], "Awards_and_Recognitions": [],
        "createdAt": "2024-01-01T00:00:00Z", "updatedAt": "2024-02-01T00:00:00Z",
        "publishedAt": "2024-01-01T00:00:00Z",
    }
    rec.update(kw)
    return rec


@pytest.fixture
def raw_records():
    return [
        raw("Dr. Test Alpha", "alpha.t@vitap.ac.in", "School of Computer Science and Engineering (SCOPE)",
            "Assistant Professor Senior Grade 1", "Machine Learning, Deep Learning, Computer Vision",
            sub="DAIML", emp="5.70101"),
        raw("Dr.Test Beta", "beta.t@vitap.ac.in", "School of Computer Science and Engineering (SCOPE)",
            "Associate Professor Grade-2", "Machine Learning; Natural Language Processing (NLP)",
            sub="DDSE", emp="5.70102",
            Patents=[{"id": 1, "patent": "1. Smart irrigation controller, Patent Publication Number - 1"}]),
        raw("Dr. Test Gamma", "gamma.t@vitap.ac.in", "School of Advanced Science (SAS)",
            "Head, Dept. of Mathematics, Professor HAG", "Graph Theory, Number Theory",
            sub="Maths", emp="2.70103"),
        raw("Ms. Test Delta", "delta.t@vitap.ac.in", "School of Law (VSL)",
            "Assistant Professor", "Constitutional Law, Criminal Law", emp=70104, photo=False),
        raw("Dr. Test Epsilon", "epsilon.t@vitap.ac.in", "School of Social Science and Humanities (VISH)",
            "Assistant professor Sr Grade 2", "--", emp="9.7010"),
    ]


@pytest.fixture
def snapshot(raw_records):
    return {"source_page": "https://vitap.ac.in/allfaculty", "captured_at": "2026-10-17T00:00:00Z",
            "records": raw_records}


@pytest.fixture
def cleaned(snapshot):
    ext, _ = extractor.extract_all(snapshot)
    recs, report = cleaner.clean_records(ext, discovered=len(snapshot["records"]))
    return recs, report


@pytest.fixture
def df(cleaned):
    return storage.to_dataframe(cleaned[0])
