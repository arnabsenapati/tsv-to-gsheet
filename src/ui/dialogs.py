"""
Dialog windows for the TSV to Excel Watcher application.

This module contains custom dialog classes:
- MultiSelectTagDialog: Beautiful tag selection dialog with colored badges
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QTextEdit,
    QFormLayout,
    QLineEdit,
    QCheckBox,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
import base64

from .widgets import ClickableTagBadge


class MultiSelectTagDialog(QDialog):
    """
    Beautiful dialog for selecting multiple tags with colored badges.
    
    Features:
    - Visual tag badges with +/✓ toggle
    - Click tags to select/deselect
    - Create new tags inline
    - Color-coded badges matching application theme
    - Grid layout for easy scanning
    
    Usage:
        dialog = MultiSelectTagDialog(
            existing_tags=["JEE", "NEET", "CUET"],
            selected_tags=["JEE"],
            title="Select Tags",
            tag_colors={"JEE": "#2563eb"},
            available_colors=TAG_COLORS,
            parent=self
        )
        if dialog.exec() == QDialog.Accepted:
            tags = dialog.get_selected_tags()
    """
    
    def __init__(self, existing_tags: list[str], selected_tags: list[str] = None, 
                 title: str = "Select Tags", tag_colors: dict[str, str] = None, 
                 available_colors: list[str] = None, parent=None):
        """
        Initialize the tag selection dialog.
        
        Args:
            existing_tags: List of existing tag names to show
            selected_tags: List of initially selected tag names
            title: Dialog window title
            tag_colors: Dict mapping tag names to hex color codes
            available_colors: List of hex color codes for new tags
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        # Store configuration
        self.tag_colors = tag_colors or {}
        self.available_colors = available_colors or ["#2563eb", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"]
        self.tag_badges = {}  # Map tag name to badge widget
        self.selected_tags_list = selected_tags or []
        
        # Build UI
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # ============================================================================
        # Header Section
        # ============================================================================
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e293b;")
        layout.addWidget(title_label)
        
        instruction = QLabel("Click on tags to select/deselect them:")
        instruction.setStyleSheet("font-size: 12px; color: #64748b; margin-bottom: 5px;")
        layout.addWidget(instruction)
        
        # ============================================================================
        # Tag Badges Section (Scrollable)
        # ============================================================================
        scroll_area = QWidget()
        self.tags_layout = QVBoxLayout(scroll_area)
        self.tags_layout.setSpacing(8)
        self.tags_layout.setAlignment(Qt.AlignTop)
        
        # Populate with existing tags or show empty message
        if existing_tags:
            self._add_tag_badges(existing_tags)
        else:
            no_tags_label = QLabel("No existing tags. Create new ones below.")
            no_tags_label.setStyleSheet("color: #94a3b8; font-style: italic; padding: 20px;")
            self.tags_layout.addWidget(no_tags_label)
        
        layout.addWidget(scroll_area, 1)
        
        # ============================================================================
        # Separator
        # ============================================================================
        separator = QWidget()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #e2e8f0;")
        layout.addWidget(separator)
        
        # ============================================================================
        # New Tag Creation Section
        # ============================================================================
        new_tag_label = QLabel("Create new tag:")
        new_tag_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #475569;")
        layout.addWidget(new_tag_label)
        
        new_tag_layout = QHBoxLayout()
        
        # Input field for new tag name
        self.new_tag_input = QLineEdit()
        self.new_tag_input.setPlaceholderText("Type tag name and press Enter or click Add")
        self.new_tag_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 2px solid #cbd5e1;
                border-radius: 6px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
            }
        """)
        self.new_tag_input.returnPressed.connect(self._add_new_tag)
        new_tag_layout.addWidget(self.new_tag_input)
        
        # Add button
        add_btn = QPushButton("Add")
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        add_btn.clicked.connect(self._add_new_tag)
        new_tag_layout.addWidget(add_btn)
        
        layout.addLayout(new_tag_layout)
        
        # ============================================================================
        # Dialog Buttons (OK/Cancel)
        # ============================================================================
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        
        # Style OK button (green)
        button_box.button(QDialogButtonBox.Ok).setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 24px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        
        # Style Cancel button (gray)
        button_box.button(QDialogButtonBox.Cancel).setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #475569;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px 24px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
            }
        """)
        
        # Connect button signals
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)


class QuestionEditDialog(QDialog):
    """Dialog to edit question metadata and text."""

    def __init__(self, question: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Question")
        self.setMinimumSize(520, 640)
        self.question = question.copy()

        self.setStyleSheet("""
            QDialog {
                background-color: #0b1020;
                color: #cbd5e1;
            }
            QLabel {
                color: #dfe7ff;
                font-weight: 600;
                padding: 2px 0;
            }
            QLineEdit, QTextEdit {
                background-color: #0f172a;
                color: #e5e7eb;
                border: 1px solid #1f2a44;
                border-radius: 6px;
                padding: 8px;
                selection-background-color: #2563eb;
            }
            QLineEdit:focus, QTextEdit:focus {
                border: 1px solid #2563eb;
            }
            QDialogButtonBox QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: 600;
            }
            QDialogButtonBox QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFormAlignment(Qt.AlignTop)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(14)

        def add_row(label_text: str, widget):
            lbl = QLabel(label_text)
            lbl.setMinimumWidth(140)
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            lbl.setWordWrap(False)
            lbl.setStyleSheet("background: transparent; border: none;")
            form.addRow(lbl, widget)

        self.qno_input = QLineEdit(str(question.get("qno", "")))
        add_row("Question No:", self.qno_input)

        self.page_input = QLineEdit(str(question.get("page", "")))
        add_row("Page:", self.page_input)

        self.set_name_input = QLineEdit(str(question.get("question_set_name", "")))
        add_row("Question Set:", self.set_name_input)

        self.mag_input = QLineEdit(str(question.get("magazine", "")))
        add_row("Magazine Edition:", self.mag_input)

        self.chapter_input = QLineEdit(str(question.get("chapter", "")))
        add_row("Chapter:", self.chapter_input)

        self.high_chapter_input = QLineEdit(str(question.get("high_level_chapter", "")))
        add_row("High-level Chapter:", self.high_chapter_input)

        self.text_input = QTextEdit(str(question.get("text", "")))
        self.text_input.setMinimumHeight(140)
        add_row("Question Text:", self.text_input)

        self.answer_input = QTextEdit(str(question.get("answer_text", "")))
        self.answer_input.setMinimumHeight(100)
        add_row("Answer Text:", self.answer_input)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 12)
        main_layout.setSpacing(12)
        main_layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Save).setText("Save")
        btns.button(QDialogButtonBox.Cancel).setText("Cancel")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        main_layout.addWidget(btns)

    def get_updates(self) -> dict:
        return {
            "question_number": self.qno_input.text().strip(),
            "page_range": self.page_input.text().strip(),
            "question_set_name": self.set_name_input.text().strip(),
            "magazine": self.mag_input.text().strip(),
            "question_text": self.text_input.toPlainText().strip(),
            "answer_text": self.answer_input.toPlainText().strip(),
            "chapter": self.chapter_input.text().strip(),
            "high_level_chapter": self.high_chapter_input.text().strip(),
        }


class PasswordPromptDialog(QDialog):
    """Simple password + confirm dialog."""

    def __init__(self, title: str = "Set Password", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_confirm = QLineEdit()
        self.password_confirm.setEchoMode(QLineEdit.Password)
        form.addRow("Password:", self.password_input)
        form.addRow("Confirm:", self.password_confirm)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setMinimumWidth(320)

    def _on_accept(self):
        if self.password_input.text() != self.password_confirm.text():
            QMessageBox.warning(self, "Mismatch", "Passwords do not match.")
            return
        if not self.password_input.text():
            QMessageBox.warning(self, "Empty", "Password cannot be empty.")
            return
        self.accept()

    def get_password(self) -> str:
        return self.password_input.text()


class CQTAuthorPreviewDialog(QDialog):
    """Preview questions with images and select correct options before export."""

    def __init__(self, questions: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preview & Set Correct Options")
        self.setMinimumSize(900, 700)
        self.questions = questions
        self.current_row = None

        root = QHBoxLayout(self)
        self.list_widget = QListWidget()
        self.list_widget.setFixedWidth(200)
        root.addWidget(self.list_widget)

        # Detail panel
        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        detail_layout.setContentsMargins(8, 8, 8, 8)
        detail_layout.setSpacing(8)

        self.meta_label = QLabel()
        self.meta_label.setStyleSheet("font-weight: 600; color: #0f172a;")
        detail_layout.addWidget(self.meta_label)

        self.type_label = QLabel()
        self.type_label.setStyleSheet("color: #475569; font-weight: 600;")
        detail_layout.addWidget(self.type_label)

        self.text_label = QLabel()
        self.text_label.setWordWrap(True)
        self.text_label.setStyleSheet("color: #0f172a;")
        detail_layout.addWidget(self.text_label)

        # Images (question + answer)
        self.image_container = QWidget()
        self.image_layout = QVBoxLayout(self.image_container)
        self.image_layout.setContentsMargins(0, 0, 0, 0)
        self.image_layout.setSpacing(6)

        img_scroll = QScrollArea()
        img_scroll.setWidgetResizable(True)
        img_scroll.setWidget(self.image_container)
        detail_layout.addWidget(img_scroll, 1)

        # Correct options checkboxes
        self.option_checks = {}
        options_layout = QHBoxLayout()
        for label in ["A", "B", "C", "D"]:
            cb = QCheckBox(label)
            self.option_checks[label] = cb
            options_layout.addWidget(cb)
            cb.stateChanged.connect(self._update_type_label)
        options_layout.addStretch()
        detail_layout.addLayout(options_layout)

        # Numerical answer input (for numerical type)
        self.numerical_input = QLineEdit()
        self.numerical_input.setPlaceholderText("Numerical answer (for numerical questions)")
        self.numerical_input.textChanged.connect(self._update_type_label)
        detail_layout.addWidget(self.numerical_input)

        root.addWidget(detail_widget, 1)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        detail_layout.addWidget(btns)

        # Populate list
        for idx, q in enumerate(self.questions, start=1):
            item = QListWidgetItem(f"Q{idx}")
            self.list_widget.addItem(item)
        self.list_widget.currentRowChanged.connect(self._on_select)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _on_select(self, row: int):
        # Persist edits for previous row before switching
        if self.current_row is not None:
            self._save_row(self.current_row)
        if row < 0 or row >= len(self.questions):
            return
        self.current_row = row
        q = self.questions[row]
        self.meta_label.setText(
            f"Q{q.get('qno','?')} | P{q.get('page','?')} | {q.get('question_set_name','')} | {q.get('magazine','')}"
        )
        self.text_label.setText(q.get("text", ""))

        # Images
        while self.image_layout.count():
            item = self.image_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for img in q.get("question_images", []):
            self._add_image(img)
        # Answer images below
        for img in q.get("answer_images", []):
            self._add_image(img, label="Answer")
        self.image_layout.addStretch()

        # Options
        correct = set(q.get("correct_options", []))
        for label, cb in self.option_checks.items():
            cb.setChecked(label in correct)
        self.numerical_input.setText(str(q.get("numerical_answer", "") or ""))
        self._update_type_label()

    def _add_image(self, img: dict, label: str | None = None):
        data = base64.b64decode(img.get("data", ""))
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        if not pixmap.isNull():
            pixmap = pixmap.scaledToWidth(480, Qt.SmoothTransformation)
        lbl = QLabel()
        lbl.setPixmap(pixmap)
        lbl.setStyleSheet("border: none; margin: 0; padding: 0;")
        if label:
            cap = QLabel(label)
            cap.setStyleSheet("font-weight: 600; color: #0f172a; padding-top: 4px;")
            self.image_layout.addWidget(cap)
        self.image_layout.addWidget(lbl)

    def apply_updates(self):
        """Write selected correct options back into questions."""
        if self.current_row is not None:
            self._save_row(self.current_row)
        return self.questions

    def _save_row(self, row: int):
        """Persist selections for a given row."""
        if row < 0 or row >= len(self.questions):
            return
        correct = [lbl for lbl, cb in self.option_checks.items() if cb.isChecked()]
        numerical_value = self.numerical_input.text().strip()
        # Infer question type
        if numerical_value:
            q_type = "numerical"
            correct = []  # numerical uses value instead of options
        elif len(correct) > 1:
            q_type = "mcq_multiple"
        elif len(correct) == 1:
            q_type = "mcq_single"
        else:
            q_type = "mcq_single"

        q = self.questions[row]
        q["correct_options"] = correct
        q["numerical_answer"] = numerical_value
        q["question_type"] = q_type
        self._update_type_label()

    def _update_type_label(self):
        """Update type label based on current inputs."""
        numerical_value = self.numerical_input.text().strip()
        correct = [lbl for lbl, cb in self.option_checks.items() if cb.isChecked()]
        if numerical_value:
            text = "Type: Numerical"
        elif len(correct) > 1:
            text = "Type: MCQ (Multiple correct)"
        elif len(correct) == 1:
            text = "Type: MCQ (Single correct)"
        else:
            text = "Type: MCQ (Single correct)"
        self.type_label.setText(text)

    def _on_accept(self):
        if self.current_row is not None:
            self._save_row(self.current_row)
        self.accept()
    
    def _add_tag_badges(self, tags: list[str]):
        """
        Add tag badges to the layout in a flowing grid (3 per row).
        
        Args:
            tags: List of tag names to add as badges
        """
        row_layout = None
        tags_per_row = 0
        max_tags_per_row = 3
        
        for tag in sorted(tags):
            # Create new row if needed
            if tags_per_row == 0:
                row_layout = QHBoxLayout()
                row_layout.setSpacing(10)
                self.tags_layout.addLayout(row_layout)
            
            # Create badge
            color = self._get_tag_color(tag)
            is_selected = tag in self.selected_tags_list
            badge = ClickableTagBadge(tag, color, is_selected)
            self.tag_badges[tag] = badge
            row_layout.addWidget(badge)
            
            # Move to next row after max tags
            tags_per_row += 1
            if tags_per_row >= max_tags_per_row:
                row_layout.addStretch()
                tags_per_row = 0
        
        # Add stretch to last incomplete row
        if row_layout and tags_per_row > 0:
            row_layout.addStretch()
    
    def _get_tag_color(self, tag: str) -> str:
        """
        Get or assign a color for a tag.
        
        Args:
            tag: Tag name
            
        Returns:
            Hex color code
        """
        if tag not in self.tag_colors:
            # Assign next color from palette (cycling)
            color_index = len(self.tag_colors) % len(self.available_colors)
            self.tag_colors[tag] = self.available_colors[color_index]
        return self.tag_colors[tag]
    
    def _add_new_tag(self):
        """
        Add a new tag from the input field.
        If tag exists, just selects it. Otherwise creates new badge.
        """
        tag = self.new_tag_input.text().strip()
        if not tag:
            return
        
        # Check if tag already exists
        if tag in self.tag_badges:
            # Already exists - just select it
            self.tag_badges[tag].is_selected = True
            self.tag_badges[tag]._update_style()
            self.new_tag_input.clear()
            return
        
        # Create new tag badge (selected by default)
        color = self._get_tag_color(tag)
        badge = ClickableTagBadge(tag, color, is_selected=True)
        self.tag_badges[tag] = badge
        
        # Find last layout row to add to
        last_layout = None
        for i in range(self.tags_layout.count()):
            item = self.tags_layout.itemAt(i)
            if isinstance(item, QHBoxLayout):
                last_layout = item
        
        # Add to existing row or create new row
        if not last_layout or last_layout.count() >= 4:  # 3 badges + 1 stretch
            # Create new row
            new_row = QHBoxLayout()
            new_row.setSpacing(10)
            new_row.addWidget(badge)
            new_row.addStretch()
            self.tags_layout.addLayout(new_row)
        else:
            # Add to existing row (remove stretch, add badge, re-add stretch)
            stretch_item = last_layout.takeAt(last_layout.count() - 1)
            last_layout.addWidget(badge)
            if stretch_item:
                last_layout.addItem(stretch_item)
        
        self.new_tag_input.clear()
    
    def get_selected_tags(self) -> list[str]:
        """
        Get list of currently selected tag names.
        
        Returns:
            List of tag names that are selected
        """
        return [tag for tag, badge in self.tag_badges.items() if badge.is_selected]
