"""
Import Physics For You questions from the Excel workbook into the SQLite database.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

EXCEL_PATH = Path(r"G:\My Drive\Aditya\IITJEE\Physics\Physics For You\Physics_Questions.xlsx")
DB_PATH = Path(r"G:\My Drive\Aditya\IITJEE\Database\question_bank.db")
SUBJECT_NAME = "Physics"
MAGAZINE_NAME = "Physics For You"


def _clean(value: object) -> str | None:
    """Return a stripped string or None when the cell is empty."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


def _ensure_subject(conn: sqlite3.Connection, name: str) -> int:
    conn.execute("INSERT OR IGNORE INTO subjects(name) VALUES (?)", (name,))
    row = conn.execute("SELECT id FROM subjects WHERE name = ?", (name,)).fetchone()
    if not row:
        raise RuntimeError(f"Failed to ensure subject '{name}' exists.")
    return int(row[0])


def main() -> None:
    if not EXCEL_PATH.exists():
        raise FileNotFoundError(f"Excel workbook not found: {EXCEL_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")

    subject_id = _ensure_subject(conn, SUBJECT_NAME)
    workbook = pd.ExcelFile(EXCEL_PATH)

    total_inserted = 0
    for sheet_name in workbook.sheet_names:
        df = workbook.parse(sheet_name)
        rows = []
        for record in df.to_dict(orient="records"):
            question_text = _clean(record.get("Full Question Text"))
            if not question_text:
                continue

            qno = _clean(record.get("Qno"))
            page_no = _clean(record.get("PageNo"))
            edition = _clean(record.get("Magazine Edition"))
            question_set = _clean(record.get("Name of Question Set"))
            chapter = _clean(record.get("High level chapter"))

            rows.append(
                (
                    subject_id,  # subject_id
                    str(EXCEL_PATH),  # source
                    MAGAZINE_NAME,  # magazine
                    MAGAZINE_NAME.lower(),  # normalized_magazine
                    edition,  # edition
                    None,  # issue_year
                    None,  # issue_month
                    page_no,  # page_range
                    question_set,  # question_set
                    question_set,  # question_set_name
                    chapter,  # chapter
                    chapter,  # high_level_chapter
                    qno,  # question_number
                    question_text,  # question_text
                    None,  # answer_text
                    None,  # explanation
                    None,  # metadata_json
                )
            )

        if not rows:
            continue

        with conn:
            conn.executemany(
                """
                INSERT INTO questions (
                    subject_id, source, magazine, normalized_magazine, edition,
                    issue_year, issue_month, page_range, question_set, question_set_name,
                    chapter, high_level_chapter, question_number, question_text,
                    answer_text, explanation, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        total_inserted += len(rows)
        print(f"{sheet_name}: inserted {len(rows)} rows")

    conn.close()
    print(f"Finished. Total inserted: {total_inserted}")


if __name__ == "__main__":
    main()
