"""Extraction of profile information from raw CMS records."""
from src import extractor


def test_parse_employee_id_float_and_padding():
    assert extractor.parse_employee_id(6.70009) == (6, "70009")
    assert extractor.parse_employee_id(1.7001) == (1, "70010")  # lost trailing zero restored
    assert extractor.parse_employee_id("11.70929") == (11, "70929")
    assert extractor.parse_employee_id(70709) == (None, "70709")
    assert extractor.parse_employee_id(None) == (None, None)


def test_photo_url_nested_and_string():
    nested = {"data": {"id": 3, "attributes": {"url": "https://x/y.avif"}}}
    assert extractor.photo_url(nested) == "https://x/y.avif"
    assert extractor.photo_url("https://x/z.jpg") == "https://x/z.jpg"
    assert extractor.photo_url({"data": None}) is None
    assert extractor.photo_url(None) is None


def test_profile_url_matches_site_pattern():
    url = extractor.build_profile_url("School of Law (VSL)", "a.b@vitap.ac.in")
    assert url == "https://vitap.ac.in/School%20of%20Law%20(VSL)/faculty/a.b"
    sbst = extractor.build_profile_url("School of Bio Sciences and Technology (SBST)", "q@vitap.ac.in")
    assert sbst == "https://vitap.ac.in/SBST/faculty/q"
    assert extractor.build_profile_url("School of Law (VSL)", None) is None


def test_extract_record_maps_fields_and_drops_phone(raw_records):
    rec = extractor.extract_record(raw_records[1])
    assert rec["name"] == "Dr.Test Beta"
    assert rec["school_raw"].endswith("(SCOPE)")
    assert rec["patents"] == ["1. Smart irrigation controller, Patent Publication Number - 1"]
    assert "Contact_No" not in rec and "contact_no" not in rec
    assert "9876543210" not in str(rec)
    assert rec["record_origin"] == "cms_api"
    assert rec["source_urls"][0] == "https://vitap.ac.in/allfaculty"


def test_extract_all_logs_failures(snapshot):
    snapshot["records"].append({"Name": ""})
    snapshot["records"].append("not a dict")
    recs, failures = extractor.extract_all(snapshot)
    assert len(recs) == 5
    assert len(failures) == 2


def test_unknown_fields_preserved(raw_records):
    raw = dict(raw_records[0], New_Field="kept")
    assert extractor.extract_record(raw)["extra_fields"] == {"New_Field": "kept"}
