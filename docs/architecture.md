# Architecture

## System architecture

```
┌──────────────────────────────┐
│  vitap.ac.in/allfaculty      │  Next.js page
│  + cms.vitap.ac.in (Strapi)  │  records loaded client-side
│  + S3 photo bucket           │
└──────────────┬───────────────┘
               │ Playwright render (robots.txt checked, paced, retries)
┌──────────────▼───────────────┐
│ COLLECTION   src/scraper.py  │──► data/raw/vitap_faculty_raw.json   (raw, provenance meta)
└──────────────┬───────────────┘
┌──────────────▼───────────────┐
│ EXTRACTION   src/extractor.py│──► data/processed/faculty_extracted.json
└──────────────┬───────────────┘
┌──────────────▼───────────────┐
│ CLEANING     src/cleaner.py  │──► data/faculty.json | faculty.csv | faculty.db
│ normalise · classify · dedupe│──► data/processed/data_quality_report.json, issues.csv
│ score · flag                 │
└──────────────┬───────────────┘
               │ scripts/validate_dataset.py (gate)
     ┌─────────┼───────────────────────┬──────────────────────┐
┌────▼─────┐ ┌─▼────────────────┐ ┌────▼─────────────┐ ┌──────▼──────┐
│analytics │ │text_analytics    │ │recommender       │ │charts.py    │
│counts,   │ │TF-IDF, NMF,      │ │TF-IDF + cosine × │ │Plotly       │
│coverage  │ │network, similarity│ │coverage          │ │builders     │
└────┬─────┘ └─┬────────────────┘ └────┬─────────────┘ └──────┬──────┘
     └─────────┴───────────┬───────────┴──────────────────────┘
                 ┌─────────▼──────────┐        ┌───────────────────────────┐
                 │ app.py (Streamlit) │        │ scripts/generate_charts.py │
                 │ 7 pages, cached    │        │ → outputs/charts/*.png     │
                 └────────────────────┘        │ → analysis_summary.json    │
                                               └───────────────────────────┘
```

## Data flow (one record)

```
CMS JSON {Name, Designation: "Assistant Professor Sr Grade 1", Department: "School of … (SCOPE)",
          sub_department: "DAIML", EMAIL, Contact_No, Photo:{data:{attributes:{url}}}, …}
   │ capture: drop Contact_No, flatten Photo → URL
   ▼
raw snapshot record
   │ extractor: rename → designation_raw, school_raw, …; Employee_Id 5.70101 → order 5, code "70101";
   │            profile_url = https://vitap.ac.in/School%20of%20…%20(SCOPE)/faculty/<email-id>
   ▼
extracted record
   │ cleaner: rank "Assistant Professor", grade "Senior Grade 1"; school_code SCOPE;
   │          department "Artificial Intelligence and Machine Learning"; specialisation list;
   │          canonical links; completeness 0.83; status "complete"; quality_issues []
   ▼
faculty.json record ──► analytics / TF-IDF index / app card & profile page
```

## Design decisions

| Decision | Reason |
|---|---|
| Streamlit + Plotly instead of React + API | one language, runs on Windows with `pip install`, interactive charts and filters out of the box; no server or database to deploy |
| Playwright, not Requests+BeautifulSoup | the directory HTML has no data; content is rendered client-side |
| Read the rendered page, not the API | the API needs the page's own request headers; reading what the page renders avoids handling credentials and includes the 7 bundled SBST records the API lacks |
| JSON canonical + CSV + SQLite | JSON keeps lists; CSV for spreadsheets; SQLite for SQL practice with normalised child tables |
| NMF over LDA | very short documents (median about 4 phrases); NMF on TF-IDF is more stable there |
| Coverage-weighted cosine | pure cosine over-rewards one-word profiles; the factor is simple and shown to users |
| CSS background for photos | if the official image fails, initials show through, with no JavaScript and no broken-image icon |
