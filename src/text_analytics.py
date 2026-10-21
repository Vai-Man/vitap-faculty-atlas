"""Text analytics over faculty research specialisations.

Input text: the ``specialisation`` lists faculty publish on the directory
(median ~3-4 short phrases per person). The corpus is small (about 600
short documents), so methods were chosen to suit short, keyword-like text:

* phrase frequency on the author-supplied phrases (they are already
  keyphrases, so no statistical keyphrase extractor is needed);
* word frequency after preprocessing;
* TF-IDF to find terms that *distinguish* each school;
* NMF topic modelling on TF-IDF (more stable than LDA on short texts);
* a phrase co-occurrence network (two phrases are linked when the same
  person lists both), analysed with degree centrality.
"""
from __future__ import annotations

import re
from collections import Counter
from itertools import combinations
from typing import Any

import numpy as np
import pandas as pd
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer

DOMAIN_STOPWORDS = {
    "research", "area", "areas", "application", "applications", "based", "using",
    "etc", "related", "various", "field", "fields", "study", "studies", "including",
    "interest", "interests", "specialization", "specialisation", "topics", "use",
    "new", "advanced", "general", "basic", "techniques", "technique", "methods",
}
STOPWORDS = frozenset(ENGLISH_STOP_WORDS) | DOMAIN_STOPWORDS

# Common abbreviations expanded so 'ML' and 'Machine Learning' count together.
ABBREVIATIONS = {
    "ai": "artificial intelligence",
    "ml": "machine learning",
    "dl": "deep learning",
    "nlp": "natural language processing",
    "iot": "internet of things",
    "cv": "computer vision",
    "vlsi": "vlsi",
}
# Display forms for phrases whose singular reads oddly.
PHRASE_CANON = {"internet of thing": "internet of things"}
_KEEP_S = ("ss", "is", "us", "ics", "ous", "sis", "ys")


def singularise(word: str) -> str:
    """Very light plural stripping: 'networks' -> 'network'; keeps
    'physics', 'analysis', 'process', 'mathematics'."""
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith(_KEEP_S):
        return word[:-1]
    return word


def tokenize(text: str | None) -> list[str]:
    """Lower-case, split on non-letters, drop stop words, singularise."""
    if not text:
        return []
    text = text.lower().replace("&", " and ")
    toks = re.findall(r"[a-z][a-z0-9+#-]*", text)
    out = []
    for t in toks:
        t = t.strip("-")
        words = ABBREVIATIONS[t].split() if t in ABBREVIATIONS else [t]
        for w in words:
            if len(w) < 2 or w in STOPWORDS:
                continue
            out.append(singularise(w))
    return out


def analyzer(text: str | None, ngram_range: tuple[int, int] = (1, 2)) -> list[str]:
    """Phrase-aware n-grams for TF-IDF.

    Specialisations are comma/semicolon separated lists, so n-grams are built
    *within* each list item only; otherwise 'Deep Learning, Healthcare' would
    produce the meaningless bigram 'learning healthcare'.
    """
    if not text:
        return []
    lo, hi = ngram_range
    feats: list[str] = []
    for seg in re.split(r"[,;.\n|/()]+", text):
        toks = tokenize(seg)
        for n in range(lo, hi + 1):
            feats.extend(" ".join(toks[i:i + n]) for i in range(len(toks) - n + 1))
    return feats


def preprocess(text: str | None) -> str:
    """Tokenise and re-join (used as the TF-IDF preprocessor)."""
    return " ".join(tokenize(text))


def normalise_phrase(phrase: str) -> str | None:
    """Canonical form of a specialisation phrase for counting.

    'Machine Learning (ML)' -> 'machine learning'; 'IoT' -> 'internet of things';
    'Wireless Sensor Networks' -> 'wireless sensor network'.
    """
    p = phrase.lower().replace("&", " and ")
    p = re.sub(r"\([^)]*\)", " ", p)           # drop parenthetical abbreviations
    p = re.sub(r"[^a-z0-9+#\- ]", " ", p)
    p = re.sub(r"\s+", " ", p).strip(" -")
    p = re.sub(r"^(and|in|of|the)\s+", "", p)
    if not p or len(p) < 2:
        return None
    if p in ABBREVIATIONS:
        p = ABBREVIATIONS[p]
    words = p.split()
    words[-1] = singularise(words[-1])
    p = " ".join(words)
    p = PHRASE_CANON.get(p, p)
    return None if p in STOPWORDS else p


def faculty_phrases(df: pd.DataFrame) -> pd.Series:
    """Series of per-faculty lists of normalised, de-duplicated phrases."""
    def norm(ps: list[str]) -> list[str]:
        seen, out = set(), []
        for x in ps or []:
            n = normalise_phrase(x)
            if n and n not in seen:
                seen.add(n)
                out.append(n)
        return out
    return df["specialisation"].apply(norm)


def phrase_frequency(df: pd.DataFrame, top_n: int = 25, school: str | None = None) -> pd.DataFrame:
    """Most frequently listed specialisation phrases (document frequency)."""
    sub = df if school is None else df[df["school_code"] == school]
    c = Counter(p for ps in faculty_phrases(sub) for p in ps)
    return pd.DataFrame(c.most_common(top_n), columns=["phrase", "faculty"])


def word_frequency(df: pd.DataFrame, top_n: int = 30) -> pd.DataFrame:
    c = Counter(t for txt in df["specialisation_text"].fillna("") for t in tokenize(txt))
    return pd.DataFrame(c.most_common(top_n), columns=["word", "count"])


def school_documents(df: pd.DataFrame) -> pd.Series:
    """One concatenated specialisation document per school."""
    docs = df.groupby("school_code")["specialisation_text"] \
        .apply(lambda s: " . ".join(t for t in s if isinstance(t, str)))
    return docs[docs.str.strip().str.len() > 0]  # schools with no text are skipped


def distinctive_terms(df: pd.DataFrame, top_n: int = 12) -> dict[str, list[tuple[str, float]]]:
    """TF-IDF across school documents: terms that characterise each school
    relative to the others (high term frequency, low spread across schools)."""
    docs = school_documents(df)
    vec = TfidfVectorizer(analyzer=analyzer, sublinear_tf=True)
    X = vec.fit_transform(docs.values)
    terms = np.array(vec.get_feature_names_out())
    out = {}
    for i, code in enumerate(docs.index):
        row = X[i].toarray().ravel()
        idx = row.argsort()[::-1][:top_n]
        out[code] = [(terms[j], round(float(row[j]), 4)) for j in idx if row[j] > 0]
    return out


def faculty_tfidf(df: pd.DataFrame, min_df: int = 2):
    """TF-IDF matrix over faculty specialisation texts. Returns (vectorizer, X, mask)
    where ``mask`` marks rows that had any text."""
    texts = df["specialisation_text"].fillna("")
    mask = texts.str.len() > 0
    vec = TfidfVectorizer(analyzer=analyzer, min_df=min_df, sublinear_tf=True)
    X = vec.fit_transform(texts[mask].values)
    return vec, X, mask


def topic_model(df: pd.DataFrame, n_topics: int = 10, top_words: int = 8,
                random_state: int = 42) -> dict[str, Any]:
    """NMF topic model on faculty TF-IDF vectors.

    Returns topics (top words + weights), each faculty's dominant topic and
    the topic mix per school. NMF with ``nndsvda`` initialisation is
    deterministic for a fixed ``random_state``.
    """
    vec, X, mask = faculty_tfidf(df)
    n_topics = max(2, min(n_topics, X.shape[0] - 1, X.shape[1] - 1))
    model = NMF(n_components=n_topics, init="nndsvda", random_state=random_state, max_iter=600)
    W = model.fit_transform(X)
    H = model.components_
    terms = np.array(vec.get_feature_names_out())
    topics = []
    for k in range(n_topics):
        idx = H[k].argsort()[::-1][:top_words]
        top = list(terms[idx])
        bigram = next((t for t in top[:3] if " " in t), None)  # only if it ranks top-3
        short = bigram or " / ".join(top[:2])
        topics.append({"topic": k, "label": f"T{k}: {short}",
                       "words": [(terms[j], round(float(H[k, j]), 3)) for j in idx]})
    dom = W.argmax(axis=1)
    strength = W.max(axis=1)
    assign = pd.DataFrame({"faculty_id": df.loc[mask, "faculty_id"].values,
                           "school_code": df.loc[mask, "school_code"].values,
                           "topic": dom, "weight": strength.round(4)})
    assign.loc[assign["weight"] == 0, "topic"] = -1  # no topic signal
    labels = {t["topic"]: t["label"] for t in topics}
    labels[-1] = "(no dominant topic)"
    assign["topic_label"] = assign["topic"].map(labels)
    mix = pd.crosstab(assign["school_code"], assign["topic_label"])
    return {"topics": topics, "assignments": assign, "school_mix": mix,
            "reconstruction_error": round(float(model.reconstruction_err_), 4),
            "n_documents": int(X.shape[0]), "n_terms": int(X.shape[1])}


def topic_k_scan(df: pd.DataFrame, ks: range = range(4, 17, 2)) -> pd.DataFrame:
    """Reconstruction error for several topic counts (elbow inspection)."""
    _, X, _ = faculty_tfidf(df)
    rows = []
    for k in ks:
        m = NMF(n_components=k, init="nndsvda", random_state=42, max_iter=600).fit(X)
        rows.append({"k": k, "reconstruction_error": round(float(m.reconstruction_err_), 4)})
    return pd.DataFrame(rows)


def cooccurrence_network(df: pd.DataFrame, top_n: int = 40, min_weight: int = 2):
    """Phrase co-occurrence graph over the ``top_n`` most common phrases.

    Nodes: phrases (attribute ``faculty`` = how many list it). Edges: number
    of faculty who list both phrases (kept when >= ``min_weight``).
    Returns a networkx Graph with ``degree_centrality`` node attributes.
    """
    import networkx as nx

    phrases = faculty_phrases(df)
    freq = Counter(p for ps in phrases for p in ps)
    keep = {p for p, _ in freq.most_common(top_n)}
    pairs: Counter = Counter()
    for ps in phrases:
        kept = sorted(set(ps) & keep)
        pairs.update(combinations(kept, 2))
    G = nx.Graph()
    for p in keep:
        G.add_node(p, faculty=freq[p])
    for (a, b), w in pairs.items():
        if w >= min_weight:
            G.add_edge(a, b, weight=w)
    cent = nx.degree_centrality(G)
    nx.set_node_attributes(G, cent, "degree_centrality")
    return G


def network_summary(G) -> pd.DataFrame:
    rows = [{"phrase": n, "faculty": d["faculty"], "connections": G.degree(n),
             "weighted_degree": G.degree(n, weight="weight"),
             "degree_centrality": round(d["degree_centrality"], 3)}
            for n, d in G.nodes(data=True)]
    return pd.DataFrame(rows).sort_values(["weighted_degree", "faculty"], ascending=False) \
        .reset_index(drop=True)


def school_similarity(df: pd.DataFrame) -> pd.DataFrame:
    """Cosine similarity between school-level TF-IDF documents (overlap of
    research vocabulary between schools)."""
    from sklearn.metrics.pairwise import cosine_similarity

    docs = school_documents(df)
    vec = TfidfVectorizer(analyzer=analyzer, sublinear_tf=True)
    X = vec.fit_transform(docs.values)
    S = cosine_similarity(X)
    return pd.DataFrame(S.round(3), index=docs.index, columns=docs.index)
