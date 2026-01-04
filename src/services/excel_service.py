"""
TSV import helpers that write directly to SQLite (no Excel workbooks).
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Optional

from config.constants import MAGAZINE_GROUPING_MAP
from services.db_service import DatabaseService
from utils.helpers import (
    normalize_magazine_edition,
    normalize_qno,
    normalize_page,
    validate_tsv,
)


# ---------------------------------------------------------------------------
# Basic helpers
# ---------------------------------------------------------------------------

def detect_magazine_name_from_normalized(normalized_magazine: str) -> str:
    if not normalized_magazine:
        return ""
    parts = normalized_magazine.split("|", 1)
    magazine_name = parts[0].strip().lower()
    for magazine_key in MAGAZINE_GROUPING_MAP.keys():
        if magazine_key in magazine_name or magazine_name in magazine_key:
            return magazine_key
    return ""


def read_tsv_with_header(tsv_path: Path) -> tuple[list[str], list[list[str]]]:
    """Return (header, rows) from TSV."""
    with tsv_path.open("r", encoding="utf-8", newline="") as tsv_file:
        reader = csv.reader(tsv_file, delimiter="\t")
        header = next(reader, [])
        rows = [row for row in reader]
    return header, rows


def read_tsv_rows(tsv_path: Path) -> list[list[str]]:
    """Backwards-compatible helper: returns rows without header."""
    _, rows = read_tsv_with_header(tsv_path)
    return rows


# ---------------------------------------------------------------------------
# TSV -> DB import
# ---------------------------------------------------------------------------

def process_tsv(
    tsv_path: Path,
    db_service: DatabaseService,
    subject_name: str,
    overwrite_duplicates: bool = False,
) -> str:
    """
    Process a TSV file and insert rows into SQLite.

    - Validates TSV format
    - Uses TSV header to detect required columns
    - Detects duplicates in DB (subject + magazine + page + qno)
    - Inserts rows into questions table
    - Returns status with ID range inserted
    """
    try:
        validate_tsv(tsv_path)
        header_row, rows = read_tsv_with_header(tsv_path)
        if not header_row:
            raise ValueError("TSV header row is empty.")

        # Find required columns
        qno_column = _find_qno_column(header_row)
        magazine_col = _find_magazine_column(header_row)
        question_set_col = _find_question_set_column(header_row)
        page_col = _find_page_column(header_row)
        question_text_col = None
        try:
            question_text_col = _find_question_text_column(header_row)
        except ValueError:
            question_text_col = None
        chapter_col = None
        try:
            chapter_col = _find_high_level_chapter_column(header_row)
        except ValueError:
            chapter_col = None

        # Validate TSV metadata
        _, row_signatures = extract_file_metadata(
            rows, magazine_col, question_set_col, qno_column, page_col
        )

        records = []
        page_numbers = []
        for row in rows:
            mag_val = row[magazine_col - 1].strip() if len(row) >= magazine_col else ""
            qno_val = row[qno_column - 1].strip() if len(row) >= qno_column else ""
            page_val = row[page_col - 1].strip() if len(row) >= page_col else ""
            qset_val = row[question_set_col - 1].strip() if len(row) >= question_set_col else ""
            qtext_val = (
                row[question_text_col - 1].strip()
                if question_text_col and len(row) >= question_text_col
                else ""
            )
            chapter_val = (
                row[chapter_col - 1].strip()
                if chapter_col and len(row) >= chapter_col
                else ""
            )

            if page_val:
                page_numbers.append(page_val)

            records.append(
                {
                    "source": str(tsv_path),
                    "magazine": mag_val,
                    "edition": "",
                    "page_range": page_val,
                    "question_set": qset_val,
                    "question_set_name": qset_val,
                    "chapter": chapter_val,
                    "high_level_chapter": chapter_val,
                    "question_number": qno_val,
                    "question_text": qtext_val,
                }
            )

        inserted_ids, duplicates, updated_ids = db_service.insert_questions_from_tsv(
            subject_name, records, overwrite_duplicates=overwrite_duplicates
        )
        if duplicates and not overwrite_duplicates:
            readable = "; ".join(
                f"Magazine '{mag}' Question '{qno}' Page '{page}' already exists (DB has Qno '{ex_qno}', Page '{ex_page}')"
                for mag, qno, page, ex_qno, ex_page in duplicates
            )
            raise ValueError(
                "Duplicate questions detected: "
                f"{readable}. Remove or update these entries before importing."
            )

        id_range = "N/A"
        if inserted_ids:
            id_range = (
                f"{min(inserted_ids)}-{max(inserted_ids)}"
                if len(inserted_ids) > 1
                else str(inserted_ids[0])
            )

        page_range = "N/A"
        if page_numbers:
            try:
                numeric_pages = []
                for page in page_numbers:
                    match = re.search(r"\d+", page)
                    if match:
                        numeric_pages.append(int(match.group()))
                if numeric_pages:
                    min_page = min(numeric_pages)
                    max_page = max(numeric_pages)
                    page_range = str(min_page) if min_page == max_page else f"{min_page}-{max_page}"
                else:
                    page_range = page_numbers[0] if len(page_numbers) == 1 else f"{page_numbers[0]}-{page_numbers[-1]}"
            except Exception:
                page_range = page_numbers[0] if len(page_numbers) == 1 else f"{page_numbers[0]}-{page_numbers[-1]}"

        status_message = f"Inserted {len(inserted_ids)} rows (IDs: {id_range}, Pages: {page_range})"
        if updated_ids:
            status_message += f"; Updated {len(updated_ids)} duplicate row(s)"

        try:
            tsv_path.unlink()
        except Exception as delete_exc:
            print(f"Warning: Could not delete TSV file {tsv_path}: {delete_exc}")

        return status_message

    except ValueError as exc:
        raise ValueError(f"TSV processing failed: {exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"Unexpected error during TSV processing: {exc}") from exc
    finally:
        try:
            if tsv_path.exists():
                tsv_path.unlink()
        except Exception as delete_exc:
            print(f"Warning: Could not delete TSV file {tsv_path}: {delete_exc}")


# ---------------------------------------------------------------------------
# Column helpers (retained from original implementation)
# ---------------------------------------------------------------------------

def infer_column_types(worksheet, num_columns: int) -> dict[int, type]:
    column_types: dict[int, type] = {}
    return column_types


def match_column(header_row: list[str], keyword_groups: list[tuple[str, ...]], friendly_name: str) -> int:
    """Find a column by matching keywords in header."""
    normalized_headers = []
    for idx, value in enumerate(header_row, start=1):
        text = "" if value is None else str(value).lower()
        normalized_headers.append((idx, text))

    for keywords in keyword_groups:
        for idx, text in normalized_headers:
            if all(keyword in text for keyword in keywords):
                return idx
    raise ValueError(f"Unable to locate column for {friendly_name}. Please ensure the header contains {keyword_groups[0]}.")


def _find_qno_column(header_row: list[str]) -> int:
    """Find the question number column index (1-based)."""
    for idx, value in enumerate(header_row, start=1):
        if value is None:
            continue
        if str(value).strip().lower() == "qno":
            return idx
    raise ValueError("Unable to locate 'Qno' column in the worksheet header. Please ensure the header includes 'Qno'.")


def _find_magazine_column(header_row: list[str]) -> int:
    """Find the magazine column index (1-based)."""
    keyword_groups = [("magazine", "edition"), ("magazine",), ("edition",)]
    return match_column(header_row, keyword_groups, "Magazine")


def _find_question_set_column(header_row: list[str]) -> int:
    """Find the question set column index (1-based)."""
    keyword_groups = [("question", "set"), ("question", "paper"), ("set", "name"), ("set",)]
    return match_column(header_row, keyword_groups, "Question Set")


def _find_page_column(header_row: list[str]) -> int:
    """Find the page number column index (1-based)."""
    keyword_groups = [("page", "no"), ("page", "number"), ("page",), ("pg",)]
    return match_column(header_row, keyword_groups, "Page Number")


def _find_high_level_chapter_column(header_row: list[str]) -> int:
    """Find the High Level Chapter column index (1-based)."""
    keyword_groups = [("high", "level", "chapter"), ("high", "level"), ("chapter",)]
    return match_column(header_row, keyword_groups, "High Level Chapter")


def _find_question_text_column(header_row: list[str]) -> int:
    """Find the question text column index (1-based)."""
    for idx, value in enumerate(header_row, start=1):
        if value is None:
            continue
        text = str(value).strip().lower()
        if not text:
            continue
        if "question" in text and not any(keyword in text for keyword in ("set", "qno", "number", "no", "id")):
            return idx
    raise ValueError("Unable to locate column containing question text.")


def extract_file_metadata(
    rows: list[list[str]],
    magazine_col: int,
    question_set_col: int,
    qno_col: int,
    page_col: int,
) -> tuple[str, list[tuple[str, str, str, str, str, str]]]:
    magazine_identifier = None
    row_signatures: list[tuple[str, str, str, str, str, str]] = []
    seen_row_signatures: set[tuple[str, str, str]] = set()

    for row in rows:
        required_columns = max(magazine_col, question_set_col, qno_col, page_col)
        if len(row) < required_columns:
            raise ValueError("TSV row does not contain all required columns.")

        magazine_value = row[magazine_col - 1].strip()
        if not magazine_value:
            raise ValueError("Magazine edition must be provided for every row.")

        normalized_magazine = normalize_magazine_edition(magazine_value)

        if magazine_identifier is None:
            magazine_identifier = normalized_magazine
        elif magazine_identifier != normalized_magazine:
            raise ValueError(
                "All rows in the TSV must belong to the same magazine edition. "
                "Please split files by edition before importing."
            )

        question_value = row[question_set_col - 1].strip()
        if not question_value:
            raise ValueError("Question set must be provided for every row.")

        qno_value = row[qno_col - 1].strip()
        if not qno_value:
            raise ValueError("Question number must be provided for every row.")

        normalized_qno = normalize_qno(qno_value)
        if not normalized_qno:
            raise ValueError(f"Unable to normalize question number '{qno_value}'.")

        page_value = row[page_col - 1].strip()
        if not page_value:
            raise ValueError("Page number must be provided for every row.")

        normalized_page = normalize_page(page_value)
        if not normalized_page:
            raise ValueError(f"Unable to normalize page number '{page_value}'.")

        combo_signature = (magazine_identifier, normalized_qno, normalized_page)
        if combo_signature in seen_row_signatures:
            raise ValueError(
                "Duplicate question/page detected within TSV for magazine edition "
                f"'{magazine_value}', question number '{qno_value}', page '{page_value}'."
            )
        seen_row_signatures.add(combo_signature)

        row_signatures.append(
            (
                normalized_magazine,
                normalized_qno,
                normalized_page,
                magazine_value,
                qno_value,
                page_value,
            )
        )

    if magazine_identifier is None:
        raise ValueError("Unable to identify magazine edition in the TSV file.")

    return magazine_identifier, row_signatures
