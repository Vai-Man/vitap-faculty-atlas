# Methodology

## 1. Website investigation (17 Oct 2026)

| Question | Finding |
|---|---|
| Page technology | `https://vitap.ac.in/allfaculty` is a Next.js (React) app. Server HTML contains only navigation, banners and the school filter list; **no faculty data**. |
| How records load | In the browser, the page script calls `cms.vitap.ac.in/api/faculty-profiles?populate=*&sort=Employee_Id:ASC&pagination[page]=N&pagination[pageSize]=100` seven times (pages 1–7, 602 records). It then appends **7 SBST records bundled in the page script**. Total shown: **609**. |
| Direct API access | Without the page's own request headers the endpoint returns HTTP 500. We did not call the API ourselves or reuse any token. The pipeline only observes what the public page loads. |
| Schools (filter list) | SCOPE, SENSE, SMEC, SAS, VSB, VSL, VISH, SBST (8). The page also has sub-department tabs DDSE, DSSE, DNS, DAIML. |
| Pagination | client-side, 20 cards per page, 31 pages |
| Profile pages | `/<Department>/faculty/<email-id>`; client-rendered from the same CMS (`filters[EMAIL][$eq]=…`). Each one shows the same fields as the directory record (verified on one profile, e.g. SMEC). |
| Photographs | Strapi media objects whose `url` points to `vitap-backend.s3.ap-south-1.amazonaws.com` (603 AVIF, 4 JPG, 2 PNG). |
| robots.txt | `User-agent: * / Allow: / / Disallow: /vitiebot`, so the directory is permitted. |
| Fields published | Name, Employee_Id (sort key), Designation, Department, sub_department, EMAIL, Office_Address, Contact_No, Research_area_of_specialization, Education_UG/PG/PHD/other, Professonal_Membership, Research_google_schloar, Research_orchid, Research_Scopus_Id, Research_Research_Gate, Research_DBLP, Research_vidwan, LinkedIn, Website, Photo, Patents[], Projects[], Awards_and_Recognitions[], CMS timestamps. |
| Not published | Publications list, years of experience, biographies. |
| Duplicates | none by e-mail or normalised name |
| Inconsistencies | 40+ spellings of the same designations (`Grade-1`, `Grade1`, `Grade I`, `Sr`); `Dr.Name` spacing; links stored as bare IDs or search pages; placeholder values such as `--`. |

## 2. Collection

`src/scraper.py` renders the directory with Playwright (Chromium) and reads the rendered
list from the page's React state. This is the same list a visitor sees, including the
bundled SBST records. Every CMS response the page receives is also logged, as a cross-check
of the API-sourced count. Before capture, robots.txt is checked; requests use a descriptive
User-Agent; HTTP helpers retry with exponential back-off and never raise, so one failure
cannot stop a run. `Contact_No` is removed at capture time.

## 3. Snapshot used for the shipped dataset

Our cloud build machine could not reach vitap.ac.in (its egress allowlist blocks the site).
The 17 Oct 2026 snapshot was therefore captured in a desktop browser by running the scraper's
own `REACT_STATE_JS` on the rendered directory page, then saving the result as
`data/raw/vitap_faculty_raw.json`. That is the same logic the Playwright capture uses. On any
machine that can reach the site, `python scripts/run_pipeline.py --live` repeats the capture
automatically.

## 4. Extraction → cleaning

* **Extraction** (`extractor.py`) renames fields to the documented schema, flattens the
  Strapi photo object to its URL, turns patent/project/award arrays into string lists,
  derives `listing_order` and `employee_code` from the sort key, and rebuilds the official
  profile URL with the site's own rule. Unknown fields go to `extra_fields`.
* **Cleaning** (`cleaner.py`): whitespace and placeholder removal; honorific spacing;
  school code parsing; sub-department code → name mapping; designation split into
  administrative role + rank + grade with spelling variants unified; list splitting and
  de-duplication; URL scheme repair; canonical ORCID/Scopus/Scholar links where an ID can
  be parsed (otherwise kept and flagged); office building extraction; rule-based PhD
  institution category; completeness score over 12 fields; quality status and flags.
* **Deduplication**: key = e-mail, else honorific-free normalised name; the most complete
  record wins; same-name/different-email pairs are flagged, not merged.
* **Outputs**: `faculty.json` (canonical, with meta), `faculty.csv`, `faculty.db` (SQLite with
  child tables), `processed/data_quality_report.json`, `processed/data_quality_issues.csv`.
  Raw (`data/raw`) and extracted (`data/processed/faculty_extracted.json`) stages are kept
  separately, so cleaning can be reproduced.

## 5. Analytics

Descriptive analytics (`analytics.py`) compute counts by school/department/rank/grade,
rank shares, field availability overall and per school, completeness distributions,
listed research activity and PhD-institution categories. All charts in the app and the
report are built from these functions.

## 6. Text analytics

| Technique | Purpose | Implementation | Limitation |
|---|---|---|---|
| Preprocessing | comparable tokens | lower-case, `&`→and, regex tokens, scikit-learn English stop words + 30 domain stop words, abbreviation expansion (ML, AI, IoT, NLP…), light singularisation | rule-based; no lemmatiser, so some variants remain |
| Keyphrase frequency | most common research areas | faculty-supplied phrases normalised and counted by document frequency | different wordings of one idea count separately |
| Word frequency | vocabulary overview | token counts after preprocessing | words lose phrase context |
| TF-IDF distinctive terms | what characterises each school | one document per school, uni+bigrams, sublinear tf | 8 documents give a coarse IDF; small schools rest on little text |
| NMF topics | latent research themes | TF-IDF (min_df=2, 758 terms) × NMF k=10, `nndsvda` init, seed 42 | short texts; error curve has no clear elbow, so k is a readability choice |
| Co-occurrence network | how interests connect | top-40 phrases, edge = ≥2 faculty listing both, degree centrality (networkx) | depends on phrase normalisation; ignores phrase order |
| School similarity | overlap between schools | cosine of school TF-IDF vectors | vocabulary overlap, not collaboration |

N-grams are built **within** each comma-separated list item (`text_analytics.analyzer`), so
"Deep Learning, Healthcare" does not create the false bigram "learning healthcare".

## 7. Faculty discovery

Profile document = specialisation ×3 + department + patent titles. TF-IDF (phrase-aware
uni+bigrams, sublinear tf). Score = cosine(query, profile) × (0.5 + 0.5 × coverage),
where coverage is the share of the query's in-vocabulary words found in the profile.
The coverage factor stops very short profiles that repeat one query word from outranking
profiles that match the whole query. Each result shows the matched terms, the cosine and the
coverage. "Similar faculty" on a profile page uses plain cosine between profile vectors.

## 8. Testing

60 pytest tests (see README). The shipped dataset is validated by
`scripts/validate_dataset.py`: required keys, unique IDs and e-mails, official source URLs,
photo URL format, allowed school/status values, no phone-number field, and a phone-number
pattern scan of free-text fields.
