"""
Simple CBT viewer for .cqt packages.

Usage: python viewer_app.py  (choose file + password)
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path
from typing import Dict, Any
import shutil
from datetime import datetime

# Ensure project src is on path
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QInputDialog,
    QLineEdit,
    QCheckBox,
    QFrame,
)

from services.cbt_package import load_cqt, save_cqt_payload, verify_eval_password


class QuestionView(QWidget):
    def __init__(self, parent=None, on_answer_change=None):
        super().__init__(parent)
        self.question: Dict[str, Any] = {}
        self.qkey: str | None = None
        self.responses: Dict[str, list[str]] = {}
        self.current_type: str = "mcq_single"
        self.evaluated: bool = False
        self._updating = False
        self.on_answer_change = on_answer_change or (lambda: None)

        self.meta_label = QLabel()
        self.meta_label.setStyleSheet("font-weight: 600; color: #cbd5e1; padding: 4px 0;")

        self.text_label = QLabel()
        self.text_label.setWordWrap(True)
        self.text_label.setStyleSheet("font-size: 13px; color: #0f172a;")

        self.type_label = QLabel()
        self.type_label.setStyleSheet("color: #94a3b8; font-weight: 600; padding: 2px 0;")

        self.image_container = QWidget()
        self.image_layout = QVBoxLayout(self.image_container)
        self.image_layout.setContentsMargins(0, 0, 0, 0)
        self.image_layout.setSpacing(6)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.image_container)

        # MCQ (checkboxes; also used for single-option mode)
        self.option_buttons: Dict[str, QCheckBox] = {}
        multi_layout = QHBoxLayout()
        self.multi_widget = QWidget()
        self.multi_widget.setLayout(multi_layout)
        for label in ["A", "B", "C", "D"]:
            btn = QCheckBox(label)
            self.option_buttons[label] = btn
            multi_layout.addWidget(btn)
            btn.stateChanged.connect(lambda state, lbl=label: self._on_option_toggled(lbl, state))
        multi_layout.addStretch()

        # Numerical input
        self.numerical_input = QLineEdit()
        self.numerical_input.setPlaceholderText("Enter numerical answer")
        self.numerical_input.textChanged.connect(self._on_numerical_changed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        layout.addWidget(self.meta_label)
        layout.addWidget(self.text_label)
        layout.addWidget(scroll, 1)
        layout.addWidget(self.type_label)
        layout.addWidget(self.multi_widget)
        layout.addWidget(self.numerical_input)

    def set_question(self, question: Dict[str, Any], responses: Dict[str, list[str] | str], display_index: int, qkey: str, show_answers: bool = False):
        self._updating = True
        self.question = question
        self.qkey = qkey
        self.responses = responses
        qid = qkey
        meta = f"Q{display_index} | P{question.get('page', '?')} | {question.get('question_set_name', '')} | {question.get('magazine', '')}"
        self.meta_label.setText(meta)
        self.text_label.setText(question.get("text", ""))
        self.current_type = question.get("question_type", "mcq_single") or "mcq_single"
        self._show_controls_for_type(self.current_type)

        # Images
        while self.image_layout.count():
            item = self.image_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for img in question.get("question_images", []):
            data = base64.b64decode(img.get("data", ""))
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            if not pixmap.isNull():
                pixmap = pixmap.scaledToWidth(360, Qt.SmoothTransformation)
            lbl = QLabel()
            lbl.setPixmap(pixmap)
            lbl.setStyleSheet("border: none; margin: 0; padding: 0;")
            self.image_layout.addWidget(lbl)
        if show_answers:
            if question.get("answer_images"):
                divider = QFrame()
                divider.setFrameShape(QFrame.HLine)
                divider.setStyleSheet("color: #cbd5e1; margin-top: 6px; margin-bottom: 6px;")
                self.image_layout.addWidget(divider)
                answer_title = QLabel("Answer Images")
                answer_title.setStyleSheet("color: #334155; font-weight: 600; padding: 2px 0;")
                self.image_layout.addWidget(answer_title)
            for img in question.get("answer_images", []):
                data = base64.b64decode(img.get("data", ""))
                pixmap = QPixmap()
                pixmap.loadFromData(data)
                if not pixmap.isNull():
                    pixmap = pixmap.scaledToWidth(360, Qt.SmoothTransformation)
                lbl = QLabel()
                lbl.setPixmap(pixmap)
                lbl.setStyleSheet("border: none; margin: 0; padding: 0;")
                self.image_layout.addWidget(lbl)
        self.image_layout.addStretch()

        # Restore response
        # Always clear UI selections before applying saved response
        for btn in self.option_buttons.values():
            btn.blockSignals(True)
            btn.setChecked(False)
            btn.blockSignals(False)
        self.numerical_input.blockSignals(True)
        self.numerical_input.setText("")
        self.numerical_input.blockSignals(False)

        selected = responses.get(str(qid), [])
        if self.current_type == "numerical":
            val = selected if isinstance(selected, str) else ""
            if not isinstance(selected, str):
                # ensure no stale option selection for numerical
                self.responses[str(qid)] = val
            self.numerical_input.setText(val)
        elif self.current_type == "mcq_multiple":
            if isinstance(selected, str):
                selected = [selected] if selected else []
            for opt in selected:
                btn = self.option_buttons.get(opt)
                if btn:
                    btn.setChecked(True)
        else:  # mcq_single
            if isinstance(selected, str):
                target = selected
            elif isinstance(selected, list) and selected:
                target = selected[0]
            else:
                target = ""
            if target:
                btn = self.option_buttons.get(target)
                if btn:
                    btn.setChecked(True)
            else:
                # ensure no default selection stored
                self.responses[str(qid)] = ""

        self._update_enabled_state()
        self._updating = False

    def _on_option_toggled(self, label: str, state: int):
        if self._updating or self.evaluated:
            return
        qid = self.qkey
        if qid is None:
            return
        selected = self.responses.get(str(qid), [])
        if self.current_type == "mcq_single":
            if state == Qt.Checked:
                # deselect others
                for opt, btn in self.option_buttons.items():
                    if opt != label:
                        btn.blockSignals(True)
                        btn.setChecked(False)
                        btn.blockSignals(False)
                self.responses[str(qid)] = label
            else:
                self.responses[str(qid)] = ""
        else:
            if isinstance(selected, str):
                selected = [selected] if selected else []
            if state == Qt.Checked:
                if label not in selected:
                    selected.append(label)
            else:
                selected = [opt for opt in selected if opt != label]
            self.responses[str(qid)] = selected
        self.on_answer_change()

    def _on_numerical_changed(self, text: str):
        if self._updating or self.evaluated:
            return
        qid = self.qkey
        if qid is None:
            return
        self.responses[str(qid)] = text.strip()
        self.on_answer_change()

    def _show_controls_for_type(self, qtype: str):
        # One checkbox row for both MCQ types; input for numerical
        self.multi_widget.setVisible(qtype in ("mcq_single", "mcq_multiple"))
        self.numerical_input.setVisible(qtype == "numerical")
        if qtype == "numerical":
            self.type_label.setText("Question Type: Numerical")
        elif qtype == "mcq_multiple":
            self.type_label.setText("Question Type: MCQ (Multiple correct)")
        else:
            self.type_label.setText("Question Type: MCQ (Single correct)")

    def set_evaluated(self, evaluated: bool):
        self.evaluated = evaluated
        self._update_enabled_state()

    def _update_enabled_state(self):
        enabled = not self.evaluated
        for btn in self.option_buttons.values():
            btn.setEnabled(enabled)
        self.numerical_input.setReadOnly(not enabled)


class ViewerWindow(QMainWindow):
    def __init__(self, package_path: Path, data: Dict[str, Any], password: str):
        super().__init__()
        self.package_path = package_path
        self.payload = data
        self.password = password
        self.evaluated = bool(data.get("evaluated"))
        # Ensure responses dict exists and is shared
        self.payload.setdefault("responses", {})

        self.setWindowTitle(f"CBT Viewer - {data.get('list_name', '')}")
        central = QWidget()
        root = QVBoxLayout(central)
        self.setCentralWidget(central)

        top_row = QHBoxLayout()
        self.list_widget = QListWidget()
        self.list_widget.setFixedWidth(180)
        top_row.addWidget(self.list_widget)

        self.question_view = QuestionView(on_answer_change=self._refresh_answer_markers)
        top_row.addWidget(self.question_view, 1)

        root.addLayout(top_row, 1)

        eval_btn = QPushButton("Evaluate")
        eval_btn.setStyleSheet("background-color: #2563eb; color: white; padding: 6px 12px; border-radius: 4px;")
        eval_btn.clicked.connect(self._on_evaluate)
        eval_row = QHBoxLayout()
        eval_row.addStretch()
        eval_row.addWidget(eval_btn)
        root.addLayout(eval_row)

        self.list_widget.currentRowChanged.connect(self._on_question_selected)

        self._load_questions()

    def _qkey(self, question: Dict[str, Any], idx: int) -> str:
        """Return a stable key for responses; fall back to list index if missing."""
        qid = question.get("question_id")
        if qid is not None and str(qid) != "":
            return str(qid)
        qno = question.get("qno")
        if qno is not None and str(qno) != "":
            return f"qno_{qno}"
        return f"idx_{idx}"

    def _load_questions(self):
        self.questions = self.payload.get("questions", [])
        for idx, q in enumerate(self.questions, start=1):
            item = QListWidgetItem(f"Q{idx}")
            item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            self.list_widget.addItem(item)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
        self._refresh_answer_markers()
        # Apply evaluated lock if already evaluated
        self.question_view.set_evaluated(self.evaluated)

    def _on_question_selected(self, row: int):
        if row < 0 or row >= len(self.questions):
            return
        q = self.questions[row]
        key = self._qkey(q, row)
        self.question_view.set_question(q, self.payload.get("responses", {}), row + 1, key, self.evaluated)
        self._refresh_answer_markers()

    def closeEvent(self, event):
        # Persist responses
        self.payload["responses"] = self.question_view.responses
        try:
            save_cqt_payload(str(self.package_path), self.payload, self.password)
        except Exception as exc:
            QMessageBox.warning(self, "Save Failed", f"Could not save responses:\n{exc}")
        super().closeEvent(event)

    def _refresh_answer_markers(self):
        responses = self.payload.get("responses", {})
        for idx, q in enumerate(self.questions):
            item = self.list_widget.item(idx)
            if not item:
                continue
            qtype = q.get("question_type", "mcq_single") or "mcq_single"
            key = self._qkey(q, idx)
            resp = responses.get(str(key), [])
            if qtype == "numerical":
                if resp is None:
                    answered = False
                elif isinstance(resp, (int, float)):
                    answered = str(resp).strip() != ""
                elif isinstance(resp, str):
                    answered = resp.strip() != ""
                else:
                    # Any other type (e.g., list/dict) counts as unanswered for numerical
                    answered = False
            else:
                if isinstance(resp, str):
                    resp_list = [resp] if resp else []
                else:
                    resp_list = resp or []
                answered = bool(resp_list)
            base_label = f"Q{idx + 1}"
            item.setText(base_label)
            font = item.font()
            font.setUnderline(answered and not self.evaluated)
            item.setFont(font)
            if not self.evaluated:
                # answered -> blue with underline; unanswered -> light gray
                item.setForeground(QColor("#2563eb") if answered else QColor("#94a3b8"))

        if self.evaluated:
            # Show correctness markers
            for idx, q in enumerate(self.questions):
                item = self.list_widget.item(idx)
                if not item:
                    continue
                key = str(self._qkey(q, idx))
                sel = responses.get(key, [])
                qtype = q.get("question_type", "mcq_single") or "mcq_single"
                correct = False
                if qtype == "numerical":
                    answer_val = str(q.get("numerical_answer", "")).strip()
                    sel_val = str(sel).strip() if sel is not None else ""
                    correct = bool(answer_val) and sel_val == answer_val
                else:
                    if isinstance(sel, str):
                        sel = [sel] if sel else []
                    correct_opts = set(q.get("correct_options", []))
                    sel_set = set(sel)
                    correct = bool(correct_opts) and sel_set == correct_opts
                marker = "✔" if correct else "✘"
                color = QColor("#16a34a") if correct else QColor("#dc2626")
                item.setText(f"Q{idx + 1}   {marker}")
                item.setForeground(color)
                font = item.font()
                font.setUnderline(False)
                item.setFont(font)

    def _on_evaluate(self):
        protection = self.payload.get("evaluation_protection", {})
        pwd, ok = QInputDialog.getText(self, "Evaluation Password", "Enter evaluation password:", QLineEdit.Password)
        if not ok or not pwd:
            return
        if not verify_eval_password(pwd, protection):
            QMessageBox.warning(self, "Incorrect", "Evaluation password is incorrect.")
            return
        # Backup original package before marking evaluated
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            backup_path = self.package_path.with_suffix(f".pre_eval_{timestamp}.bak.cqt")
            shutil.copy2(self.package_path, backup_path)
        except Exception:
            # If backup fails, continue but inform later
            backup_path = None

        self.evaluated = True
        self.payload["evaluated"] = True
        self.payload["evaluated_at"] = datetime.utcnow().isoformat() + "Z"
        self.question_view.set_evaluated(True)
        self._refresh_answer_markers()
        # refresh current question to show answer images
        row = self.list_widget.currentRow()
        if row >= 0:
            q = self.questions[row]
            self.question_view.set_question(q, self.payload.get("responses", {}), row + 1, self.evaluated)
        # Persist immediately so evaluated flag is saved
        try:
            save_cqt_payload(str(self.package_path), self.payload, self.password)
        except Exception as exc:
            QMessageBox.warning(self, "Save Failed", f"Could not save evaluated state:\n{exc}")
        if backup_path:
            QMessageBox.information(self, "Evaluation Complete", f"Evaluation done. Backup saved to:\n{backup_path}")


def prompt_file_and_password() -> tuple[Path, str] | tuple[None, None]:
    file_path, _ = QFileDialog.getOpenFileName(None, "Open CBT Package", "", "CBT Package (*.cqt)")
    if not file_path:
        return None, None
    pwd, ok = QInputDialog.getText(None, "Password", "Enter package password:", QLineEdit.Password)
    if not ok or not pwd:
        return None, None
    return Path(file_path), pwd


def main():
    app = QApplication(sys.argv)
    package_path, password = prompt_file_and_password()
    if not package_path:
        sys.exit(0)
    try:
        data = load_cqt(str(package_path), password)
    except Exception as exc:
        QMessageBox.critical(None, "Open Failed", f"Could not open package:\n{exc}")
        sys.exit(1)

    win = ViewerWindow(package_path, data, password)
    win.resize(900, 700)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
