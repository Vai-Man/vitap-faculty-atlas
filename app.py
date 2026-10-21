"""VITbutAP Faculty Atlas: Streamlit application.

Run from the project folder:

    streamlit run app.py

Pages: Overview · Directory · Faculty profile · Department analytics ·
Research & text analytics · Faculty discovery · Data & methodology.
All numbers shown are computed live from data/faculty.json.
"""
from __future__ import annotations

import base64
import html
import json
import math
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src import analytics, charts, config, storage, text_analytics  # noqa: E402
from src.recommender import FacultyRecommender  # noqa: E402

st.set_page_config(page_title="VITbutAP Faculty Atlas", page_icon="🎓", layout="wide",
                   initial_sidebar_state="expanded")

PAGES = ["Overview", "Directory", "Faculty profile", "Department analytics",
         "Research & text analytics", "Faculty discovery", "Data & methodology"]
PAGE_SIZE = 24

# ------------------------------------------------------------------ dark mode state
if "dark_mode" not in st.session_state:
    st.session_state["dark_mode"] = False

_LIGHT_VARS = """
:root { --ink:#0b0b0b; --ink2:#52514e; --muted:#898781; --line:#e1e0d9;
        --surface:#ffffff; --plane:#f9f9f7; --accent:#1c5cab; --accent-soft:#e8f0fb;
        --note-bg:#f4f8fd; --note-border:#86b6ef; --chip-grey-bg:#f0efec; --match-bg:#f0efec;
        --card-shadow:rgba(13,54,107,.10); }
[data-testid="stAppViewContainer"] { background: #ffffff; }
[data-testid="stSidebar"] { background: #f4f6f9; }
"""

_DARK_VARS = """
:root { --ink:#e8e8e6; --ink2:#a8a8a4; --muted:#6b6b68; --line:#2e2e2c;
        --surface:#1e1e1c; --plane:#161614; --accent:#5b9ef0; --accent-soft:#1a2d4a;
        --note-bg:#1a2535; --note-border:#3a6ea8; --chip-grey-bg:#2a2a28; --match-bg:#2a2a28;
        --card-shadow:rgba(0,0,0,.35); }
[data-testid="stAppViewContainer"] { background: #121210; }
[data-testid="stSidebar"] { background: #1a1a18; }
"""

# ------------------------------------------------------------------ styling
_theme_vars = _DARK_VARS if st.session_state["dark_mode"] else _LIGHT_VARS
st.markdown(f"""
<style>
{_theme_vars}
.block-container {{ padding-top: 1.6rem; max-width: 1280px; }}
h1, h2, h3 {{ letter-spacing: -0.01em; }}
.hero {{ padding: 22px 26px; border-radius: 14px; background: linear-gradient(120deg,#0d366b 0%,#1c5cab 60%,#2a78d6 100%);
        color: #fff; margin-bottom: 18px; }}
.hero h1 {{ color:#fff; margin:0 0 4px 0; font-size: 2rem; }}
.hero p {{ color:#dbe8fa; margin:0; font-size: 0.98rem; }}
.kpi {{ border:1px solid var(--line); border-radius:12px; padding:14px 16px; background:var(--surface); height:100%; }}
.kpi .v {{ font-size:1.75rem; font-weight:650; color:var(--ink); line-height:1.1; }}
.kpi .l {{ font-size:0.82rem; color:var(--ink2); margin-top:4px; }}
.kpi .s {{ font-size:0.75rem; color:var(--muted); margin-top:2px; }}
.grid {{ display:grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap:14px; }}
.card {{ border:1px solid var(--line); border-radius:12px; padding:14px; background:var(--surface);
        display:flex; gap:12px; align-items:flex-start; transition: box-shadow .15s, border-color .15s; }}
.card:hover {{ box-shadow: 0 4px 14px var(--card-shadow); border-color:#b7d3f6; }}
.avatar {{ position:relative; flex:0 0 64px; width:64px; height:64px; border-radius:50%; overflow:hidden;
          display:flex; align-items:center; justify-content:center; font-weight:650; color:#fff; font-size:1.2rem; }}
.avatar .ph {{ position:absolute; inset:0; background-size:cover; background-position:center top; background-repeat:no-repeat; }}
.avatar.lg {{ flex-basis:150px; width:150px; height:150px; font-size:2.6rem; border-radius:16px; }}
.card .nm {{ font-weight:620; color:var(--ink); font-size:0.95rem; line-height:1.25; }}
.card .ds {{ color:var(--ink2); font-size:0.8rem; margin-top:2px; }}
.card .dp {{ color:var(--muted); font-size:0.76rem; margin-top:2px; }}
.card a.btn {{ display:inline-block; margin-top:8px; font-size:0.78rem; color:var(--accent); text-decoration:none; font-weight:600; }}
.chip {{ display:inline-block; padding:3px 10px; border-radius:999px; background:var(--accent-soft); color:var(--accent);
        font-size:0.78rem; margin:2px 4px 2px 0; }}
.chip.grey {{ background:var(--chip-grey-bg); color:var(--ink2); }}
.tag {{ display:inline-block; padding:2px 8px; border-radius:6px; font-size:0.72rem; font-weight:600; }}
.tag.complete {{ background:#e3f4e3; color:#006300; }} .tag.partial {{ background:#fff3d6; color:#7a5200; }}
.tag.minimal {{ background:#fbe3e3; color:#9b1c1c; }}
.note {{ border-left:3px solid var(--note-border); background:var(--note-bg); padding:10px 14px; border-radius:6px; color:var(--ink2);
        font-size:0.88rem; margin:6px 0 14px 0; }}
.match {{ font-family: ui-monospace, Menlo, Consolas, monospace; font-size:0.78rem; background:var(--match-bg);
         padding:1px 6px; border-radius:4px; margin-right:4px; color:var(--ink); }}
.src a {{ color:var(--accent); }}
.empty {{ text-align:center; padding:40px; color:var(--muted); border:1px dashed var(--line); border-radius:12px; }}
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------ data
@st.cache_data(show_spinner="Loading faculty dataset…")
def load_data() -> tuple[pd.DataFrame, dict, dict]:
    if not config.FACULTY_JSON.exists():
        return pd.DataFrame(), {}, {}
    df = storage.to_dataframe(storage.load_records())
    meta = storage.load_meta()
    report = json.loads(config.QUALITY_REPORT.read_text(encoding="utf-8")) \
        if config.QUALITY_REPORT.exists() else {}
    return df, meta, report


@st.cache_resource(show_spinner="Building the search index…")
def get_recommender(n: int) -> FacultyRecommender:  # n busts the cache when data changes
    df, _, _ = load_data()
    return FacultyRecommender().fit(df)


@st.cache_data(show_spinner="Fitting topic model…")
def get_topics(n: int, k: int):
    df, _, _ = load_data()
    return text_analytics.topic_model(df, n_topics=k)


@st.cache_data
def get_k_scan(n: int):
    df, _, _ = load_data()
    return text_analytics.topic_k_scan(df)


@st.cache_data
def local_photo_uri(fid: str) -> str | None:
    """data: URI for a locally cached photo (scripts/download_photos.py)."""
    for p in config.PHOTO_DIR.glob(f"{fid}.*"):
        mime = {".avif": "image/avif", ".png": "image/png", ".webp": "image/webp"}.get(
            p.suffix.lower(), "image/jpeg")
        return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()
    return None


df, META, REPORT = load_data()
if df.empty:
    st.error("No dataset found. Run `python scripts/run_pipeline.py` first, then reload.")
    st.stop()
N = len(df)
BY_ID = df.set_index("faculty_id")


# ------------------------------------------------------------------ helpers
def esc(x) -> str:
    return html.escape(str(x)) if x is not None and not (isinstance(x, float) and math.isnan(x)) else ""


def initials(name: str) -> str:
    parts = [p for p in (name or "").replace("Dr.", "").replace("Mr.", "").replace("Ms.", "").split() if p[:1].isalpha()]
    return "".join(p[0] for p in parts[:2]).upper() or "?"


def avatar_html(row, large: bool = False) -> str:
    """Initials disc with the official photo layered on top. If the photo
    cannot load (offline, blocked, missing) the empty-alt <img> renders
    nothing and the initials show through: a graceful fallback without JS."""
    color = charts.SCHOOL_COLORS.get(row["school_code"], "#898781")
    src = local_photo_uri(row["faculty_id"]) or row.get("photograph_url")
    # CSS background layer: if the URL fails it simply paints nothing (no
    # broken-image icon), leaving the initials underneath visible.
    photo = f'<div class="ph" style="background-image:url(&quot;{esc(src)}&quot;)"></div>' if src else ""
    cls = "avatar lg" if large else "avatar"
    return f'<div class="{cls}" style="background:{color}">{esc(initials(row["name"]))}{photo}</div>'


def kpi(value, label, sub="") -> str:
    return f'<div class="kpi"><div class="v">{value}</div><div class="l">{label}</div><div class="s">{sub}</div></div>'


def kpi_row(items) -> None:
    cols = st.columns(len(items))
    for c, it in zip(cols, items):
        c.markdown(kpi(*it), unsafe_allow_html=True)


def profile_link(fid: str) -> str:
    return f"?page=profile&fid={fid}"


def chips(items, grey=False) -> str:
    cls = "chip grey" if grey else "chip"
    return "".join(f'<span class="{cls}">{esc(i)}</span>' for i in items)


def plot(fig) -> None:
    st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})


# ------------------------------------------------------------------ navigation
qp = st.query_params
if "page" not in st.session_state:
    st.session_state["page"] = "Overview"
if qp.get("page") == "profile" and qp.get("fid") in BY_ID.index:
    st.session_state["page"] = "Faculty profile"
    st.session_state["profile_fid"] = qp.get("fid")
    st.query_params.clear()

with st.sidebar:
    st.markdown("### 🎓 VITbutAP Faculty Atlas")
    st.caption("CSE 4039 · Advanced Social, Text and Media Analytics Lab")
    page = st.radio("Navigate", PAGES, key="page", label_visibility="collapsed")
    st.divider()
    _dm = st.session_state["dark_mode"]
    _toggle_label = "☀️ Light mode" if _dm else "🌙 Dark mode"
    if st.button(_toggle_label, use_container_width=True):
        st.session_state["dark_mode"] = not _dm
        st.rerun()
    st.divider()
    st.caption(f"**{N}** faculty profiles · **{df['school_code'].nunique()}** schools")
    st.caption(f"Snapshot: {str(META.get('snapshot_captured_at', ''))[:10]}")
    st.caption("Source: [vitap.ac.in/allfaculty](https://vitap.ac.in/allfaculty)")
    st.caption("Team VITbutAP: Vaibhav Manihar · Udit Ray · Ajitesh Mohapatra")


# ================================================================== pages
def page_overview() -> None:
    s = analytics.summary(df, REPORT)
    st.markdown(f"""<div class="hero"><h1>VIT-AP Faculty Atlas</h1>
    <p>A searchable directory and analytics view of the {s['profiles_processed']} faculty profiles published on the
    official VIT-AP University website, built for CSE 4039 ATSMA Lab.</p></div>""", unsafe_allow_html=True)
    kpi_row([
        (s["profiles_discovered"], "Profiles discovered", "on vitap.ac.in/allfaculty"),
        (s["profiles_processed"], "Profiles processed", f"{REPORT.get('duplicates_removed', 0)} duplicates removed"),
        (s["schools"], "Schools", f"{s['departments']} named sub-departments"),
        (f"{100 * s['with_specialisation'] / N:.0f}%", "List a specialisation", f"{s['distinct_phrases']} distinct phrases"),
        (f"{100 * s['mean_completeness']:.0f}%", "Mean completeness", "across 12 tracked fields"),
    ])
    st.markdown('<div class="note">Counts describe the profiles the university publishes in its online directory on the '
                'snapshot date. They are not a verified headcount of the university workforce.</div>',
                unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1])
    with c1:
        plot(charts.school_bar(df))
    with c2:
        plot(charts.rank_stacked(df))
    c1, c2 = st.columns([1, 1])
    with c1:
        top = text_analytics.phrase_frequency(df, 12)
        plot(charts.phrase_bar(top, "Most listed research specialisations"))
    with c2:
        st.markdown("#### University leadership listed in the directory")
        lead = analytics.leadership(df)
        st.dataframe(lead.rename(columns={"name": "Name", "admin_role": "Role", "admin_role_type": "Type",
                                          "academic_rank": "Rank", "school_code": "School"}),
                     hide_index=True, use_container_width=True, height=440)


def filter_panel(data: pd.DataFrame) -> pd.DataFrame:
    c1, c2, c3, c4 = st.columns([2.2, 1.4, 1.6, 1.4])
    q = c1.text_input("Search by name", placeholder="e.g. Kumar", key="dir_q")
    schools = c2.multiselect("School", charts.SCHOOL_ORDER, key="dir_school",
                             format_func=lambda c: f"{c} · {config.SCHOOLS[c].replace('School of ', '')}")
    depts = sorted(data.loc[data["department_level"] == "department", "department"].dropna().unique())
    dept = c3.multiselect("Department", depts, key="dir_dept")
    ranks = c4.multiselect("Academic rank", [r for r in config.RANK_ORDER if r in set(data["academic_rank"])],
                           key="dir_rank")
    c5, c6, c7, c8 = st.columns([2.2, 1.4, 1.6, 1.4])
    phrases = text_analytics.phrase_frequency(data, 200)["phrase"].tolist()
    spec = c5.selectbox("Specialisation (normalised phrase)", ["(any)"] + phrases, key="dir_spec")
    kw = c6.text_input("Keyword in specialisation", placeholder="e.g. robotics", key="dir_kw")
    sort = c7.selectbox("Sort by", ["Directory order", "Name A–Z", "School", "Completeness (high→low)"], key="dir_sort")
    quality = c8.multiselect("Data quality", ["complete", "partial", "minimal"], key="dir_quality")

    out = data
    if q:
        out = out[out["name"].str.contains(q, case=False, na=False, regex=False)]
    if schools:
        out = out[out["school_code"].isin(schools)]
    if dept:
        out = out[out["department"].isin(dept)]
    if ranks:
        out = out[out["academic_rank"].isin(ranks)]
    if spec != "(any)":
        ph = text_analytics.faculty_phrases(out)
        out = out[ph.apply(lambda ps: spec in ps)]
    if kw:
        out = out[out["specialisation_text"].str.contains(kw, case=False, na=False, regex=False)]
    if quality:
        out = out[out["data_quality_status"].isin(quality)]
    if sort == "Name A–Z":
        out = out.assign(_k=out["name"].str.replace(r"^(Dr|Mr|Ms|Prof)\.\s*", "", regex=True)).sort_values("_k")
    elif sort == "School":
        out = out.sort_values(["school_code", "name"])
    elif sort.startswith("Completeness"):
        out = out.sort_values("completeness", ascending=False)
    return out


def page_directory() -> None:
    st.markdown("## Faculty directory")
    res = filter_panel(df)
    n = len(res)
    pages = max(1, math.ceil(n / PAGE_SIZE))
    c1, c2, c3 = st.columns([3, 1, 1])
    c1.markdown(f"**{n}** of {N} profiles match")
    pg = c2.number_input("Page", 1, pages, 1, key="dir_page") if pages > 1 else 1
    c3.download_button("⬇ Download results (CSV)", storage.flatten_for_csv(res).to_csv(index=False).encode("utf-8-sig"),
                       "vitap_faculty_filtered.csv", "text/csv", use_container_width=True)
    if n == 0:
        st.markdown('<div class="empty">No profiles match these filters. Try removing a filter or a shorter search term.</div>',
                    unsafe_allow_html=True)
        return
    chunk = res.iloc[(pg - 1) * PAGE_SIZE: pg * PAGE_SIZE]
    cards = []
    for _, r in chunk.iterrows():
        spec = ", ".join(r["specialisation"][:3]) if r["specialisation"] else "Specialisation not listed"
        dept = r["department"] if r["department_level"] == "department" \
            else str(r["school"]).replace("School of ", "")
        cards.append(f"""<div class="card">{avatar_html(r)}<div style="min-width:0">
          <div class="nm">{esc(r['name'])}</div><div class="ds">{esc(r['designation'])}</div>
          <div class="dp">{esc(dept)} · {esc(r['school_code'])}</div>
          <div class="dp" style="margin-top:6px">{esc(spec[:110])}{'…' if len(spec) > 110 else ''}</div>
          <a class="btn" href="{profile_link(r['faculty_id'])}" target="_self">View profile →</a></div></div>""")
    st.markdown(f'<div class="grid">{"".join(cards)}</div>', unsafe_allow_html=True)
    st.caption(f"Page {pg} of {pages}. Photos load from the official VIT-AP image store; initials appear if a photo is unavailable.")


def link_list(r) -> str:
    links = [("Official profile", r["profile_url"]), ("Google Scholar", r["google_scholar"]),
             ("ORCID", r["orcid"]), ("Scopus", r["scopus"]), ("ResearchGate", r["researchgate"]),
             ("Vidwan / IRINS", r["vidwan"]), ("DBLP", r["dblp"]), ("LinkedIn", r["linkedin"]),
             ("Website", r["personal_website"])]
    parts = [f'<a href="{esc(u)}" target="_blank" rel="noopener">{lbl} ↗</a>' for lbl, u in links
             if isinstance(u, str) and u]
    return " · ".join(parts) or "No external links published."


def page_profile() -> None:
    st.markdown("## Faculty profile")
    ids = df["faculty_id"].tolist()
    labels = {r.faculty_id: f"{r.name} · {r.school_code}" for r in df.itertuples()}
    cur = st.session_state.get("profile_fid", ids[0])
    fid = st.selectbox("Choose a faculty member", ids, index=ids.index(cur) if cur in ids else 0,
                       format_func=lambda i: labels[i])
    st.session_state["profile_fid"] = fid
    r = BY_ID.loc[fid].copy()
    r["faculty_id"] = fid

    c1, c2 = st.columns([1, 3])
    with c1:
        st.markdown(avatar_html(r, large=True), unsafe_allow_html=True)
        st.markdown(f'<div style="margin-top:10px"><span class="tag {r["data_quality_status"]}">'
                    f'{r["data_quality_status"].upper()}</span> &nbsp;completeness {100 * r["completeness"]:.0f}%</div>',
                    unsafe_allow_html=True)
        st.progress(float(r["completeness"]))
    with c2:
        st.markdown(f"### {esc(r['name'])}")
        role = f"<b>{esc(r['admin_role'])}</b> · " if isinstance(r["admin_role"], str) else ""
        st.markdown(f"{role}{esc(r['designation'])}<br>{esc(r['department'])} · {esc(r['school'])} ({esc(r['school_code'])})",
                    unsafe_allow_html=True)
        email = r["official_email"] if isinstance(r["official_email"], str) else None
        st.markdown(f"**Email:** {f'[{email}](mailto:{email})' if email else '_not published_'}  \n"
                    f"**Office:** {esc(r['office_location']) or '_not published_'}")
        st.markdown(f'<div class="src">{link_list(r)}</div>', unsafe_allow_html=True)
        st.markdown("**Research specialisation**")
        st.markdown(chips(r["specialisation"]) if r["specialisation"] else "_Not listed on the official profile._",
                    unsafe_allow_html=True)

    t1, t2, t3, t4 = st.tabs(["Education & memberships", f"Patents ({r['n_patents']}) · Projects ({r['n_projects']}) · Awards ({r['n_awards']})",
                              "Similar faculty", "Provenance"])
    with t1:
        for lbl, key in [("Undergraduate", "education_ug"), ("Postgraduate", "education_pg"),
                         ("Doctorate", "education_phd"), ("Other", "education_other")]:
            v = r[key]
            st.markdown(f"**{lbl}:** {esc(v) if isinstance(v, str) else '_not listed_'}")
        st.markdown(f"**PhD institution category (rule-based):** {r['phd_institution_category']}")
        st.markdown("**Professional memberships:** " + (chips(r["professional_memberships"], grey=True)
                    if r["professional_memberships"] else "_not listed_"), unsafe_allow_html=True)
    with t2:
        for title, key in [("Patents", "patents"), ("Funded projects", "projects"), ("Awards & recognitions", "awards")]:
            items = r[key]
            st.markdown(f"**{title}**")
            if items:
                for it in items:
                    st.markdown(f"- {esc(it)}")
            else:
                st.caption("None listed on the official profile.")
        st.caption("Publications and experience are not published in the directory data, so they are not shown.")
    with t3:
        sims = get_recommender(N).similar_to(fid, k=6)
        if not sims:
            st.info("No specialisation text on this profile, so similarity cannot be computed.")
        for s in sims:
            terms = "".join(f'<span class="match">{esc(t)}</span>' for t in s.matched_terms)
            st.markdown(f'<a href="{profile_link(s.faculty_id)}" target="_self"><b>{esc(s.name)}</b></a> · {esc(s.department)} '
                        f'· similarity {s.score:.2f}<br>{terms}', unsafe_allow_html=True)
        st.caption("Similarity = cosine similarity of TF-IDF vectors built from published specialisations. "
                   "It reflects shared vocabulary, not research quality or impact.")
    with t4:
        st.markdown("**Source URLs**")
        for u in r["source_urls"]:
            st.markdown(f"- [{u}]({u})")
        st.markdown(f"**Photo URL (official):** {esc(r['photograph_url']) or '_none_'}")
        st.markdown(f"**Captured:** {esc(r['last_verified'])} · **CMS last updated:** {esc(r['cms_updated_at']) or 'n/a'} "
                    f"· **Record origin:** {esc(r['record_origin'])} · **Raw designation:** {esc(r['designation_raw'])}")
        st.markdown("**Quality flags:** " + (chips(r["quality_issues"], grey=True) if r["quality_issues"] else "none"),
                    unsafe_allow_html=True)


def page_departments() -> None:
    st.markdown("## Department analytics")
    s = analytics.summary(df, REPORT)
    kpi_row([
        (s["profiles_processed"], "Profiles processed", f"of {s['profiles_discovered']} discovered"),
        (int((df["academic_rank"] == "Assistant Professor").sum()), "Assistant Professors",
         f"{100 * (df['academic_rank'] == 'Assistant Professor').mean():.0f}% of profiles"),
        (s["with_patents"], "Profiles listing patents", f"{df['n_patents'].sum()} patent entries"),
        (s["with_projects"], "Profiles listing projects", f"{df['n_projects'].sum()} project entries"),
    ])
    t1, t2, t3, t4 = st.tabs(["Structure", "Ranks & qualifications", "Data completeness", "Research activity listed"])
    with t1:
        c1, c2 = st.columns([1, 1])
        with c1:
            plot(charts.school_bar(df))
        with c2:
            plot(charts.department_sunburst(df))
        d = analytics.faculty_by_department(df)
        st.markdown("**Named sub-departments** (only SAS and SCOPE publish sub-departments; other schools are counted at school level)")
        st.dataframe(d.rename(columns={"school_code": "School", "department": "Department", "count": "Profiles"}),
                     hide_index=True, use_container_width=True)
    with t2:
        plot(charts.rank_stacked(df))
        c1, c2 = st.columns(2)
        with c1:
            g = analytics.counts_by(df, "grade")
            plot(charts.counts_bar(g, "count", "grade", "Grade within rank (all schools)", height=360))
        with c2:
            plot(charts.phd_stacked(df))
        st.markdown('<div class="note">PhD categories come from simple keyword rules on the published doctorate text '
                    '(e.g. "IIT", "National Institute of Technology"). "Other / unclassified" holds every institution the '
                    'rules do not name, so it mixes many Indian universities with some foreign ones.</div>', unsafe_allow_html=True)
    with t3:
        c1, c2 = st.columns([1, 1.25])
        with c1:
            plot(charts.availability_bar(df))
        with c2:
            plot(charts.availability_heatmap(df))
        plot(charts.completeness_box(df))
        st.dataframe(analytics.completeness_by_school(df), use_container_width=True)
    with t4:
        plot(charts.research_output_bars(df))
        st.dataframe(analytics.research_output_by_school(df), use_container_width=True)
        st.markdown('<div class="note">These are entries that faculty list on their own profiles. Most profiles list none, '
                    'so low numbers mean "not listed", not "none exist".</div>', unsafe_allow_html=True)


def page_text() -> None:
    st.markdown("## Research & text analytics")
    st.markdown('<div class="note">Corpus: the research specialisation each faculty member publishes '
                f'({int(df["specialisation_text"].notna().sum())} of {N} profiles; short, keyword-style text).</div>',
                unsafe_allow_html=True)
    t1, t2, t3, t4, t5 = st.tabs(["Keyphrases & words", "Distinctive terms (TF-IDF)", "Topics (NMF)",
                                  "Co-occurrence network", "School similarity"])
    with t1:
        c0, _ = st.columns([1, 2])
        sc = c0.selectbox("School", ["All schools"] + charts.SCHOOL_ORDER, key="tx_school")
        sc_val = None if sc == "All schools" else sc
        c1, c2 = st.columns(2)
        with c1:
            d = text_analytics.phrase_frequency(df, 20, school=sc_val)
            plot(charts.phrase_bar(d, "Top specialisation phrases", charts.SCHOOL_COLORS.get(sc_val, charts.CATEGORICAL[0])))
        with c2:
            sub = df if sc_val is None else df[df["school_code"] == sc_val]
            w = text_analytics.word_frequency(sub, 20)
            plot(charts.counts_bar(w, "count", "word", "Top words after preprocessing",
                                   color=charts.SCHOOL_COLORS.get(sc_val, charts.CATEGORICAL[0]), height=520))
        with st.expander("Method & limitations"):
            st.markdown("Phrases are split from each profile's list (commas, semicolons), lower-cased, parenthetical "
                        "abbreviations removed, common abbreviations expanded (ML → machine learning) and the last word "
                        "singularised. Counts are *document frequency*: how many faculty list the phrase. Different wordings "
                        "of the same idea (\"wireless communication\" vs \"wireless communications systems\") still count separately.")
    with t2:
        terms = text_analytics.distinctive_terms(df, 10)
        cols = st.columns(4)
        for i, sc in enumerate([s for s in charts.SCHOOL_ORDER if s in terms]):
            with cols[i % 4]:
                st.markdown(f"**{sc}** <span style='color:#898781;font-size:.8rem'>({config.SCHOOLS[sc].replace('School of ', '')})</span>",
                            unsafe_allow_html=True)
                st.markdown(chips([t for t, _ in terms[sc]]), unsafe_allow_html=True)
        with st.expander("Method & limitations"):
            st.markdown("All specialisation text of a school is joined into one document; TF-IDF (unigrams + bigrams, sublinear tf) "
                        "is computed across the 8 school documents. High-scoring terms are frequent in that school and rare in others. "
                        "With only 8 documents, IDF is coarse, and small schools (SBST has 7 profiles) rest on very little text.")
    with t3:
        k = st.slider("Number of topics (k)", 4, 16, 10, 1)
        tm = get_topics(N, k)
        rows = [{"Topic": t["topic"], "Top terms": ", ".join(w for w, _ in t["words"]),
                 "Faculty (dominant)": int((tm["assignments"]["topic"] == t["topic"]).sum())} for t in tm["topics"]]
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        plot(charts.topic_mix_heatmap(tm["school_mix"]))
        c1, c2 = st.columns([1, 1])
        with c1:
            plot(charts.k_scan_line(get_k_scan(N)))
        with c2:
            st.markdown(f"**Documents:** {tm['n_documents']} · **Vocabulary:** {tm['n_terms']} terms (min_df=2) · "
                        f"**Reconstruction error:** {tm['reconstruction_error']}")
            st.markdown("NMF factorises the TF-IDF matrix into k non-negative topic vectors. It is preferred over LDA here "
                        "because documents are very short. Error falls smoothly with k (no sharp elbow), so k=10 is a readability "
                        "choice, not an optimum. Topics are descriptive groupings, not ground truth.")
    with t4:
        c1, c2 = st.columns([1, 1])
        top_n = c1.slider("Phrases in network", 20, 60, 40, 5)
        min_w = c2.slider("Minimum shared faculty per link", 1, 5, 2)
        G = text_analytics.cooccurrence_network(df, top_n=top_n, min_weight=min_w)
        plot(charts.network_figure(G))
        st.dataframe(text_analytics.network_summary(G).head(15), hide_index=True, use_container_width=True)
        st.caption("Nodes are the most listed phrases (size = faculty listing it). A link means at least the chosen number of "
                   "faculty list both phrases. Degree centrality shows which interests act as hubs between others.")
    with t5:
        plot(charts.similarity_heatmap(text_analytics.school_similarity(df)))
        st.caption("Cosine similarity of school-level TF-IDF vectors. Higher means the schools describe research with more "
                   "shared vocabulary.")


def page_discovery() -> None:
    st.markdown("## Faculty discovery")
    st.markdown("Describe a research topic and get faculty whose published specialisations match it.")
    rec = get_recommender(N)
    examples = ["machine learning for healthcare", "power electronics electric vehicles", "graph theory",
                "corporate finance", "constitutional law", "thin film solar cells", "natural language processing",
                "english literature"]
    c1, c2, c3 = st.columns([3, 1.2, 1])
    ex = c1.selectbox("Try an example (or type your own below)", ["—"] + examples, key="disc_ex")
    query = c1.text_input("Research interest", value="" if ex == "—" else ex, key="disc_q",
                          placeholder="e.g. wireless sensor networks and IoT security")
    school = c2.selectbox("Limit to school", ["All"] + charts.SCHOOL_ORDER, key="disc_school")
    k = c3.slider("Results", 5, 30, 10)
    if not query.strip():
        st.markdown('<div class="empty">Enter a research topic to see matching faculty.</div>', unsafe_allow_html=True)
        return
    res = rec.recommend(query, k=k, school=None if school == "All" else school)
    if not res:
        st.markdown('<div class="empty">No faculty specialisation shares words with this query. Try broader or different terms.</div>',
                    unsafe_allow_html=True)
        return
    top = res[0].score or 1
    for i, s in enumerate(res, start=1):
        r = BY_ID.loc[s.faculty_id].copy()
        r["faculty_id"] = s.faculty_id
        terms = "".join(f'<span class="match">{esc(t)}</span>' for t in s.matched_terms)
        spec = ", ".join(r["specialisation"][:6])
        bar = f'<div style="height:6px;background:#e8f0fb;border-radius:3px;margin-top:6px"><div style="height:6px;width:{100 * s.score / top:.0f}%;background:#2a78d6;border-radius:3px"></div></div>'
        st.markdown(f"""<div class="card" style="margin-bottom:10px">{avatar_html(r)}<div style="flex:1;min-width:0">
            <div class="nm">{i}. {esc(s.name)} <span style="color:#898781;font-weight:400">· score {s.score:.3f}
            (cosine {s.cosine:.3f}, coverage {100 * s.coverage:.0f}%)</span></div>
            <div class="ds">{esc(s.designation)} · {esc(s.department)} · {esc(s.school_code)}</div>
            <div class="dp" style="margin-top:4px">{esc(spec)}</div>
            <div style="margin-top:6px;font-size:.78rem;color:#52514e">Matched terms: {terms}</div>{bar}
            <a class="btn" href="{profile_link(s.faculty_id)}" target="_self">View profile →</a></div></div>""",
                    unsafe_allow_html=True)
    st.markdown('<div class="note">Score = cosine similarity between TF-IDF vectors of your query and each profile '
                '(specialisations weighted ×3, department name, patent titles) × (0.5 + 0.5 × coverage), where coverage is the '
                'share of your query words found in the profile. It measures shared wording only: it does not '
                'rank research quality, impact or availability, and faculty who publish little text are under-represented.</div>',
                unsafe_allow_html=True)


def page_methodology() -> None:
    st.markdown("## Data sources, coverage & methodology")
    kpi_row([
        (REPORT.get("profiles_discovered", N), "Profiles discovered", "records loaded by the directory page"),
        (REPORT.get("extraction_failures", 0), "Extraction failures", ""),
        (REPORT.get("duplicates_removed", 0), "Duplicates removed", "by e-mail / normalised name"),
        (REPORT.get("profiles_processed", N), "Profiles processed", "in this dataset"),
    ])
    st.markdown(f"""
**Official source:** [https://vitap.ac.in/allfaculty](https://vitap.ac.in/allfaculty) (robots.txt allows `/`).
Snapshot captured **{esc(META.get('snapshot_captured_at'))}**.

The directory is a Next.js page. Its server HTML has no faculty data; the browser downloads records from the university's
CMS (7 pages × 100) and adds 7 SBST records bundled in the page script. The pipeline renders the page in a real browser
and reads the list the page displays, so the dataset matches what a visitor sees. Each record keeps the directory URL and
its official profile URL (`/<School>/faculty/<email-id>`, the same pattern the site uses) as provenance.
""")
    st.graphviz_chart("""
digraph G { rankdir=LR; node [shape=box, style="rounded,filled", fillcolor="#e8f0fb", color="#86b6ef", fontname="Helvetica", fontsize=11];
  site [label="vitap.ac.in/allfaculty\\n(Next.js page + CMS)"]; cap [label="Capture\\nPlaywright render\\nscraper.py"];
  raw [label="Raw snapshot\\ndata/raw/*.json", fillcolor="#f0efec"]; ext [label="Extract\\nfield mapping\\nextractor.py"];
  cln [label="Clean & validate\\nnormalise, dedupe, score\\ncleaner.py"]; out [label="faculty.json / .csv / .db", fillcolor="#f0efec"];
  ana [label="Analytics\\nanalytics.py"]; txt [label="Text analytics\\nTF-IDF · NMF · network"]; rec [label="Recommender\\nTF-IDF + cosine"];
  app [label="Streamlit app", fillcolor="#cde2fb"];
  site -> cap -> raw -> ext -> cln -> out; out -> ana -> app; out -> txt -> app; out -> rec -> app; }""")
    st.markdown("### Field coverage")
    cov = REPORT.get("field_coverage", {})
    cov_df = pd.DataFrame([{"Field": analytics.FIELD_LABELS.get(k, k), "Profiles": v["count"], "%": v["pct"]}
                           for k, v in cov.items()]).sort_values("%", ascending=False)
    st.dataframe(cov_df, hide_index=True, use_container_width=True)
    st.markdown("**Not available on the website:** publications list and years of experience. These fields exist in the "
                "schema but are always empty: they were not invented.")
    st.markdown("### Data-quality flags")
    ic = REPORT.get("issue_counts", {})
    st.dataframe(pd.DataFrame([{"Flag": k, "Profiles": v} for k, v in ic.items()]), hide_index=True, use_container_width=True)
    if config.ISSUES_CSV.exists():
        st.download_button("⬇ Download per-profile issue list (CSV)", config.ISSUES_CSV.read_bytes(),
                           "data_quality_issues.csv", "text/csv")
    st.download_button("⬇ Download full cleaned dataset (CSV)", config.FACULTY_CSV.read_bytes(), "faculty.csv", "text/csv")
    st.markdown("### Ethics & privacy")
    st.markdown("- Only information the university publishes publicly is used; personal phone numbers present in the source are "
                "**dropped at capture** and never stored.\n- Photos are referenced at their official URLs, not redistributed.\n"
                "- Rankings and similarity scores reflect text overlap, not merit. No individual is scored on quality.\n"
                "- Requests are paced and robots.txt is respected; no authentication or protection is bypassed.")


ROUTES = {"Overview": page_overview, "Directory": page_directory, "Faculty profile": page_profile,
          "Department analytics": page_departments, "Research & text analytics": page_text,
          "Faculty discovery": page_discovery, "Data & methodology": page_methodology}
ROUTES[page]()
