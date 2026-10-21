# Data folder

| File | Stage | Description |
|---|---|---|
| `raw/vitap_faculty_raw.json` | raw | snapshot of the 609 records shown by https://vitap.ac.in/allfaculty on 2026-10-17 (06:32 UTC), with capture metadata; phone numbers removed |
| `processed/faculty_extracted.json` | extracted | records mapped to the documented schema, values untouched |
| `processed/data_quality_report.json` | report | counts discovered/processed, duplicates, field coverage, issue counts |
| `processed/data_quality_issues.csv` | report | one row per (profile, quality flag) with the official profile URL |
| `faculty.json` | clean | canonical dataset `{meta, records}` |
| `faculty.csv` | clean | same data; list fields joined with ` \| ` (UTF-8 with BOM for Excel) |
| `faculty.db` | clean | SQLite: `faculty` + child tables for list fields |
| `photos/` | optional | local photo cache made by `scripts/download_photos.py` (not shipped) |

Field definitions: `../docs/data_dictionary.md`.

**Provenance.** Every record has `source_urls` (directory + official profile URL),
`last_verified` (capture time) and `record_origin`.

**Redistribution.** The information is publicly published by VIT-AP University. It is
included here for a non-commercial academic lab submission. Photographs are referenced by
URL and are not redistributed.
