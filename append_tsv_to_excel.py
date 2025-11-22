from __future__ import annotations

import csv
import sys
import datetime as dt
import queue
import re
import threading
import time
from decimal import Decimal, InvalidOperation
from itertools import repeat
from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPalette, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
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
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from openpyxl import load_workbook
import pandas as pd


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


def _find_page_column(header_row: list[str]) -> int:
    keyword_groups = [
        ("page", "no"),
        ("page", "number"),
        ("page",),
        ("pg",),
    ]
    return _match_column(header_row, keyword_groups, "Page Number")


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

        self.input_edit = QLineEdit()
        self.input_edit.editingFinished.connect(self.refresh_file_list)
        input_row = QHBoxLayout()
        input_row.addWidget(self._create_label("Input folder"))
        input_row.addWidget(self.input_edit)
        browse_input = QPushButton("Browse?")
        browse_input.clicked.connect(self.select_input_folder)
        input_row.addWidget(browse_input)
        top_layout.addLayout(input_row)

        self.output_edit = QLineEdit()
        self.output_edit.editingFinished.connect(self.update_row_count)
        output_row = QHBoxLayout()
        output_row.addWidget(self._create_label("Workbook"))
        output_row.addWidget(self.output_edit)
        browse_output = QPushButton("Browse?")
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

        control_card = self._create_card()
        control_layout = QHBoxLayout(control_card)
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
        root_layout.addWidget(control_card)

        splitter = QSplitter(Qt.Vertical)
        root_layout.addWidget(splitter, 1)

        status_card = self._create_card()
        status_layout = QVBoxLayout(status_card)
        status_layout.addWidget(self._create_label("File Status"))
        self.file_table = QTableWidget(0, 3)
        self.file_table.setHorizontalHeaderLabels(["File", "Status", "Message"])
        self.file_table.horizontalHeader().setStretchLastSection(True)
        self.file_table.verticalHeader().setVisible(False)
        self.file_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.file_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.file_table.cellDoubleClicked.connect(self.on_file_double_clicked)
        status_layout.addWidget(self.file_table)
        splitter.addWidget(status_card)

        mag_card = self._create_card()
        mag_layout = QVBoxLayout(mag_card)
        mag_layout.addWidget(self._create_label("Magazine Editions"))
        mag_split = QSplitter(Qt.Horizontal)
        mag_layout.addWidget(mag_split, 1)

        self.mag_tree = QTreeWidget()
        self.mag_tree.setColumnCount(3)
        self.mag_tree.setHeaderLabels(["Magazine", "Edition", "Missing Ranges"])
        self.mag_tree.setRootIsDecorated(False)
        self.mag_tree.itemSelectionChanged.connect(self.on_magazine_select)
        mag_split.addWidget(self.mag_tree)

        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        self.question_label = QLabel("Select a workbook to display magazine editions.")
        self.question_label.setObjectName("infoLabel")
        detail_layout.addWidget(self.question_label)
        self.question_list = QListWidget()
        detail_layout.addWidget(self.question_list)
        mag_split.addWidget(detail_widget)
        splitter.addWidget(mag_card)

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
            return

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
                self.event_queue.put(("metrics", req_id, row_count, magazine_details, warnings))
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
                _, req_id, row_count, details, warnings = event
                if req_id != self.metrics_request_id:
                    continue
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
                for warning in warnings:
                    self.log(warning)
            elif event_type == "metrics_error":
                _, req_id, error_message = event
                if req_id != self.metrics_request_id:
                    continue
                self.row_count_label.setText("Total rows: Error")
                self._set_magazine_summary("Magazines: Error", "Missing ranges: Error")
                self._populate_magazine_tree([])
                self._populate_question_sets([])
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
