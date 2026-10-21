"""Faculty discovery: TF-IDF + cosine similarity over research text.

Each faculty member becomes a document made of their published
specialisation phrases (weighted x3, because they are the person's own
statement of interests), their department name and the titles of any
patents they list. A free-text query is vectorised the same way and
faculty are ranked by cosine similarity.

Ranking = cosine similarity x (0.5 + 0.5 x query coverage), where coverage
is the fraction of the query's words found in the profile, so a profile that
matches more of the query beats a very short one that repeats a single word.
Every result carries the query terms that actually matched, so a user can
see *why* someone was suggested. A high score means textual overlap with
the query; it says nothing about research quality or impact.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import partial
from typing import Any

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

from .text_analytics import analyzer, preprocess

SPEC_WEIGHT = 3


def patent_title(entry: str) -> str:
    """'1. Boost converter ..., Patent Publication Number - ...' -> 'Boost converter ...'"""
    t = re.sub(r"^\s*\d+[.)]\s*", "", entry or "")
    return re.split(r",\s*(?:patent|application|publication|grant)", t, flags=re.I)[0]


def _s(value: Any) -> str:
    """String or empty string (handles None / NaN from pandas)."""
    return value if isinstance(value, str) else ""


def build_document(row: pd.Series | dict[str, Any]) -> str:
    spec = _s(row.get("specialisation_text"))
    dept = _s(row.get("department"))
    pats_raw = row.get("patents")
    pats = " . ".join(patent_title(p) for p in (pats_raw if isinstance(pats_raw, list) else []))
    return " . ".join([spec] * SPEC_WEIGHT + [dept, pats])


@dataclass
class Recommendation:
    faculty_id: str
    name: str
    school_code: str | None
    department: str | None
    designation: str | None
    score: float
    matched_terms: list[str]
    cosine: float = 0.0
    coverage: float = 1.0


class FacultyRecommender:
    """Fit once on the cleaned DataFrame, then query repeatedly."""

    def __init__(self, ngram_range: tuple[int, int] = (1, 2)):
        self.vectorizer = TfidfVectorizer(
            analyzer=partial(analyzer, ngram_range=ngram_range), sublinear_tf=True)
        self.df: pd.DataFrame | None = None
        self.X = None
        self.terms: np.ndarray | None = None

    def fit(self, df: pd.DataFrame) -> "FacultyRecommender":
        self.df = df.reset_index(drop=True)
        docs = self.df.apply(build_document, axis=1)
        self.X = self.vectorizer.fit_transform(docs.values)
        self.terms = np.array(self.vectorizer.get_feature_names_out())
        return self

    def _rank(self, qvec, k: int, school: str | None, exclude: str | None,
              min_score: float, use_coverage: bool) -> list[Recommendation]:
        """Score = cosine x (0.5 + 0.5 x coverage) when ``use_coverage``.

        ``coverage`` is the share of the query's single-word terms that the
        profile also contains. Plain cosine favours very short profiles that
        repeat one query word; the coverage factor rewards profiles that
        match *more of* the query. Both parts are reported in the result.
        """
        assert self.df is not None and self.X is not None and self.terms is not None
        cos = linear_kernel(qvec, self.X).ravel()  # rows are L2-normalised
        q_idx = set(qvec.nonzero()[1])
        q_uni = {j for j in q_idx if " " not in self.terms[j]}
        cand = np.flatnonzero(cos > min_score)
        scored = []
        for i in cand:
            row = self.df.iloc[i]
            if exclude and row["faculty_id"] == exclude:
                continue
            if school and row["school_code"] != school:
                continue
            doc_idx = set(self.X[i].nonzero()[1])
            cov = len(q_uni & doc_idx) / len(q_uni) if q_uni else 1.0
            score = cos[i] * (0.5 + 0.5 * cov) if use_coverage else cos[i]
            scored.append((score, cos[i], cov, i))
        scored.sort(reverse=True)
        out: list[Recommendation] = []
        for score, c, cov, i in scored[:k]:
            row = self.df.iloc[i]
            doc = self.X[i]
            shared = [j for j in doc.nonzero()[1] if j in q_idx]
            shared.sort(key=lambda j: doc[0, j] * qvec[0, j], reverse=True)
            out.append(Recommendation(row["faculty_id"], row["name"], row["school_code"],
                                      row["department"], row["designation"],
                                      round(float(score), 4),
                                      [str(self.terms[j]) for j in shared[:6]],
                                      round(float(c), 4), round(float(cov), 3)))
        return out

    def recommend(self, query: str, k: int = 10, school: str | None = None,
                  min_score: float = 0.0) -> list[Recommendation]:
        """Rank faculty for a free-text research query. Empty or
        out-of-vocabulary queries return an empty list."""
        if not query or not preprocess(query):
            return []
        q = self.vectorizer.transform([query])
        if q.nnz == 0:
            return []
        return self._rank(q, k, school, None, min_score, use_coverage=True)

    def similar_to(self, faculty_id: str, k: int = 5) -> list[Recommendation]:
        """Faculty whose research text is most similar to ``faculty_id``."""
        assert self.df is not None
        hits = self.df.index[self.df["faculty_id"] == faculty_id]
        if len(hits) == 0:
            return []
        q = self.X[hits[0]]
        if q.nnz == 0:
            return []
        return self._rank(q, k, None, faculty_id, 0.0, use_coverage=False)
