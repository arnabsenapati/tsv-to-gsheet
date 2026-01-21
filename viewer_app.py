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

from PySide6.QtCore import Qt, QBuffer, QPointF, QEvent, QSize
from PySide6.QtGui import QPixmap, QColor, QPainter, QPen, QImage
from PySide6.QtCore import QBuffer
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
    QSplitter,
    QButtonGroup,
    QRadioButton,
)

from services.cbt_package import load_cqt, save_cqt_payload, verify_eval_password
from ui.icon_utils import load_icon


class SketchBoard(QWidget):
    """Simple drawing surface that can export/import PNG as base64."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pen_color = QColor("#e5e7eb")
        self.pen_width = 3
        self.current_color = QColor(self.pen_color)
        self._show_cursor_preview = False
        self._preview_pos: QPointF | None = None
        self.color_group = QButtonGroup(self)
        self.colors = [
            "#e5e7eb",  # light gray
            "#f97316",  # light orange
            "#38bdf8",  # light blue
            "#a855f7",  # light purple
            "#22c55e",  # light green
        ]
        self._strokes: list[dict[str, Any]] = []
        self._current: list[QPointF] = []
        self._background: QPixmap | None = None
        self._scroll_area = None
        self._pan_start: QPointF | None = None
        self._pan_origin = (0, 0)
        # A4 aspect ratio ~210x297; choose screen-friendly size (width doubled for extra space)
        self.setFixedSize(1680, 1188)
        self.setMinimumHeight(220)
        self.setAutoFillBackground(True)

    def set_scroll_area(self, scroll_area):
        self._scroll_area = scroll_area

    def set_pen_color(self, color: str):
        self.pen_color = QColor(color)
        self.current_color = QColor(color)

    def set_pen_width(self, width: int):
        self.pen_width = max(1, int(width))

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            if self._scroll_area:
                self._pan_start = event.position()
                h = self._scroll_area.horizontalScrollBar()
                v = self._scroll_area.verticalScrollBar()
                self._pan_origin = (h.value(), v.value())
                self.setCursor(Qt.ClosedHandCursor)
            return
        if event.button() == Qt.LeftButton:
            self._current = [event.position()]
            self._preview_pos = event.position()
            self.update()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.RightButton and self._scroll_area and self._pan_start is not None:
            dx = event.position().x() - self._pan_start.x()
            dy = event.position().y() - self._pan_start.y()
            h = self._scroll_area.horizontalScrollBar()
            v = self._scroll_area.verticalScrollBar()
            h.setValue(int(self._pan_origin[0] - dx))
            v.setValue(int(self._pan_origin[1] - dy))
            return
        if self._current:
            self._current.append(event.position())
            self._preview_pos = event.position()
            self.update()
        else:
            self._preview_pos = event.position()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.RightButton:
            self._pan_start = None
            self.setCursor(Qt.ArrowCursor)
            return
        if event.button() == Qt.LeftButton and self._current:
            self._strokes.append({"color": QColor(self.current_color), "points": list(self._current), "width": self.pen_width})
            self._current = []
            self._preview_pos = None
            self.update()
            self._emit_changed()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.black)
        if self._background and not self._background.isNull():
            painter.drawPixmap(self.rect(), self._background)
        painter.setRenderHint(QPainter.Antialiasing, True)
        for stroke in self._strokes:
            pts = stroke.get("points") or []
            col = stroke.get("color", self.pen_color)
            width = stroke.get("width", self.pen_width)
            painter.setPen(QPen(col, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            if len(pts) > 1:
                for i in range(1, len(pts)):
                    painter.drawLine(pts[i - 1], pts[i])
        if len(self._current) > 1:
            painter.setPen(QPen(self.current_color, self.pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            for i in range(1, len(self._current)):
                painter.drawLine(self._current[i - 1], self._current[i])
        # Draw cursor preview (eraser/pen boundary)
        if self._preview_pos is not None:
            preview_pen = QPen(QColor("#94a3b8"))
            preview_pen.setStyle(Qt.DashLine)
            preview_pen.setWidth(1)
            painter.setPen(preview_pen)
            radius = self.pen_width / 2
            painter.drawEllipse(self._preview_pos, radius, radius)
        painter.end()

    def clear_board(self):
        self._strokes.clear()
        self._current = []
        self._background = None
        self.update()
        self._emit_changed()

    def to_png_base64(self) -> str | None:
        # Quick empty check: no strokes and no active stroke
        if not self._strokes and len(self._current) <= 1:
            return None

        image = QImage(self.size(), QImage.Format_ARGB32)
        image.fill(Qt.black)
        painter = QPainter(image)
        if self._background and not self._background.isNull():
            painter.drawPixmap(self.rect(), self._background)
        painter.setRenderHint(QPainter.Antialiasing, True)
        for stroke in self._strokes:
            pts = stroke.get("points") or []
            col = stroke.get("color", self.pen_color)
            width = stroke.get("width", self.pen_width)
            painter.setPen(QPen(col, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            if len(pts) > 1:
                for i in range(1, len(pts)):
                    painter.drawLine(pts[i - 1], pts[i])
        if len(self._current) > 1:
            painter.setPen(QPen(self.current_color, self.pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            for i in range(1, len(self._current)):
                painter.drawLine(self._current[i - 1], self._current[i])
        painter.end()

        # Safeguard: if rendering matches a blank background, treat as empty
        blank = QImage(self.size(), QImage.Format_ARGB32)
        blank.fill(Qt.black)
        if image == blank:
            return None

        buffer = QBuffer()
        buffer.open(QBuffer.ReadWrite)
        image.save(buffer, "PNG")
        png_bytes = buffer.data()
        buffer.close()
        return base64.b64encode(png_bytes).decode("ascii")

    def is_base64_blank(self, data: str | None) -> bool:
        """Check if provided base64 PNG is effectively a blank board."""
        if not data:
            return True
        try:
            raw = base64.b64decode(data)
            image = QImage()
            image.loadFromData(raw)
            if image.isNull():
                return True
            blank = QImage(image.size(), QImage.Format_ARGB32)
            blank.fill(Qt.black)
            return image == blank
        except Exception:
            return True

    def load_from_base64(self, data: str | None):
        if not data:
            self.clear_board()
            return
        try:
            pixmap = QPixmap()
            pixmap.loadFromData(base64.b64decode(data))
            if pixmap.isNull():
                self.clear_board()
                return
            self._background = pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._strokes.clear()
            self._current = []
            self.update()
        except Exception:
            self.clear_board()

    def _emit_changed(self):
        # Hook method to let parent know the sketch changed; overridden later
        pass


class ReviewListItemWidget(QWidget):
    """List row widget with review toggle and highlight."""

    def __init__(self, label_text: str, toggle_cb, parent=None):
        super().__init__(parent)
        self._reviewed = False
        self._list_widget = None
        self._row_index = None

        self.review_bar = QFrame()
        self.review_bar.setFixedWidth(4)
        self.review_bar.setStyleSheet("background-color: #f59e0b; border-radius: 2px;")
        self.review_bar.setVisible(False)

        self.label = QLabel(label_text)
        self.label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        self.review_btn = QPushButton("☆")
        self.review_btn.setCursor(Qt.PointingHandCursor)
        self.review_btn.setToolTip("Mark for review")
        self.review_btn.setFixedSize(22, 22)
        self.review_btn.setStyleSheet(
            "QPushButton { border: none; background: transparent; }"
            "QPushButton:hover { background-color: #1f2937; border-radius: 4px; }"
        )
        self.review_btn.setText("")
        self.review_btn.setIcon(load_icon("mark_for_review_unmarked.png"))
        self.review_btn.setIconSize(QSize(16, 16))
        self.review_btn.clicked.connect(toggle_cb)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(6)
        layout.addWidget(self.review_bar)
        layout.addWidget(self.label, 1)
        layout.addWidget(self.review_btn)
        self.setFixedHeight(28)

    def bind_list_context(self, list_widget: QListWidget, row_index: int) -> None:
        self._list_widget = list_widget
        self._row_index = row_index

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._list_widget is not None and self._row_index is not None:
            self._list_widget.setCurrentRow(self._row_index)
        super().mousePressEvent(event)

    def set_reviewed(self, reviewed: bool) -> None:
        self._reviewed = bool(reviewed)
        self.review_bar.setVisible(self._reviewed)
        if self._reviewed:
            self.review_btn.setIcon(load_icon("mark_for_review_marked.png"))
            self.review_btn.setToolTip("Unmark review")
        else:
            self.review_btn.setIcon(load_icon("mark_for_review_unmarked.png"))
            self.review_btn.setToolTip("Mark for review")

    def set_review_enabled(self, enabled: bool) -> None:
        self.review_btn.setVisible(bool(enabled))
        if not enabled:
            self.review_bar.setVisible(False)

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
        self._current_image_pixmaps: list[QPixmap] = []
        self._answer_image_pixmaps: list[QPixmap] = []
        self._show_answers: bool = False
        self._last_image_render_size: tuple[int | None, int | None] = (None, None)
        self._active_pen_color: str = ""
        self._default_pen_width = 3
        self._eraser_width = 36  # 3x bigger eraser
        self.has_sketch: bool = False

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
        self.image_layout.setSpacing(0)
        self.image_layout.setAlignment(Qt.AlignTop)
        self.image_container.setMinimumWidth(340)

        self.image_scroll = QScrollArea()
        self.image_scroll.setWidgetResizable(True)
        self.image_scroll.setWidget(self.image_container)
        self.image_scroll.setMinimumWidth(360)
        self.image_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.image_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # Re-render images on resize to fit available area
        self.image_scroll.viewport().installEventFilter(self)

        self.board = SketchBoard()
        # Patch hook so board can notify when strokes change
        self.board._emit_changed = self._on_board_changed
        self._active_pen_color = self.board.colors[0]
        self.eraser_btn = QPushButton("Eraser")
        self.eraser_btn.setCheckable(True)
        self.eraser_btn.setStyleSheet("padding: 4px 8px;")
        self.eraser_btn.toggled.connect(self._toggle_eraser)
        color_row = QHBoxLayout()
        color_row.setSpacing(4)
        color_row.addStretch()
        for idx, color in enumerate(self.board.colors):
            btn = QRadioButton()
            btn.setStyleSheet(
                f"""
                QRadioButton::indicator {{
                    width: 18px;
                    height: 18px;
                    border-radius: 9px;
                    background: {color};
                    border: 1px solid #cbd5e1;
                }}
                QRadioButton::indicator:checked {{
                    border: 2px solid #2563eb;
                }}
                """
            )
            if idx == 0:
                btn.setChecked(True)
                self._active_pen_color = color
            btn.toggled.connect(lambda checked, c=color: checked and self._set_pen_color(c))
            self.board.color_group.addButton(btn)
            color_row.addWidget(btn)
        color_row.addStretch()
        board_scroll = QScrollArea()
        board_scroll.setWidgetResizable(False)
        board_scroll.setWidget(self.board)
        board_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        board_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.board.set_scroll_area(board_scroll)
        self.clear_board_btn = QPushButton("Clear Sketch")
        self.clear_board_btn.clicked.connect(self._clear_sketch)
        self.sketch_status_btn = QPushButton()
        self.sketch_status_btn.setIcon(load_icon("sketch-empty.png"))
        self.sketch_status_btn.setIconSize(QSize(20, 20))
        self.sketch_status_btn.setEnabled(False)
        board_controls = QHBoxLayout()
        board_controls.addWidget(self.clear_board_btn)
        board_controls.addWidget(self.sketch_status_btn)
        board_controls.addWidget(self.eraser_btn)
        for idx, color in enumerate(self.board.colors):
            btn = QRadioButton()
            btn.setStyleSheet(
                f"""
                QRadioButton::indicator {{
                    width: 18px;
                    height: 18px;
                    border-radius: 9px;
                    background: {color};
                    border: 1px solid #cbd5e1;
                }}
                QRadioButton::indicator:checked {{
                    border: 2px solid #2563eb;
                }}
                """
            )
            if idx == 0:
                btn.setChecked(True)
                self._active_pen_color = color
            btn.toggled.connect(lambda checked, c=color: checked and self._set_pen_color(c))
            self.board.color_group.addButton(btn)
            board_controls.addWidget(btn)
        board_controls.addStretch()
        board_container = QWidget()
        board_container_layout = QVBoxLayout(board_container)
        board_container_layout.setContentsMargins(0, 0, 0, 0)
        board_container_layout.setSpacing(6)
        board_container_layout.addLayout(board_controls)
        board_container_layout.addWidget(board_scroll, 1)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.image_scroll)
        self.splitter.addWidget(board_container)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)

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
        layout.addWidget(self.splitter, 1)
        layout.addWidget(self.type_label)
        layout.addWidget(self.multi_widget)
        layout.addWidget(self.numerical_input)

    def _extract_answer_and_sketch(self, resp) -> tuple[Any, str | None]:
        if isinstance(resp, dict):
            return resp.get("answer"), resp.get("sketch_png")
        return resp, None

    def _set_answer_value(self, answer: Any):
        if self.qkey is None:
            return
        current_resp = self.responses.get(str(self.qkey))
        _, sketch = self._extract_answer_and_sketch(current_resp)
        if sketch is None and not isinstance(current_resp, dict):
            self.responses[str(self.qkey)] = answer
        else:
            self.responses[str(self.qkey)] = {"answer": answer, "sketch_png": sketch}

    def _set_sketch_value(self, sketch_b64: str | None):
        if self.qkey is None:
            return
        answer, _ = self._extract_answer_and_sketch(self.responses.get(str(self.qkey)))
        if answer is None:
            if self.current_type == "mcq_multiple":
                answer = []
            else:
                answer = ""
        self.responses[str(self.qkey)] = {"answer": answer, "sketch_png": sketch_b64}

    def _render_question_images(self, include_answers: bool = False, force: bool = False):
        """Render question (and optionally answer) images scaled to fit available viewport while keeping aspect ratio."""
        min_scale_width = 320
        max_scale_width = 1600

        while self.image_layout.count():
            item = self.image_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not self._current_image_pixmaps and not (include_answers and self._answer_image_pixmaps):
            return
        available_width = 360
        available_height = 320
        if self.image_scroll and self.image_scroll.viewport():
            # Use the scrollbar width if visible, otherwise a fallback
            vbar_width = self.image_scroll.verticalScrollBar().sizeHint().width() if self.image_scroll.verticalScrollBar() else 16
            reserved_scrollbar_px = max(16, vbar_width)
            viewport_w = self.image_scroll.viewport().width()
            available_width = max(min_scale_width, viewport_w - reserved_scrollbar_px)
            available_width = min(max_scale_width, available_width)
            available_height = max(200, self.image_scroll.viewport().height() - 4)
        # Prevent repeated renders with the same size to avoid flicker
        cache_key = (available_width, available_height, include_answers)
        if not force and cache_key == self._last_image_render_size:
            return
        self._last_image_render_size = cache_key

        def _add_images(pixmaps: list[QPixmap]):
            for pix in pixmaps:
                if pix.isNull():
                    continue
                scaled = pix.scaled(
                    available_width,
                    available_height,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                lbl = QLabel()
                lbl.setPixmap(scaled)
                lbl.setStyleSheet("border: none; margin: 0; padding: 0;")
                lbl.setAlignment(Qt.AlignLeft | Qt.AlignTop)
                self.image_layout.addWidget(lbl)

        _add_images(self._current_image_pixmaps)

        if include_answers and self._answer_image_pixmaps:
            divider = QFrame()
            divider.setFrameShape(QFrame.HLine)
            divider.setStyleSheet("color: #cbd5e1; margin-top: 6px; margin-bottom: 6px;")
            self.image_layout.addWidget(divider)
            answer_title = QLabel("Answer Images")
            answer_title.setStyleSheet("font-weight: 600; color: #334155; padding: 2px 0;")
            self.image_layout.addWidget(answer_title)
            _add_images(self._answer_image_pixmaps)

    def _set_pen_color(self, color: str):
        """Set active pen color and exit eraser mode."""
        self._active_pen_color = color
        self.board.set_pen_color(color)
        self.board.set_pen_width(self._default_pen_width)
        if self.eraser_btn.isChecked():
            self.eraser_btn.blockSignals(True)
            self.eraser_btn.setChecked(False)
            self.eraser_btn.blockSignals(False)

    def _toggle_eraser(self, checked: bool):
        if checked:
            self.board.set_pen_color("#000000")
            self.board.set_pen_width(self._eraser_width)
        else:
            self.board.set_pen_color(self._active_pen_color)
            self.board.set_pen_width(self._default_pen_width)

    def _update_sketch_label(self):
        if hasattr(self, "sketch_status_btn"):
            if self.has_sketch:
                self.sketch_status_btn.setIcon(load_icon("sketch-filled.png"))
            else:
                self.sketch_status_btn.setIcon(load_icon("sketch-empty.png"))

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
        self._current_image_pixmaps = []
        self._answer_image_pixmaps = []
        for img in question.get("question_images", []):
            data = base64.b64decode(img.get("data", ""))
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            if not pixmap.isNull():
                self._current_image_pixmaps.append(pixmap)
        for img in question.get("answer_images", []):
            data = base64.b64decode(img.get("data", ""))
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            if not pixmap.isNull():
                self._answer_image_pixmaps.append(pixmap)
        # Force a fresh render for new question
        self._last_image_render_size = (None, None, False)
        self._show_answers = show_answers
        self._render_question_images(include_answers=self._show_answers, force=True)

        # Restore response
        # Always clear UI selections before applying saved response
        for btn in self.option_buttons.values():
            btn.blockSignals(True)
            btn.setChecked(False)
            btn.blockSignals(False)
        self.numerical_input.blockSignals(True)
        self.numerical_input.setText("")
        self.numerical_input.blockSignals(False)

        selected_raw = responses.get(str(qid), [])
        selected, sketch_b64 = self._extract_answer_and_sketch(selected_raw)
        if sketch_b64 and self.board.is_base64_blank(sketch_b64):
            sketch_b64 = None
        self.has_sketch = bool(sketch_b64)
        self._update_sketch_label()
        if self.current_type == "numerical":
            val = selected if isinstance(selected, str) else ""
            if not isinstance(selected, str):
                # ensure no stale option selection for numerical
                self._set_answer_value(val)
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
                self._set_answer_value("")

        self._update_enabled_state()
        self._updating = False
        # Load sketch (if any) into the board tab
        self.board.load_from_base64(sketch_b64)

    def eventFilter(self, obj, event):
        if obj == self.image_scroll.viewport() and event.type() == QEvent.Resize:
            self._render_question_images(include_answers=self._show_answers)
        return super().eventFilter(obj, event)

    def _on_option_toggled(self, label: str, state: int):
        if self._updating or self.evaluated:
            return
        qid = self.qkey
        if qid is None:
            return
        selected_raw = self.responses.get(str(qid), [])
        selected, _ = self._extract_answer_and_sketch(selected_raw)
        # Qt sends int states (0/1/2); convert to boolean checked flag
        is_checked = state == Qt.CheckState.Checked.value if isinstance(state, int) else state == Qt.CheckState.Checked
        if self.current_type == "mcq_single":
            if is_checked:
                # deselect others
                for opt, btn in self.option_buttons.items():
                    if opt != label:
                        btn.blockSignals(True)
                        btn.setChecked(False)
                        btn.blockSignals(False)
                new_answer = label
            else:
                new_answer = ""
            self._set_answer_value(new_answer)
        else:
            if isinstance(selected, str):
                selected = [selected] if selected else []
            elif not isinstance(selected, list):
                selected = []
            if is_checked:
                if label not in selected:
                    selected.append(label)
            else:
                selected = [opt for opt in selected if opt != label]
            self._set_answer_value(selected)
        self.on_answer_change()

    def _on_numerical_changed(self, text: str):
        if self._updating or self.evaluated:
            return
        qid = self.qkey
        if qid is None:
            return
        self._set_answer_value(text.strip())
        self.on_answer_change()

    def _save_sketch(self):
        if self.qkey is None:
            return
        sketch_b64 = self.board.to_png_base64()
        self.has_sketch = bool(sketch_b64)
        self._update_sketch_label()
        if sketch_b64:
            self._set_sketch_value(sketch_b64)
        else:
            self._set_sketch_value(None)
        self.on_answer_change()

    def _clear_sketch(self):
        self.board.clear_board()
        if self.qkey is None:
            return
        self.has_sketch = False
        self._update_sketch_label()
        self._set_sketch_value(None)
        self.on_answer_change()

    def _on_board_changed(self):
        if self.qkey is None:
            return
        sketch_b64 = self.board.to_png_base64()
        # If empty/None, clear stored sketch; otherwise save
        self.has_sketch = bool(sketch_b64)
        self._update_sketch_label()
        if sketch_b64:
            self._set_sketch_value(sketch_b64)
        else:
            self._set_sketch_value(None)
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
        self.show_answer_images = bool(self.evaluated)
        # Ensure responses dict exists and is shared
        self.responses = self.payload.setdefault("responses", {})
        self.review_marks = self.payload.setdefault("review_marks", {})
        if self.evaluated and self.review_marks:
            self.review_marks = {}
            self.payload["review_marks"] = {}

        self.setWindowTitle(f"CBT Viewer - {data.get('list_name', '')}")
        central = QWidget()
        root = QVBoxLayout(central)
        self.setCentralWidget(central)

        top_row = QHBoxLayout()
        self.list_widget = QListWidget()
        self.list_widget.setFixedWidth(180)
        top_row.addWidget(self.list_widget)

        self.question_view = QuestionView(on_answer_change=self._on_answer_change)
        top_row.addWidget(self.question_view, 1)

        root.addLayout(top_row, 1)

        eval_btn = QPushButton("Evaluate")
        eval_btn.setStyleSheet("background-color: #2563eb; color: white; padding: 6px 12px; border-radius: 4px;")
        eval_btn.clicked.connect(self._on_evaluate)
        self.show_answers_cb = QCheckBox("Show answer images")
        self.show_answers_cb.setChecked(self.show_answer_images)
        self.show_answers_cb.setVisible(self.evaluated)
        self.show_answers_cb.setEnabled(self.evaluated)
        self.show_answers_cb.toggled.connect(self._on_toggle_answer_images)
        eval_row = QHBoxLayout()
        eval_row.addStretch()
        eval_row.addWidget(self.show_answers_cb)
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
            row_index = idx - 1
            item = QListWidgetItem()
            item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            widget = ReviewListItemWidget(
                f"Q{idx}",
                toggle_cb=lambda checked=False, i=row_index: self._toggle_review_mark(i),
            )
            widget.bind_list_context(self.list_widget, row_index)
            item.setSizeHint(widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)
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
        self.question_view.set_question(q, self.responses, row + 1, key, self.show_answer_images)
        self._refresh_answer_markers()

    def _on_answer_change(self):
        """Refresh markers and persist responses to the package on every change."""
        self.payload["responses"] = self.responses
        self._refresh_answer_markers()
        try:
            save_cqt_payload(str(self.package_path), self.payload, self.password)
        except Exception as exc:
            print(f"[viewer] Failed to persist responses: {exc}", flush=True)

    def _toggle_review_mark(self, row: int) -> None:
        if self.evaluated:
            return
        if row < 0 or row >= len(self.questions):
            return
        key = str(self._qkey(self.questions[row], row))
        if self.review_marks.get(key):
            self.review_marks.pop(key, None)
        else:
            self.review_marks[key] = True
        self.payload["review_marks"] = self.review_marks
        self._refresh_answer_markers()
        try:
            save_cqt_payload(str(self.package_path), self.payload, self.password)
        except Exception as exc:
            print(f"[viewer] Failed to persist review marks: {exc}", flush=True)

    def closeEvent(self, event):
        # Persist responses
        self.payload["responses"] = self.responses
        self.payload["review_marks"] = self.review_marks
        try:
            save_cqt_payload(str(self.package_path), self.payload, self.password)
        except Exception as exc:
            QMessageBox.warning(self, "Save Failed", f"Could not save responses:\n{exc}")
        super().closeEvent(event)

    def _refresh_answer_markers(self):
        responses = self.responses
        for idx, q in enumerate(self.questions):
            item = self.list_widget.item(idx)
            if not item:
                continue
            widget = self.list_widget.itemWidget(item)
            label = widget.label if isinstance(widget, ReviewListItemWidget) else None
            qtype = q.get("question_type", "mcq_single") or "mcq_single"
            key = self._qkey(q, idx)
            resp_raw = responses.get(str(key), [])
            resp, _ = self.question_view._extract_answer_and_sketch(resp_raw) if hasattr(self, "question_view") else (resp_raw, None)
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
            if self.evaluated:
                sel_raw = responses.get(str(key), [])
                sel, _ = self.question_view._extract_answer_and_sketch(sel_raw) if hasattr(self, "question_view") else (sel_raw, None)
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
                text_value = f"Q{idx + 1}   {marker}"
                underline = False
            else:
                color = QColor("#2563eb") if answered else QColor("#94a3b8")
                text_value = f"Q{idx + 1}"
                underline = answered

            if label:
                label.setText(text_value)
                font = label.font()
                font.setUnderline(underline and not self.evaluated)
                label.setFont(font)
                label.setStyleSheet(f"color: {color.name()};")
            else:
                item.setText(text_value)
                font = item.font()
                font.setUnderline(underline and not self.evaluated)
                item.setFont(font)
                item.setForeground(color)

            if isinstance(widget, ReviewListItemWidget):
                reviewed = bool(self.review_marks.get(str(key)))
                widget.set_review_enabled(not self.evaluated)
                widget.set_reviewed(reviewed and not self.evaluated)

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
        self.show_answer_images = True
        self.payload["evaluated"] = True
        self.payload["evaluated_at"] = datetime.utcnow().isoformat() + "Z"
        self.review_marks = {}
        self.payload["review_marks"] = {}
        self.question_view.set_evaluated(True)
        self.show_answers_cb.setChecked(True)
        self.show_answers_cb.setVisible(True)
        self.show_answers_cb.setEnabled(True)
        self._refresh_answer_markers()
        # refresh current question to show answer images
        row = self.list_widget.currentRow()
        if row >= 0:
            q = self.questions[row]
            key = self._qkey(q, row)
            self.question_view.set_question(q, self.responses, row + 1, key, show_answers=self.show_answer_images)
        # Persist immediately so evaluated flag is saved
        try:
            save_cqt_payload(str(self.package_path), self.payload, self.password)
        except Exception as exc:
            QMessageBox.warning(self, "Save Failed", f"Could not save evaluated state:\n{exc}")
        if backup_path:
            QMessageBox.information(self, "Evaluation Complete", f"Evaluation done. Backup saved to:\n{backup_path}")

    def _on_toggle_answer_images(self, checked: bool) -> None:
        if not self.evaluated:
            return
        self.show_answer_images = bool(checked)
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.questions):
            return
        q = self.questions[row]
        key = self._qkey(q, row)
        self.question_view.set_question(q, self.responses, row + 1, key, show_answers=self.show_answer_images)


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
