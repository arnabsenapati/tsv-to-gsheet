"""
Simple CBT viewer for .cqt packages.

Usage: python viewer_app.py  (choose file + password)
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path
from typing import Dict, Any

# Ensure project src is on path
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
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
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QButtonGroup,
    QInputDialog,
    QLineEdit,
)

from services.cbt_package import load_cqt, save_cqt_payload


class QuestionView(QWidget):
    def __init__(self, parent=None, on_answer_change=None):
        super().__init__(parent)
        self.question: Dict[str, Any] = {}
        self.responses: Dict[str, str] = {}
        self.on_answer_change = on_answer_change or (lambda: None)

        self.meta_label = QLabel()
        self.meta_label.setStyleSheet("font-weight: 600; color: #cbd5e1; padding: 4px 0;")

        self.text_label = QLabel()
        self.text_label.setWordWrap(True)
        self.text_label.setStyleSheet("font-size: 13px; color: #0f172a;")

        self.image_container = QWidget()
        self.image_layout = QVBoxLayout(self.image_container)
        self.image_layout.setContentsMargins(0, 0, 0, 0)
        self.image_layout.setSpacing(6)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.image_container)

        # Options
        self.option_group = QButtonGroup(self)
        self.option_buttons: Dict[str, QRadioButton] = {}
        options_layout = QHBoxLayout()
        for label in ["A", "B", "C", "D"]:
            btn = QRadioButton(label)
            self.option_group.addButton(btn)
            self.option_buttons[label] = btn
            options_layout.addWidget(btn)
        options_layout.addStretch()
        self.option_group.buttonClicked.connect(self._on_option_selected)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        layout.addWidget(self.meta_label)
        layout.addWidget(self.text_label)
        layout.addWidget(scroll, 1)
        layout.addLayout(options_layout)

    def set_question(self, question: Dict[str, Any], responses: Dict[str, str], display_index: int):
        self.question = question
        self.responses = responses
        qid = question.get("question_id") or ""
        meta = f"Q{display_index} | P{question.get('page', '?')} | {question.get('question_set_name', '')} | {question.get('magazine', '')}"
        self.meta_label.setText(meta)
        self.text_label.setText(question.get("text", ""))

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
        self.image_layout.addStretch()

        # Restore response
        selected = responses.get(str(qid), "")
        # Clear selection first
        self.option_group.setExclusive(False)
        for btn in self.option_buttons.values():
            btn.setChecked(False)
        self.option_group.setExclusive(True)
        if selected:
            btn = self.option_buttons.get(selected)
            if btn:
                btn.setChecked(True)

    def _on_option_selected(self, button):
        qid = self.question.get("question_id")
        if qid is None:
            return
        self.responses[str(qid)] = button.text()
        self.on_answer_change()


class ViewerWindow(QMainWindow):
    def __init__(self, package_path: Path, data: Dict[str, Any], password: str):
        super().__init__()
        self.package_path = package_path
        self.payload = data
        self.password = password

        self.setWindowTitle(f"CBT Viewer - {data.get('list_name', '')}")
        central = QWidget()
        root = QHBoxLayout(central)
        self.setCentralWidget(central)

        self.list_widget = QListWidget()
        self.list_widget.setFixedWidth(180)
        root.addWidget(self.list_widget)

        self.question_view = QuestionView(on_answer_change=self._refresh_answer_markers)
        root.addWidget(self.question_view, 1)

        self.list_widget.currentRowChanged.connect(self._on_question_selected)

        self._load_questions()

    def _load_questions(self):
        self.questions = self.payload.get("questions", [])
        for idx, q in enumerate(self.questions, start=1):
            item = QListWidgetItem(f"Q{idx}")
            # Reserve space for badge on the right
            item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            self.list_widget.addItem(item)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
        self._refresh_answer_markers()

    def _on_question_selected(self, row: int):
        if row < 0 or row >= len(self.questions):
            return
        q = self.questions[row]
        self.question_view.set_question(q, self.payload.get("responses", {}), row + 1)
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
            answered = bool(responses.get(str(q.get("question_id")), ""))
            base_label = f"Q{idx + 1}"
            badge = "   "  # spacer
            if answered:
                badge = " \u2705 "  # green check emoji
                item.setText(f"{base_label}{badge}")
                # Use rich display with right badge via tab
                item.setText(f"{base_label}\t{badge}")
            else:
                item.setText(base_label)


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
