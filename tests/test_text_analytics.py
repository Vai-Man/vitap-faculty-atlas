"""Text preprocessing, phrase normalisation and text analytics."""
from src import text_analytics as T


def test_tokenize_stopwords_abbrev_singular():
    assert T.tokenize("Research in Wireless Sensor Networks and IoT") == \
        ["wireless", "sensor", "network", "internet", "thing"]
    assert T.tokenize("Physics & Mathematics analysis") == ["physics", "mathematics", "analysis"]
    assert T.tokenize(None) == []


def test_singularise_keeps_ics_and_sis():
    assert T.singularise("networks") == "network"
    assert T.singularise("technologies") == "technology"
    for w in ["physics", "analysis", "process", "electronics"]:
        assert T.singularise(w) == w


def test_normalise_phrase():
    assert T.normalise_phrase("Machine Learning (ML)") == "machine learning"
    assert T.normalise_phrase("IoT") == "internet of things"
    assert T.normalise_phrase("Internet of Things") == "internet of things"
    assert T.normalise_phrase("Wireless Sensor Networks") == "wireless sensor network"
    assert T.normalise_phrase("&") is None


def test_analyzer_does_not_cross_list_items():
    feats = T.analyzer("Deep Learning, Healthcare Analytics")
    assert "deep learning" in feats and "healthcare analytics" in feats
    assert "learning healthcare" not in feats


def test_phrase_frequency(df):
    pf = T.phrase_frequency(df, 5)
    top = dict(zip(pf["phrase"], pf["faculty"]))
    assert top["machine learning"] == 2
    scope = T.phrase_frequency(df, 10, school="VSL")
    assert set(scope["phrase"]) == {"constitutional law", "criminal law"}


def test_distinctive_terms_per_school(df):
    terms = T.distinctive_terms(df, 5)
    assert "law" in [t for t, _ in terms["VSL"]]
    assert set(terms) == {"SCOPE", "SAS", "VSL"}  # VISH has no specialisation text


def test_topic_model_shapes(df):
    tm = T.topic_model(df, n_topics=2)
    assert len(tm["topics"]) == 2
    assert tm["n_documents"] == 4
    assert set(tm["assignments"]["faculty_id"]) <= set(df["faculty_id"])


def test_cooccurrence_network(df):
    G = T.cooccurrence_network(df, top_n=20, min_weight=1)
    assert G.has_edge("constitutional law", "criminal law")
    assert G.nodes["machine learning"]["faculty"] == 2
    summ = T.network_summary(G)
    assert {"phrase", "connections", "degree_centrality"} <= set(summ.columns)


def test_school_similarity_symmetric(df):
    S = T.school_similarity(df)
    assert (S.values.round(3) == S.values.T.round(3)).all()
    assert all(abs(S.loc[s, s] - 1) < 1e-6 for s in S.index)
