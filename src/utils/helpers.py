"""
Utility functions for text normalization, date parsing, and data validation.
These functions are used throughout the application for consistent data processing.
"""

import csv
import re
import datetime as dt
from decimal import Decimal, InvalidOperation
from pathlib import Path

from config.constants import MONTH_ALIASES


# ============================================================================
# File Validation Functions
# ============================================================================

def validate_tsv(tsv_path: Path) -> None:
    """
    Validate that a TSV file has consistent column counts across all rows.
    
    Args:
        tsv_path: Path to TSV file to validate
        
    Raises:
        ValueError: If file is empty, missing header, or has inconsistent columns
    """
    with tsv_path.open("r", encoding="utf-8", newline="") as tsv_file:
        reader = csv.reader(tsv_file, delimiter="\t")
        header = next(reader, None)
        if header is None:
            raise ValueError(f"{tsv_path.name} is empty or missing a header row.")

        column_count = len(header)
        for line_no, row in enumerate(reader, start=2):
            if len(row) != column_count:
                raise ValueError(
                    f"{tsv_path.name} line {line_no}: expected {column_count} columns but found {len(row)}."
                )


# ============================================================================
# Text Normalization Functions
# ============================================================================

def normalize_text(value: str) -> str:
    """
    Normalize text by converting to lowercase and removing special characters.
    
    Args:
        value: Input string to normalize
        
    Returns:
        Normalized string with only lowercase alphanumeric characters and spaces
    """
    cleaned = re.sub(r"[^a-z0-9]+", " ", value.lower())
    return " ".join(cleaned.split())


def normalize_month_year(value: str) -> str:
    """
    Extract and normalize month-year from a text string.
    Recognizes month names and year formats like '2023', '23, or '23'.
    
    Args:
        value: Input string containing month and/or year
        
    Returns:
        Normalized string in format 'YYYY-MM' or just year if month not found
    """
    lower = value.lower()
    month = None
    
    # Find month using aliases
    for alias, number in MONTH_ALIASES.items():
        if alias in lower:
            month = number
            break

    # Find year (supports formats: 2023, 1999, '23)
    year_match = re.search(r"(20\d{2}|19\d{2}|'\d{2})", lower)
    year = None
    if year_match:
        token = year_match.group(0)
        if token.startswith("'"):
            year = 2000 + int(token.strip("'"))
        else:
            year = int(token)

    # Format result based on what was found
    if month and year:
        return f"{year:04d}-{month:02d}"
    if year and not month:
        return str(year)
    return normalize_text(value)


def normalize_magazine_edition(value: str) -> str:
    """
    Normalize magazine edition string.
    Expected format: "Magazine Name | Month Year"
    
    Args:
        value: Magazine edition string
        
    Returns:
        Normalized string in format "normalized_name|YYYY-MM"
    """
    if not value:
        return ""
    
    # Split by pipe separator
    parts = value.split("|", 1)
    magazine_name = parts[0].strip()
    edition_part = parts[1].strip() if len(parts) > 1 else ""
    
    # Normalize both parts
    normalized_mag_name = normalize_text(magazine_name)
    normalized_edition = normalize_month_year(edition_part or magazine_name)
    
    return f"{normalized_mag_name}|{normalized_edition}"


def normalize_question_set(value: str) -> str:
    """
    Normalize question set name for comparison.
    
    Args:
        value: Question set name
        
    Returns:
        Normalized question set name
    """
    return normalize_text(value)


def normalize_qno(value) -> str:
    """
    Normalize question number for consistent comparison.
    Handles numeric and text question numbers.
    
    Args:
        value: Question number (can be int, float, or string)
        
    Returns:
        Normalized question number as string
    """
    if value is None:
        return ""
    
    # Handle numeric types
    if isinstance(value, (int, float)):
        try:
            return str(int(round(value)))
        except (TypeError, ValueError):
            pass
    
    # Handle string types
    text = str(value).strip()
    if text.isdigit():
        return str(int(text))
    
    cleaned = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return " ".join(cleaned.split())


def normalize_page(value) -> str:
    """
    Normalize page number for consistent comparison.
    
    Args:
        value: Page number
        
    Returns:
        Normalized page number as string
    """
    if value is None:
        return ""
    return normalize_text(str(value))


# ============================================================================
# Excel Column Finding Functions
# ============================================================================

def _find_qno_column(header_row: list[str]) -> int:
    """
    Find the 'Qno' column index in the Excel header.
    
    Args:
        header_row: List of header cell values
        
    Returns:
        1-based column index
        
    Raises:
        ValueError: If column not found
    """
    for idx, value in enumerate(header_row, start=1):
        if value is None:
            continue
        if str(value).strip().lower() == "qno":
            return idx
    raise ValueError("Could not find 'Qno' column in Excel header.")


def match_column(header_row: list[str], keyword_groups: list[tuple[str, ...]], 
                 friendly_name: str) -> int:
    """
    Find a column by matching keywords in header.
    
    Args:
        header_row: List of header cell values
        keyword_groups: List of keyword tuples to match (tries each group in order)
        friendly_name: Descriptive name for error messages
        
    Returns:
        1-based column index
        
    Raises:
        ValueError: If no matching column found
    """
    normalized_headers = []
    for idx, value in enumerate(header_row, start=1):
        text = "" if value is None else str(value).lower()
        normalized_headers.append((idx, text))

    # Try each keyword group
    for keywords in keyword_groups:
        for idx, text in normalized_headers:
            if all(keyword in text for keyword in keywords):
                return idx
    
    raise ValueError(
        f"Unable to locate column for {friendly_name}. "
        f"Please ensure the header contains {keyword_groups[0]}."
    )


def _find_magazine_column(header_row: list[str]) -> int:
    """Find the Magazine Edition column."""
    keyword_groups = [
        ("magazine", "edition"),
        ("magazine", "issue"),
        ("magazine",),
        ("edition",),
    ]
    return match_column(header_row, keyword_groups, "Magazine Edition")


def _find_question_set_column(header_row: list[str]) -> int:
    """Find the Question Set column."""
    keyword_groups = [
        ("question", "set"),
        ("question", "paper"),
        ("set", "name"),
        ("set",),
    ]
    return match_column(header_row, keyword_groups, "Question Set")


def _find_high_level_chapter_column(header_row: list[str]) -> int:
    """Find the High Level Chapter column."""
    keyword_groups = [
        ("high", "level", "chapter"),
        ("high", "level"),
        ("chapter",),
    ]
    return match_column(header_row, keyword_groups, "High Level Chapter")


def _find_question_set_name_column(header_row: list[str]) -> int:
    """Find the 'Name of Question set' column."""
    for idx, value in enumerate(header_row, start=1):
        if value is None:
            continue
        text = str(value).strip().lower()
        if text == "name of question set" or text == "name of the question set":
            return idx
    raise ValueError("Unable to locate 'Name of Question set' column.")


def _find_page_column(header_row: list[str]) -> int:
    """Find the Page Number column."""
    keyword_groups = [
        ("page", "no"),
        ("page", "number"),
        ("page",),
        ("pg",),
    ]
    return match_column(header_row, keyword_groups, "Page Number")


def _find_question_text_column(header_row: list[str]) -> int:
    """
    Find the column containing question text.
    Looks for 'question' but excludes columns with 'set', 'qno', etc.
    """
    for idx, value in enumerate(header_row, start=1):
        if value is None:
            continue
        text = str(value).strip().lower()
        if not text:
            continue
        if "question" in text and not any(
            keyword in text for keyword in ("set", "qno", "number", "no", "id")
        ):
            return idx
    raise ValueError("Unable to locate column containing question text.")


# ============================================================================
# Data Type Conversion Functions
# ============================================================================

def convert_value_for_column(value: str, target_type: type | None, 
                            header_row: list[str], col_idx: int):
    """
    Convert a string value to the appropriate type for an Excel column.
    
    Args:
        value: String value to convert
        target_type: Target Python type (int, float, bool, etc.)
        header_row: Header row for error messages
        col_idx: 1-based column index
        
    Returns:
        Converted value in the target type
        
    Raises:
        ValueError: If conversion fails
    """
    header_label = (header_row[col_idx - 1] if col_idx - 1 < len(header_row) 
                   else f"Column {col_idx}")
    
    # No conversion needed for string or None
    if target_type is None or target_type is str:
        return value

    stripped = value.strip()
    
    # Boolean conversion
    if target_type is bool:
        lowered = stripped.lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
        raise ValueError(
            f"Value '{value}' cannot be interpreted as boolean "
            f"for column '{header_label}'."
        )
    
    # Integer conversion
    if target_type is int:
        try:
            return int(stripped)
        except ValueError:
            try:
                return int(float(stripped))
            except ValueError as exc:
                raise ValueError(
                    f"Value '{value}' cannot be interpreted as integer "
                    f"for column '{header_label}'."
                ) from exc
    
    # Float conversion
    if target_type is float:
        try:
            return float(stripped)
        except ValueError as exc:
            raise ValueError(
                f"Value '{value}' cannot be interpreted as float "
                f"for column '{header_label}'."
            ) from exc
    
    # Decimal conversion
    if target_type is Decimal:
        try:
            return Decimal(stripped)
        except InvalidOperation as exc:
            raise ValueError(
                f"Value '{value}' cannot be interpreted as decimal "
                f"for column '{header_label}'."
            ) from exc
    
    # Datetime conversion
    if isinstance(target_type, type) and issubclass(target_type, dt.datetime):
        try:
            return dt.datetime.fromisoformat(stripped)
        except ValueError as exc:
            raise ValueError(
                f"Value '{value}' is not a valid datetime "
                f"for column '{header_label}'."
            ) from exc
    
    # Date conversion
    if isinstance(target_type, type) and issubclass(target_type, dt.date):
        try:
            return dt.date.fromisoformat(stripped)
        except ValueError as exc:
            raise ValueError(
                f"Value '{value}' is not a valid date "
                f"for column '{header_label}'."
            ) from exc

    return value
