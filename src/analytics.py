"""Descriptive analytics over the cleaned faculty dataset.

Every function takes the cleaned DataFrame (``storage.to_dataframe``) and
returns a small DataFrame or dict, so the same numbers feed the Streamlit
charts, the static report charts and the unit tests.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from . import config

FIELD_LABELS = {
    "photograph_url": "Photo",
    "designation": "Designation",
    "official_email": "Email",
    "office_location": "Office",
    "specialisation": "Specialisation",
    "education_ug": "UG degree",
    "education_pg": "PG degree",
    "education_phd": "PhD",
    "google_scholar": "Google Scholar",
    "orcid": "ORCID",
    "scopus": "Scopus",
    "linkedin": "LinkedIn",
    "researchgate": "ResearchGate",
    "vidwan": "Vidwan/IRINS",
    "dblp": "DBLP",
    "personal_website": "Website",
    "professional_memberships": "Memberships",
    "patents": "Patents",
    "projects": "Projects",
    "awards": "Awards",
}


def _filled(series: pd.Series) -> pd.Series:
    """Boolean mask: value present (not None/NaN/empty string/empty list)."""
    def ok(v: Any) -> bool:
        if v is None:
            return False
        if isinstance(v, float) and pd.isna(v):
            return False
        if isinstance(v, (list, tuple, dict, str)) and len(v) == 0:
            return False
        return True
    return series.apply(ok)


def summary(df: pd.DataFrame, report: dict[str, Any] | None = None) -> dict[str, Any]:
    """Headline numbers for the home dashboard."""
    report = report or {}
    return {
        "profiles_discovered": report.get("profiles_discovered", len(df)),
        "profiles_processed": len(df),
        "schools": int(df["school_code"].nunique()),
        "departments": int(df.loc[df["department_level"] == "department", "department"].nunique()),
        "with_photo": int(_filled(df["photograph_url"]).sum()),
        "with_specialisation": int(_filled(df["specialisation"]).sum()),
        "with_patents": int((df["n_patents"] > 0).sum()),
        "with_projects": int((df["n_projects"] > 0).sum()),
        "with_awards": int((df["n_awards"] > 0).sum()),
        "mean_completeness": round(float(df["completeness"].mean()), 3),
        "distinct_phrases": int(len({p.lower() for ps in df["specialisation"] for p in ps})),
    }


def counts_by(df: pd.DataFrame, col: str, order: list[str] | None = None) -> pd.DataFrame:
    """Value counts of ``col`` as a tidy frame with count and percent."""
    s = df[col].fillna("Not stated").value_counts()
    if order:
        s = s.reindex([o for o in order if o in s.index] + [i for i in s.index if i not in order])
    out = s.rename_axis(col).reset_index(name="count")
    out["percent"] = (100 * out["count"] / out["count"].sum()).round(1)
    return out


def faculty_by_school(df: pd.DataFrame) -> pd.DataFrame:
    out = counts_by(df, "school_code")
    out["school"] = out["school_code"].map(config.SCHOOLS)
    return out


def faculty_by_department(df: pd.DataFrame) -> pd.DataFrame:
    """Department-level counts (only where the site gives a sub-department)."""
    sub = df[df["department_level"] == "department"]
    return (sub.groupby(["school_code", "department"]).size()
            .reset_index(name="count").sort_values("count", ascending=False))


def rank_by_school(df: pd.DataFrame) -> pd.DataFrame:
    """Crosstab school x academic rank (counts)."""
    ct = pd.crosstab(df["school_code"], df["academic_rank"])
    cols = [r for r in config.RANK_ORDER if r in ct.columns]
    return ct[cols]


def rank_share_by_school(df: pd.DataFrame) -> pd.DataFrame:
    ct = rank_by_school(df)
    return (100 * ct.div(ct.sum(axis=1), axis=0)).round(1)


def field_availability(df: pd.DataFrame, fields: list[str] | None = None) -> pd.DataFrame:
    """Percent of profiles with each field filled."""
    fields = fields or list(FIELD_LABELS)
    rows = []
    for f in fields:
        if f in df.columns:
            n = int(_filled(df[f]).sum())
            rows.append({"field": f, "label": FIELD_LABELS.get(f, f), "count": n,
                         "percent": round(100 * n / max(len(df), 1), 1)})
    return pd.DataFrame(rows).sort_values("percent", ascending=False).reset_index(drop=True)


def availability_by_school(df: pd.DataFrame, fields: list[str] | None = None) -> pd.DataFrame:
    """Matrix school x field -> percent filled (heatmap input)."""
    fields = fields or list(FIELD_LABELS)
    data = {}
    for code, grp in df.groupby("school_code"):
        data[code] = {FIELD_LABELS.get(f, f): round(100 * _filled(grp[f]).mean(), 1)
                      for f in fields if f in grp.columns}
    return pd.DataFrame(data).T


def completeness_by_school(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("school_code")["completeness"]
    out = pd.DataFrame({"faculty": g.size(), "mean_completeness": g.mean().round(3),
                        "median_completeness": g.median().round(3)})
    status = pd.crosstab(df["school_code"], df["data_quality_status"])
    return out.join(status).sort_values("mean_completeness", ascending=False)


def research_output_by_school(df: pd.DataFrame) -> pd.DataFrame:
    """Self-reported patents / projects / awards listed on profiles, per school.

    These are counts of *entries listed on the website*, not verified
    research output, and most profiles list none.
    """
    g = df.groupby("school_code")
    out = pd.DataFrame({
        "faculty": g.size(),
        "patents_listed": g["n_patents"].sum(),
        "projects_listed": g["n_projects"].sum(),
        "awards_listed": g["n_awards"].sum(),
        "pct_with_patent": (100 * g["n_patents"].apply(lambda s: (s > 0).mean())).round(1),
        "pct_with_project": (100 * g["n_projects"].apply(lambda s: (s > 0).mean())).round(1),
        "pct_with_award": (100 * g["n_awards"].apply(lambda s: (s > 0).mean())).round(1),
    })
    return out.sort_values("faculty", ascending=False)


def phd_categories(df: pd.DataFrame, by_school: bool = False) -> pd.DataFrame:
    if by_school:
        return pd.crosstab(df["school_code"], df["phd_institution_category"])
    return counts_by(df, "phd_institution_category")


def academic_profile_links(df: pd.DataFrame) -> pd.DataFrame:
    """How many academic identity links each profile lists (0-6)."""
    cols = ["google_scholar", "orcid", "scopus", "researchgate", "vidwan", "dblp"]
    n = sum(_filled(df[c]).astype(int) for c in cols)
    return n.value_counts().sort_index().rename_axis("links").reset_index(name="faculty")


def leadership(df: pd.DataFrame) -> pd.DataFrame:
    sub = df[df["admin_role"].notna()]
    return sub[["name", "admin_role", "admin_role_type", "academic_rank", "school_code"]] \
        .reset_index(drop=True)
