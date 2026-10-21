"""End-to-end data pipeline.

    python scripts/run_pipeline.py                 # re-use data/raw snapshot
    python scripts/run_pipeline.py --live          # re-capture with Playwright
    python scripts/run_pipeline.py --snapshot path/to/vitap_faculty_raw.json

Stages: capture/load -> extract -> clean/dedupe -> save JSON/CSV/SQLite ->
quality report -> validation. Logs go to logs/pipeline.log.
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import cleaner, config, extractor, scraper, storage  # noqa: E402
from scripts.validate_dataset import validate  # noqa: E402


def setup_logging() -> None:
    config.ensure_dirs()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        handlers=[logging.FileHandler(config.LOG_DIR / "pipeline.log", encoding="utf-8"),
                  logging.StreamHandler(sys.stdout)],
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--live", action="store_true", help="re-capture the directory with Playwright")
    ap.add_argument("--snapshot", type=Path, help="import a browser-saved snapshot JSON")
    ap.add_argument("--headed", action="store_true", help="show the browser during --live")
    args = ap.parse_args(argv)
    setup_logging()
    log = logging.getLogger("pipeline")

    # 1. capture / load ------------------------------------------------------
    if args.live:
        try:
            snap = scraper.capture_directory(headless=not args.headed)
            if config.RAW_SNAPSHOT.exists():  # keep the previous snapshot
                shutil.copy2(config.RAW_SNAPSHOT, config.RAW_DIR / "vitap_faculty_raw.previous.json")
            scraper.save_snapshot(snap)
        except Exception as exc:  # noqa: BLE001
            log.error("Live capture failed (%s); falling back to existing snapshot", exc)
            if not config.RAW_SNAPSHOT.exists():
                return 1
    elif args.snapshot:
        snap = scraper.load_snapshot(args.snapshot)
        scraper.save_snapshot(snap)
    snap = scraper.load_snapshot(config.RAW_SNAPSHOT)
    log.info("Snapshot: %d records captured at %s", len(snap["records"]), snap.get("captured_at"))

    # 2. extract -------------------------------------------------------------
    extracted, failures = extractor.extract_all(snap)
    config.EXTRACTED_JSON.write_text(json.dumps(extracted, ensure_ascii=False, indent=1), encoding="utf-8")

    # 3. clean ---------------------------------------------------------------
    records, report = cleaner.clean_records(extracted, discovered=len(snap["records"]),
                                            extraction_failures=len(failures))
    report["extraction_failure_details"] = failures
    report["snapshot_captured_at"] = snap.get("captured_at")
    report["source_page"] = snap.get("source_page")

    # 4. save ----------------------------------------------------------------
    meta = {k: report[k] for k in ("profiles_discovered", "profiles_processed",
                                   "duplicates_removed", "extraction_failures",
                                   "snapshot_captured_at", "source_page", "generated_at")}
    storage.save_json(records, meta=meta)
    storage.save_csv(records)
    storage.save_sqlite(records)
    config.QUALITY_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    issues = [{"faculty_id": r["faculty_id"], "name": r["name"], "issue": i,
               "profile_url": r["profile_url"]} for r in records for i in r["quality_issues"]]
    storage.pd.DataFrame(issues).to_csv(config.ISSUES_CSV, index=False, encoding="utf-8-sig")
    log.info("Saved %s, %s, %s", config.FACULTY_JSON.name, config.FACULTY_CSV.name, config.FACULTY_DB.name)

    # 5. validate ------------------------------------------------------------
    problems = validate(config.FACULTY_JSON)
    for p in problems:
        log.error("VALIDATION: %s", p)
    log.info("Pipeline finished: %d discovered, %d processed, %d validation problems",
             report["profiles_discovered"], report["profiles_processed"], len(problems))
    return 0 if not problems else 2


if __name__ == "__main__":
    raise SystemExit(main())
