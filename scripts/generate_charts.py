"""Export the report/presentation charts as static PNG + an analysis summary.

    python scripts/generate_charts.py

Uses the same figure builders as the app (src/charts.py), so the report shows
exactly the numbers the app computes. PNG export needs `kaleido` (and a
Chrome/Chromium; set BROWSER_PATH if it is not found automatically).
Also writes outputs/analysis_summary.json with every number quoted in the
report.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import analytics, charts, config, storage, text_analytics  # noqa: E402
from src.recommender import FacultyRecommender  # noqa: E402


def main() -> int:
    config.ensure_dirs()
    df = storage.to_dataframe(storage.load_records())
    report = json.loads(config.QUALITY_REPORT.read_text(encoding="utf-8"))
    tm = text_analytics.topic_model(df, n_topics=10)
    G = text_analytics.cooccurrence_network(df, top_n=40, min_weight=2)
    sim = text_analytics.school_similarity(df)
    figs = {
        "school_bar": charts.school_bar(df),
        "department_sunburst": charts.department_sunburst(df),
        "rank_stacked": charts.rank_stacked(df),
        "availability_bar": charts.availability_bar(df),
        "availability_heatmap": charts.availability_heatmap(df),
        "completeness_box": charts.completeness_box(df),
        "phd_stacked": charts.phd_stacked(df),
        "research_output": charts.research_output_bars(df),
        "top_phrases": charts.phrase_bar(text_analytics.phrase_frequency(df, 20), "Top 20 specialisation phrases"),
        "network": charts.network_figure(G),
        "topic_mix": charts.topic_mix_heatmap(tm["school_mix"]),
        "school_similarity": charts.similarity_heatmap(sim),
        "k_scan": charts.k_scan_line(text_analytics.topic_k_scan(df)),
    }
    for name, fig in figs.items():
        fig.update_layout(paper_bgcolor="white")
        out = config.CHART_DIR / f"{name}.png"
        fig.write_image(str(out), width=1000, height=fig.layout.height or 420, scale=2)
        print("wrote", out.relative_to(ROOT))

    rec = FacultyRecommender().fit(df)
    examples = {}
    for q in ["machine learning for healthcare", "power electronics electric vehicles",
              "constitutional law", "thin film solar cells"]:
        examples[q] = [r.__dict__ for r in rec.recommend(q, k=5)]
    summary = {
        "summary": analytics.summary(df, report),
        "by_school": analytics.faculty_by_school(df).to_dict("records"),
        "by_department": analytics.faculty_by_department(df).to_dict("records"),
        "rank_counts": analytics.counts_by(df, "academic_rank").to_dict("records"),
        "grade_counts": analytics.counts_by(df, "grade").to_dict("records"),
        "rank_share_by_school": analytics.rank_share_by_school(df).to_dict("index"),
        "field_availability": analytics.field_availability(df).to_dict("records"),
        "completeness_by_school": analytics.completeness_by_school(df).reset_index().to_dict("records"),
        "research_output_by_school": analytics.research_output_by_school(df).reset_index().to_dict("records"),
        "phd_categories": analytics.phd_categories(df).to_dict("records"),
        "academic_links": analytics.academic_profile_links(df).to_dict("records"),
        "top_phrases": text_analytics.phrase_frequency(df, 25).to_dict("records"),
        "top_words": text_analytics.word_frequency(df, 25).to_dict("records"),
        "distinctive_terms": text_analytics.distinctive_terms(df, 10),
        "topics": tm["topics"],
        "topic_sizes": tm["assignments"]["topic_label"].value_counts().to_dict(),
        "topic_meta": {k: tm[k] for k in ("reconstruction_error", "n_documents", "n_terms")},
        "network": {"nodes": G.number_of_nodes(), "edges": G.number_of_edges(),
                    "top": text_analytics.network_summary(G).head(10).to_dict("records")},
        "school_similarity": sim.to_dict("index"),
        "recommendation_examples": examples,
        "quality": {k: report[k] for k in ("profiles_discovered", "profiles_processed",
                                           "duplicates_removed", "extraction_failures",
                                           "issue_counts", "status_counts")},
    }
    (config.OUTPUT_DIR / "analysis_summary.json").write_text(
        json.dumps(summary, indent=1, default=str), encoding="utf-8")
    print("wrote outputs/analysis_summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
