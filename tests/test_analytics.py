"""Analytics calculations on the synthetic fixture (hand-checkable numbers)."""
import pandas as pd

from src import analytics


def test_summary_counts(df):
    s = analytics.summary(df, {"profiles_discovered": 6})
    assert s["profiles_discovered"] == 6
    assert s["profiles_processed"] == 5
    assert s["schools"] == 4
    assert s["with_photo"] == 4
    assert s["with_specialisation"] == 4
    assert s["with_patents"] == 1


def test_counts_by_school_sum_and_percent(df):
    d = analytics.faculty_by_school(df)
    assert d["count"].sum() == 5
    assert d.loc[d["school_code"] == "SCOPE", "count"].item() == 2
    assert abs(d["percent"].sum() - 100) < 0.5


def test_rank_crosstab(df):
    ct = analytics.rank_by_school(df)
    assert ct.loc["SAS", "Professor"] == 1
    assert ct.values.sum() == 5
    share = analytics.rank_share_by_school(df)
    assert (share.sum(axis=1).round() == 100).all()


def test_field_availability(df):
    fa = analytics.field_availability(df).set_index("field")
    assert fa.loc["photograph_url", "percent"] == 80.0
    assert fa.loc["specialisation", "count"] == 4
    assert fa.loc["patents", "count"] == 1


def test_filled_handles_lists_nan_and_empty():
    s = pd.Series([None, float("nan"), "", [], "x", ["a"]])
    assert analytics._filled(s).tolist() == [False, False, False, False, True, True]


def test_research_output_by_school(df):
    r = analytics.research_output_by_school(df)
    assert r.loc["SCOPE", "patents_listed"] == 1
    assert r.loc["SCOPE", "pct_with_patent"] == 50.0


def test_departments_only_where_published(df):
    d = analytics.faculty_by_department(df)
    assert set(d["department"]) == {"Artificial Intelligence and Machine Learning",
                                    "Data Science and Engineering", "Mathematics"}


def test_leadership(df):
    lead = analytics.leadership(df)
    assert len(lead) == 1 and lead.iloc[0]["admin_role_type"] == "Head of Department"
