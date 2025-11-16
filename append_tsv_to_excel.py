from __future__ import annotations

import csv
import datetime as dt
from decimal import Decimal, InvalidOperation
import queue
import threading
import time
from pathlib import Path
from tkinter import BOTH, END, LEFT, Tk, Text, filedialog, messagebox, StringVar
from tkinter import ttk

from openpyxl import load_workbook


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


def append_tsv_to_excel(tsv_path: Path, workbook_path: Path) -> str:
    if not workbook_path.exists():
        raise FileNotFoundError(f"Workbook not found: {workbook_path}")

    workbook = load_workbook(workbook_path)
    sheet_name = workbook.sheetnames[0]
    worksheet = workbook[sheet_name]

    header_row = [cell.value for cell in next(worksheet.iter_rows(min_row=1, max_row=1))]
    column_types = infer_column_types(worksheet, len(header_row))
    qno_column = _find_qno_column(header_row)
    insert_row = _find_insert_row(worksheet, qno_column)

    appended_rows = 0
    with tsv_path.open("r", encoding="utf-8", newline="") as tsv_file:
        reader = csv.reader(tsv_file, delimiter="\t")
        header_skipped = False
        for row in reader:
            if not header_skipped:
                header_skipped = True
                continue
            for col_idx, value in enumerate(row, start=1):
                target_type = column_types.get(col_idx)
                converted = convert_value_for_column(value, target_type, header_row, col_idx)
                worksheet.cell(row=insert_row, column=col_idx, value=converted)
            insert_row += 1
            appended_rows += 1

    workbook.save(workbook_path)
    return f"Appended {appended_rows} rows to '{sheet_name}'"


def process_tsv(tsv_path: Path, workbook_path: Path) -> str:
    validate_tsv(tsv_path)
    status_message = append_tsv_to_excel(tsv_path, workbook_path)
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


if __name__ == "__main__":
    root = Tk()
    app = TSVWatcherApp(root)

    def on_close() -> None:
        app.stop_watching()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()
