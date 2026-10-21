"""Persistence: JSON (canonical), CSV (spreadsheet-friendly) and SQLite."""
from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from . import config

log = logging.getLogger(__name__)

LIST_COLUMNS = ["specialisation", "professional_memberships", "patents", "projects",
                "awards", "source_urls", "quality_issues"]


def save_json(records: list[dict[str, Any]], path: Path = config.FACULTY_JSON,
              meta: dict[str, Any] | None = None) -> Path:
    """Canonical dataset: ``{"meta": {...}, "records": [...]}``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"meta": meta or {}, "records": records}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def load_records(path: Path = config.FACULTY_JSON) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data["records"] if isinstance(data, dict) else data


def load_meta(path: Path = config.FACULTY_JSON) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data.get("meta", {}) if isinstance(data, dict) else {}


def to_dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
    """Records -> DataFrame (list columns stay Python lists)."""
    df = pd.DataFrame(records)
    for col in LIST_COLUMNS:
        if col in df.columns:
            df[col] = df[col].apply(lambda v: v if isinstance(v, list) else [])
    return df


def flatten_for_csv(df: pd.DataFrame) -> pd.DataFrame:
    """Join list columns with ' | ' and drop nested columns for CSV export."""
    out = df.copy()
    for col in LIST_COLUMNS:
        if col in out.columns:
            out[col] = out[col].apply(lambda v: " | ".join(v) if isinstance(v, list) else v)
    return out.drop(columns=[c for c in ("extra_fields",) if c in out.columns])


def save_csv(records: list[dict[str, Any]], path: Path = config.FACULTY_CSV) -> Path:
    flatten_for_csv(to_dataframe(records)).to_csv(path, index=False, encoding="utf-8-sig")
    return path


def save_sqlite(records: list[dict[str, Any]], path: Path = config.FACULTY_DB) -> Path:
    """Normalised SQLite: ``faculty`` + one child table per list field."""
    if path.exists():
        path.unlink()
    df = to_dataframe(records)
    scalar = flatten_for_csv(df).drop(columns=[c for c in LIST_COLUMNS if c in df.columns])
    with sqlite3.connect(path) as con:
        scalar.to_sql("faculty", con, index=False)
        for col in ("specialisation", "patents", "projects", "awards",
                    "professional_memberships", "quality_issues"):
            rows = [(r["faculty_id"], i, v) for r in records for i, v in enumerate(r.get(col) or [])]
            con.execute(f"CREATE TABLE {col} (faculty_id TEXT, position INTEGER, value TEXT)")
            con.executemany(f"INSERT INTO {col} VALUES (?,?,?)", rows)
        con.execute("CREATE UNIQUE INDEX ix_faculty_id ON faculty(faculty_id)")
    return path
