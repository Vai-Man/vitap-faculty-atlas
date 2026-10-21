"""Data cleaning, normalisation, missing fields and duplicate detection."""
from src import cleaner


def test_clean_text_whitespace_and_placeholders():
    assert cleaner.clean_text("  Machine   Learning \n") == "Machine Learning"
    for p in ["", "--", "NA", "n/a", "  -  ", None]:
        assert cleaner.clean_text(p) is None


def test_clean_name_fixes_honorific_spacing():
    assert cleaner.clean_name("Dr.Arunkumar Sivakumar") == ("Dr. Arunkumar Sivakumar", "Dr.")
    assert cleaner.clean_name("Dr Jane Roe") == ("Dr. Jane Roe", "Dr.")
    assert cleaner.clean_name("Ms. A B") == ("Ms. A B", "Ms.")


def test_split_list_dedupes_case_insensitively():
    assert cleaner.split_list("ML, ml; Deep Learning,  , Vision.") == ["ML", "Deep Learning", "Vision"]


def test_parse_school_and_department_normalisation():
    assert cleaner.parse_school("School of Law (VSL)") == ("VSL", "School of Law")
    assert cleaner.normalise_department("Maths", "SAS", "School of Advanced Science") == ("Mathematics", "department")
    assert cleaner.normalise_department("DAIML", "SCOPE", "x")[0] == "Artificial Intelligence and Machine Learning"
    assert cleaner.normalise_department(None, "VSL", "School of Law") == ("School of Law", "school")


def test_parse_designation_variants():
    d = cleaner.parse_designation("Dean, SAS, Professor HAG")
    assert (d["admin_role"], d["admin_role_type"], d["academic_rank"], d["grade"]) == \
        ("Dean, SAS", "Dean", "Professor", "HAG")
    assert cleaner.parse_designation("Assistant Professor Sr Grade 1")["designation"] == \
        "Assistant Professor Senior Grade 1"
    assert cleaner.parse_designation("Assistant Professor Grade-2")["grade"] == "Grade 2"
    assert cleaner.parse_designation("Professor Grade1")["grade"] == "Grade 1"
    assert cleaner.parse_designation("Assistant Professor Grade I")["grade"] == "Grade 1"
    h = cleaner.parse_designation("Head, Dept. of Artificial Intelligence and Machine Learning. Professor Grade 2")
    assert h["academic_rank"] == "Professor" and h["admin_role_type"] == "Head of Department"
    vc = cleaner.parse_designation("Vice Chancellor (I/c)")
    assert vc["academic_rank"] == "Not stated" and vc["admin_role_type"] == "Vice Chancellor"
    assert cleaner.parse_designation("Emeritus professor")["academic_rank"] == "Emeritus Professor"


def test_classify_phd():
    assert cleaner.classify_phd("Ph.D, IIT Bombay") == "IIT"
    assert cleaner.classify_phd("PhD, National Institute of Technology Warangal") == "NIT"
    assert cleaner.classify_phd("Indian Institute of Science, Bangalore") == "IISc"
    assert cleaner.classify_phd("IISER Pune") == "IISER"
    assert cleaner.classify_phd("Ph.D, IIIT Hyderabad") == "IIIT"
    assert cleaner.classify_phd("PhD, University of Bristol, UK") == "Foreign"
    assert cleaner.classify_phd("Pursuing PhD") == "Pursuing"
    assert cleaner.classify_phd(None) == "Not stated"
    assert cleaner.classify_phd("Anna University") == "Other / unclassified"


def test_canonical_links():
    assert cleaner.canonical_orcid("https://orcid.org/my-orcid?orcid=0000-0003-4575-6437")[0] == \
        "https://orcid.org/0000-0003-4575-6437"
    assert cleaner.canonical_scholar("wTFkdAEAAAAJ") == \
        ("https://scholar.google.com/citations?user=wTFkdAEAAAAJ", True)
    assert cleaner.canonical_scholar("https://scholar.google.com/schhp?hl=en")[1] is False
    assert cleaner.canonical_scopus("57215589253")[0].endswith("authorId=57215589253")
    assert cleaner.normalise_url("www.linkedin.com/in/x") == "https://www.linkedin.com/in/x"
    assert cleaner.normalise_url("not a url") is None


def test_office_building():
    assert cleaner.parse_office_building("145, AB-1") == "AB-1"
    assert cleaner.parse_office_building("124-J, AB2") == "AB-2"
    assert cleaner.parse_office_building("626 - C, Central Block") == "CB"
    assert cleaner.parse_office_building("Some company, Mangalore") is None


def test_missing_fields_flagged_not_invented(cleaned):
    recs, report = cleaned
    eps = next(r for r in recs if "Epsilon" in r["name"])
    assert eps["specialisation"] == []
    assert "missing_specialisation" in eps["quality_issues"]
    delta = next(r for r in recs if "Delta" in r["name"])
    assert delta["photograph_url"] is None and "missing_photo" in delta["quality_issues"]
    assert all(r["publications"] is None and r["experience"] is None for r in recs)
    assert report["fields_not_published"] == ["publications", "experience"]


def test_deduplicate_keeps_most_complete(cleaned):
    recs, _ = cleaned
    a = dict(recs[0], completeness=0.2, quality_issues=[])
    b = dict(recs[0], completeness=0.9, quality_issues=[], name="Dr. Test Alpha (copy)")
    kept, dups = cleaner.deduplicate([a, b, dict(recs[1], quality_issues=[])])
    assert len(kept) == 2 and len(dups) == 1
    assert dups[0]["kept"] == "Dr. Test Alpha (copy)"


def test_dedupe_key_without_email():
    assert cleaner.dedupe_key({"official_email": None, "name": "Dr. A. Kumar"}) == \
        cleaner.dedupe_key({"official_email": None, "name": "A Kumar"})


def test_ids_unique_and_status_values(cleaned):
    recs, report = cleaned
    ids = [r["faculty_id"] for r in recs]
    assert len(set(ids)) == len(ids)
    assert "VITAP-70101" in ids
    assert {r["data_quality_status"] for r in recs} <= {"complete", "partial", "minimal"}
    assert report["profiles_discovered"] == report["profiles_processed"] == 5
