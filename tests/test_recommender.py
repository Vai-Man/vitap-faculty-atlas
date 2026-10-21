"""Recommendation logic: ranking, evidence terms, filters, edge cases."""
import pytest

from src.recommender import FacultyRecommender, patent_title


@pytest.fixture
def rec(df):
    return FacultyRecommender().fit(df)


def test_query_ranks_matching_faculty_first(rec):
    res = rec.recommend("constitutional law", k=3)
    assert res[0].name == "Ms. Test Delta"
    assert "constitutional law" in res[0].matched_terms
    assert 0 < res[0].score <= 1


def test_scores_descending_and_explained(rec):
    res = rec.recommend("machine learning", k=5)
    assert [r.score for r in res] == sorted([r.score for r in res], reverse=True)
    assert all(r.matched_terms for r in res)
    assert {r.school_code for r in res} == {"SCOPE"}


def test_coverage_rewards_matching_more_query_words(rec):
    res = rec.recommend("machine learning natural language processing", k=2)
    assert res[0].name == "Dr. Test Beta"
    assert res[0].coverage > res[1].coverage


def test_school_filter(rec):
    assert rec.recommend("machine learning", school="VSL") == []


def test_empty_and_unknown_queries(rec):
    assert rec.recommend("") == []
    assert rec.recommend("the and of") == []
    assert rec.recommend("qwertyzzz") == []


def test_similar_to_excludes_self(rec, df):
    fid = df.loc[df["name"] == "Dr. Test Alpha", "faculty_id"].item()
    sims = rec.similar_to(fid, k=3)
    assert sims and all(s.faculty_id != fid for s in sims)
    assert sims[0].name == "Dr.Test Beta" or sims[0].name == "Dr. Test Beta"
    assert rec.similar_to("VITAP-NOPE") == []


def test_patent_title():
    assert patent_title("1. Smart Hook, Patent Publication Number - 1") == "Smart Hook"
