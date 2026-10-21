# Data dictionary: `data/faculty.json` / `faculty.csv` / `faculty.db`

One record per faculty profile (609 records, snapshot 17 Oct 2026).
"Source" names the raw CMS field (spelling as published, typos included); *derived* means
the value was computed by `src/cleaner.py`. Coverage is the share of the 609 profiles with a
non-empty value.

In the CSV, list fields are joined with ` | `. In SQLite, the scalar fields are in table
`faculty`, and each list field has its own child table (`specialisation`, `patents`,
`projects`, `awards`, `professional_memberships`, `quality_issues`) with columns
`faculty_id, position, value`.

## Identity and position

| Field | Type | Source | Description | Coverage |
|---|---|---|---|---|
| faculty_id | str | derived | `VITAP-<employee_code>`; `VITAP-X####` fallback if a code is missing or repeated | 100 % |
| name | str | Name | display name with honorific spacing fixed (`Dr.X` → `Dr. X`) | 100 % |
| honorific | str | derived | Dr. / Mr. / Ms. / Prof. | 100 % |
| designation | str | Designation | normalised academic title, e.g. `Assistant Professor Senior Grade 1` | 100 % |
| designation_raw | str | Designation | title exactly as published (whitespace cleaned) | 100 % |
| academic_rank | str | derived | Professor, Associate Professor, Assistant Professor, Emeritus Professor, Professor of Practice, Adjunct Faculty, Not stated | 100 % |
| grade | str | derived | Grade 1/2, Senior Grade 1/2, Senior, Junior, HAG | 97.4 % |
| admin_role | str | derived | administrative part of the title, e.g. `Dean, SAS`, `Head, Dept. of Physics` | 27 profiles |
| admin_role_type | str | derived | Dean, Associate Dean, Assistant Dean, Head of Department, Registrar, Vice Chancellor | 27 profiles |
| school_code | str | Department | SCOPE, SAS, SENSE, VISH, VSB, VSL, SMEC, SBST | 100 % |
| school | str | Department | full school name | 100 % |
| department | str | sub_department | department name if published (SAS, SCOPE), otherwise the school name | 100 % |
| department_level | str | derived | `department` (sub-department published) or `school` (fallback) | 100 % |
| listing_order | int | Employee_Id | integer part of the CMS sort key (leaders first) | 98.5 % |
| employee_code | str | Employee_Id | staff number from the sort key (matches photo file names) | 100 % |

## Research and education

| Field | Type | Source | Description | Coverage |
|---|---|---|---|---|
| specialisation | list[str] | Research_area_of_specialization | phrases split on `,` `;` newline, de-duplicated | 94.7 % |
| specialisation_text | str | Research_area_of_specialization | original text (whitespace cleaned), used by text analytics | 94.7 % |
| education_ug / _pg / _phd / _other | str | Education_* | degree text as published | 97.2 / 96.2 / 94.9 / 21.3 % |
| phd_institution_category | str | derived | rule-based: IIT, NIT, IISc, IISER, IIIT, BITS, VIT, Foreign, Pursuing, Other / unclassified, Not stated | 100 % |
| professional_memberships | list[str] | Professonal_Membership | split list | 41.1 % |
| patents / projects / awards | list[str] | Patents / Projects / Awards_and_Recognitions | entries listed on the profile | 15.8 / 12.8 / 24.0 % |
| n_patents / n_projects / n_awards | int | derived | list lengths | 100 % |
| publications | null | – | **not published on the directory**; always null, never invented | 0 % |
| experience | null | – | **not published on the directory**; always null | 0 % |

## Contact and links

| Field | Type | Source | Description | Coverage |
|---|---|---|---|---|
| official_email | str | EMAIL | lower-cased, format-validated institutional address | 99.8 % |
| office_location | str | Office_Address | room and building as published | 98.4 % |
| office_building | str | derived | AB-1, AB-2 or CB (Central Block) | 98.0 % |
| photograph_url | str | Photo | original official image URL (S3 bucket used by vitap.ac.in) | 100 % |
| google_scholar | str | Research_google_schloar | canonical `citations?user=` URL when parsable | 78.8 % |
| orcid | str | Research_orchid | canonical `https://orcid.org/<id>` when parsable | 32.7 % |
| scopus | str | Research_Scopus_Id | canonical author URL when parsable | 62.4 % |
| researchgate, dblp, vidwan, linkedin, personal_website | str | Research_* / LinkedIn / Website | URLs with a missing `https://` added | 46.3 / 3.9 / 26.6 / 52.1 / 4.1 % |

## Provenance and quality

| Field | Type | Description |
|---|---|---|
| profile_url | str | official profile page, `https://vitap.ac.in/<School>/faculty/<email-id>` (the pattern the directory itself uses); missing for 1 profile with no e-mail |
| source_urls | list[str] | directory URL plus profile URL |
| record_origin | str | `cms_api` (loaded from the CMS) or `page_bundle` (7 SBST records bundled in the page script) |
| cms_updated_at | str | CMS last-modified timestamp (API records only) |
| last_verified | str | snapshot capture time (UTC) |
| completeness | float | share of 12 tracked fields filled (photo, designation, e-mail, office, specialisation, UG, PG, PhD, Scholar, ORCID, Scopus, LinkedIn) |
| data_quality_status | str | `complete` (≥ 0.75 and no blocking issue) / `partial` (≥ 0.40) / `minimal` |
| quality_issues | list[str] | flags, see below |
| extra_fields | dict | any CMS field not in the schema (currently none), kept rather than discarded |

### Quality flags (counts in the 17 Oct 2026 snapshot)

| Flag | Meaning | Profiles |
|---|---|---|
| scopus_unparsed | Scopus field present but no author ID found | 33 |
| missing_specialisation | no research specialisation published | 32 |
| scholar_not_profile_link | Scholar field points to a search page or homepage | 23 |
| orcid_unparsed | ORCID field present but no valid ORCID iD | 4 |
| rank_not_stated | designation has no academic rank (Vice Chancellor I/c) | 1 |
| missing_email / no_profile_url | no e-mail, so no profile URL can be built | 1 |
| non_institutional_email | e-mail not on vitap.ac.in | 1 |

**Removed on purpose:** `Contact_No` (personal phone numbers) is dropped at capture.
