# VITbutAP Faculty Atlas

**CSE 4039: Advanced Social, Text and Media Analytics Lab · Fall 2026 · Slots L39/L40**
**Team VITbutAP:** Vaibhav Manihar (23BCB7163) · Udit Ray (23BCB7008) · Ajitesh Mohapatra (23BCB7178)
**Institution:** VIT-AP University, Andhra Pradesh

A searchable faculty directory and analytics platform built from the public faculty
directory at <https://vitap.ac.in/allfaculty>. It covers a reproducible collection
pipeline, a cleaned dataset (JSON, CSV and SQLite), descriptive analytics, text analytics
(TF-IDF, NMF topics, phrase co-occurrence network) and a TF-IDF faculty-discovery engine,
all delivered as a Streamlit web app.

| Snapshot (17 Oct 2026) | Value |
|---|---|
| Profiles discovered on the directory page | **609** |
| Profiles processed into the dataset | **609** (0 extraction failures, 0 duplicates) |
| Schools | **8** (SCOPE, SAS, SENSE, VISH, VSB, VSL, SMEC, SBST) |
| Named sub-departments | **7** (3 in SAS, 4 in SCOPE) |
| Profiles with a research specialisation | 577 (94.7 %) |
| Unit and smoke tests | 60 passing |

> These counts are the profiles the university publishes online on that date. They are not a
> verified headcount of the university's workforce.

---

## 1. Quick start on Windows

You need **Python 3.11, 3.12 or 3.13** (from <https://www.python.org/downloads/>; tick
*"Add python.exe to PATH"* during installation).

Open **PowerShell** in the project folder (the folder that contains `app.py`) and run:

```powershell
# 1. create and activate a virtual environment
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
#   If PowerShell blocks the script, run this once, then activate again:
#   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

# 2. install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# 3. launch the app (the cleaned dataset is already included)
streamlit run app.py
```

Your browser opens <http://localhost:8501>. Stop the app with `Ctrl + C`.

Using **Command Prompt** instead of PowerShell? Activate with `.venv\Scripts\activate.bat`.

## 2. Running the pipeline

The shipped dataset was built from `data/raw/vitap_faculty_raw.json`, a snapshot of the
directory captured on 17 Oct 2026.

```powershell
# rebuild data/faculty.json/.csv/.db from the stored raw snapshot
python scripts\run_pipeline.py

# validate the dataset (exit code 0 = valid)
python scripts\validate_dataset.py

# re-capture the live directory (needs Chromium for Playwright, one-time)
python -m playwright install chromium
python scripts\run_pipeline.py --live            # add --headed to watch the browser

# import a snapshot saved from a browser (see docs/methodology.md, section 3)
python scripts\run_pipeline.py --snapshot path\to\vitap_faculty_raw.json
```

If a live capture fails (no network, site changed), the pipeline logs the error and keeps
the previous snapshot, so the app still works. Logs go to `logs\pipeline.log`.

Optional extras:

```powershell
python scripts\download_photos.py --limit 50       # cache official photos locally (1.5 s apart)
python scripts\generate_charts.py                  # export report charts to outputs\charts
streamlit run app.py --server.port 8501 --server.headless true   # terminal 1
python scripts\capture_screenshots.py              # terminal 2: app screenshots
```

## 3. Tests

```powershell
python -m pytest -q
```

This runs 60 tests: extraction, cleaning, normalisation, duplicate detection, missing
fields, text preprocessing, analytics numbers, recommender logic, failed-request
handling, dataset validation, and a headless run of every app page.

## 4. What the app contains

| Page | What it shows |
|---|---|
| Overview | headline numbers, faculty by school, rank mix, top specialisations, leadership |
| Directory | name search; filters for school, department, rank, specialisation phrase, keyword and quality; sorting; 24 per page; CSV download |
| Faculty profile | photo (or initials fallback), designation, contact, links, specialisations, education, patents/projects/awards, similar faculty, provenance and quality flags |
| Department analytics | structure (school → department), ranks and grades, PhD-institution categories, field completeness heatmap, listed research activity |
| Research & text analytics | keyphrases and word frequency, distinctive TF-IDF terms per school, NMF topics with a k scan, phrase co-occurrence network, school similarity |
| Faculty discovery | free-text query → ranked faculty with matched terms, cosine and coverage |
| Data & methodology | coverage, pipeline diagram, field coverage, quality flags, ethics |

## 5. Project structure

```
vitbutap/
├── app.py                     Streamlit application
├── requirements.txt
├── .streamlit/config.toml     theme
├── src/
│   ├── config.py              paths, URLs, reference mappings
│   ├── scraper.py             Playwright capture, retries, robots.txt
│   ├── extractor.py           raw CMS record → flat schema
│   ├── cleaner.py             normalise, classify, dedupe, score
│   ├── storage.py             JSON / CSV / SQLite
│   ├── analytics.py           descriptive analytics
│   ├── text_analytics.py      preprocessing, TF-IDF, NMF, network
│   ├── recommender.py         TF-IDF + cosine faculty discovery
│   └── charts.py              Plotly figure builders (app + report)
├── scripts/                   run_pipeline, validate_dataset, generate_charts,
│                              capture_screenshots, download_photos
├── tests/                     pytest suite (60 tests)
├── data/                      faculty.json/.csv/.db, raw/, processed/
├── docs/                      methodology, architecture, data dictionary
├── outputs/                   charts/, screenshots/, analysis_summary.json
├── report/                    final_report.tex / .pdf
└── presentation/              presentation.pptx, presenter_script.md
```

## 6. Troubleshooting

| Problem | Fix |
|---|---|
| `streamlit` is not recognised | Activate the venv first (`.\.venv\Scripts\Activate.ps1`) or run `python -m streamlit run app.py` |
| PowerShell: "running scripts is disabled" | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then activate again |
| App says "No dataset found" | Run `python scripts\run_pipeline.py` from the project folder |
| Photos show initials | The photos load from the university's image server, so you need internet access. Initials are the intended fallback. To work offline, run `scripts\download_photos.py` while you are online. |
| Port 8501 busy | `streamlit run app.py --server.port 8502` |
| `--live` fails with a browser error | `python -m playwright install chromium` |
| PNG chart export fails | `pip install kaleido`. Kaleido needs Chrome or Edge; set `BROWSER_PATH` to the browser's .exe if it is not found |
| `pip install` fails on pandas or numpy | Use Python 3.11–3.13 (64-bit) |

## 7. Data, ethics and licence notes

* Source: public pages of vitap.ac.in. The site's robots.txt (`Allow: /`) permits the directory.
  The collector paces requests and does not bypass authentication or any protection.
* Personal phone numbers that appear in the source data are dropped at capture and never stored.
* Photos are referenced at their official URLs and are not redistributed in the ZIP.
* Every record keeps `source_urls`, `last_verified` and `quality_issues` for provenance.
* Similarity and recommendation scores measure shared wording only. They are not a judgement of merit.
* The data belongs to VIT-AP University. This project is a non-commercial student lab exercise.
