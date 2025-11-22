from __future__ import annotations

import csv
import json
import sys
import datetime as dt
import queue
import re
import threading
import time
from decimal import Decimal, InvalidOperation
from itertools import repeat
from pathlib import Path
from PySide6.QtCore import Qt, QMimeData, QTimer
from PySide6.QtGui import QColor, QPalette, QDrag, QDragEnterEvent, QDropEvent, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from openpyxl import load_workbook
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
PHYSICS_CHAPTER_FILE = BASE_DIR / "physicsCHapters.txt"
PHYSICS_GROUPING_FILE = BASE_DIR / "PhysicsChapterGrouping.json"


MONTH_ALIASES = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def validate_tsv(tsv_path: Path) -> None:
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
            for col_idx, value in enumerate(row, start=1):
                if value.strip() == "":
                    raise ValueError(
                        f"{tsv_path.name} line {line_no} column {col_idx}: value must not be blank."
                    )


def _find_qno_column(header_row: list[str]) -> int:
    for idx, value in enumerate(header_row, start=1):
        if value is None:
            continue
        if str(value).strip().lower() == "qno":
            return idx
    raise ValueError("Could not find 'Qno' column in Excel header.")


def _match_column(header_row: list[str], keyword_groups: list[tuple[str, ...]], friendly_name: str) -> int:
    normalized_headers = []
    for idx, value in enumerate(header_row, start=1):
        text = "" if value is None else str(value).lower()
        normalized_headers.append((idx, text))

    for keywords in keyword_groups:
        for idx, text in normalized_headers:
            if all(keyword in text for keyword in keywords):
                return idx
    raise ValueError(f"Unable to locate column for {friendly_name}. Please ensure the header contains {keyword_groups[0]}.")


def _find_magazine_column(header_row: list[str]) -> int:
    keyword_groups = [
        ("magazine", "edition"),
        ("magazine", "issue"),
        ("magazine",),
        ("edition",),
    ]
    return _match_column(header_row, keyword_groups, "Magazine Edition")


def _find_question_set_column(header_row: list[str]) -> int:
    keyword_groups = [
        ("question", "set"),
        ("question", "paper"),
        ("set", "name"),
        ("set",),
    ]
    return _match_column(header_row, keyword_groups, "Question Set")


def _find_high_level_chapter_column(header_row: list[str]) -> int:
    keyword_groups = [
        ("high", "level", "chapter"),
        ("high", "level"),
        ("chapter",),
    ]
    return _match_column(header_row, keyword_groups, "High Level Chapter")


def _find_page_column(header_row: list[str]) -> int:
    keyword_groups = [
        ("page", "no"),
        ("page", "number"),
        ("page",),
        ("pg",),
    ]
    return _match_column(header_row, keyword_groups, "Page Number")


def _find_question_text_column(header_row: list[str]) -> int:
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


def _find_insert_row(worksheet) -> int:
    """Locate the next empty row by scanning for the last row that contains any value."""

    def _has_value(value) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        return True

    for row_idx in range(worksheet.max_row, 1, -1):
        for cell in worksheet[row_idx]:
            if _has_value(cell.value):
                return row_idx + 1
    return 2


def infer_column_types(worksheet, num_columns: int) -> dict[int, type]:
    column_types: dict[int, type] = {}
    for col_idx in range(1, num_columns + 1):
        for row_idx in range(2, worksheet.max_row + 1):
            value = worksheet.cell(row=row_idx, column=col_idx).value
            if value is not None:
                column_types[col_idx] = type(value)
                break
    return column_types


def convert_value_for_column(value: str, target_type: type | None, header_row: list[str], col_idx: int):
    header_label = header_row[col_idx - 1] if col_idx - 1 < len(header_row) else f"Column {col_idx}"
    if target_type is None or target_type is str:
        return value

    stripped = value.strip()
    if target_type is bool:
        lowered = stripped.lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
        raise ValueError(f"Value '{value}' cannot be interpreted as boolean for column '{header_label}'.")
    if target_type is int:
        try:
            return int(stripped)
        except ValueError:
            try:
                return int(float(stripped))
            except ValueError as exc:
                raise ValueError(f"Value '{value}' cannot be interpreted as integer for column '{header_label}'.") from exc
    if target_type is float:
        try:
            return float(stripped)
        except ValueError as exc:
            raise ValueError(f"Value '{value}' cannot be interpreted as float for column '{header_label}'.") from exc
    if target_type is Decimal:
        try:
            return Decimal(stripped)
        except InvalidOperation as exc:
            raise ValueError(f"Value '{value}' cannot be interpreted as decimal for column '{header_label}'.") from exc
    if isinstance(target_type, type) and issubclass(target_type, dt.datetime):
        try:
            return dt.datetime.fromisoformat(stripped)
        except ValueError as exc:
            raise ValueError(f"Value '{value}' is not a valid datetime for column '{header_label}'.") from exc
    if isinstance(target_type, type) and issubclass(target_type, dt.date):
        try:
            return dt.date.fromisoformat(stripped)
        except ValueError as exc:
            raise ValueError(f"Value '{value}' is not a valid date for column '{header_label}'.") from exc

    return value


def _normalize_text(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", value.lower())
    return " ".join(cleaned.split())


def _normalize_month_year(value: str) -> str:
    lower = value.lower()
    month = None
    for alias, number in MONTH_ALIASES.items():
        if alias in lower:
            month = number
            break

    year_match = re.search(r"(20\d{2}|19\d{2}|'\d{2})", lower)
    year = None
    if year_match:
        token = year_match.group(0)
        if token.startswith("'"):
            year = 2000 + int(token.strip("'"))
        else:
            year = int(token)

    if month and year:
        return f"{year:04d}-{month:02d}"
    if year and not month:
        return str(year)
    return _normalize_text(value)


def normalize_magazine_edition(value: str) -> str:
    if not value:
        return ""
    parts = value.split("|", 1)
    magazine_name = parts[0].strip()
    edition_part = parts[1].strip() if len(parts) > 1 else ""
    normalized_mag_name = _normalize_text(magazine_name)
    normalized_edition = _normalize_month_year(edition_part or magazine_name)
    return f"{normalized_mag_name}|{normalized_edition}"


def normalize_question_set(value: str) -> str:
    return _normalize_text(value)


def normalize_qno(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        try:
            return str(int(round(value)))
        except (TypeError, ValueError):
            pass
    text = str(value).strip()
    if text.isdigit():
        return str(int(text))
    cleaned = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return " ".join(cleaned.split())


def normalize_page(value) -> str:
    if value is None:
        return ""
    return _normalize_text(str(value))


class GroupingChapterListWidget(QListWidget):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.setSelectionMode(QListWidget.SingleSelection)
        self.setDragEnabled(True)

    def startDrag(self, supportedActions) -> None:
        item = self.currentItem()
        if not item:
            return
        chapter = item.data(Qt.UserRole) or item.text()
        mime = QMimeData()
        mime.setText(chapter)
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.MoveAction)


class GroupListWidget(QListWidget):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.setSelectionMode(QListWidget.SingleSelection)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        if not event.mimeData().hasText():
            super().dropEvent(event)
            return
        chapter = event.mimeData().text().strip()
        if not chapter:
            return
        position = event.position().toPoint() if hasattr(event, "position") else event.pos()
        target_item = self.itemAt(position)
        if not target_item:
            target_item = self.currentItem()
        if not target_item:
            return
        group = target_item.data(Qt.UserRole) or target_item.text()
        current_item = self.parent_window.group_list.currentItem()
        source_group = current_item.data(Qt.UserRole) if current_item else None
        self.parent_window.move_chapter_to_group(chapter, group, stay_on_group=source_group)
        event.acceptProposedAction()


class QuestionTableWidget(QTableWidget):
    MIME_TYPE = "application/x-question-row"

    def __init__(self, parent_window):
        super().__init__(0, 4)
        self.parent_window = parent_window
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragOnly)

    def startDrag(self, supportedActions) -> None:
        row = self.currentRow()
        if row < 0 or row >= len(self.parent_window.current_questions):
            return
        question = self.parent_window.current_questions[row]
        payload = json.dumps(
            {
                "row_number": question.get("row_number"),
                "qno": question.get("qno"),
                "question_set": question.get("question_set"),
                "group": question.get("group"),
            }
        )
        mime = QMimeData()
        mime.setData(self.MIME_TYPE, payload.encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.MoveAction)


class ChapterTableWidget(QTableWidget):
    def __init__(self, parent_window):
        super().__init__(0, 2)
        self.parent_window = parent_window
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DropOnly)
        self.setDragEnabled(False)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasFormat(QuestionTableWidget.MIME_TYPE):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasFormat(QuestionTableWidget.MIME_TYPE):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        if not event.mimeData().hasFormat(QuestionTableWidget.MIME_TYPE):
            super().dropEvent(event)
            return
        try:
            payload = bytes(event.mimeData().data(QuestionTableWidget.MIME_TYPE)).decode("utf-8")
            question = json.loads(payload)
        except Exception:
            return

        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        index = self.indexAt(pos)
        if not index.isValid():
            return
        chapter_item = self.item(index.row(), 0)
        if not chapter_item:
            return
        target_group = chapter_item.data(Qt.UserRole) or chapter_item.text()
        self.parent_window.reassign_question(question, target_group)
        event.acceptProposedAction()

def read_tsv_rows(tsv_path: Path) -> list[list[str]]:
    with tsv_path.open("r", encoding="utf-8", newline="") as tsv_file:
        reader = csv.reader(tsv_file, delimiter="\t")
        next(reader, None)  # Skip header
        return [row for row in reader]


def collect_existing_triplets(
    worksheet, magazine_col: int, qno_col: int, page_col: int
) -> dict[tuple[str, str, str], tuple[str, str, str]]:
    triplets: dict[tuple[str, str, str], tuple[str, str, str]] = {}
    for row_idx in range(2, worksheet.max_row + 1):
        magazine_value = worksheet.cell(row=row_idx, column=magazine_col).value
        if not magazine_value:
            continue
        qno_value = worksheet.cell(row=row_idx, column=qno_col).value
        page_value = worksheet.cell(row=row_idx, column=page_col).value
        normalized_magazine = normalize_magazine_edition(str(magazine_value))
        normalized_qno = normalize_qno(qno_value)
        normalized_page = normalize_page(page_value)
        if normalized_qno and normalized_page:
            key = (normalized_magazine, normalized_qno, normalized_page)
            triplets.setdefault(
                key,
                (
                    str(magazine_value),
                    str(qno_value) if qno_value is not None else "",
                    str(page_value) if page_value is not None else "",
                ),
            )
    return triplets


def extract_file_metadata(
    rows: list[list[str]],
    magazine_col: int,
    question_set_col: int,
    qno_col: int,
    page_col: int,
) -> tuple[str, list[tuple[str, str, str, str, str, str, str]]]:
    magazine_identifier = None
    row_signatures: list[tuple[str, str, str, str, str, str, str]] = []
    seen_row_signatures: set[tuple[str, str, str]] = set()
    for row in rows:
        # Guard against short rows
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


def append_rows_to_excel(
    workbook_path: Path,
    worksheet,
    header_row: list[str],
    column_types: dict[int, type],
    rows: list[list[str]],
    insert_row: int,
) -> str:
    appended_rows = 0
    for row in rows:
        for col_idx, value in enumerate(row, start=1):
            target_type = column_types.get(col_idx)
            converted = convert_value_for_column(value, target_type, header_row, col_idx)
            worksheet.cell(row=insert_row, column=col_idx, value=converted)
        insert_row += 1
        appended_rows += 1

    worksheet.parent.save(workbook_path)
    return f"Appended {appended_rows} rows to '{worksheet.title}'"


def process_tsv(tsv_path: Path, workbook_path: Path) -> str:
    try:
        validate_tsv(tsv_path)
        rows = read_tsv_rows(tsv_path)

        if not workbook_path.exists():
            raise FileNotFoundError(f"Workbook not found: {workbook_path}")

        workbook = load_workbook(workbook_path)
        sheet_name = workbook.sheetnames[0]
        worksheet = workbook[sheet_name]

        header_row = [cell.value for cell in next(worksheet.iter_rows(min_row=1, max_row=1))]
        if not header_row:
            raise ValueError("Worksheet header row is empty.")

        qno_column = _find_qno_column(header_row)
        magazine_col = _find_magazine_column(header_row)
        question_set_col = _find_question_set_column(header_row)
        page_col = _find_page_column(header_row)
        insert_row = _find_insert_row(worksheet)

        column_types = infer_column_types(worksheet, len(header_row))
        existing_triplets = collect_existing_triplets(worksheet, magazine_col, qno_column, page_col)

        magazine_identifier, row_signatures = extract_file_metadata(
            rows, magazine_col, question_set_col, qno_column, page_col
        )

        duplicates = []
        for normalized_magazine, normalized_qno, normalized_page, original_mag, original_qno, original_page in row_signatures:
            combo = (normalized_magazine, normalized_qno, normalized_page)
            if combo in existing_triplets:
                existing_mag, existing_qno, existing_page = existing_triplets[combo]
                duplicates.append(
                    (
                        original_mag or existing_mag,
                        original_qno,
                        original_page,
                        existing_qno,
                        existing_page,
                    )
                )

        if duplicates:
            readable = "; ".join(
                f"Magazine '{mag}' Question '{qno}' Page '{page}' already exists (Workbook has Qno '{ex_qno}', Page '{ex_page}')"
                for mag, qno, page, ex_qno, ex_page in duplicates
            )
            raise ValueError(
                "Duplicate questions detected: "
                f"{readable}. Remove or update these entries before importing."
            )

        status_message = append_rows_to_excel(
            workbook_path=workbook_path,
            worksheet=worksheet,
            header_row=header_row,
            column_types=column_types,
            rows=rows,
            insert_row=insert_row,
        )
    except ValueError as exc:
        tsv_path.unlink(missing_ok=True)
        raise ValueError(f"{exc} (file removed due to validation failure)") from exc

    tsv_path.unlink()
    return status_message + " (file removed)"


class TSVWatcherWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("TSV to Excel Watcher")
        self.resize(1200, 820)

        self.event_queue: queue.Queue[tuple] = queue.Queue()
        self.watch_thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.file_rows: dict[str, int] = {}
        self.file_errors: dict[str, str] = {}
        self.metrics_request_id = 0
        self.chapter_questions: dict[str, list[dict[str, str]]] = {}
        self.current_questions: list[dict[str, str]] = []
        self.canonical_chapters = self._load_canonical_chapters()
        self.chapter_lookup: dict[str, str] = {}
        self.chapter_groups = self._load_chapter_grouping()
        self.current_workbook_path: Path | None = None
        self.high_level_column_index: int | None = None

        self._build_ui()
        self._setup_timer()
        self.update_row_count()

    def _build_ui(self) -> None:
        self._apply_palette()
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(14)

        top_card = self._create_card()
        top_layout = QVBoxLayout(top_card)
        top_layout.setSpacing(10)

        self.output_edit = QLineEdit()
        self.output_edit.editingFinished.connect(self.update_row_count)
        output_row = QHBoxLayout()
        output_row.addWidget(self._create_label("Workbook"))
        output_row.addWidget(self.output_edit)
        browse_output = QPushButton("Browse…")
        browse_output.clicked.connect(self.select_output_file)
        output_row.addWidget(browse_output)
        top_layout.addLayout(output_row)

        info_row = QHBoxLayout()
        self.row_count_label = QLabel("Total rows: N/A")
        self.row_count_label.setObjectName("headerLabel")
        self.mag_summary_label = QLabel("Magazines: N/A")
        self.mag_summary_label.setObjectName("infoLabel")
        self.mag_missing_label = QLabel("Missing ranges: N/A")
        self.mag_missing_label.setObjectName("infoLabel")
        info_row.addWidget(self.row_count_label)
        info_row.addStretch()
        info_row.addWidget(self.mag_summary_label)
        info_row.addWidget(self.mag_missing_label)
        top_layout.addLayout(info_row)
        root_layout.addWidget(top_card)

        tab_widget = QTabWidget()
        root_layout.addWidget(tab_widget, 1)

        qa_tab = QWidget()
        qa_layout = QVBoxLayout(qa_tab)
        qa_tabs = QTabWidget()
        qa_layout.addWidget(qa_tabs)

        magazine_tab = QWidget()
        magazine_tab_layout = QVBoxLayout(magazine_tab)
        mag_card = self._create_card()
        magazine_tab_layout.addWidget(mag_card)
        mag_layout = QVBoxLayout(mag_card)
        mag_layout.addWidget(self._create_label("Magazine Editions"))
        mag_split = QSplitter(Qt.Horizontal)
        mag_layout.addWidget(mag_split, 1)

        self.mag_tree = QTreeWidget()
        self.mag_tree.setColumnCount(3)
        self.mag_tree.setHeaderLabels(["Magazine", "Edition", "Missing Ranges"])
        self.mag_tree.setRootIsDecorated(False)
        self.mag_tree.itemSelectionChanged.connect(self.on_magazine_select)
        self.mag_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        mag_split.addWidget(self.mag_tree)

        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        self.question_label = QLabel("Select a workbook to display magazine editions.")
        self.question_label.setObjectName("infoLabel")
        detail_layout.addWidget(self.question_label)
        self.question_list = QListWidget()
        detail_layout.addWidget(self.question_list)
        mag_split.addWidget(detail_widget)
        qa_tabs.addTab(magazine_tab, "Magazine Editions")

        questions_tab = QWidget()
        questions_tab_layout = QVBoxLayout(questions_tab)
        analysis_card = self._create_card()
        questions_tab_layout.addWidget(analysis_card)
        analysis_layout = QVBoxLayout(analysis_card)
        analysis_split = QSplitter(Qt.Horizontal)
        analysis_layout.addWidget(analysis_split, 1)

        chapter_card = self._create_card()
        chapter_layout = QVBoxLayout(chapter_card)
        chapter_layout.addWidget(self._create_label("Chapters"))
        self.chapter_table = ChapterTableWidget(self)
        self.chapter_table.setHorizontalHeaderLabels(["Chapter", "Questions"])
        self.chapter_table.horizontalHeader().setStretchLastSection(False)
        self.chapter_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.chapter_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.chapter_table.verticalHeader().setVisible(False)
        self.chapter_table.itemSelectionChanged.connect(self.on_chapter_selected)
        chapter_layout.addWidget(self.chapter_table)
        analysis_split.addWidget(chapter_card)

        question_card = self._create_card()
        question_layout = QVBoxLayout(question_card)
        question_layout.addWidget(self._create_label("Questions"))
        self.question_table = QuestionTableWidget(self)
        self.question_table.setHorizontalHeaderLabels(["Question No", "Page", "Question Set Name", "Magazine"])
        self.question_table.horizontalHeader().setStretchLastSection(True)
        self.question_table.verticalHeader().setVisible(False)
        self.question_table.itemSelectionChanged.connect(self.on_question_selected)
        question_splitter = QSplitter(Qt.Vertical)
        question_splitter.addWidget(self.question_table)
        question_layout.addWidget(self._create_label("Question Text"))
        self.question_text_view = QTextEdit()
        self.question_text_view.setReadOnly(True)
        question_splitter.addWidget(self.question_text_view)
        question_splitter.setStretchFactor(0, 3)
        question_splitter.setStretchFactor(1, 1)
        question_splitter.setSizes([400, 120])
        question_layout.addWidget(question_splitter)
        analysis_split.addWidget(question_card)
        qa_tabs.addTab(questions_tab, "Question List")

        grouping_tab = QWidget()
        grouping_layout = QVBoxLayout(grouping_tab)
        grouping_card = self._create_card()
        grouping_layout.addWidget(grouping_card)
        grouping_card_layout = QHBoxLayout(grouping_card)

        self.group_list = GroupListWidget(self)
        self.group_list.itemSelectionChanged.connect(self.on_group_selected)
        grouping_card_layout.addWidget(self.group_list, 1)

        self.group_chapter_list = GroupingChapterListWidget(self)
        grouping_card_layout.addWidget(self.group_chapter_list, 2)

        group_controls = QVBoxLayout()
        group_controls.addWidget(self._create_label("Move chapter to group"))
        self.move_target_combo = QComboBox()
        group_controls.addWidget(self.move_target_combo)
        move_button = QPushButton("Move Chapter")
        move_button.clicked.connect(self.move_selected_chapter)
        group_controls.addWidget(move_button)
        group_controls.addStretch()
        grouping_card_layout.addLayout(group_controls)
        qa_tabs.addTab(grouping_tab, "Chapter Grouping")
        tab_widget.addTab(qa_tab, "Question Analysis")

        import_tab = QWidget()
        import_layout = QVBoxLayout(import_tab)

        import_form_card = self._create_card()
        import_form_layout = QVBoxLayout(import_form_card)
        self.input_edit = QLineEdit()
        self.input_edit.editingFinished.connect(self.refresh_file_list)
        input_row = QHBoxLayout()
        input_row.addWidget(self._create_label("Input folder"))
        input_row.addWidget(self.input_edit)
        browse_input = QPushButton("Browse…")
        browse_input.clicked.connect(self.select_input_folder)
        input_row.addWidget(browse_input)
        import_form_layout.addLayout(input_row)

        control_layout = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh Files")
        self.refresh_button.clicked.connect(self.refresh_file_list)
        self.start_button = QPushButton("Start Watching")
        self.start_button.clicked.connect(self.start_watching)
        self.stop_button = QPushButton("Stop Watching")
        self.stop_button.clicked.connect(self.stop_watching)
        control_layout.addWidget(self.refresh_button)
        control_layout.addWidget(self.start_button)
        control_layout.addWidget(self.stop_button)
        control_layout.addStretch()
        import_form_layout.addLayout(control_layout)
        import_layout.addWidget(import_form_card)

        status_card = self._create_card()
        status_layout = QVBoxLayout(status_card)
        status_layout.addWidget(self._create_label("Upload Status"))
        self.file_table = QTableWidget(0, 3)
        self.file_table.setHorizontalHeaderLabels(["File", "Status", "Message"])
        self.file_table.horizontalHeader().setStretchLastSection(True)
        self.file_table.verticalHeader().setVisible(False)
        self.file_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.file_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.file_table.cellDoubleClicked.connect(self.on_file_double_clicked)
        status_layout.addWidget(self.file_table)
        import_layout.addWidget(status_card)

        tab_widget.addTab(import_tab, "Data Import")

        self.log_toggle = QPushButton("Show Log")
        self.log_toggle.setCheckable(True)
        self.log_toggle.toggled.connect(self.toggle_log_visibility)
        root_layout.addWidget(self.log_toggle, 0, alignment=Qt.AlignLeft)

        self.log_card = self._create_card()
        log_layout = QVBoxLayout(self.log_card)
        log_layout.addWidget(self._create_label("Log"))
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setObjectName("logView")
        log_layout.addWidget(self.log_view)
        root_layout.addWidget(self.log_card, 0)
        self.log_card.setVisible(False)
        self._refresh_grouping_ui()

    def _apply_palette(self) -> None:
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor("#f4f5f9"))
        palette.setColor(QPalette.Base, QColor("#ffffff"))
        palette.setColor(QPalette.Text, QColor("#0f172a"))
        palette.setColor(QPalette.Button, QColor("#2563eb"))
        palette.setColor(QPalette.ButtonText, QColor("#ffffff"))
        self.setPalette(palette)
        self.setStyleSheet(
            """
            QWidget#card {
                background-color: #ffffff;
                border-radius: 14px;
                padding: 12px;
            }
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:disabled {
                background-color: #94a3b8;
            }
            QLabel#headerLabel {
                font-weight: 600;
                color: #0f172a;
            }
            QLabel#infoLabel {
                color: #475569;
            }
            QTreeWidget, QTableWidget, QListWidget {
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                background-color: #ffffff;
                color: #0f172a;
                alternate-background-color: #f8fafc;
            }
            QTreeWidget::item:selected, QTableWidget::item:selected, QListWidget::item:selected {
                background-color: #d0e2ff;
                color: #0f172a;
            }
            QTextEdit#logView {
                background-color: #0f172a;
                color: #e2e8f0;
                border-radius: 8px;
                padding: 8px;
                font-family: Consolas, 'Courier New', monospace;
            }
            """
        )

    def _create_card(self) -> QWidget:
        card = QWidget()
        card.setObjectName("card")
        return card

    def _create_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("headerLabel")
        return label

    def toggle_log_visibility(self, checked: bool) -> None:
        self.log_card.setVisible(checked)
        self.log_toggle.setText("Hide Log" if checked else "Show Log")

    def _load_canonical_chapters(self) -> list[str]:
        if not PHYSICS_CHAPTER_FILE.exists():
            return []
        chapters: list[str] = []
        for line in PHYSICS_CHAPTER_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or not line.startswith("-"):
                continue
            chapter = line.lstrip("-").strip()
            if chapter:
                chapters.append(chapter)
        return chapters

    def _load_chapter_grouping(self) -> dict[str, list[str]]:
        if PHYSICS_GROUPING_FILE.exists():
            try:
                data = json.loads(PHYSICS_GROUPING_FILE.read_text(encoding="utf-8"))
                groups = data.get("groups", {})
            except json.JSONDecodeError:
                groups = {}
        else:
            groups = {}
        for group in self.canonical_chapters:
            groups.setdefault(group, [])
        groups.setdefault("Others", [])
        # Remove duplicates while preserving order
        for key, values in list(groups.items()):
            seen = set()
            unique = []
            for value in values:
                if value not in seen:
                    unique.append(value)
                    seen.add(value)
            groups[key] = unique
        self._rebuild_chapter_lookup(groups)
        return groups

    def _save_chapter_grouping(self) -> None:
        data = {
            "canonical_order": self.canonical_chapters,
            "groups": self.chapter_groups,
        }
        PHYSICS_GROUPING_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self._rebuild_chapter_lookup(self.chapter_groups)

    def _ordered_groups(self) -> list[str]:
        order = list(self.canonical_chapters)
        if "Others" not in order:
            order.append("Others")
        return order

    def _rebuild_chapter_lookup(self, groups: dict[str, list[str]]) -> None:
        lookup: dict[str, str] = {}
        for group, values in groups.items():
            norm_group = self._normalize_label(group)
            if norm_group:
                lookup[norm_group] = group
            for value in values:
                norm_value = self._normalize_label(value)
                if norm_value and norm_value not in lookup:
                    lookup[norm_value] = group
        self.chapter_lookup = lookup

    def _refresh_grouping_ui(self) -> None:
        if not hasattr(self, "group_list"):
            return
        self.group_list.blockSignals(True)
        self.group_list.clear()
        for group in self._ordered_groups():
            chapters = self.chapter_groups.get(group, [])
            item = QListWidgetItem(f"{group} ({len(chapters)})")
            item.setData(Qt.UserRole, group)
            self.group_list.addItem(item)
        self.group_list.blockSignals(False)
        if hasattr(self, "move_target_combo"):
            self.move_target_combo.clear()
            self.move_target_combo.addItems(self._ordered_groups())
        if hasattr(self, "group_chapter_list"):
            self.group_chapter_list.clear()

    def _select_group_in_ui(self, group: str) -> None:
        if not hasattr(self, "group_list"):
            return
        for row in range(self.group_list.count()):
            item = self.group_list.item(row)
            if (item.data(Qt.UserRole) or item.text()).startswith(group):
                self.group_list.setCurrentRow(row)
                break

    def _setup_timer(self) -> None:
        self.queue_timer = QTimer(self)
        self.queue_timer.setInterval(200)
        self.queue_timer.timeout.connect(self._process_queue)
        self.queue_timer.start()

    def update_row_count(self) -> None:
        workbook_path = Path(self.output_edit.text().strip())
        if not workbook_path.is_file():
            self.row_count_label.setText("Total rows: N/A")
            self._set_magazine_summary("Magazines: N/A", "Missing ranges: N/A")
            self._populate_magazine_tree([])
            self._populate_question_sets([])
            self.question_label.setText("Select a workbook to display magazine editions.")
            self.current_workbook_path = None
            self.high_level_column_index = None
            return

        self.current_workbook_path = workbook_path
        self.row_count_label.setText("Total rows: Loading...")
        self._set_magazine_summary("Magazines: Loading...", "Tracked editions: Loading...")
        self._populate_magazine_tree([])
        self._populate_question_sets([])
        self.question_label.setText("Loading editions...")
        self.metrics_request_id += 1
        request_id = self.metrics_request_id

        def worker(path: Path, req_id: int) -> None:
            try:
                # Pandas is used here to keep the UI responsive while gathering workbook metrics.
                df = pd.read_excel(path, sheet_name=0, dtype=object)
                row_count = self._compute_row_count_from_df(df)
                magazine_details, warnings = self._collect_magazine_details(df)
                chapter_data, qa_warnings, question_col, raw_chapter_inputs = self._collect_question_analysis_data(df)
                warnings.extend(qa_warnings)
                self.event_queue.put(
                    (
                        "metrics",
                        req_id,
                        row_count,
                        magazine_details,
                        warnings,
                        chapter_data,
                        question_col,
                        raw_chapter_inputs,
                    )
                )
            except Exception as exc:
                self.event_queue.put(("metrics_error", req_id, str(exc)))

        threading.Thread(target=worker, args=(workbook_path, request_id), daemon=True).start()

    def _set_magazine_summary(self, primary: str, secondary: str) -> None:
        self.mag_summary_label.setText(primary)
        self.mag_missing_label.setText(secondary)

    def _collect_magazine_details(self, df: pd.DataFrame) -> tuple[list[dict], list[str]]:
        warnings: list[str] = []
        if df.empty:
            return [], warnings

        header_row = [None if pd.isna(col) else str(col) for col in df.columns]
        try:
            magazine_col = _find_magazine_column(header_row)
        except ValueError:
            warnings.append("Unable to determine magazine column for summary display.")
            return [], warnings

        question_set_col = None
        try:
            question_set_col = _find_question_set_column(header_row)
        except ValueError:
            warnings.append("Unable to determine question set column; question sets will not be listed.")

        coverage: dict[str, dict[str, object]] = {}
        magazine_series = df.iloc[:, magazine_col - 1]
        question_series = (
            df.iloc[:, question_set_col - 1] if question_set_col is not None else repeat(None, len(df))
        )
        for magazine_value, question_value in zip(magazine_series, question_series):
            if pd.isna(magazine_value):
                continue
            text = str(magazine_value).strip()
            if not text:
                continue
            display_parts = [part.strip() for part in text.split("|", 1)]
            display_name = display_parts[0] or "Unknown"
            display_edition = display_parts[1] if len(display_parts) > 1 else ""
            normalized = normalize_magazine_edition(text)
            norm_parts = normalized.split("|", 1)
            norm_name = norm_parts[0]
            norm_edition = norm_parts[1] if len(norm_parts) > 1 else ""
            entry = coverage.setdefault(
                norm_name,
                {
                    "display_name": display_name,
                    "editions": {},
                    "normalized_editions": set(),
                },
            )
            edition_label = display_edition or "(unspecified)"
            edition_entry = entry["editions"].setdefault(
                norm_edition,
                {
                    "display": edition_label,
                    "question_sets": set(),
                },
            )
            if question_set_col is not None and not pd.isna(question_value):
                q_text = str(question_value).strip()
                if q_text:
                    edition_entry["question_sets"].add(q_text)
            entry["normalized_editions"].add(norm_edition)

        if not coverage:
            return [], warnings

        details: list[dict] = []
        for norm_name in sorted(coverage.keys(), key=lambda key: str(coverage[key]["display_name"]).lower()):
            data = coverage[norm_name]
            edition_items = []
            for norm_edition, edition_data in sorted(
                data["editions"].items(),
                key=lambda item: self._edition_sort_key(item[0], item[1]["display"]),
            ):
                question_sets = sorted(edition_data["question_sets"], key=lambda value: value.lower())
                edition_items.append(
                    {
                        "display": edition_data["display"],
                        "normalized": norm_edition,
                        "question_sets": question_sets,
                    }
                )
            missing_ranges = self._compute_missing_ranges(data["normalized_editions"])
            details.append(
                {
                    "display_name": data["display_name"],
                    "missing_ranges": missing_ranges,
                    "editions": edition_items,
                }
            )
        return details, warnings

    def _collect_question_analysis_data(
        self, df: pd.DataFrame
    ) -> tuple[dict[str, list[dict]], list[str], int | None, list[str]]:
        warnings: list[str] = []
        if df.empty:
            return {}, warnings, None, []

        header_row = [None if pd.isna(col) else str(col) for col in df.columns]
        try:
            question_set_col = _find_high_level_chapter_column(header_row)
            qno_col = _find_qno_column(header_row)
            page_col = _find_page_column(header_row)
        except ValueError as exc:
            warnings.append(f"Question analysis unavailable: {exc}")
            return {}, warnings, None, []

        question_text_col = None
        try:
            question_text_col = _find_question_text_column(header_row)
        except ValueError as exc:
            warnings.append(str(exc))

        magazine_col = None
        try:
            magazine_col = _find_magazine_column(header_row)
        except ValueError as exc:
            warnings.append(str(exc))

        def normalize(value) -> str:
            if pd.isna(value):
                return ""
            text = str(value).strip()
            return text

        chapters: dict[str, list[dict]] = {}
        raw_inputs: set[str] = set()
        for row_number, row in enumerate(df.itertuples(index=False, name=None), start=2):
            values = list(row)
            raw_chapter_name = normalize(values[question_set_col - 1])
            if not raw_chapter_name:
                continue
            raw_inputs.add(raw_chapter_name)
            chapter_name = self._match_chapter_group(raw_chapter_name)
            qno_value = normalize(values[qno_col - 1])
            page_value = normalize(values[page_col - 1])
            question_text = normalize(values[question_text_col - 1]) if question_text_col else ""
            magazine_value = normalize(values[magazine_col - 1]) if magazine_col else ""

            chapters.setdefault(chapter_name, []).append(
                {
                    "group": chapter_name,
                    "question_set": raw_chapter_name,
                    "qno": qno_value,
                    "page": page_value,
                    "magazine": magazine_value,
                    "text": question_text,
                    "row_number": row_number,
                }
            )

        return chapters, warnings, question_set_col, sorted(raw_inputs)

    def _normalize_label(self, label: str) -> str:
        return re.sub(r"\s+", " ", label.strip().lower())

    def _auto_assign_chapters(self, chapters: list[str]) -> None:
        changed = False
        existing = {
            self._normalize_label(ch)
            for values in self.chapter_groups.values()
            for ch in values
        }
        for chapter in chapters:
            normalized = self._normalize_label(chapter)
            if not normalized or normalized in existing:
                continue
            target = self._match_chapter_group(chapter)
            self.chapter_groups.setdefault(target, []).append(chapter)
            existing.add(normalized)
            changed = True
        if changed:
            self._save_chapter_grouping()
            self._refresh_grouping_ui()

    def _match_chapter_group(self, chapter: str) -> str:
        normalized = self._normalize_label(chapter)
        if not normalized:
            return "Others"
        direct = self.chapter_lookup.get(normalized)
        if direct:
            return direct
        for norm_value, group in self.chapter_lookup.items():
            if norm_value in normalized or normalized in norm_value:
                return group
        for group in self.canonical_chapters:
            norm_group = self._normalize_label(group)
            if normalized == norm_group:
                return group
        for group in self.canonical_chapters:
            norm_group = self._normalize_label(group)
            if norm_group in normalized or normalized in norm_group:
                return group
        return "Others"

    def _compute_row_count_from_df(self, df: pd.DataFrame) -> int:
        def row_has_value(row) -> bool:
            for value in row:
                if isinstance(value, str):
                    if value.strip():
                        return True
                    continue
                if pd.isna(value):
                    continue
                return True
            return False

        for idx in range(len(df) - 1, -1, -1):
            if row_has_value(df.iloc[idx]):
                return idx + 2  # DataFrame row index is zero-based, Excel rows start at 2 after header.
        return 1

    def _compute_missing_ranges(self, normalized_editions: set[str]) -> list[str]:
        monthly_tokens = sorted(
            {
                token
                for token in normalized_editions
                if re.fullmatch(r"\d{4}-\d{2}", token)
            }
        )
        if len(monthly_tokens) < 2:
            return []

        months = [dt.date(int(token[:4]), int(token[5:7]), 1) for token in monthly_tokens]
        present_keys = set(monthly_tokens)
        missing_ranges: list[str] = []
        current = months[0]
        last = months[-1]
        missing_start: dt.date | None = None

        while current <= last:
            key = current.strftime("%Y-%m")
            if key not in present_keys:
                if missing_start is None:
                    missing_start = current
            else:
                if missing_start is not None:
                    end = self._previous_month(current)
                    missing_ranges.append(self._format_range(missing_start, end))
                    missing_start = None
            current = self._add_month(current)

        if missing_start is not None:
            missing_ranges.append(self._format_range(missing_start, last))
        return missing_ranges

    def _add_month(self, date_value: dt.date) -> dt.date:
        if date_value.month == 12:
            return dt.date(date_value.year + 1, 1, 1)
        return dt.date(date_value.year, date_value.month + 1, 1)

    def _previous_month(self, date_value: dt.date) -> dt.date:
        if date_value.month == 1:
            return dt.date(date_value.year - 1, 12, 1)
        return dt.date(date_value.year, date_value.month - 1, 1)

    def _format_range(self, start: dt.date, end: dt.date) -> str:
        if start == end:
            return start.strftime("%b %Y")
        return f"{start.strftime('%b %Y')} - {end.strftime('%b %Y')}"

    def _parse_normalized_month(self, normalized: str) -> dt.date | None:
        if normalized and re.fullmatch(r"\d{4}-\d{2}", normalized):
            return dt.date(int(normalized[:4]), int(normalized[5:7]), 1)
        return None

    def _edition_sort_key(self, normalized: str, display_label: str) -> tuple:
        parsed = self._parse_normalized_month(normalized)
        if parsed:
            return (0, -parsed.toordinal(), display_label.lower())
        return (1, display_label.lower(), "")

    def _populate_magazine_tree(self, details: list[dict]) -> None:
        if not hasattr(self, "mag_tree"):
            return
        self.mag_tree.clear()
        if not details:
            return

        for entry in details:
            missing_text = ", ".join(entry["missing_ranges"]) if entry["missing_ranges"] else "None"
            parent = QTreeWidgetItem([entry["display_name"], "", missing_text])
            parent.setData(0, Qt.UserRole, {"type": "magazine", "display_name": entry["display_name"]})
            self.mag_tree.addTopLevelItem(parent)
            for edition in entry["editions"]:
                edition_label = edition["display"] or "(unspecified)"
                question_sets = edition["question_sets"]
                edition_value = (
                    f"{edition_label} ({len(question_sets)} set(s))" if question_sets else edition_label
                )
                child = QTreeWidgetItem(["", edition_value, ""])
                data = {
                    "type": "edition",
                    "display_name": entry["display_name"],
                    "edition_label": edition_label,
                    "question_sets": question_sets,
                }
                child.setData(0, Qt.UserRole, data)
                parent.addChild(child)
        self.mag_tree.expandAll()

    def _populate_question_sets(self, question_sets: list[str] | None) -> None:
        if not hasattr(self, "question_list"):
            return
        self.question_list.clear()
        if not question_sets:
            return
        for name in question_sets:
            QListWidgetItem(name, self.question_list)

    def _populate_chapter_list(self, chapters: dict[str, list[dict]]) -> None:
        if not hasattr(self, "chapter_table"):
            return
        self.chapter_questions = chapters or {}
        self.chapter_table.setRowCount(0)
        self.question_table.setRowCount(0)
        self.question_text_view.clear()
        if not self.chapter_questions:
            return
        sorted_chapters = sorted(
            self.chapter_questions.items(),
            key=lambda kv: (-len(kv[1]), kv[0].lower()),
        )
        self.chapter_table.setRowCount(len(sorted_chapters))
        for row, (chapter, questions) in enumerate(sorted_chapters):
            name_item = QTableWidgetItem(chapter)
            name_item.setData(Qt.UserRole, chapter)
            count_item = QTableWidgetItem(str(len(questions)))
            count_item.setTextAlignment(Qt.AlignCenter)
            self.chapter_table.setItem(row, 0, name_item)
            self.chapter_table.setItem(row, 1, count_item)
        self.chapter_table.resizeColumnToContents(0)
        self.chapter_table.resizeColumnToContents(1)
        if self.chapter_table.rowCount() > 0:
            self.chapter_table.selectRow(0)

    def _populate_question_table(self, questions: list[dict]) -> None:
        if not hasattr(self, "question_table"):
            return
        self.current_questions = questions or []
        self.question_table.setRowCount(0)
        self.question_text_view.clear()
        if not questions:
            return
        self.question_table.setRowCount(len(questions))
        for row, question in enumerate(questions):
            self.question_table.setItem(row, 0, QTableWidgetItem(question.get("qno", "")))
            self.question_table.setItem(row, 1, QTableWidgetItem(question.get("page", "")))
            self.question_table.setItem(row, 2, QTableWidgetItem(question.get("question_set", "")))
            self.question_table.setItem(row, 3, QTableWidgetItem(question.get("magazine", "")))
        self.question_table.resizeColumnsToContents()
        self.question_table.selectRow(0)

    def on_magazine_select(self) -> None:
        selected = self.mag_tree.selectedItems()
        if not selected:
            self.question_label.setText("Select an edition to view question sets.")
            self._populate_question_sets([])
            return
        item = selected[0]
        data = item.data(0, Qt.UserRole)
        if not isinstance(data, dict) or data.get("type") != "edition":
            self.question_label.setText("Select an edition to view question sets.")
            self._populate_question_sets([])
            return

        question_sets = data.get("question_sets", [])
        label = f"{data.get('display_name', 'Magazine')} - {data.get('edition_label', 'Edition')}"
        if question_sets:
            self.question_label.setText(f"{label} ({len(question_sets)} set(s))")
            self._populate_question_sets(question_sets)
        else:
            self.question_label.setText(f"{label} (no question sets)")
            self._populate_question_sets([])

    def on_group_selected(self) -> None:
        if not hasattr(self, "group_list"):
            return
        item = self.group_list.currentItem()
        self.group_chapter_list.clear()
        if not item:
            return
        group = item.data(Qt.UserRole) or item.text()
        for chapter in sorted(self.chapter_groups.get(group, []), key=lambda value: value.lower()):
            chapter_item = QListWidgetItem(chapter)
            chapter_item.setData(Qt.UserRole, chapter)
            self.group_chapter_list.addItem(chapter_item)

    def move_selected_chapter(self) -> None:
        group_item = getattr(self, "group_list", None)
        chapter_list = getattr(self, "group_chapter_list", None)
        target_combo = getattr(self, "move_target_combo", None)
        if (
            not group_item
            or not chapter_list
            or not target_combo
            or not group_item.currentItem()
            or not chapter_list.currentItem()
        ):
            return
        current_group = group_item.currentItem().data(Qt.UserRole)
        chapter_name = chapter_list.currentItem().data(Qt.UserRole)
        target_group = target_combo.currentText()
        if not chapter_name or not target_group or current_group == target_group:
            return
        self.move_chapter_to_group(chapter_name, target_group)

    def move_chapter_to_group(self, chapter_name: str, target_group: str, stay_on_group: str | None = None) -> None:
        if not chapter_name or not target_group:
            return
        for group, values in self.chapter_groups.items():
            if chapter_name in values:
                values.remove(chapter_name)
                break
        self.chapter_groups.setdefault(target_group, [])
        if chapter_name not in self.chapter_groups[target_group]:
            self.chapter_groups[target_group].append(chapter_name)
        self._save_chapter_grouping()
        self._refresh_grouping_ui()
        self._select_group_in_ui(stay_on_group or target_group)
        self.on_group_selected()

    def reassign_question(self, question: dict, target_group: str) -> None:
        if not question or not target_group:
            return
        if self.current_workbook_path is None or self.high_level_column_index is None:
            QMessageBox.warning(self, "Unavailable", "Workbook must be loaded before regrouping questions.")
            return
        old_group = question.get("group")
        if old_group == target_group:
            return
        row_number = question.get("row_number")
        if not isinstance(row_number, int):
            QMessageBox.warning(self, "Unavailable", "Question row information is missing.")
            return
        qno = question.get("qno", "")
        prompt = f"Move question '{qno}' to '{target_group}'?"
        if QMessageBox.question(self, "Confirm Reassignment", prompt) != QMessageBox.Yes:
            return
        try:
            workbook = load_workbook(self.current_workbook_path)
            sheet = workbook[workbook.sheetnames[0]]
            sheet.cell(row=row_number, column=self.high_level_column_index, value=target_group)
            workbook.save(self.current_workbook_path)
        except Exception as exc:
            QMessageBox.critical(self, "Update Failed", f"Unable to update workbook: {exc}")
            return
        self.log(f"Question '{qno}' moved to '{target_group}'. Reloading data...")
        self.update_row_count()

    def on_chapter_selected(self) -> None:
        if not hasattr(self, "chapter_table"):
            return
        row = self.chapter_table.currentRow()
        if row < 0:
            self._populate_question_table([])
            return
        item = self.chapter_table.item(row, 0)
        if not item:
            self._populate_question_table([])
            return
        chapter_key = item.data(Qt.UserRole) or item.text()
        questions = self.chapter_questions.get(chapter_key, [])
        self._populate_question_table(questions)

    def on_question_selected(self) -> None:
        if not hasattr(self, "question_table"):
            return
        selection_model = self.question_table.selectionModel()
        if selection_model is None:
            self.question_text_view.clear()
            return
        selected_rows = selection_model.selectedRows()
        if not selected_rows:
            self.question_text_view.clear()
            return
        row = selected_rows[0].row()
        if 0 <= row < len(self.current_questions):
            self.question_text_view.setPlainText(self.current_questions[row].get("text", ""))
        else:
            self.question_text_view.clear()

    def log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.log_view.append(f"[{timestamp}] {message}")
        self.log_view.moveCursor(QTextCursor.End)

    def select_input_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Input Folder")
        if folder:
            self.input_edit.setText(folder)
            self.refresh_file_list()

    def select_output_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Excel Workbook",
            "",
            "Excel files (*.xlsx)",
        )
        if file_path:
            self.output_edit.setText(file_path)
            self.update_row_count()

    def refresh_file_list(self) -> None:
        input_path = Path(self.input_edit.text().strip())
        if not input_path.exists():
            self.log("Input folder does not exist.")
            return

        tsv_files = sorted(input_path.glob("*.tsv"))
        for tsv_file in tsv_files:
            self._ensure_row(tsv_file.name)
        self.log(f"Found {len(tsv_files)} TSV file(s) in input folder.")

    def _ensure_row(self, filename: str) -> int:
        row = self.file_rows.get(filename)
        if row is not None:
            return row
        row = self.file_table.rowCount()
        self.file_table.insertRow(row)
        self.file_table.setItem(row, 0, QTableWidgetItem(filename))
        self.file_table.setItem(row, 1, QTableWidgetItem("Pending"))
        self.file_table.setItem(row, 2, QTableWidgetItem("Awaiting processing"))
        self.file_rows[filename] = row
        return row

    def update_file_status(self, filename: str, status: str, message: str) -> None:
        row = self._ensure_row(filename)
        for col, value in enumerate((filename, status, message)):
            item = self.file_table.item(row, col)
            if item is None:
                item = QTableWidgetItem(value)
                self.file_table.setItem(row, col, item)
            else:
                item.setText(value)
        if status.lower() == "error":
            self.file_errors[filename] = message
        else:
            self.file_errors.pop(filename, None)

    def on_file_double_clicked(self, row: int, column: int) -> None:  # noqa: ARG002
        filename_item = self.file_table.item(row, 0)
        status_item = self.file_table.item(row, 1)
        message_item = self.file_table.item(row, 2)
        if not filename_item or not status_item:
            return
        if status_item.text().lower() != "error":
            return
        filename = filename_item.text()
        detail = self.file_errors.get(filename, message_item.text() if message_item else "")
        QMessageBox.critical(self, "Validation Error", f"{filename}\n\n{detail}")

    def start_watching(self) -> None:
        if self.watch_thread and self.watch_thread.is_alive():
            QMessageBox.information(self, "Watcher", "Watcher is already running.")
            return

        input_path = Path(self.input_edit.text().strip())
        workbook_path = Path(self.output_edit.text().strip())

        if not input_path.is_dir():
            QMessageBox.critical(self, "Invalid Input", "Please select a valid input folder.")
            return
        if not workbook_path.is_file():
            QMessageBox.critical(self, "Invalid Workbook", "Please select an existing Excel workbook.")
            return

        self.stop_event.clear()
        self.watch_thread = threading.Thread(
            target=self._watch_loop, args=(input_path, workbook_path), daemon=True
        )
        self.watch_thread.start()
        self.start_button.setEnabled(False)
        self.log("Started watching for TSV files.")

    def stop_watching(self) -> None:
        self.stop_event.set()
        if self.watch_thread and self.watch_thread.is_alive():
            self.watch_thread.join(timeout=0.1)
        self.start_button.setEnabled(True)
        self.log("Stopped watching.")

    def _watch_loop(self, input_dir: Path, workbook_path: Path) -> None:
        poll_interval = 3.0
        while not self.stop_event.is_set():
            tsv_files = sorted(input_dir.glob("*.tsv"))
            if not tsv_files:
                time.sleep(poll_interval)
                continue

            for tsv_file in tsv_files:
                if self.stop_event.is_set():
                    break
                self.event_queue.put(("status", tsv_file.name, "Processing", "Validating..."))
                try:
                    result_message = process_tsv(tsv_file, workbook_path)
                except Exception as exc:
                    self.event_queue.put(("status", tsv_file.name, "Error", str(exc)))
                    self.event_queue.put(("log", f"Error processing {tsv_file.name}: {exc}"))
                else:
                    self.event_queue.put(("status", tsv_file.name, "Completed", result_message))
                    self.event_queue.put(("log", f"Processed {tsv_file.name}: {result_message}"))
                    self.event_queue.put(("rowcount",))

            time.sleep(poll_interval)

    def _process_queue(self) -> None:
        while True:
            try:
                event = self.event_queue.get_nowait()
            except queue.Empty:
                break

            event_type = event[0]
            if event_type == "status":
                _, filename, status, message = event
                self.update_file_status(filename, status, message)
            elif event_type == "log":
                _, message = event
                self.log(message)
            elif event_type == "metrics":
                _, req_id, row_count, details, warnings, chapter_data, question_col, raw_chapter_inputs = event
                if req_id != self.metrics_request_id:
                    continue
                self.high_level_column_index = question_col
                self.row_count_label.setText(f"Total rows: {row_count}")
                total_editions = sum(len(entry["editions"]) for entry in details)
                self._set_magazine_summary(
                    f"Magazines loaded: {len(details)}",
                    f"Tracked editions: {total_editions}",
                )
                self._populate_magazine_tree(details)
                self._populate_question_sets([])
                missing_qset_warning = next(
                    (msg for msg in warnings if "question set" in msg.lower()), None
                )
                if missing_qset_warning:
                    label_message = missing_qset_warning
                elif details:
                    label_message = "Select an edition to view question sets."
                else:
                    label_message = warnings[0] if warnings else "No magazine editions found."
                self.question_label.setText(label_message)
                self._auto_assign_chapters(raw_chapter_inputs)
                self._populate_chapter_list(chapter_data)
                self._refresh_grouping_ui()
                for warning in warnings:
                    self.log(warning)
            elif event_type == "metrics_error":
                _, req_id, error_message = event
                if req_id != self.metrics_request_id:
                    continue
                self.high_level_column_index = None
                self.row_count_label.setText("Total rows: Error")
                self._set_magazine_summary("Magazines: Error", "Missing ranges: Error")
                self._populate_magazine_tree([])
                self._populate_question_sets([])
                self._populate_chapter_list({})
                self._refresh_grouping_ui()
                self.question_label.setText("Unable to load editions.")
                self.log(f"Unable to read workbook rows: {error_message}")
            elif event_type == "rowcount":
                self.update_row_count()
        # Timer will trigger this method again; no manual reschedule needed.

    def closeEvent(self, event) -> None:
        self.stop_watching()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TSVWatcherWindow()
    window.show()
    sys.exit(app.exec())
