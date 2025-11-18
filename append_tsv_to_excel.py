from __future__ import annotations

import csv
import datetime as dt
import queue
import re
import threading
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from tkinter import BOTH, END, LEFT, Tk, Text, filedialog, messagebox, StringVar
from tkinter import ttk

from openpyxl import load_workbook


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


def _find_insert_row(worksheet, qno_column: int) -> int:
    last_row_with_qno = 1
    for row_idx in range(worksheet.max_row, 1, -1):
        cell_value = worksheet.cell(row=row_idx, column=qno_column).value
        if cell_value is None:
            continue
        if isinstance(cell_value, int):
            last_row_with_qno = row_idx
            break
        if isinstance(cell_value, str) and cell_value.strip().isdigit():
            last_row_with_qno = row_idx
            break
    return last_row_with_qno + 1


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
        insert_row = _find_insert_row(worksheet, qno_column)

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


class TSVWatcherApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        root.title("TSV to Excel Watcher")
        root.geometry("900x600")

        self.input_var = StringVar()
        self.output_var = StringVar()

        self.event_queue: queue.Queue[tuple] = queue.Queue()
        self.watch_thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.file_rows: dict[str, str] = {}
        self.file_errors: dict[str, str] = {}

        self._build_ui()
        self._schedule_queue_processing()

    def _build_ui(self) -> None:
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(fill=BOTH)

        # Input folder selection
        input_label = ttk.Label(top_frame, text="Input folder:")
        input_label.grid(row=0, column=0, sticky="w")
        input_entry = ttk.Entry(top_frame, textvariable=self.input_var, width=70)
        input_entry.grid(row=0, column=1, padx=5)
        ttk.Button(top_frame, text="Browse...", command=self.select_input_folder).grid(row=0, column=2)

        # Output workbook selection
        out_label = ttk.Label(top_frame, text="Workbook:")
        out_label.grid(row=1, column=0, sticky="w", pady=5)
        out_entry = ttk.Entry(top_frame, textvariable=self.output_var, width=70)
        out_entry.grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(top_frame, text="Browse...", command=self.select_output_file).grid(row=1, column=2, pady=5)

        # Controls
        control_frame = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        control_frame.pack(fill=BOTH)
        ttk.Button(control_frame, text="Refresh Files", command=self.refresh_file_list).pack(side=LEFT)
        self.start_button = ttk.Button(control_frame, text="Start Watching", command=self.start_watching)
        self.start_button.pack(side=LEFT, padx=5)
        ttk.Button(control_frame, text="Stop Watching", command=self.stop_watching).pack(side=LEFT)

        # File status table
        tree_frame = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        tree_frame.pack(fill=BOTH, expand=True)

        columns = ("file", "status", "message")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=10)
        for col, width in zip(columns, (300, 150, 400)):
            self.tree.heading(col, text=col.title())
            self.tree.column(col, width=width, anchor="w")
        self.tree.pack(fill=BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        # Log output
        log_frame = ttk.LabelFrame(self.root, text="Log", padding=10)
        log_frame.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))
        self.log_text = Text(log_frame, height=8)
        self.log_text.pack(fill=BOTH, expand=True)

    def log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(END, f"[{timestamp}] {message}\n")
        self.log_text.see(END)

    def select_input_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select Input Folder")
        if folder:
            self.input_var.set(folder)
            self.refresh_file_list()

    def select_output_file(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Select Excel Workbook",
            filetypes=[("Excel files", "*.xlsx")],
        )
        if file_path:
            self.output_var.set(file_path)

    def refresh_file_list(self) -> None:
        input_path = Path(self.input_var.get())
        if not input_path.exists():
            self.log("Input folder does not exist.")
            return

        tsv_files = sorted(input_path.glob("*.tsv"))
        for tsv_file in tsv_files:
            self._ensure_row(tsv_file.name)
        self.log(f"Found {len(tsv_files)} TSV file(s) in input folder.")

    def _ensure_row(self, filename: str) -> None:
        if filename in self.file_rows:
            return
        iid = self.tree.insert("", END, values=(filename, "Pending", "Awaiting processing"))
        self.file_rows[filename] = iid

    def update_file_status(self, filename: str, status: str, message: str) -> None:
        self._ensure_row(filename)
        iid = self.file_rows[filename]
        self.tree.item(iid, values=(filename, status, message))
        if status.lower() == "error":
            self.file_errors[filename] = message
        else:
            self.file_errors.pop(filename, None)

    def start_watching(self) -> None:
        if self.watch_thread and self.watch_thread.is_alive():
            messagebox.showinfo("Watcher", "Watcher is already running.")
            return

        input_path = Path(self.input_var.get())
        workbook_path = Path(self.output_var.get())

        if not input_path.is_dir():
            messagebox.showerror("Invalid Input", "Please select a valid input folder.")
            return
        if not workbook_path.is_file():
            messagebox.showerror("Invalid Workbook", "Please select an existing Excel workbook.")
            return

        self.stop_event.clear()
        self.watch_thread = threading.Thread(
            target=self._watch_loop, args=(input_path, workbook_path), daemon=True
        )
        self.watch_thread.start()
        self.start_button.config(state="disabled")
        self.log("Started watching for TSV files.")

    def stop_watching(self) -> None:
        self.stop_event.set()
        if self.watch_thread and self.watch_thread.is_alive():
            self.watch_thread.join(timeout=0.1)
        self.start_button.config(state="normal")
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

            time.sleep(poll_interval)

    def _schedule_queue_processing(self) -> None:
        self.root.after(200, self._process_queue)

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

        self._schedule_queue_processing()

    def on_tree_select(self, event) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        iid = selected[0]
        filename, status, message = self.tree.item(iid, "values")
        if status.lower() != "error":
            return
        detail = self.file_errors.get(filename, message)
        messagebox.showerror("Validation Error", f"{filename}\n\n{detail}")


if __name__ == "__main__":
    root = Tk()
    app = TSVWatcherApp(root)

    def on_close() -> None:
        app.stop_watching()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()
