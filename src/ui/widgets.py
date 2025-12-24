"""

Custom UI widgets for the TSV to Excel Watcher application.



This module contains all custom widget classes used throughout the application:

- TagBadge: Small clickable tag display for filtering

- ClickableTagBadge: Interactive tag with +/G toggle for selection dialogs

- QuestionTreeWidget: Tree widget displaying grouped questions with drag support

- ChapterTableWidget: Table widget for chapter management with drop support

- QuestionTableWidget: Table widget for question display with drag support

- GroupingChapterListWidget: Draggable list of chapters for grouping

- GroupListWidget: Droppable list of groups for chapter organization

- QuestionCardWidget: Individual question card with inline preview

- QuestionAccordionGroup: Collapsible group for question cards

- QuestionListCardView: Scrollable container for accordion groups

- DashboardView: Dashboard with workbook selector and statistics

- NavigationSidebar: Collapsible sidebar navigation for main views

- QuestionChip: Small chip widget for question metadata with remove button

- DragDropQuestionPanel: Drag-and-drop panel for adding questions to lists

"""



import json
import os
from pathlib import Path

from PySide6.QtCore import Qt, QMimeData, Signal, QRect, QPoint, QTimer, QSize, QByteArray, QBuffer
from PySide6.QtGui import QColor, QDrag, QDragEnterEvent, QDropEvent, QPixmap, QPainter, QFont, QGuiApplication, QPen, QImage, QCursor
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QTableWidget,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QLineEdit,
    QComboBox,
    QApplication,
    QStyle,
    QFileDialog,
    QMessageBox,
    QDialog,
    QTabWidget,
    QGraphicsDropShadowEffect,
)

from ui.icon_utils import load_icon
from utils.helpers import normalize_magazine_edition





class TagBadge(QLabel):

    """

    Small colored tag badge that can be clicked to filter questions.

    

    Features:

    - Compact size (9px font, minimal padding)

    - Colored background with rounded corners

    - Emits clicked signal with tag name

    - Hover effect for interactivity

    

    Signals:

        clicked(str): Emitted when badge is clicked, passes tag name

    """

    

    clicked = Signal(str)

    

    def __init__(self, tag: str, color: str, parent=None):

        """

        Initialize a tag badge.

        

        Args:

            tag: Tag text to display

            color: Hex color code for background (e.g., '#2563eb')

            parent: Parent widget

        """

        super().__init__(parent)

        self.tag = tag

        self.setText(f" {tag} ")

        

        # Style with minimal padding and small font for compact display

        self.setStyleSheet(f"""

            QLabel {{

                background-color: {color};

                color: white;

                border-radius: 2px;

                padding: 1px 4px;

                font-size: 9px;

                font-weight: bold;

            }}

            QLabel:hover {{

                opacity: 0.8;

            }}

        """)

        self.setCursor(Qt.PointingHandCursor)

    

    def mousePressEvent(self, event):

        """Handle mouse clicks on the badge."""

        if event.button() == Qt.LeftButton:

            self.clicked.emit(self.tag)

        super().mousePressEvent(event)





class ClickableTagBadge(QPushButton):

    """

    Interactive tag badge with selection toggle for multi-select dialogs.

    

    Features:

    - Shows '+' icon when unselected, '✓' when selected

    - Solid color when selected, outline when unselected

    - Smooth color transitions on hover

    - Click to toggle selection state

    

    Usage:

        badge = ClickableTagBadge("JEE", "#2563eb", is_selected=True)

        selected_state = badge.is_selected

    """

    

    def __init__(self, tag: str, color: str, is_selected: bool = False, parent=None):

        """

        Initialize a clickable tag badge.

        

        Args:

            tag: Tag text to display

            color: Hex color code for background (e.g., '#2563eb')

            is_selected: Initial selection state

            parent: Parent widget

        """

        super().__init__(parent)

        self.tag = tag

        self.color = color

        self.is_selected = is_selected

        self.setFixedHeight(32)

        self.setCursor(Qt.PointingHandCursor)

        self.clicked.connect(self._toggle_selection)

        self._update_style()

    

    def _toggle_selection(self):

        """Toggle between selected and unselected states."""

        self.is_selected = not self.is_selected

        self._update_style()

    

    def _update_style(self):

        """Update button appearance based on selection state."""

        icon = "✓" if self.is_selected else "+"

        

        if self.is_selected:

            # Selected: solid color with white text

            self.setStyleSheet(f"""

                QPushButton {{

                    background-color: {self.color};

                    color: white;

                    border: 2px solid {self.color};

                    border-radius: 6px;

                    padding: 6px 12px;

                    font-size: 13px;

                    font-weight: bold;

                    text-align: left;

                }}

                QPushButton:hover {{

                    background-color: {self._darken_color(self.color)};

                    border-color: {self._darken_color(self.color)};

                }}

            """)

        else:

            # Unselected: white background with colored border and text

            self.setStyleSheet(f"""

                QPushButton {{

                    background-color: white;

                    color: {self.color};

                    border: 2px solid {self.color};

                    border-radius: 6px;

                    padding: 6px 12px;

                    font-size: 13px;

                    font-weight: bold;

                    text-align: left;

                }}

                QPushButton:hover {{

                    background-color: {self._lighten_color(self.color)};

                }}

            """)

        

        self.setText(f"{icon}  {self.tag}")

    

    def _darken_color(self, color: str) -> str:

        """Darken a hex color by 20% for hover effect."""

        color = color.lstrip('#')

        r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)

        r, g, b = int(r * 0.8), int(g * 0.8), int(b * 0.8)

        return f"#{r:02x}{g:02x}{b:02x}"

    

    def _lighten_color(self, color: str) -> str:

        """Lighten a hex color for hover effect by adding transparency."""

        return f"{color}20"





class QuestionTreeWidget(QTreeWidget):

    """

    Tree widget for displaying grouped questions with drag support.

    

    Features:

    - Hierarchical display (groups as parents, questions as children)

    - Drag and drop support for moving questions to custom lists

    - Extended selection mode (Ctrl+click for multi-select)

    - Four columns: Question No, Page, Question Set Name, Magazine

    

    Structure:

        Group Name (45 questions)  [parent item]

        GGG Q1  |  25  |  JEE Main 2023  |  Physics For You Jan 2023  [child]

        GGG Q2  |  26  |  JEE Main 2023  |  Physics For You Jan 2023  [child]

        GGG ...

    """

    

    MIME_TYPE = "application/x-question-row"



    def __init__(self, parent_window):

        """

        Initialize the question tree widget.

        

        Args:

            parent_window: Reference to main window for event handling

        """

        super().__init__()

        self.parent_window = parent_window

        

        # Configure columns

        self.setColumnCount(4)

        self.setHeaderLabels(["Question No", "Page", "Question Set Name", "Magazine"])

        

        # Configure behavior

        self.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.setSelectionMode(QAbstractItemView.ExtendedSelection)  # Ctrl+click

        self.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.setDragEnabled(True)

        self.setDragDropMode(QAbstractItemView.DragOnly)

        self.setAlternatingRowColors(True)

        

        # Connect signals

        self.itemSelectionChanged.connect(self.parent_window.on_question_selected)

        self.header().setStretchLastSection(True)



    def startDrag(self, supportedActions) -> None:

        """

        Handle drag operation start.

        Supports dragging multiple selected questions (leaf items only).

        Shows count of questions being dragged.

        """

        # Get all selected items

        selected_items = self.selectedItems()

        if not selected_items:

            return

        

        # Filter to only leaf items (actual questions, not group headers)

        question_items = [item for item in selected_items if item.childCount() == 0]

        if not question_items:

            return

        

        # Collect question data from all selected questions

        questions_data = []

        for item in question_items:

            question_data = item.data(0, Qt.UserRole)

            if question_data:

                questions_data.append({

                    "row_number": question_data.get("row_number"),

                    "qno": question_data.get("qno"),

                    "question_set": question_data.get("question_set"),

                    "group": question_data.get("group"),

                })

        

        if not questions_data:

            return

        

        # Create JSON payload with array of questions

        payload = json.dumps({

            "questions": questions_data,

            "count": len(questions_data)

        })

        

        # Create mime data and start drag

        mime = QMimeData()

        mime.setData(self.MIME_TYPE, payload.encode("utf-8"))

        mime.setText(f"Moving {len(questions_data)} question(s)")

        

        # Create visual drag indicator with count badge

        drag = QDrag(self)

        drag.setMimeData(mime)

        

        # Create small circular badge showing count

        size = 32

        pixmap = QPixmap(size, size)

        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)

        painter.setRenderHint(QPainter.Antialiasing)

        

        # Draw circle background

        painter.setBrush(QColor("#2563eb"))

        painter.setPen(Qt.NoPen)

        painter.drawEllipse(0, 0, size, size)

        

        # Draw number only

        painter.setPen(QColor("white"))

        font = QFont()

        font.setPointSize(10)

        font.setBold(True)

        painter.setFont(font)

        painter.drawText(QRect(0, 0, size, size), Qt.AlignCenter, str(len(questions_data)))

        painter.end()

        

        drag.setPixmap(pixmap)

        # Shift hotspot left and up to align with pointer tip

        drag.setHotSpot(QPoint(size // 2 + 8, size // 2 + 8))

        drag.exec(Qt.MoveAction)





class ChapterCardWidget(QWidget):

    """

    Custom chapter card widget with integrated badge - everything painted in one rectangle.

    

    Features:

    - Single rectangle with chapter text (left) and badge (right) painted together

    - No separate elements - true single rectangle

    - Hover: background color change + height increase

    - Custom painting for precise control

    """

    

    clicked = Signal(str)  # Signal emits chapter_key when clicked

    

    def __init__(self, chapter_name: str, chapter_key: str, question_count: int):

        super().__init__()

        self.chapter_name = chapter_name

        self.chapter_key = chapter_key

        self.question_count = question_count

        self.is_selected = False

        self.is_hovered = False

        self.base_height = 44

        self.hover_height = int(self.base_height * 1.15)  # 15% increase

        

        self.setMinimumHeight(self.base_height)

        self.setMaximumHeight(self.base_height)

        self.setCursor(Qt.PointingHandCursor)

        self._update_style()

    

    def _update_style(self):

        """Update styling based on state"""

        if self.is_selected:

            self.bg_color = QColor("#e0e7ff")  # Light indigo

            self.border_color = QColor("#3b82f6")

        elif self.is_hovered:

            self.bg_color = QColor("#f0f4f8")  # Slightly darker on hover

            self.border_color = QColor("#cbd5e1")

        else:

            self.bg_color = QColor("#f8fafc")  # Very light gray

            self.border_color = QColor("#e2e8f0")  # Light border

        

        self.update()

    

    def set_selected(self, selected: bool):

        """Update selection state"""

        self.is_selected = selected

        self._update_style()

    

    def paintEvent(self, event):

        """Custom paint event to draw card with text and badge in one rectangle"""

        painter = QPainter(self)

        painter.setRenderHint(QPainter.Antialiasing)

        

        rect = self.rect()

        

        # Draw main background rectangle

        painter.fillRect(rect, self.bg_color)

        painter.setPen(QPen(self.border_color, 1))

        painter.drawRect(0, 0, rect.width() - 1, rect.height() - 1)

        

        # Draw chapter name text (left side)

        painter.setPen(QColor("#1e293b"))

        name_font = QFont()

        name_font.setPointSize(10)

        name_font.setWeight(QFont.Medium)  # Use QFont.Medium instead of 500

        painter.setFont(name_font)

        

        text_rect = QRect(12, 0, rect.width() - 100, rect.height())

        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, self.chapter_name)

        

        # Draw badge (right side)

        badge_text = str(self.question_count)

        badge_font = QFont()

        badge_font.setPointSize(9)

        badge_font.setWeight(QFont.Bold)  # Use QFont.Bold instead of 600

        painter.setFont(badge_font)

        

        # Calculate badge dimensions

        fm = painter.fontMetrics()

        badge_width = fm.horizontalAdvance(badge_text) + 16  # text + padding

        badge_height = 24

        badge_x = rect.width() - badge_width - 12

        badge_y = (rect.height() - badge_height) // 2

        badge_rect = QRect(badge_x, badge_y, badge_width, badge_height)

        

        # Draw badge background with rounded corners

        painter.setBrush(QColor("#3b82f6"))

        painter.setPen(QPen(QColor("#2563eb"), 1))

        painter.drawRoundedRect(badge_rect, 6, 6)

        

        # Draw badge text

        painter.setPen(QColor("white"))

        painter.drawText(badge_rect, Qt.AlignCenter, badge_text)

        

        painter.end()

    

    def enterEvent(self, event):

        """Handle mouse enter - change background and increase size"""

        self.is_hovered = True

        self.setMinimumHeight(self.hover_height)

        self.setMaximumHeight(self.hover_height)

        self._update_style()

        super().enterEvent(event)

    

    def leaveEvent(self, event):

        """Handle mouse leave - reset background and size"""

        self.is_hovered = False

        self.setMinimumHeight(self.base_height)

        self.setMaximumHeight(self.base_height)

        self._update_style()

        super().leaveEvent(event)

    

    def mousePressEvent(self, event):

        """Handle mouse click"""

        if event.button() == Qt.LeftButton:

            self.clicked.emit(self.chapter_key)

        super().mousePressEvent(event)





class ChapterCardView(QWidget):

    """

    Scrollable vertical stack of simple chapter row cards.

    

    Features:

    - Single column vertical layout

    - Hairline gaps between cards (0px)

    - Hover scale animation (15% increase)

    - Click selection with visual feedback

    - Emits chapter_selected signal when card is clicked

    """

    

    chapter_selected = Signal(str)  # Signal emits chapter_key when card clicked

    

    def __init__(self, parent=None):

        super().__init__(parent)

        self.chapter_cards = {}  # chapter_key -> ChapterCardWidget

        self.selected_chapter = None

        

        # Main layout

        main_layout = QVBoxLayout()

        main_layout.setContentsMargins(0, 0, 0, 0)  # No margins for hairline gaps

        main_layout.setSpacing(0)  # Hairline gap between cards

        

        # Scroll area for card stack

        scroll_area = QScrollArea()

        scroll_area.setWidgetResizable(True)

        scroll_area.setStyleSheet("QScrollArea { border: none; background: #f8fafc; }")

        

        # Container widget for vertical stack

        container = QWidget()

        self.cards_layout = QVBoxLayout()

        self.cards_layout.setContentsMargins(0, 0, 0, 0)  # No margins

        self.cards_layout.setSpacing(0)  # Hairline gap

        

        container.setLayout(self.cards_layout)

        scroll_area.setWidget(container)

        

        main_layout.addWidget(scroll_area)

        self.setLayout(main_layout)

        

        self.setStyleSheet("background: #f8fafc;")

    

    def add_chapter(self, chapter_name: str, chapter_key: str, question_count: int):

        """Add a chapter card to the vertical stack"""

        card = ChapterCardWidget(chapter_name, chapter_key, question_count)

        card.clicked.connect(self._on_card_clicked)

        

        self.chapter_cards[chapter_key] = card

        self.cards_layout.addWidget(card)

    

    def clear_chapters(self):

        """Clear all chapter cards"""

        for card in self.chapter_cards.values():

            card.deleteLater()

        self.chapter_cards.clear()

        self.selected_chapter = None

    

    def _on_card_clicked(self, chapter_key: str):

        """Handle card click"""

        # Deselect previous

        if self.selected_chapter and self.selected_chapter in self.chapter_cards:

            self.chapter_cards[self.selected_chapter].set_selected(False)

        

        # Select new

        self.selected_chapter = chapter_key

        if chapter_key in self.chapter_cards:

            self.chapter_cards[chapter_key].set_selected(True)

        

        # Emit signal

        self.chapter_selected.emit(chapter_key)





class ChapterTableWidget(QTableWidget):

    """

    Table widget for chapter management with drop support.

    

    Features:

    - Accepts dropped questions from QuestionTableWidget

    - Two columns: Chapter name and question count

    - Drop questions to reassign them to different chapters

    - Single row selection only

    

    Usage:

        Drag questions from question table and drop on chapter rows

        to reassign questions to that chapter.

    """



    def __init__(self, parent_window):

        """

        Initialize chapter table widget.

        

        Args:

            parent_window: Reference to main window for event handling

        """

        super().__init__(0, 2)

        self.parent_window = parent_window

        

        # Configure behavior

        self.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.setAcceptDrops(True)

        self.setDragDropMode(QAbstractItemView.DropOnly)

        self.setDragEnabled(False)



    def dragEnterEvent(self, event: QDragEnterEvent) -> None:

        """Accept drag events with question data."""

        if event.mimeData().hasFormat(QuestionTableWidget.MIME_TYPE):

            event.acceptProposedAction()

        else:

            super().dragEnterEvent(event)



    def dragMoveEvent(self, event: QDragEnterEvent) -> None:

        """Allow dragging over the table."""

        if event.mimeData().hasFormat(QuestionTableWidget.MIME_TYPE):

            event.acceptProposedAction()

        else:

            super().dragMoveEvent(event)



    def dropEvent(self, event: QDropEvent) -> None:

        """

        Handle question drop event.

        Reassigns the dropped question(s) to the chapter at drop position.

        Supports both single and multiple questions.

        """

        # Validate mime data format

        if not event.mimeData().hasFormat(QuestionTableWidget.MIME_TYPE):

            super().dropEvent(event)

            return

        

        # Parse question data from drag payload

        try:

            payload = bytes(event.mimeData().data(QuestionTableWidget.MIME_TYPE)).decode("utf-8")

            data = json.loads(payload)

        except Exception:

            return



        # Find the target chapter at drop position

        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()

        index = self.indexAt(pos)

        if not index.isValid():

            return

        

        chapter_item = self.item(index.row(), 0)

        if not chapter_item:

            return

        

        # Get chapter name (from UserRole if available, otherwise from text)

        target_group = chapter_item.data(Qt.UserRole) or chapter_item.text()

        

        # Handle both old single-question format and new multi-question format

        if "questions" in data:

            # New format: multiple questions

            questions = data["questions"]

            self.parent_window.reassign_questions(questions, target_group)

        else:

            # Old format: single question (for backward compatibility)

            self.parent_window.reassign_question(data, target_group)

        

        event.acceptProposedAction()





class QuestionTableWidget(QTableWidget):

    """

    Table widget for displaying questions with drag support.

    

    Features:

    - Drag questions to chapter table or custom lists

    - Four columns: Question No, Page, Question Set Name, Magazine

    - Extended selection mode for multi-select

    - Drag-only mode (no drops)

    

    Used in the chapter-based question analysis view.

    """

    

    MIME_TYPE = "application/x-question-row"



    def __init__(self, parent_window):

        """

        Initialize question table widget.

        

        Args:

            parent_window: Reference to main window for event handling

        """

        super().__init__(0, 4)

        self.parent_window = parent_window

        

        # Configure behavior

        self.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.setSelectionMode(QAbstractItemView.ExtendedSelection)  # Enable multi-select

        self.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.setDragEnabled(True)

        self.setDragDropMode(QAbstractItemView.DragOnly)



    def startDrag(self, supportedActions) -> None:

        """

        Handle drag operation start.

        Supports dragging multiple selected questions.

        Shows count of questions being dragged.

        """

        # Get all selected rows

        selected_rows = sorted(set(index.row() for index in self.selectedIndexes()))

        if not selected_rows:

            return

        

        # Collect question data from all selected rows

        questions_data = []

        for row in selected_rows:

            if 0 <= row < len(self.parent_window.current_questions):

                question = self.parent_window.current_questions[row]

                questions_data.append({

                    "row_number": question.get("row_number"),

                    "qno": question.get("qno"),

                    "question_set": question.get("question_set"),

                    "group": question.get("group"),

                })

        

        if not questions_data:

            return

        

        # Create JSON payload with array of questions

        payload = json.dumps({

            "questions": questions_data,

            "count": len(questions_data)

        })

        

        # Create mime data and start drag

        mime = QMimeData()

        mime.setData(self.MIME_TYPE, payload.encode("utf-8"))

        mime.setText(f"Moving {len(questions_data)} question(s)")

        

        # Create visual drag indicator with count badge

        drag = QDrag(self)

        drag.setMimeData(mime)

        

        # Create small circular badge showing count

        size = 32

        pixmap = QPixmap(size, size)

        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)

        painter.setRenderHint(QPainter.Antialiasing)

        

        # Draw circle background

        painter.setBrush(QColor("#2563eb"))

        painter.setPen(Qt.NoPen)

        painter.drawEllipse(0, 0, size, size)

        

        # Draw number only

        painter.setPen(QColor("white"))

        font = QFont()

        font.setPointSize(10)

        font.setBold(True)

        painter.setFont(font)

        painter.drawText(QRect(0, 0, size, size), Qt.AlignCenter, str(len(questions_data)))

        painter.end()

        

        drag.setPixmap(pixmap)

        # Shift hotspot left and up to align with pointer tip

        drag.setHotSpot(QPoint(size // 2 + 8, size // 2 + 8))

        drag.exec(Qt.MoveAction)





class GroupingChapterListWidget(QListWidget):

    """

    Draggable list widget for chapters in the grouping interface.

    

    Features:

    - Single selection mode

    - Drag enabled to move chapters to groups

    - Stores chapter name in item's UserRole

    

    Usage:

        Drag chapters from this list to the group list to assign

        chapters to groups.

    """



    def __init__(self, parent_window):

        """

        Initialize grouping chapter list widget.

        

        Args:

            parent_window: Reference to main window for event handling

        """

        super().__init__()

        self.parent_window = parent_window

        self.setSelectionMode(QListWidget.SingleSelection)

        self.setDragEnabled(True)



    def startDrag(self, supportedActions) -> None:

        """

        Handle drag operation start.

        Creates text mime data with chapter name.

        """

        item = self.currentItem()

        if not item:

            return

        

        # Get chapter name (from UserRole if available, otherwise from text)

        chapter = item.data(Qt.UserRole) or item.text()

        

        # Create text mime data

        mime = QMimeData()

        mime.setText(chapter)

        

        # Start drag operation

        drag = QDrag(self)

        drag.setMimeData(mime)

        drag.exec(Qt.MoveAction)





class GroupListWidget(QListWidget):

    """

    Droppable list widget for groups in the grouping interface.

    

    Features:

    - Single selection mode

    - Drop enabled to receive chapters

    - Stores group name in item's UserRole

    

    Usage:

        Drop chapters from the chapter list onto group items to assign

        chapters to that group.

    """



    def __init__(self, parent_window):

        """

        Initialize group list widget.

        

        Args:

            parent_window: Reference to main window for event handling

        """

        super().__init__()

        self.parent_window = parent_window

        self.setSelectionMode(QListWidget.SingleSelection)

        self.setAcceptDrops(True)



    def dragEnterEvent(self, event: QDragEnterEvent) -> None:

        """Accept drag events with text data (chapter names)."""

        if event.mimeData().hasText():

            event.acceptProposedAction()

        else:

            super().dragEnterEvent(event)



    def dragMoveEvent(self, event: QDragEnterEvent) -> None:

        """Allow dragging over the list."""

        if event.mimeData().hasText():

            event.acceptProposedAction()

        else:

            super().dragMoveEvent(event)



    def dropEvent(self, event: QDropEvent) -> None:

        """

        Handle chapter drop event.

        Moves the dropped chapter to the group at drop position.

        """

        # Validate mime data format

        if not event.mimeData().hasText():

            super().dropEvent(event)

            return

        

        # Get chapter name from drag payload

        chapter = event.mimeData().text().strip()

        if not chapter:

            return

        

        # Find target group at drop position

        position = event.position().toPoint() if hasattr(event, "position") else event.pos()

        target_item = self.itemAt(position)

        

        # Fall back to current item if no item at position

        if not target_item:

            target_item = self.currentItem()

        

        if not target_item:

            return

        

        # Get group name (from UserRole if available, otherwise from text)

        group = target_item.data(Qt.UserRole) or target_item.text()

        

        # Get source group to maintain selection after move

        current_item = self.parent_window.group_list.currentItem()

        source_group = current_item.data(Qt.UserRole) if current_item else None

        

        # Move chapter to target group

        self.parent_window.move_chapter_to_group(chapter, group, stay_on_group=source_group)

        event.acceptProposedAction()





class QuestionCardWithRemoveButton(QWidget):

    """

    Wrapper widget for QuestionCardWidget that adds a remove button in top-right corner on hover.

    

    Features:

    - Displays question card normally with no hover darkening

    - Shows G icon button in top-right corner on hover

    - Single click on button to remove

    - Double click on card works normally for copying

    """

    

    clicked = Signal(dict)  # Emits question data when card clicked

    remove_requested = Signal(dict)  # Emits question data when remove button clicked

    

    def __init__(self, question_data: dict, parent=None):

        super().__init__(parent)

        self.question_data = question_data
        self.question_id = question_data.get("question_id")
        self.db_service = getattr(parent, "db_service", None) if parent else None

        self.setMinimumHeight(100)

        self.setMaximumHeight(150)

        

        # Main layout for the card

        layout = QVBoxLayout(self)

        layout.setContentsMargins(0, 0, 0, 0)

        layout.setSpacing(0)

        

        # Create the card widget

        self.card = QuestionCardWidget(question_data, self)

        self.card.is_custom_list_card = True  # Ensure copy mode uses custom list setting

        self.card.clicked.connect(lambda q: self.clicked.emit(q))

        layout.addWidget(self.card)

        # Image button (top-right, beside remove)
        self.image_btn = QPushButton(self)
        self.image_btn.setIcon(load_icon("image.svg"))
        self.image_btn.setIconSize(QSize(16, 16))
        self.image_btn.setToolTip("View / add question & answer images")
        self.image_btn.setStyleSheet(self._image_button_style(active=False))
        self.image_btn.setFixedSize(28, 28)
        self.image_btn.clicked.connect(self._show_image_popover)
        self.image_btn.setVisible(False)
        self.image_btn.setCursor(Qt.PointingHandCursor)

        # Edit button (matches base card style)
        self.edit_btn = QPushButton(self)
        self.edit_btn.setIcon(load_icon("edit.svg"))
        self.edit_btn.setIconSize(QSize(14, 14))
        self.edit_btn.setToolTip("Edit question")
        self.edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #f59e0b;
                color: white;
                border: none;
                border-radius: 50%;
                width: 24px;
                height: 24px;
                padding: 0px;
                font-weight: bold;
                font-size: 12px;
                qproperty-flat: true;
            }
            QPushButton:hover {
                background-color: #d97706;
            }
        """)
        self.edit_btn.setFixedSize(24, 24)
        self.edit_btn.clicked.connect(self._show_edit_dialog)
        self.edit_btn.setVisible(False)
        self.edit_btn.setCursor(Qt.PointingHandCursor)

        # Create remove button (positioned absolutely in top-right corner)

        self.remove_btn = QPushButton(self)
        self.remove_btn.setIcon(load_icon("close.svg"))
        self.remove_btn.setIconSize(QSize(14, 14))

        self.remove_btn.setStyleSheet("""

            QPushButton {

                background-color: #ef4444;

                color: white;

                border: none;

                border-radius: 50%;

                width: 28px;

                height: 28px;

                padding: 0px;

                font-weight: bold;

                font-size: 16px;

                qproperty-flat: true;

            }

            QPushButton:hover {

                background-color: #dc2626;

            }

        """)

        self.remove_btn.setFixedSize(28, 28)

        self.remove_btn.clicked.connect(self._on_remove_clicked)

        self.remove_btn.setVisible(False)

        self.remove_btn.setCursor(Qt.PointingHandCursor)

        self.remove_btn.raise_()
        self.image_btn.raise_()
        self.edit_btn.raise_()
        self._update_image_button_state()

    def enterEvent(self, event):

        """Show remove button in top-right corner on hover."""

        self.remove_btn.setVisible(True)
        self.image_btn.setVisible(True)
        self.edit_btn.setVisible(True)

        # Position buttons in top-right corner
        self.remove_btn.move(self.width() - 32, 4)
        self.image_btn.move(self.width() - 64, 4)
        self.edit_btn.move(self.width() - 92, 6)

        super().enterEvent(event)



    def leaveEvent(self, event):

        """Hide remove button when leaving."""

        self.remove_btn.setVisible(False)
        self.image_btn.setVisible(False)
        self.edit_btn.setVisible(False)

        super().leaveEvent(event)

    

    def mouseDoubleClickEvent(self, event):

        """Pass double-click events to the card widget."""

        if hasattr(self.card, 'mouseDoubleClickEvent'):

            self.card.mouseDoubleClickEvent(event)

        else:

            super().mouseDoubleClickEvent(event)

    

    def _on_remove_clicked(self):

        """Emit remove signal when button clicked."""

        self.remove_requested.emit(self.question_data)

    def _show_edit_dialog(self):
        """Forward edit to inner card to avoid duplicate logic."""
        if hasattr(self.card, "_show_edit_dialog"):
            self.card._show_edit_dialog()

    def _image_button_style(self, active: bool) -> str:
        """Return stylesheet for image button; green when active, blue otherwise."""
        if active:
            return """
            QPushButton {
                background-color: #16a34a;
                color: white;
                border: none;
                border-radius: 50%;
                width: 28px;
                height: 28px;
                padding: 0px;
                font-weight: bold;
                font-size: 14px;
                qproperty-flat: true;
            }
            QPushButton:hover {
                background-color: #15803d;
            }
            """
        return """
        QPushButton {
            background-color: #0ea5e9;
            color: white;
            border: none;
            border-radius: 50%;
            width: 28px;
            height: 28px;
            padding: 0px;
            font-weight: bold;
            font-size: 14px;
            qproperty-flat: true;
        }
        QPushButton:hover {
            background-color: #0284c7;
        }
        """

    def _update_image_button_state(self):
        """Switch icon to filled version when images exist."""
        icon = load_icon("image.svg")
        has_images = False
        if self.db_service and self.question_id:
            try:
                counts = self.db_service.get_image_counts(int(self.question_id))
                has_images = bool(counts and any(v > 0 for v in counts.values()))
                if has_images:
                    icon = load_icon("image_filled.svg")
            except Exception:
                pass
        previous = getattr(self, "has_images", False)
        self.has_images = has_images
        self.image_btn.setIcon(icon)
        self.image_btn.setStyleSheet(self._image_button_style(active=has_images))
        if has_images != previous:
            if hasattr(self, "card"):
                try:
                    self.card.has_images = has_images
                    self.card._build_card()
                except Exception:
                    pass

    def _show_image_popover(self):
        """Show dialog with tabs for question/answer images."""
        if not self.question_id:
            QMessageBox.information(self, "No Question ID", "Cannot manage images because this question is missing an ID.")
            return

        if not self.db_service:
            QMessageBox.warning(self, "Database Unavailable", "Database service is not available to load/save images.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Images")
        dialog.setMinimumSize(520, 400)

        root_layout = QVBoxLayout(dialog)
        tabs = QTabWidget(dialog)
        root_layout.addWidget(tabs)

        def build_tab(kind: str):
            tab = QWidget()
            layout = QVBoxLayout(tab)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(4)

            buttons = QHBoxLayout()
            add_btn = QPushButton("Add from files")
            add_btn.setIcon(load_icon("add.svg"))
            add_btn.setIconSize(QSize(14, 14))
            add_btn.clicked.connect(lambda: self._add_images(kind, refresh))
            buttons.addWidget(add_btn)

            paste_btn = QPushButton("Paste from clipboard")
            paste_btn.setToolTip("Paste an image currently in clipboard")
            paste_btn.clicked.connect(lambda: self._paste_image(kind, refresh))
            buttons.addWidget(paste_btn)

            clear_btn = QPushButton("Clear all")
            clear_btn.setStyleSheet("background-color: #ef4444; color: white; border: none; border-radius: 4px; padding: 6px 12px;")
            clear_btn.clicked.connect(lambda: self._clear_images(kind, refresh))
            buttons.addWidget(clear_btn)

            buttons.addStretch()
            layout.addLayout(buttons)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            content = QWidget()
            content_layout = QVBoxLayout(content)
            content_layout.setAlignment(Qt.AlignTop)
            content_layout.setSpacing(0)
            content_layout.setContentsMargins(0, 0, 0, 0)
            scroll.setWidget(content)
            layout.addWidget(scroll)

            def refresh():
                while content_layout.count():
                    item = content_layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
                try:
                    images = self.db_service.get_images(int(self.question_id), kind)
                except Exception as exc:
                    err = QLabel(f"Failed to load images: {exc}")
                    err.setStyleSheet("color: #dc2626;")
                    content_layout.addWidget(err)
                    return

                if not images:
                    empty = QLabel("No images yet.")
                    empty.setStyleSheet("color: #94a3b8;")
                    content_layout.addWidget(empty)
                    return

                for img in images:
                    pixmap = QPixmap()
                    pixmap.loadFromData(bytes(img["data"]))
                    if not pixmap.isNull():
                        pixmap = pixmap.scaledToWidth(360, Qt.SmoothTransformation)
                    lbl = QLabel()
                    lbl.setPixmap(pixmap)
                    lbl.setStyleSheet("padding: 0px; border: none; margin: 0;")
                    content_layout.addWidget(lbl)

            refresh()
            return tab, refresh

        q_tab, q_refresh = build_tab("question")
        a_tab, a_refresh = build_tab("answer")
        tabs.addTab(q_tab, "Question images")
        tabs.addTab(a_tab, "Answer images")

        dialog.exec()
        self._update_image_button_state()

    def _add_images(self, kind: str, refresh_callback=None):
        """Open file picker and attach images of the given kind for this question."""
        if not self.question_id or not self.db_service:
            return

        dialog_title = "Select question images" if kind == "question" else "Select answer images"
        files, _ = QFileDialog.getOpenFileNames(
            self,
            dialog_title,
            "",
            "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp);;All Files (*)",
        )
        if not files:
            return

        for file_path in files:
            try:
                self.db_service.add_question_image(int(self.question_id), kind, Path(file_path))
            except Exception:
                QMessageBox.warning(self, "Save Failed", f"Could not save image: {file_path}")

        if refresh_callback:
            refresh_callback()
        self._update_image_button_state()

    def _paste_image(self, kind: str, refresh_callback=None):
        """Save an image from clipboard."""
        if not self.question_id or not self.db_service:
            return

        clipboard = QGuiApplication.clipboard()
        image: QImage = clipboard.image()
        if image.isNull():
            QMessageBox.information(self, "No Image", "Clipboard does not contain an image.")
            return

        buffer = QBuffer()
        buffer.open(QBuffer.WriteOnly)
        image.save(buffer, "PNG")
        data = buffer.data().data()

        try:
            self.db_service.add_question_image_bytes(int(self.question_id), kind, data, "image/png")
        except Exception:
            QMessageBox.warning(self, "Save Failed", "Could not save image from clipboard.")
            return

        if refresh_callback:
            refresh_callback()
        self._update_image_button_state()

    def _clear_images(self, kind: str, refresh_callback=None):
        """Delete all images for this kind."""
        if not self.question_id or not self.db_service:
            return

        confirm = QMessageBox.question(
            self,
            "Clear images",
            f"Remove all {kind} images for this question?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        try:
            self.db_service.delete_images(int(self.question_id), kind)
        except Exception:
            QMessageBox.warning(self, "Delete Failed", "Could not delete images.")
            return

        if refresh_callback:
            refresh_callback()
        self._update_image_button_state()





class QuestionCardWidget(QLabel):

    """

    Modern card widget for displaying a single question with preview.

    

    Features:

    - Card-based layout with shadow effect

    - Inline question preview (max 20 words)

    - Prominent Qno and page number

    - Tag badges inline

    - Source metadata (question set | magazine)

    - Hover effect with elevation

    - Selectable with visual feedback

    

    Layout:

        GGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG

        G Q15  = Page 45    =+n+ important -+ prev-year    G

        G GGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG  G

        G A particle of mass 2kg moves under a force...   G

        G Calculate the acceleration when velocity is...  G

        G                                                  G

        G = JEE Main 2024 Paper 1 | Physics For You     G

        GGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG

    """

    

    clicked = Signal(dict)  # Emits full question data

    

    def __init__(self, question_data: dict, parent=None):

        """

        Initialize question card.

        

        Args:

            question_data: Dict with qno, page, question_text, question_set_name, magazine, tags

            parent: Parent widget

        """

        super().__init__(parent)

        self.question_data = question_data

        self.question_id = question_data.get("question_id") or question_data.get("id")
        self.db_service = self._find_db_service()

        self.is_selected = False
        self.original_stylesheet = ""
        self.is_custom_list_card = False  # Flag set by wrapper when used in custom list view
        self.has_images = False  # Tracks whether this question has any images

        # Enable drag
        self.setAcceptDrops(False)  # Cards don't accept drops

        # Build card HTML
        self.has_images = self._compute_has_images()
        self._build_card()

        

        # Card styling

        self.setTextFormat(Qt.RichText)

        self.setWordWrap(True)

        self.setTextInteractionFlags(Qt.NoTextInteraction)  # Disable text selection, enable click

        self.original_stylesheet = """

            QLabel {

                background-color: #f8fafc;

                border: 1px solid #e2e8f0;

                border-radius: 8px;

                padding: 12px;

                margin: 4px;

            }

            QLabel:hover {

                background-color: #ffffff;

                border: 2px solid #3b82f6;

            }

        """

        self.setStyleSheet(self.original_stylesheet)

        

        self.setCursor(Qt.PointingHandCursor)

        self.setMinimumHeight(100)

        self.setMaximumHeight(150)

        # Image button
        self.image_btn = QPushButton(self)
        self.image_btn.setIcon(load_icon("image.svg"))
        self.image_btn.setIconSize(QSize(16, 16))
        self.image_btn.setToolTip("View / add question & answer images")
        self.image_btn.setStyleSheet(self._image_button_style(active=False))
        self.image_btn.setFixedSize(28, 28)
        self.image_btn.clicked.connect(self._show_image_popover)
        self.image_btn.setVisible(False)
        self.image_btn.setCursor(Qt.PointingHandCursor)

        # Edit button
        self.edit_btn = QPushButton(self)
        self.edit_btn.setIcon(load_icon("edit.svg"))
        self.edit_btn.setIconSize(QSize(14, 14))
        self.edit_btn.setToolTip("Edit question")
        self.edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #f59e0b;
                color: white;
                border: none;
                border-radius: 50%;
                width: 24px;
                height: 24px;
                padding: 0px;
                font-weight: bold;
                font-size: 12px;
                qproperty-flat: true;
            }
            QPushButton:hover {
                background-color: #d97706;
            }
        """)
        self.edit_btn.setFixedSize(24, 24)
        self.edit_btn.clicked.connect(self._show_edit_dialog)
        self.edit_btn.setVisible(False)
        self.edit_btn.setCursor(Qt.PointingHandCursor)
        self.image_btn.raise_()

        self._update_image_button_state()

    

    def _compute_has_images(self) -> bool:
        """Determine if this question has any images stored."""
        if not (self.db_service and self.question_id):
            return False
        try:
            counts = self.db_service.get_image_counts(int(self.question_id))
            return bool(counts and any(v > 0 for v in counts.values()))
        except Exception:
            return False


    def _build_card(self):

        """Build HTML content for the card."""

        q = self.question_data

        

        # Extract data with fallbacks

        qno = q.get("qno", "?")

        page = q.get("page", "?")

        question_text = q.get("text", q.get("question_text", "No question text available"))

        question_set = q.get("question_set_name", "Unknown")

        magazine = q.get("magazine", "Unknown")

        tags = q.get("tags", [])

        

        # Truncate question to ~20 words (approximately 100 chars)

        preview = self._truncate_text(question_text, max_words=20)

        

        # Build tag badges HTML

        tag_html = ""

        if tags:

            tag_colors = {

                "important": "#ef4444",

                "previous year": "#f59e0b",

                "prev-year": "#f59e0b",

                "conceptual": "#8b5cf6",

                "numerical": "#10b981",

                "difficult": "#dc2626",

                "easy": "#22c55e",

            }

            tag_badges = []

            for tag in tags[:3]:  # Show max 3 tags

                color = tag_colors.get(tag.lower(), "#6b7280")

                tag_badges.append(

                    f'<span style="background-color: {color}; color: white; '

                    f'padding: 2px 6px; border-radius: 3px; font-size: 10px; '

                    f'font-weight: bold; margin-left: 4px;">{tag}</span>'

                )

            tag_html = " ".join(tag_badges)

        

        # Add checkmark if selected

        selection_icon = ""

        if self.is_selected:

            selection_icon = '<span style="color: #10b981; font-size: 18px; font-weight: bold; margin-right: 8px;">✓</span>'


        camera_html = ""
        if self.has_images:
            camera_html = '<span style="margin-left: 6px; font-size: 12px; color: #0ea5e9;">📷</span>'
        

        # Build card HTML

        html = f"""

        <div style="line-height: 1.4;">

            <div style="margin-bottom: 8px;">

                {selection_icon}<span style="color: #1e40af; font-size: 16px; font-weight: bold;">{qno}</span>

                <span style="color: #64748b; font-size: 12px; margin-left: 12px;">Page {page}</span>{camera_html}

                {tag_html}

            </div>

            <div style="border-top: 1px solid #cbd5e1; padding-top: 8px; margin-bottom: 8px;">

                <p style="color: #1f2937; font-size: 13px; margin: 0; line-height: 1.5;">

                    {preview}

                </p>

            </div>

            <div style="font-size: 11px; color: #94a3b8;">

                <span style="color: #475569;">{question_set}</span> | 

                <span style="color: #475569;">{magazine}</span>

            </div>

        </div>

        """

        

        self.setText(html)

    

    def _truncate_text(self, text: str, max_words: int = 20) -> str:

        """

        Truncate text to approximately max_words.

        

        Args:

            text: Full text

            max_words: Maximum number of words

            

        Returns:

            Truncated text with ellipsis

        """

        words = text.split()

        if len(words) <= max_words:

            return text



        truncated = " ".join(words[:max_words])

        return truncated + "..."

    def enterEvent(self, event):
        """Show image/edit buttons on hover."""
        self.image_btn.setVisible(True)
        # Always show edit button so user can see the affordance; dialog will guard missing IDs.
        self.edit_btn.setVisible(True)
        self._position_top_buttons()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Hide hover buttons when leaving."""
        self.image_btn.setVisible(False)
        self.edit_btn.setVisible(False)
        super().leaveEvent(event)

    def resizeEvent(self, event):
        """Keep hover buttons anchored top-right on resize."""
        super().resizeEvent(event)
        self._position_top_buttons()

    def _position_top_buttons(self):
        self.image_btn.move(self.width() - 32, 4)
        self.edit_btn.move(self.width() - 64, 4)

    def _find_db_service(self):
        """Walk parents to find db_service if available."""
        parent = self.parent()
        while parent:
            if hasattr(parent, "db_service"):
                return getattr(parent, "db_service")
            parent = parent.parent()
        return None

    def _image_button_style(self, active: bool) -> str:
        """Return stylesheet for image button; green when active, blue otherwise."""
        if active:
            return """
            QPushButton {
                background-color: #16a34a;
                color: white;
                border: none;
                border-radius: 50%;
                width: 28px;
                height: 28px;
                padding: 0px;
                font-weight: bold;
                font-size: 14px;
                qproperty-flat: true;
            }
            QPushButton:hover {
                background-color: #15803d;
            }
            """
        return """
        QPushButton {
            background-color: #0ea5e9;
            color: white;
            border: none;
            border-radius: 50%;
            width: 28px;
            height: 28px;
            padding: 0px;
            font-weight: bold;
            font-size: 14px;
            qproperty-flat: true;
        }
        QPushButton:hover {
            background-color: #0284c7;
        }
        """

    def _show_edit_dialog(self):
        """Open edit dialog and persist changes."""
        if not (self.db_service and self.question_id):
            try:
                print(f"[debug] edit_unavailable db={bool(self.db_service)} qid={self.question_id}", flush=True)
            except Exception:
                pass
            msg = QMessageBox(self)
            msg.setWindowTitle("Edit unavailable")
            msg.setText("Database service or question ID missing.")
            msg.setIcon(QMessageBox.Information)
            msg.setStyleSheet("QLabel{color: #0f172a;}")
            msg.exec()
            return
        from ui.dialogs import QuestionEditDialog  # local import to avoid circular

        dlg = QuestionEditDialog(self.question_data, self)
        if dlg.exec() != QDialog.Accepted:
            return

        updates = dlg.get_updates()
        try:
            self.db_service.update_question_fields(int(self.question_id), updates)
            # Update local data and rebuild card
            self.question_data.update(
                {
                    "qno": updates.get("question_number", self.question_data.get("qno")),
                    "page": updates.get("page_range", self.question_data.get("page")),
                    "question_set_name": updates.get("question_set_name", self.question_data.get("question_set_name")),
                    "magazine": updates.get("magazine", self.question_data.get("magazine")),
                    "text": updates.get("question_text", self.question_data.get("text")),
                    "answer_text": updates.get("answer_text", self.question_data.get("answer_text")),
                    "chapter": updates.get("chapter", self.question_data.get("chapter")),
                    "high_level_chapter": updates.get("high_level_chapter", self.question_data.get("high_level_chapter")),
                }
            )
            self._build_card()
        except Exception as exc:
            QMessageBox.warning(self, "Save failed", f"Could not save changes:\n{exc}")

    def _update_image_button_state(self):
        """Switch icon to filled version when images exist."""
        icon = load_icon("image.svg")
        has_images = False
        if self.db_service and self.question_id:
            try:
                counts = self.db_service.get_image_counts(int(self.question_id))
                has_images = bool(counts and any(v > 0 for v in counts.values()))
                if has_images:
                    icon = load_icon("image_filled.svg")
            except Exception:
                pass
        self.image_btn.setIcon(icon)
        self.image_btn.setStyleSheet(self._image_button_style(active=has_images))

    def _show_image_popover(self):
        """Show dialog with tabs for question/answer images."""
        if not self.question_id:
            QMessageBox.information(self, "No Question ID", "Cannot manage images because this question is missing an ID.")
            return

        if not self.db_service:
            QMessageBox.warning(self, "Database Unavailable", "Database service is not available to load/save images.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Images")
        dialog.setMinimumSize(520, 400)

        root_layout = QVBoxLayout(dialog)
        tabs = QTabWidget(dialog)
        root_layout.addWidget(tabs)

        def build_tab(kind: str):
            tab = QWidget()
            layout = QVBoxLayout(tab)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(8)

            buttons = QHBoxLayout()
            add_btn = QPushButton("Add from files")
            add_btn.setIcon(load_icon("add.svg"))
            add_btn.setIconSize(QSize(14, 14))
            add_btn.clicked.connect(lambda: self._add_images(kind, refresh))
            buttons.addWidget(add_btn)

            paste_btn = QPushButton("Paste from clipboard")
            paste_btn.setToolTip("Paste an image currently in clipboard")
            paste_btn.clicked.connect(lambda: self._paste_image(kind, refresh))
            buttons.addWidget(paste_btn)

            clear_btn = QPushButton("Clear all")
            clear_btn.setStyleSheet("background-color: #ef4444; color: white; border: none; border-radius: 4px; padding: 6px 12px;")
            clear_btn.clicked.connect(lambda: self._clear_images(kind, refresh))
            buttons.addWidget(clear_btn)

            buttons.addStretch()
            layout.addLayout(buttons)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            content = QWidget()
            content_layout = QVBoxLayout(content)
            content_layout.setAlignment(Qt.AlignTop)
            scroll.setWidget(content)
            layout.addWidget(scroll)

            def refresh():
                while content_layout.count():
                    item = content_layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
                try:
                    images = self.db_service.get_images(int(self.question_id), kind)
                except Exception as exc:
                    err = QLabel(f"Failed to load images: {exc}")
                    err.setStyleSheet("color: #dc2626;")
                    content_layout.addWidget(err)
                    return

                if not images:
                    empty = QLabel("No images yet.")
                    empty.setStyleSheet("color: #94a3b8;")
                    content_layout.addWidget(empty)
                    return

                for img in images:
                    pixmap = QPixmap()
                    pixmap.loadFromData(bytes(img["data"]))
                    if not pixmap.isNull():
                        pixmap = pixmap.scaledToWidth(360, Qt.SmoothTransformation)
                    lbl = QLabel()
                    lbl.setPixmap(pixmap)
                    lbl.setStyleSheet("padding: 4px; border: 1px solid #e2e8f0; border-radius: 6px;")
                    content_layout.addWidget(lbl)

            refresh()
            return tab, refresh

        q_tab, q_refresh = build_tab("question")
        a_tab, a_refresh = build_tab("answer")
        tabs.addTab(q_tab, "Question images")
        tabs.addTab(a_tab, "Answer images")

        dialog.exec()
        self._update_image_button_state()

    def _add_images(self, kind: str, refresh_callback=None):
        """Open file picker and attach images of the given kind for this question."""
        if not self.question_id or not self.db_service:
            return

        dialog_title = "Select question images" if kind == "question" else "Select answer images"
        files, _ = QFileDialog.getOpenFileNames(
            self,
            dialog_title,
            "",
            "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp);;All Files (*)",
        )
        if not files:
            return

        for file_path in files:
            try:
                self.db_service.add_question_image(int(self.question_id), kind, Path(file_path))
            except Exception:
                QMessageBox.warning(self, "Save Failed", f"Could not save image: {file_path}")

        if refresh_callback:
            refresh_callback()
        self._update_image_button_state()

    def _paste_image(self, kind: str, refresh_callback=None):
        """Save an image from clipboard."""
        if not self.question_id or not self.db_service:
            return

        clipboard = QGuiApplication.clipboard()
        image: QImage = clipboard.image()
        if image.isNull():
            QMessageBox.information(self, "No Image", "Clipboard does not contain an image.")
            return

        buffer = QBuffer()
        buffer.open(QBuffer.WriteOnly)
        image.save(buffer, "PNG")
        data = buffer.data().data()

        try:
            self.db_service.add_question_image_bytes(int(self.question_id), kind, data, "image/png")
        except Exception:
            QMessageBox.warning(self, "Save Failed", "Could not save image from clipboard.")
            return

        if refresh_callback:
            refresh_callback()
        self._update_image_button_state()

    def _clear_images(self, kind: str, refresh_callback=None):
        """Delete all images for this kind."""
        if not self.question_id or not self.db_service:
            return

        confirm = QMessageBox.question(
            self,
            "Clear images",
            f"Remove all {kind} images for this question?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        try:
            self.db_service.delete_images(int(self.question_id), kind)
        except Exception:
            QMessageBox.warning(self, "Delete Failed", "Could not delete images.")
            return

        if refresh_callback:
            refresh_callback()
        self._update_image_button_state()

    

    def mousePressEvent(self, event):

        """Handle card click - toggle selection or copy metadata."""

        if event.button() == Qt.LeftButton:

            # Store press position for drag distance calculation

            self._drag_start_position = event.pos()

            # Emit signal for selection handling (parent will handle multi-select logic)

            self.clicked.emit(self.question_data)

        super().mousePressEvent(event)

    

    def mouseDoubleClickEvent(self, event):

        """Handle double-click - copy based on selected mode."""

        if event.button() == Qt.LeftButton:

            q = self.question_data

            qno = q.get("qno", "?")

            page = q.get("page", "?")

            question_set = q.get("question_set_name", "Unknown")

            magazine = q.get("magazine", "Unknown")

            chapter = q.get("chapter", "Unknown")

            tags = q.get("tags", "")

            question_text = q.get("text", "")

            

            # Get copy mode from parent window

            parent_window = self._get_parent_window()

            if parent_window:

                if self.is_custom_list_card and hasattr(parent_window, "list_copy_mode"):

                    copy_mode = parent_window.list_copy_mode

                else:

                    copy_mode = parent_window.copy_mode

            else:

                copy_mode = "Copy: Text"

            

            # Build clipboard text based on selected mode

            if copy_mode == "Copy: Metadata":

                # Metadata only: Q15 | P34 | Chapter | Question set name | Magazine edition

                clipboard_text = f"Q{qno} | P{page} | {chapter} | {question_set} | {magazine}"

            elif copy_mode == "Copy: Both":

                # Both: Full formatted text with question and metadata

                tags_str = f" | Tags: {tags}" if tags else ""

                clipboard_text = (

                    f"Q{qno} - {question_set}\n"

                    f"Chapter: {chapter} | Page: {page}{tags_str}\n"

                    f"Magazine: {magazine}\n\n"

                    f"{question_text}"

                )

            else:  # "Copy: Text" - default

                # Text only: Just the question

                clipboard_text = question_text

            

            # Copy to clipboard

            clipboard = QGuiApplication.clipboard()

            clipboard.setText(clipboard_text)

            

            # Visual feedback - flash green

            self._show_copy_feedback()

        super().mouseDoubleClickEvent(event)

    

    def _get_parent_window(self):

        """Traverse up widget hierarchy to find the main window."""

        parent = self.parent()

        while parent:

            if hasattr(parent, 'copy_mode'):

                return parent

            parent = parent.parent()

        return None

    

    def mouseMoveEvent(self, event):

        """Handle drag initiation."""

        if event.buttons() & Qt.LeftButton:

            # Only start drag if moved beyond minimum distance

            if not hasattr(self, '_drag_start_position'):

                super().mouseMoveEvent(event)

                return

            

            drag_distance = (event.pos() - self._drag_start_position).manhattanLength()

            if drag_distance < QApplication.startDragDistance():

                super().mouseMoveEvent(event)

                return

            

            # Start drag operation

            drag = QDrag(self)

            mime_data = QMimeData()

            

            # Serialize question data as JSON (pre-cache this if possible)

            if not hasattr(self, '_cached_question_json'):

                self._cached_question_json = json.dumps(self.question_data)

            

            mime_data.setData("application/x-question-data", self._cached_question_json.encode())

            drag.setMimeData(mime_data)

            

            # Create a simplified drag pixmap (use text instead of full render)

            # This is much faster than rendering the entire widget

            pixmap = QPixmap(200, 80)

            pixmap.fill(Qt.transparent)

            painter = QPainter(pixmap)

            painter.setOpacity(0.8)

            

            # Draw a simple colored rectangle with text

            painter.fillRect(pixmap.rect(), QColor("#f8fafc"))

            painter.setPen(QColor("#1e40af"))

            painter.setFont(QFont("Arial", 10, QFont.Bold))

            painter.drawRect(0, 0, pixmap.width() - 1, pixmap.height() - 1)

            

            # Draw question number and preview

            qno = self.question_data.get('qno', '?')

            text = self.question_data.get('text', '')[:40] + "..."

            painter.drawText(10, 20, f"Q{qno}")

            painter.setFont(QFont("Arial", 8))

            painter.drawText(10, 40, text)

            painter.end()

            

            drag.setPixmap(pixmap)

            drag.setHotSpot(event.pos() - QPoint(100, 40))

            

            # Execute drag (use DropAction instead of just CopyAction for better compatibility)

            drag.exec(Qt.MoveAction | Qt.CopyAction)

        

        super().mouseMoveEvent(event)

    

    def _show_copy_feedback(self):

        """Show visual feedback that copy was successful."""

        # Flash green background

        self.setStyleSheet("""

            QLabel {

                background-color: #d1fae5;

                border: 2px solid #10b981;

                border-radius: 8px;

                padding: 12px;

                margin: 4px;

            }

        """)

        

        # Reset after 500ms

        QTimer.singleShot(500, self._reset_style)

    

    def _reset_style(self):

        """Reset to original style."""

        if not self.is_selected:

            self.setStyleSheet(self.original_stylesheet)

    

    def set_selected(self, selected: bool):

        """Update visual state for selection."""

        self.is_selected = selected

        

        # Rebuild card HTML to show/hide checkmark

        self._build_card()

        

        if selected:

            # Strong blue background with green accent border

            self.setStyleSheet("""

                QLabel {

                    background-color: #bfdbfe;

                    border: 3px solid #10b981;

                    border-radius: 8px;

                    padding: 12px;

                    margin: 4px;

                }

            """)

        else:

            self.setStyleSheet(self.original_stylesheet)





class QuestionAccordionGroup(QWidget):

    """

    Accordion group widget for collapsible question sets.

    

    Features:

    - Collapsible header with expand/collapse icon

    - Question count badge

    - Tag badges for group tags

    - Contains multiple QuestionCardWidget children

    - Smooth expand/collapse animation

    - Context menu support for tagging

    

    Layout:

        =+ JEE Main 2024                    = 75 Questions

           [Tag badges if any]

        GGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG

        [QuestionCardWidget]

        [QuestionCardWidget]

        [QuestionCardWidget]

    """

    

    def __init__(self, group_key: str, questions: list[dict], tags: list[str] = None, tag_colors: dict = None, parent=None, show_page_range: bool = True):

        """

        Initialize accordion group.

        

        Args:

            group_key: Group identifier/name

            questions: List of question data dicts

            tags: List of tag names for this group

            tag_colors: Dict mapping tag names to color hex codes

            parent: Parent widget

        """

        super().__init__(parent)

        self.group_key = group_key

        self.questions = questions

        self.tags = tags or []

        self.tag_colors = tag_colors or {}

        self.show_page_range = show_page_range

        self.is_expanded = False

        self.question_cards = []

        

        # Main layout

        layout = QVBoxLayout(self)

        layout.setContentsMargins(0, 0, 0, 0)

        layout.setSpacing(0)

        

        # Header widget

        self.header = self._create_header()

        self.header.setContextMenuPolicy(Qt.CustomContextMenu)

        self.header.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(self.header)

        

        # Content container (collapsible) with 2-column grid

        self.content_widget = QWidget()

        self.content_layout = QVBoxLayout(self.content_widget)

        self.content_layout.setContentsMargins(8, 8, 8, 8)

        self.content_layout.setSpacing(4)

        

        # Add question cards in 2-column grid layout

        row_layout = None

        for i, question in enumerate(questions):

            card = QuestionCardWidget(question, self)

            card.clicked.connect(self._on_card_clicked)

            self.question_cards.append(card)

            

            # Create new row every 2 cards

            if i % 2 == 0:

                row_layout = QHBoxLayout()

                row_layout.setSpacing(8)

                self.content_layout.addLayout(row_layout)

            

            row_layout.addWidget(card)

            

            # Add stretch to last row if odd number of cards

            if i == len(questions) - 1 and len(questions) % 2 == 1:

                row_layout.addStretch()

        

        self.content_widget.setVisible(False)

        layout.addWidget(self.content_widget)

    

    def _create_header(self) -> QWidget:

        """Create the header widget with expand/collapse button."""

        from PySide6.QtWidgets import QHBoxLayout, QWidget, QPushButton

        

        header_widget = QWidget()

        header_widget.setStyleSheet("""

            QWidget {

                background-color: #e0e7ff;

                border-radius: 6px;

                padding: 8px;

            }

            QWidget:hover {

                background-color: #c7d2fe;

            }

        """)

        header_widget.setCursor(Qt.PointingHandCursor)

        

        header_layout = QHBoxLayout(header_widget)

        header_layout.setContentsMargins(8, 8, 8, 8)

        

        # Expand/collapse icon + title

        self.expand_btn = QPushButton()
        self.expand_btn.setIcon(self.style().standardIcon(QStyle.SP_ArrowRight))
        self.expand_btn.setIconSize(QSize(16, 16))

        self.expand_btn.setStyleSheet("""

            QPushButton {

                background: transparent;

                border: none;

                font-size: 14px;

                padding: 0;

                min-width: 20px;

            }

        """)

        self.expand_btn.clicked.connect(self.toggle_expanded)

        header_layout.addWidget(self.expand_btn)

        

        # Group title

        title = QLabel(self.group_key.title())

        title.setStyleSheet("color: #1e40af; font-weight: bold; font-size: 14px; background: transparent;")

        header_layout.addWidget(title)

        

        # Tag badges

        if self.tags:

            tag_container = QWidget()

            tag_container.setStyleSheet("background: transparent;")

            tag_layout = QHBoxLayout(tag_container)

            tag_layout.setContentsMargins(0, 0, 0, 0)

            tag_layout.setSpacing(4)

            

            for tag in self.tags[:3]:  # Max 3 tags in header

                color = self.tag_colors.get(tag, self._get_tag_color(tag))

                tag_badge = TagBadge(tag, color)

                tag_layout.addWidget(tag_badge)

            

            header_layout.addWidget(tag_container)

        

        header_layout.addStretch()

        

        # Tag management button

        self.tag_btn = QPushButton("Tags")

        self.tag_btn.setToolTip("Manage tags for this group")
        self.tag_btn.setIcon(load_icon("tag.svg"))
        self.tag_btn.setIconSize(QSize(14, 14))

        self.tag_btn.setStyleSheet("""

            QPushButton {

                background: transparent;

                border: 1px solid #3b82f6;

                border-radius: 4px;

                padding: 4px 8px;

                font-size: 14px;

                min-width: 30px;

            }

            QPushButton:hover {

                background-color: #3b82f6;

            }

        """)

        self.tag_btn.clicked.connect(self._show_tag_menu)

        header_layout.addWidget(self.tag_btn)

        

        # Question count + page range badge (compact)

        page_range = self._compute_page_range() if self.show_page_range else ""

        count_text = f"{len(self.questions)} q"

        if page_range:

            count_text += f" | {page_range}"

        count_label = QLabel(count_text)

        count_label.setStyleSheet("""

            QLabel {

                background-color: #3b82f6;

                color: white;

                padding: 2px 8px;

                border-radius: 4px;

                font-size: 11px;

                font-weight: 600;

                letter-spacing: 0.2px;

            }

        """)

        header_layout.addWidget(count_label)

        # Make entire header clickable

        header_widget.mousePressEvent = lambda e: self.toggle_expanded()

        

        return header_widget



    def _compute_page_range(self) -> str:

        """Return a compact page range like 'p2-15' for questions in this group."""

        pages = []

        for q in self.questions:

            try:

                page_val = float(str(q.get("page", "")).strip())

            except (ValueError, TypeError):

                continue

            pages.append(page_val)

        if not pages:

            return ""

        min_p, max_p = min(pages), max(pages)



        def _fmt(val: float) -> str:

            if val.is_integer():

                return str(int(val))

            text = f"{val:.2f}".rstrip("0").rstrip(".")

            return text



        if min_p == max_p:

            return f"p{_fmt(min_p)}"

        return f"p{_fmt(min_p)}-{_fmt(max_p)}"

    

    def toggle_expanded(self):

        """Toggle expand/collapse state."""

        self.is_expanded = not self.is_expanded

        self.content_widget.setVisible(self.is_expanded)

        icon = QStyle.SP_ArrowDown if self.is_expanded else QStyle.SP_ArrowRight
        self.expand_btn.setIcon(self.style().standardIcon(icon))

    

    def _on_card_clicked(self, question_data: dict):

        """Handle click on a question card."""

        # Forward to parent window for handling

        if hasattr(self.parent(), 'on_question_card_clicked'):

            self.parent().on_question_card_clicked(question_data)

    

    def get_all_cards(self) -> list:

        """Return all question card widgets."""

        return self.question_cards

    

    def _show_context_menu(self, position):

        """Show context menu for group operations."""

        if hasattr(self.parent(), 'show_group_context_menu'):

            self.parent().show_group_context_menu(self.group_key, self.header.mapToGlobal(position))

    

    def _show_tag_menu(self):

        """Show tag management dialog."""

        # Navigate up to find main window

        widget = self.parent()

        while widget:

            if hasattr(widget, '_assign_tag_to_group'):

                widget._assign_tag_to_group(self.group_key)

                return

            if hasattr(widget, 'main_window') and hasattr(widget.main_window, '_assign_tag_to_group'):

                widget.main_window._assign_tag_to_group(self.group_key)

                return

            widget = widget.parent() if hasattr(widget, 'parent') and callable(widget.parent) else None

    

    def _get_tag_color(self, tag: str) -> str:

        """Get fallback color for a tag."""

        colors = {

            "important": "#ef4444",

            "previous year": "#f59e0b",

            "prev-year": "#f59e0b",

            "conceptual": "#8b5cf6",

            "numerical": "#10b981",

            "difficult": "#dc2626",

            "easy": "#22c55e",

        }

        return colors.get(tag.lower(), "#6b7280")





class QuestionListCardView(QScrollArea):

    """

    Scrollable container for question accordion groups (Option 1 design).

    

    Replaces the traditional QTreeWidget with a modern card-based layout.

    Contains multiple QuestionAccordionGroup widgets in a vertical layout.

    

    Features:

    - Smooth scrolling

    - Responsive layout

    - Multiple selection support via card clicks

    - Context menu support

    - Question detail viewing on click

    """

    

    question_selected = Signal(dict)  # Emits question data when card clicked

    

    def __init__(self, parent=None):

        """Initialize the card view container."""

        super().__init__(parent)

        

        self.main_window = parent  # Store reference to main window

        

        # Scroll area setup

        self.setWidgetResizable(True)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        

        # Container widget

        self.container = QWidget()

        self.container_layout = QVBoxLayout(self.container)

        self.container_layout.setContentsMargins(8, 8, 8, 8)

        self.container_layout.setSpacing(12)

        self.container_layout.addStretch()  # Push groups to top

        

        self.setWidget(self.container)

        

        # Track accordion groups

        self.accordion_groups = []

        self.selected_questions = []  # Track selected question data

        

        # Styling

        self.setStyleSheet("""

            QScrollArea {

                border: 1px solid #e2e8f0;

                background-color: #ffffff;

            }

        """)

    

    def clear(self):

        """Remove all accordion groups."""

        # Remove all groups except the stretch

        while self.container_layout.count() > 1:

            item = self.container_layout.takeAt(0)

            if item.widget():

                item.widget().deleteLater()

        

        self.accordion_groups.clear()

        self.selected_questions.clear()

    

    def add_group(self, group_key: str, questions: list[dict], tags: list[str] = None, tag_colors: dict = None, show_page_range: bool = True):

        """

        Add an accordion group to the view.

        

        Args:

            group_key: Group identifier

            questions: List of question data dicts

            tags: List of tags for this group

            tag_colors: Dict mapping tag names to color hex codes

        """

        group = QuestionAccordionGroup(group_key, questions, tags, tag_colors, self, show_page_range)

        

        # Insert before the stretch at the end

        self.container_layout.insertWidget(len(self.accordion_groups), group)

        self.accordion_groups.append(group)

    

    def on_question_card_clicked(self, question_data: dict):

        """

        Handle question card click with selection support.

        

        Args:

            question_data: Full question data dict

        """

        from PySide6.QtWidgets import QApplication

        

        # Check if Ctrl key is pressed

        modifiers = QApplication.keyboardModifiers()

        ctrl_pressed = bool(modifiers & Qt.ControlModifier)

        

        # Find the card widget that was clicked

        clicked_card = None

        for group in self.accordion_groups:

            for card in group.get_all_cards():

                if card.question_data == question_data:

                    clicked_card = card

                    break

            if clicked_card:

                break

        

        if not clicked_card:

            # Emit signal for detail display even if card not found

            self.question_selected.emit(question_data)

            return

        

        # Handle selection

        if ctrl_pressed:

            # Toggle selection (multi-select)

            if clicked_card.is_selected:

                clicked_card.set_selected(False)

                if question_data in self.selected_questions:

                    self.selected_questions.remove(question_data)

            else:

                clicked_card.set_selected(True)

                if question_data not in self.selected_questions:

                    self.selected_questions.append(question_data)

        else:

            # Single selection - clear others

            for group in self.accordion_groups:

                for card in group.get_all_cards():

                    if card != clicked_card:

                        card.set_selected(False)

            

            # Clear selection list and add only this one

            self.selected_questions.clear()

            clicked_card.set_selected(True)

            self.selected_questions.append(question_data)

        

        # Emit signal for detail display

        self.question_selected.emit(question_data)

    

    def show_group_context_menu(self, group_key: str, position):

        """

        Forward context menu request to parent window.

        

        Args:

            group_key: Group identifier

            position: Global position for menu

        """

        if hasattr(self.parent(), 'show_group_context_menu_for_card'):

            self.parent().show_group_context_menu_for_card(group_key, position)

    

    def get_selected_questions(self) -> list[dict]:

        """

        Get all currently selected questions.

        

        Returns:

            List of question data dicts

        """

        return self.selected_questions

    

    def expand_all(self):

        """Expand all accordion groups."""

        for group in self.accordion_groups:

            if not group.is_expanded:

                group.toggle_expanded()

    

    def collapse_all(self):

        """Collapse all accordion groups."""

        for group in self.accordion_groups:

            if group.is_expanded:

                group.toggle_expanded()





class DashboardView(QWidget):

    """

    Dashboard view with workbook statistics and data samples.

    

    Displays:

    - Total questions and chapters statistics

    - Chapter-wise question count (using chapter grouping JSON)

    - Latest magazine edition info (last row)

    - Page range for latest magazine

    """

    

    def __init__(self, parent=None):

        """Initialize dashboard view."""

        super().__init__(parent)

        

        layout = QVBoxLayout(self)

        layout.setContentsMargins(20, 20, 20, 20)

        layout.setSpacing(8)  # Reduced spacing to keep stats close to title

        

        # Title

        title = QLabel("Dashboard")

        title.setStyleSheet("""

            QLabel {

                font-size: 24px;

                font-weight: bold;

                color: #1e40af;

                padding-bottom: 0px;

                margin-bottom: 0px;

            }

        """)

        layout.addWidget(title)

        

        # === Summary Stats Cards (2 Rows) ===

        summary_container = QVBoxLayout()

        summary_container.setSpacing(12)

        summary_container.setContentsMargins(0, 0, 0, 0)

        

        # First Row: Total Questions, Total Chapters, Unique Magazines

        first_row_layout = QHBoxLayout()

        first_row_layout.setSpacing(12)

        first_row_layout.setContentsMargins(0, 0, 0, 0)

        

        # Total Questions Card

        self.total_q_card = self._create_stat_card("Total Questions", "0", "#3b82f6")

        first_row_layout.addWidget(self.total_q_card)

        

        # Total Chapters Card

        self.total_chapters_card = self._create_stat_card("Total Chapters", "0", "#8b5cf6")

        first_row_layout.addWidget(self.total_chapters_card)

        

        # Unique Magazines Card

        self.unique_mags_card = self._create_stat_card("Unique Magazines", "0", "#ec4899")

        first_row_layout.addWidget(self.unique_mags_card)

        

        first_row_layout.addStretch()

        summary_container.addLayout(first_row_layout)

        

        # Second Row: Last Magazine Card

        second_row_layout = QHBoxLayout()

        second_row_layout.setSpacing(12)

        second_row_layout.setContentsMargins(0, 0, 0, 0)

        

        # Last Magazine Card

        self.last_mag_card = self._create_stat_card("Last Magazine Inserted", "-", "#f59e0b")

        second_row_layout.addWidget(self.last_mag_card)

        

        second_row_layout.addStretch()

        summary_container.addLayout(second_row_layout)

        

        layout.addLayout(summary_container)

        

        layout.addStretch()

    

    def _create_stat_card(self, title: str, value: str, color: str) -> QWidget:

        """Create a statistics card with title and value."""

        card = QWidget()

        card.setStyleSheet(f"""

            QWidget {{

                background-color: transparent;

                border: none;

                padding: 8px;

            }}

        """)

        card_layout = QVBoxLayout(card)

        card_layout.setContentsMargins(0, 0, 0, 0)

        card_layout.setSpacing(4)

        

        title_label = QLabel(title)

        title_label.setStyleSheet(f"""

            QLabel {{

                font-size: 12px;

                color: #475569;

                font-weight: 600;

            }}

        """)

        card_layout.addWidget(title_label)

        

        value_label = QLabel(value)

        value_label.setStyleSheet(f"""

            QLabel {{

                font-size: 28px;

                font-weight: bold;

                color: {color};

            }}

        """)

        card_layout.addWidget(value_label)

        

        # Store value label for updates

        card.value_label = value_label

        return card

    



    

    def update_dashboard_data(

        self,

        df,

        chapter_groups: dict[str, list[str]],

        magazine_details: list[dict] | None = None,

        mag_display_name: str = "",

        mag_page_ranges: dict[str, tuple[str, str]] | None = None,

    ) -> None:

        """

        Update dashboard with data from workbook DataFrame.

        

        Args:

            df: Pandas DataFrame with workbook data

            chapter_groups: Dict mapping group names to chapter lists

            magazine_details: Optional list of magazine details from analysis

            mag_display_name: Display name of the currently detected magazine

            mag_page_ranges: Optional mapping of normalized edition -> (min_page, max_page)

        """

        if df is None or df.empty:

            return

        

        # === Update Summary Stats ===

        total_questions = len(df)

        self.total_q_card.value_label.setText(str(total_questions))

        

        magazine_col = None

        for col in ['Magazine', 'magazine', 'Magazine edition', 'JEE Main Session']:

            if col in df.columns:

                magazine_col = col

                break

        magazines = set()



        # Get unique chapters - prefer grouping config, fallback to dataframe

        if chapter_groups:

            chapters_in_data = {ch for group in chapter_groups.values() for ch in group}

            total_chapters = len(chapters_in_data)

        else:

            chapters_in_data = set()

            chapter_col = None

            if 'Chapter' in df.columns:

                chapter_col = 'Chapter'

            elif 'chapter' in df.columns:

                chapter_col = 'chapter'

            elif 'High level chapter from IIT JEE' in df.columns:  # Fallback for JEE papers

                chapter_col = 'High level chapter from IIT JEE'

            elif 'Subject' in df.columns:  # Fallback for different column naming

                chapter_col = 'Subject'

            

            if chapter_col:

                chapters_in_data = set(df[chapter_col].dropna().unique())

            total_chapters = len(chapters_in_data)

        self.total_chapters_card.value_label.setText(str(total_chapters))

        

        # Get unique magazines count from analysis if available

        # Detect magazine column once for reuse

        magazine_col = None

        for col in ['Magazine', 'magazine', 'Magazine edition', 'JEE Main Session']:

            if col in df.columns:

                magazine_col = col

                break

        

        magazines = set()

        if magazine_details is not None:

            self.unique_mags_card.value_label.setText(str(len(magazine_details)))

        elif magazine_col:

            magazines = set(df[magazine_col].dropna().unique())

            self.unique_mags_card.value_label.setText(str(len(magazines)))

        else:

            self.unique_mags_card.value_label.setText("0")

        

        # === Update Latest Magazine Edition ===

        latest_display = "-"

        last_info = self._get_last_magazine_entry(df)

        if last_info:

            last_mag = last_info["mag"]

            full_norm = normalize_magazine_edition(last_mag)

            page_min, page_max = ("", "")

            if mag_page_ranges:

                page_min, page_max = mag_page_ranges.get(full_norm, ("", ""))

            if (not page_min or not page_max) and df is not None:

                page_min, page_max = self._compute_page_range_from_df(df, full_norm)

            page_text = f"(Pages: {page_min}-{page_max})" if page_min and page_max else "(Pages: N/A)"

            latest_display = f"{last_mag}\n{page_text}"

        elif magazine_details:

            # Fallback: derive from computed details when magazine column is missing

            normalized_current = self._normalize_label(mag_display_name) if mag_display_name else ""

            chosen_entry = None

            for entry in magazine_details:

                if normalized_current and self._normalize_label(entry.get("display_name", "")) == normalized_current:

                    chosen_entry = entry

                    break

            if chosen_entry is None and magazine_details:

                chosen_entry = magazine_details[-1]

            

            editions = chosen_entry.get("editions", []) if chosen_entry else []

            if editions:

                latest = editions[-1]

                display = latest.get("display", "Unknown")

                full_norm = normalize_magazine_edition(f"{chosen_entry.get('display_name', '')} | {display}")

                page_min, page_max = mag_page_ranges.get(full_norm, ("", "")) if mag_page_ranges else ("", "")

                page_text = f"(Pages: {page_min}-{page_max})" if page_min and page_max else "(Pages: N/A)"

                latest_display = f"{chosen_entry.get('display_name', 'Unknown')} | {display}\n{page_text}"

        self.last_mag_card.value_label.setText(latest_display)



    def _normalize_label(self, label: str) -> str:

        return "".join(c.lower() for c in label if c.isalnum() or c.isspace()).strip()



    def _find_magazine_column_name(self, df) -> str | None:

        """Return magazine column using case-insensitive matching."""

        targets = {"magazine", "magazine edition", "magazine edition ", "jEE main session".lower()}

        for col in df.columns:

            norm = str(col).strip().lower()

            if norm in targets:

                return col

        return None



    def _find_page_column_name(self, df) -> str | None:

        """Return page column using case-insensitive matching and common aliases."""

        targets = {

            "page",

            "page number",

            "page no",

            "pageno",

            "page_no",

            "page number ",

            "page no.",

        }

        for col in df.columns:

            norm = str(col).strip().lower()

            if norm in targets:

                return col

        return None



    def _get_last_magazine_entry(self, df) -> dict | None:

        """Return last non-empty magazine entry with raw row for debugging."""

        mag_col = self._find_magazine_column_name(df)

        if not mag_col:

            return None

        mag_series = df[mag_col]

        last_idx = mag_series.last_valid_index()

        if last_idx is None:

            return None

        mag_value = str(mag_series.loc[last_idx]).strip()

        page_col = self._find_page_column_name(df)

        page_value = df.at[last_idx, page_col] if page_col else None

        return {

            "mag": mag_value,

            "page": page_value,

            "index": last_idx,

            "row": df.loc[last_idx].to_dict(),

        }



    def _compute_page_range_from_df(self, df, normalized_magazine: str) -> tuple[str, str]:

        """Compute page range for a normalized magazine edition from the dataframe."""

        if df is None or df.empty or not normalized_magazine:

            return ("", "")

        

        magazine_col = self._find_magazine_column_name(df)

        if magazine_col is None:

            return ("", "")

        

        page_col = self._find_page_column_name(df)

        if page_col is None:

            return ("", "")

        

        pages = []

        for mag_val, page_val in zip(df[magazine_col], df[page_col]):

            if mag_val is None or page_val is None:

                continue

            normalized = normalize_magazine_edition(str(mag_val))

            if normalized != normalized_magazine:

                continue

            try:

                page_num = int(float(str(page_val).strip()))

                pages.append(page_num)

            except ValueError:

                continue

        if not pages:

            return ("", "")

        return (str(min(pages)), str(max(pages)))

            







class NavigationSidebar(QWidget):

    """

    Collapsible sidebar navigation for main application views.

    

    Features:

    - 7 navigation items organized hierarchically

    - Visual grouping for Question Analysis sub-items

    - Collapse/expand functionality (150px G 40px)

    - Selected item highlighting

    - Hover effects

    - Icon-only mode when collapsed

    

    Navigation structure:

        = Dashboard

        = Magazine Editions (Question Analysis group)

        = Question List (Question Analysis group)

        = Chapter Grouping (Question Analysis group)

        = Custom Lists (Question Analysis group)

        = Data Import

        = JEE Main Papers

    """

    

    navigation_changed = Signal(int)  # Emits index of selected view

    

    def __init__(self, parent=None):

        super().__init__(parent)

        self.is_expanded = True

        self.selected_index = 0

        self.nav_buttons = []

        

        # Main layout

        layout = QVBoxLayout(self)

        layout.setContentsMargins(0, 0, 0, 0)

        layout.setSpacing(0)

        

        # Scroll area for navigation items

        scroll = QScrollArea()

        scroll.setWidgetResizable(True)

        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll.setStyleSheet("QScrollArea { border: none; background: #f8fafc; }")

        

        # Container for nav buttons

        nav_container = QWidget()

        self.nav_layout = QVBoxLayout(nav_container)

        self.nav_layout.setContentsMargins(0, 8, 0, 8)

        self.nav_layout.setSpacing(2)

        

        # Navigation items: (icon, text, index, is_indented)

        nav_items = [
            ("", "Dashboard", 0, False),
            ("", "Magazine Editions", 1, True),
            ("", "Question List", 2, True),
            ("", "Chapter Grouping", 3, True),
            ("", "Custom Lists", 4, True),
            ("", "Question Set Groups", 5, True),
            ("", "Data Import", 6, False),
            ("", "JEE Main Papers", 7, False),
            ("", "Exams", 8, False),
        ]

        

        for icon, text, index, is_indented in nav_items:

            btn = self._create_nav_button(icon, text, index, is_indented)

            self.nav_buttons.append(btn)

            self.nav_layout.addWidget(btn)

        

        self.nav_layout.addStretch()

        scroll.setWidget(nav_container)

        layout.addWidget(scroll, 1)

        

        # Collapse/expand button at bottom

        self.toggle_btn = QPushButton("G")

        self.toggle_btn.setToolTip("Collapse sidebar")

        self.toggle_btn.clicked.connect(self.toggle_collapse)

        self.toggle_btn.setStyleSheet("""

            QPushButton {

                background-color: #e2e8f0;

                border: none;

                border-top: 1px solid #cbd5e1;

                padding: 12px;

                font-size: 16px;

                text-align: center;

            }

            QPushButton:hover {

                background-color: #cbd5e1;

            }

        """)

        layout.addWidget(self.toggle_btn)

        

        # Set initial size

        self.setMinimumWidth(200)

        self.setMaximumWidth(200)

        

        # Apply sidebar styling

        self.setStyleSheet("""

            QWidget {

                background-color: #f8fafc;

                border-right: 1px solid #e2e8f0;

            }

        """)

        

        # Set initial selection

        self._update_button_states()

    

    def _create_nav_button(self, icon: str, text: str, index: int, is_indented: bool) -> QPushButton:

        """Create a navigation button."""

        btn_text = text if not icon else f"{icon}  {text}"
        btn = QPushButton(btn_text)

        btn.setProperty("nav_index", index)

        btn.setProperty("is_indented", is_indented)

        btn.setCursor(Qt.PointingHandCursor)

        btn.clicked.connect(lambda: self._on_nav_clicked(index))

        

        # Calculate left padding based on indentation

        left_padding = 24 if is_indented else 12

        

        btn.setStyleSheet(f"""

            QPushButton {{

                background-color: transparent;

                border: none;

                border-left: 3px solid transparent;

                padding: 12px 12px 12px {left_padding}px;

                text-align: left;

                font-size: 13px;

                color: #475569;

                font-weight: 500;

            }}

            QPushButton:hover {{

                background-color: #e0e7ff;

                color: #1e40af;

            }}

        """)

        

        return btn

    

    def _on_nav_clicked(self, index: int):

        """Handle navigation button click."""

        if self.selected_index != index:

            self.selected_index = index

            self._update_button_states()

            self.navigation_changed.emit(index)

    

    def _update_button_states(self):

        """Update visual state of all buttons based on selection."""

        for btn in self.nav_buttons:

            index = btn.property("nav_index")

            is_indented = btn.property("is_indented")

            left_padding = 24 if is_indented else 12

            

            if index == self.selected_index:

                # Selected state

                btn.setStyleSheet(f"""

                    QPushButton {{

                        background-color: #dbeafe;

                        border: none;

                        border-left: 3px solid #2563eb;

                        padding: 12px 12px 12px {left_padding}px;

                        text-align: left;

                        font-size: 13px;

                        color: #1e40af;

                        font-weight: 600;

                    }}

                """)

            else:

                # Normal state

                btn.setStyleSheet(f"""

                    QPushButton {{

                        background-color: transparent;

                        border: none;

                        border-left: 3px solid transparent;

                        padding: 12px 12px 12px {left_padding}px;

                        text-align: left;

                        font-size: 13px;

                        color: #475569;

                        font-weight: 500;

                    }}

                    QPushButton:hover {{

                        background-color: #e0e7ff;

                        color: #1e40af;

                    }}

                """)

    

    def toggle_collapse(self):

        """Toggle sidebar between expanded and collapsed states."""

        self.is_expanded = not self.is_expanded

        

        if self.is_expanded:

            # Expand

            self.setMinimumWidth(200)

            self.setMaximumWidth(200)

            self.toggle_btn.setText("G")

            self.toggle_btn.setToolTip("Collapse sidebar")

            

            # Show text on buttons

            nav_items = [

                ("=", "Dashboard"),

                ("=", "Magazine Editions"),

                ("=", "Question List"),

                ("=", "Chapter Grouping"),

                ("=", "Custom Lists"),

                ("=", "Data Import"),

                ("=", "JEE Main Papers"),

            ]

            for i, btn in enumerate(self.nav_buttons):

                icon, text = nav_items[i]

                btn.setText(f"{icon}  {text}")

        else:

            # Collapse

            self.setMinimumWidth(50)

            self.setMaximumWidth(50)

            self.toggle_btn.setText("G")

            self.toggle_btn.setToolTip("Expand sidebar")

            

            # Show only icons

            icons = ["*", "*", "*", "*", "*", "*", "*"]

            for i, btn in enumerate(self.nav_buttons):

                btn.setText(icons[i])

        

        self._update_button_states()

    

    def set_selected_index(self, index: int):

        """Programmatically set selected navigation item."""

        if 0 <= index < len(self.nav_buttons):

            self.selected_index = index

            self._update_button_states()

    

    def get_selected_index(self) -> int:

        """Get currently selected navigation index."""

        return self.selected_index





class QuestionChip(QWidget):

    """

    Compact chip widget as a filled rounded rectangle.

    Shows Q# | P# | Edition with a close button on the right.

    Clickable to highlight corresponding question card.

    """

    

    remove_clicked = Signal(dict)  # Emits question data when remove is clicked

    chip_clicked = Signal(dict)  # Emits question data when chip is clicked

    

    # Class-level cache for tag data to avoid repeated file reads

    _tag_cache = None

    

    @classmethod

    def _load_tag_data(cls):
        """Load tag data from DB (cached at class level)."""
        if cls._tag_cache is not None:
            return cls._tag_cache
        
        from src.config.constants import DEFAULT_DB_PATH
        import json
        
        try:
            db_path = Path(DEFAULT_DB_PATH)
            if db_path.is_file():
                conn = sqlite3.connect(db_path)
                cur = conn.execute("SELECT value_json FROM configs WHERE key = 'TagsConfig'")
                row = cur.fetchone()
                conn.close()
                if row and row[0]:
                    data = json.loads(row[0])
                    group_tags = data.get("group_tags", {})
                    tag_colors = data.get("tag_colors", {})
                    cls._tag_cache = (group_tags, tag_colors)
                    return cls._tag_cache
        except Exception:
            pass
        
        cls._tag_cache = ({}, {})
        return cls._tag_cache
    

    @classmethod

    def invalidate_tag_cache(cls):

        """Invalidate the tag cache (call when tags are updated)."""

        cls._tag_cache = None

    

    def __init__(self, question_data: dict, parent=None):

        super().__init__(parent)

        self.setAttribute(Qt.WA_StyledBackground, True)  # Ensure background color is painted

        self.question_data = question_data

        self.is_highlighted = False

        

        # Get tag color for chip background using group_key to look up tags

        group_key = question_data.get("group_key", "")

        self.bg_color = "#60a5fa"  # Default lighter blue

        

        # Load tag data directly from tags.cfg

        group_tags, tag_colors = self._load_tag_data()

        

        if group_key:

            tags = group_tags.get(group_key, [])

            if tags and tag_colors:

                first_tag = tags[0] if tags else ""

                if first_tag in tag_colors:

                    self.bg_color = tag_colors[first_tag]



        

        layout = QHBoxLayout(self)

        layout.setContentsMargins(6, 4, 6, 4)

        layout.setSpacing(4)

        

        # Extract metadata

        qno = question_data.get("qno", "?")

        page = question_data.get("page", "?")

        magazine = question_data.get("magazine", "")

        

        # Extract just the edition

        edition = self._extract_edition(magazine)

        

        # Compact text: Q# | P# | Edition

        text = f"Q{qno} | P{page}"

        if edition:

            text += f" | {edition}"

        

        self.label = QLabel(text)

        self.label.setObjectName("chipLabel")

        self.label.setStyleSheet("""

            QLabel#chipLabel {

                color: white;

                font-size: 10px;

                font-weight: 600;

                background: transparent;

                border: none;

            }

        """)

        layout.addWidget(self.label)

        

        # Remove button with cross icon

        remove_btn = QPushButton()

        remove_btn.setObjectName("chipRemoveBtn")

        remove_btn.setFixedSize(14, 14)

        remove_btn.setIcon(load_icon("close.svg"))

        remove_btn.setIconSize(QSize(8, 8))

        remove_btn.setStyleSheet("""

            QPushButton#chipRemoveBtn {

                background-color: #ef4444;

                border: none;

                border-radius: 7px;

                padding: 0px;

                margin: 0px;

            }

            QPushButton#chipRemoveBtn:hover {

                background-color: #dc2626;

            }

        """)

        remove_btn.clicked.connect(lambda: self.remove_clicked.emit(self.question_data))

        layout.addWidget(remove_btn)

        

        # Make chip clickable

        self.setCursor(Qt.PointingHandCursor)

        

        # Chip styling - fixed size for consistent layout (4 per row)

        self._update_style()

        self.setFixedSize(120, 24)

    

    def _extract_edition(self, magazine: str) -> str:

        """Extract edition part from magazine string."""

        if not magazine:

            return ""

        

        import re

        

        # Try to match Month'YY pattern

        match = re.search(r"([A-Z][a-z]{2})'(\d{2})", magazine)

        if match:

            return f"{match.group(1)}'{match.group(2)}"

        

        # Try to match Month YY or Month YYYY

        match = re.search(r"([A-Z][a-z]{2,8})\s*['\-]?\s*(\d{2,4})", magazine)

        if match:

            month = match.group(1)[:3]

            year = match.group(2)[-2:]

            return f"{month}'{year}"

        

        # Fallback

        return magazine[:10] if len(magazine) > 10 else magazine

    

    def mousePressEvent(self, event):

        """Handle chip click to highlight corresponding question."""

        if event.button() == Qt.LeftButton:

            self.chip_clicked.emit(self.question_data)

        super().mousePressEvent(event)

    

    def set_highlighted(self, highlighted: bool):

        """Set highlighted state."""

        self.is_highlighted = highlighted

        self._update_style()

    

    def _update_style(self):

        """Update chip styling based on state - filled rounded rectangle."""

        if self.is_highlighted:

            self.setStyleSheet("""

                QuestionChip {

                    background-color: #fef08a;

                    border: 2px solid #eab308;

                    border-radius: 12px;

                }

            """)

        else:

            # Use tag-based color directly in stylesheet

            self.setStyleSheet(f"""

                QuestionChip {{

                    background-color: {self.bg_color};

                    border: 1px solid {self.bg_color};

                    border-radius: 12px;

                }}

            """)





class InactiveQuestionChip(QWidget):

    """

    Deactivated chip for existing questions in a list.

    

    Similar to QuestionChip but:

    - Grayed out background (no color from tags)

    - No close/remove button

    - Still clickable for highlighting

    - Shows as deactivated state

    """

    

    chip_clicked = Signal(dict)  # Emits question data when chip is clicked

    

    def __init__(self, question_data: dict, parent=None):

        super().__init__(parent)

        self.setAttribute(Qt.WA_StyledBackground, True)

        self.question_data = question_data

        self.is_highlighted = False

        

        layout = QHBoxLayout(self)

        layout.setContentsMargins(6, 4, 6, 4)

        layout.setSpacing(4)

        

        # Extract metadata

        qno = question_data.get("qno", "?")

        page = question_data.get("page", "?")

        magazine = question_data.get("magazine", "")

        

        # Extract just the edition

        edition = self._extract_edition(magazine)

        

        # Compact text: Q# | P# | Edition

        text = f"Q{qno} | P{page}"

        if edition:

            text += f" | {edition}"

        

        self.label = QLabel(text)

        self.label.setObjectName("inactiveChipLabel")

        self.label.setStyleSheet("""

            QLabel#inactiveChipLabel {

                color: #64748b;

                font-size: 10px;

                font-weight: 600;

                background: transparent;

                border: none;

            }

        """)

        layout.addWidget(self.label)

        

        # No remove button for inactive chips

        self.setCursor(Qt.PointingHandCursor)

        

        # Chip styling - fixed size, grayed out

        self._update_style()

        self.setFixedSize(120, 24)

    

    def _extract_edition(self, magazine: str) -> str:

        """Extract edition part from magazine string."""

        if not magazine:

            return ""

        

        import re

        

        # Try to match Month'YY pattern

        match = re.search(r"([A-Z][a-z]{2})'(\d{2})", magazine)

        if match:

            return f"{match.group(1)}'{match.group(2)}"

        

        # Try to match Month YY or Month YYYY

        match = re.search(r"([A-Z][a-z]{2,8})\s*['\-]?\s*(\d{2,4})", magazine)

        if match:

            month = match.group(1)[:3]

            year = match.group(2)[-2:]

            return f"{month}'{year}"

        

        # Fallback

        return magazine[:10] if len(magazine) > 10 else magazine

    

    def mousePressEvent(self, event):

        """Handle chip click to highlight corresponding question."""

        if event.button() == Qt.LeftButton:

            self.chip_clicked.emit(self.question_data)

        super().mousePressEvent(event)

    

    def set_highlighted(self, highlighted: bool):

        """Set highlighted state."""

        self.is_highlighted = highlighted

        self._update_style()

    

    def _update_style(self):

        """Update chip styling - grayed out by default."""

        if self.is_highlighted:

            self.setStyleSheet("""

                InactiveQuestionChip {

                    background-color: #fef08a;

                    border: 2px solid #eab308;

                    border-radius: 12px;

                }

            """)

        else:

            # Grayed out background for deactivated state

            self.setStyleSheet("""

                InactiveQuestionChip {

                    background-color: #e2e8f0;

                    border: 1px solid #cbd5e1;

                    border-radius: 12px;

                }

            """)





class DragDropQuestionPanel(QWidget):

    """

    Panel for drag-and-drop question list management.

    

    Features:

    - Dropdown to select target question list

    - Drag-drop area to add questions

    - Shows added questions as removable chips

    - Save (G) and Cancel (G) buttons

    

    Layout:

        GGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG

        G  Add to list: [Dropdown G+]                         [G] [G] G

        GGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG

        G  GGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG

        G  G  [Chip1] [Chip2] [Chip3] [Chip4] [Chip5] [Chip6] ...    GG

        G  G  G Drag questions here                                  GG

        G  GGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG

        GGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG

    """

    

    save_clicked = Signal(str, list)  # Emits (list_name, questions)

    cancel_clicked = Signal()

    

    def __init__(self, question_lists: dict, parent=None):

        super().__init__(parent)

        self.question_lists = question_lists

        self.pending_questions = []  # Questions to be added

        

        self.setAcceptDrops(True)

        

        # Main vertical layout

        main_layout = QVBoxLayout(self)

        main_layout.setContentsMargins(8, 8, 8, 8)

        main_layout.setSpacing(6)

        

        # Top row: List selector + action buttons

        top_row = QHBoxLayout()

        top_row.setSpacing(8)

        

        # List selector label

        list_label = QLabel("Add to list:")

        list_label.setStyleSheet("color: #1e40af; font-weight: 600; background: transparent;")

        top_row.addWidget(list_label)

        

        # List selector

        self.list_selector = QComboBox()

        self.list_selector.addItems(sorted(question_lists.keys()))

        self.list_selector.setMinimumWidth(200)

        self.list_selector.setStyleSheet("""

            QComboBox {

                padding: 4px 8px;

                border: 1px solid #cbd5e1;

                border-radius: 4px;

                background: white;

                color: #0f172a;

            }

            QComboBox::drop-down {

                border: none;

                width: 20px;

            }

            QComboBox QAbstractItemView {

                background: white;

                color: #0f172a;

                selection-background-color: #dbeafe;

                selection-color: #1e40af;

            }

        """)

        top_row.addWidget(self.list_selector)

        

        # Connect dropdown change to update existing questions

        self.list_selector.currentTextChanged.connect(self._on_list_selector_changed)

        

        # Spacer to push buttons to right

        top_row.addStretch()

        

        # Save button - use text that renders reliably

        save_btn = QPushButton("Save")

        save_btn.setToolTip("Save questions to list")

        save_btn.setMinimumWidth(60)

        save_btn.setFixedHeight(28)

        save_btn.setStyleSheet("""

            QPushButton {

                background-color: #10b981;

                color: white;

                border: none;

                border-radius: 4px;

                font-size: 12px;

                font-weight: bold;

                padding: 4px 12px;

            }

            QPushButton:hover {

                background-color: #059669;

            }

        """)

        save_btn.clicked.connect(self._on_save)

        top_row.addWidget(save_btn)

        

        # Cancel button

        cancel_btn = QPushButton("Cancel")

        cancel_btn.setToolTip("Cancel and close")

        cancel_btn.setMinimumWidth(60)

        cancel_btn.setFixedHeight(28)

        cancel_btn.setStyleSheet("""

            QPushButton {

                background-color: #ef4444;

                color: white;

                border: none;

                border-radius: 4px;

                font-size: 12px;

                font-weight: bold;

                padding: 4px 12px;

            }

            QPushButton:hover {

                background-color: #dc2626;

            }

        """)

        cancel_btn.clicked.connect(self._on_cancel)

        top_row.addWidget(cancel_btn)

        

        main_layout.addLayout(top_row)

        

        # Existing questions container

        existing_container = QWidget()

        existing_layout = QVBoxLayout(existing_container)

        existing_layout.setContentsMargins(0, 0, 0, 0)

        existing_layout.setSpacing(4)

        existing_layout.setAlignment(Qt.AlignTop)

        

        # Existing questions label

        existing_label = QLabel("Existing Questions:")

        existing_label.setStyleSheet("""

            QLabel {

                color: #475569;

                font-weight: 600;

                font-size: 11px;

                background: transparent;

            }

        """)

        existing_layout.addWidget(existing_label)

        

        # Scroll area for existing chips

        self.existing_chip_scroll = QScrollArea()

        self.existing_chip_scroll.setWidgetResizable(True)

        self.existing_chip_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.existing_chip_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.existing_chip_scroll.setMaximumHeight(100)  # Increased from 40 to fit chips better

        self.existing_chip_scroll.setStyleSheet("""

            QScrollArea {

                border: none;

                background: transparent;

            }

        """)

        

        # Existing chips container with flow layout

        self.existing_chip_container = QWidget()

        self.existing_chip_layout = QVBoxLayout(self.existing_chip_container)

        self.existing_chip_layout.setContentsMargins(0, 0, 0, 0)

        self.existing_chip_layout.setSpacing(4)

        self.existing_chip_layout.setAlignment(Qt.AlignTop)

        

        # Track existing chips rows

        self.existing_current_row = None

        self.existing_chips_in_row = 0

        

        self.existing_chip_scroll.setWidget(self.existing_chip_container)

        self.existing_chip_scroll.setVisible(False)

        existing_layout.addWidget(self.existing_chip_scroll)

        

        existing_container.setStyleSheet("""

            QWidget {

                background: transparent;

            }

        """)

        main_layout.addWidget(existing_container)

        

        # Drop area container (full width)

        drop_container = QWidget()

        drop_container.setMinimumHeight(50)

        drop_container_layout = QVBoxLayout(drop_container)

        drop_container_layout.setContentsMargins(8, 8, 8, 8)

        drop_container_layout.setSpacing(4)

        

        # Drop area label

        self.drop_label = QLabel("G Drag questions here")

        self.drop_label.setAlignment(Qt.AlignCenter)

        self.drop_label.setStyleSheet("""

            QLabel {

                color: #64748b;

                font-style: italic;

                background: transparent;

            }

        """)

        drop_container_layout.addWidget(self.drop_label)

        

        # Scroll area for chips (full width)

        self.chip_scroll = QScrollArea()

        self.chip_scroll.setWidgetResizable(True)

        self.chip_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.chip_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.chip_scroll.setStyleSheet("""

            QScrollArea {

                border: none;

                background: transparent;

            }

        """)

        

        # Chip container with flow layout (wrapping)

        self.chip_container = QWidget()

        self.chip_main_layout = QVBoxLayout(self.chip_container)

        self.chip_main_layout.setContentsMargins(0, 0, 0, 0)

        self.chip_main_layout.setSpacing(4)

        self.chip_main_layout.setAlignment(Qt.AlignTop)

        

        # Track current row for chip wrapping - more chips per row now

        self.current_chip_row = None

        self.chips_in_current_row = 0

        self.max_chips_per_row = 8  # Increased for full width

        

        self.chip_scroll.setWidget(self.chip_container)

        self.chip_scroll.setVisible(False)

        drop_container_layout.addWidget(self.chip_scroll)

        

        drop_container.setStyleSheet("""

            QWidget {

                background-color: #f8fafc;

                border: 2px dashed #cbd5e1;

                border-radius: 6px;

            }

        """)

        main_layout.addWidget(drop_container, 1)  # Stretch to fill available space

        

        # Panel styling

        self.setStyleSheet("""

            DragDropQuestionPanel {

                background-color: #e0f2fe;

                border: 2px solid #0284c7;

                border-radius: 8px;

            }

        """)

        self.setMinimumHeight(90)

        self.setMaximumHeight(180)

    

    def dragEnterEvent(self, event: QDragEnterEvent):

        """Accept drag events with question data."""

        if event.mimeData().hasFormat("application/x-question-data"):

            event.acceptProposedAction()

            # Highlight drop area

            self.setStyleSheet("""

                DragDropQuestionPanel {

                    background-color: #dbeafe;

                    border: 2px solid #3b82f6;

                    border-radius: 8px;

                }

            """)

    

    def dragLeaveEvent(self, event):

        """Reset styling when drag leaves."""

        self.setStyleSheet("""

            DragDropQuestionPanel {

                background-color: #e0f2fe;

                border: 2px solid #0284c7;

                border-radius: 8px;

            }

        """)

    

    def dropEvent(self, event: QDropEvent):

        """Handle dropped question."""

        if event.mimeData().hasFormat("application/x-question-data"):

            question_json = event.mimeData().data("application/x-question-data").data().decode()

            question_data = json.loads(question_json)

            

            # Check for duplicates

            if not any(q.get("row_number") == question_data.get("row_number") for q in self.pending_questions):

                self.pending_questions.append(question_data)

                self._add_chip(question_data)

            

            event.acceptProposedAction()

            

            # Reset styling

            self.setStyleSheet("""

                DragDropQuestionPanel {

                    background-color: #e0f2fe;

                    border: 2px solid #0284c7;

                    border-radius: 8px;

                }

            """)

    

    def _add_chip(self, question_data: dict):

        """Add a chip for the dropped question."""

        chip = QuestionChip(question_data, self)

        chip.remove_clicked.connect(self._remove_chip)

        chip.chip_clicked.connect(self._on_chip_clicked)

        

        # Create new row if needed (simple max chips per row; width is flexible)

        chips_per_row = self.max_chips_per_row or 6

        if self.current_chip_row is None or self.chips_in_current_row >= chips_per_row:

            self.current_chip_row = QHBoxLayout()

            self.current_chip_row.setSpacing(4)

            self.current_chip_row.setAlignment(Qt.AlignLeft)

            self.chip_main_layout.addLayout(self.current_chip_row)

            self.chips_in_current_row = 0

        

        # Add chip to current row

        self.current_chip_row.addWidget(chip)

        self.chips_in_current_row += 1

        

        # Show chip container, hide label

        self.drop_label.setVisible(False)

        self.chip_scroll.setVisible(True)

    

    def _remove_chip(self, question_data: dict):

        """Remove a chip and its question from pending list."""

        # Remove from pending questions

        self.pending_questions = [q for q in self.pending_questions if q.get("row_number") != question_data.get("row_number")]

        

        # Remove chip widget - search through all rows

        for row_idx in range(self.chip_main_layout.count()):

            row_layout = self.chip_main_layout.itemAt(row_idx).layout()

            if row_layout:

                for i in range(row_layout.count()):

                    widget = row_layout.itemAt(i).widget()

                    if isinstance(widget, QuestionChip) and widget.question_data == question_data:

                        widget.deleteLater()

                        # Rebuild layout after removal

                        self._rebuild_chip_layout()

                        return

        

        # Show label if no chips left

        if not self.pending_questions:

            self.drop_label.setVisible(True)

            self.chip_scroll.setVisible(False)

            self.current_chip_row = None

            self.chips_in_current_row = 0

    

    def _on_chip_clicked(self, question_data: dict):

        """Handle chip click - highlight corresponding question card."""

        # Highlight clicked chip, unhighlight others

        for row_idx in range(self.chip_main_layout.count()):

            row_layout = self.chip_main_layout.itemAt(row_idx).layout()

            if row_layout:

                for i in range(row_layout.count()):

                    widget = row_layout.itemAt(i).widget()

                    if isinstance(widget, QuestionChip):

                        widget.set_highlighted(widget.question_data == question_data)

        

        # Find main window by traversing up the widget hierarchy

        main_window = self.parent()

        while main_window:

            if hasattr(main_window, '_highlight_question_card'):

                main_window._highlight_question_card(question_data)

                return

            parent_widget = main_window.parent() if hasattr(main_window, 'parent') else None

            if parent_widget is None or parent_widget == main_window:

                break

            main_window = parent_widget

    

    def _rebuild_chip_layout(self):

        """Rebuild chip layout after removal to maintain proper row structure."""

        # Clear all existing rows

        while self.chip_main_layout.count() > 0:

            item = self.chip_main_layout.takeAt(0)

            if item.layout():

                while item.layout().count() > 0:

                    widget_item = item.layout().takeAt(0)

                    if widget_item.widget():

                        widget_item.widget().setParent(None)

        

        # Reset row tracking

        self.current_chip_row = None

        self.chips_in_current_row = 0

        

        # Re-add all chips

        questions_copy = self.pending_questions.copy()

        self.pending_questions.clear()

        

        for question in questions_copy:

            # Create chip without adding to pending_questions yet

            chip = QuestionChip(question, self)

            chip.remove_clicked.connect(self._remove_chip)

            chip.chip_clicked.connect(self._on_chip_clicked)

            

            # Create new row if needed

            if self.current_chip_row is None or self.chips_in_current_row >= self.max_chips_per_row:

                self.current_chip_row = QHBoxLayout()

                self.current_chip_row.setSpacing(4)

                self.current_chip_row.addStretch()

                self.chip_main_layout.addLayout(self.current_chip_row)

                self.chips_in_current_row = 0

            

            self.current_chip_row.insertWidget(self.chips_in_current_row, chip)

            self.chips_in_current_row += 1

            self.pending_questions.append(question)

    

    def _on_save(self):

        """Emit save signal with selected list and questions."""

        if not self.pending_questions:

            from PySide6.QtWidgets import QMessageBox

            QMessageBox.information(self, "No Questions", "Please drag some questions to add to the list.")

            return

        

        list_name = self.list_selector.currentText()

        if list_name:

            self.save_clicked.emit(list_name, self.pending_questions.copy())

            self._clear()

    

    def _on_cancel(self):

        """Emit cancel signal and clear pending questions."""

        self._clear()

        self.cancel_clicked.emit()

    

    def _clear(self):

        """Clear all pending questions and chips."""

        self.pending_questions.clear()

        

        # Remove all chips from all rows

        while self.chip_main_layout.count() > 0:

            item = self.chip_main_layout.takeAt(0)

            if item.layout():

                while item.layout().count() > 0:

                    widget_item = item.layout().takeAt(0)

                    if widget_item.widget():

                        widget_item.widget().deleteLater()

        

        self.current_chip_row = None

        self.chips_in_current_row = 0

        self.drop_label.setVisible(True)

        self.chip_scroll.setVisible(False)

    

    def update_list_selector(self, question_lists: dict):

        """Update the list selector dropdown with current question lists."""

        self.list_selector.blockSignals(True)

        self.list_selector.clear()

        list_names = sorted(question_lists.keys())

        self.list_selector.addItems(list_names)

        self.list_selector.blockSignals(False)

        self.question_lists = question_lists

        

        # Trigger the change handler to update existing questions display

        if list_names:

            first_list = list_names[0]

            self._on_list_selector_changed(first_list)

    

    def _on_list_selector_changed(self, list_name: str):

        """Handle dropdown selection change - update existing questions display."""

        if list_name and list_name in self.question_lists:

            questions = self.question_lists[list_name]

            self.display_existing_questions(questions)

    

    def display_existing_questions(self, questions: list):

        """Display existing questions in the list as inactive chips."""

        # Clear existing chips

        while self.existing_chip_layout.count() > 0:

            item = self.existing_chip_layout.takeAt(0)

            if item.layout():

                while item.layout().count() > 0:

                    widget_item = item.layout().takeAt(0)

                    if widget_item.widget():

                        widget_item.widget().deleteLater()

            elif item.widget():

                item.widget().deleteLater()

        

        # Reset row tracking for existing chips

        self.existing_current_row = None

        self.existing_chips_in_row = 0

        

        if not questions:

            self.existing_chip_scroll.setVisible(False)

            return

        

        # Add inactive chips for existing questions

        for idx, question_data in enumerate(questions):

            self._add_existing_chip(question_data)

        

        self.existing_chip_scroll.setVisible(True)

        

        # Update layout and scroll area

        self.existing_chip_container.updateGeometry()

        self.existing_chip_scroll.widget().updateGeometry()

    

    def _add_existing_chip(self, question_data: dict):

        """Add a single inactive chip for an existing question."""

        chip = InactiveQuestionChip(question_data)

        chip.chip_clicked.connect(self._on_existing_chip_clicked)

        

        # Create row if needed

        if self.existing_current_row is None or self.existing_chips_in_row >= self.max_chips_per_row:

            row_layout = QHBoxLayout()

            row_layout.setSpacing(6)

            row_layout.setContentsMargins(0, 0, 0, 0)

            row_layout.addStretch()  # Right align chips

            self.existing_chip_layout.addLayout(row_layout)

            self.existing_current_row = row_layout

            self.existing_chips_in_row = 0

        

        self.existing_current_row.insertWidget(self.existing_current_row.count() - 1, chip)

        self.existing_chips_in_row += 1

    

    def _on_existing_chip_clicked(self, question_data: dict):

        """Handle click on existing question chip - highlight the card."""

        # Find parent main window and highlight the question card

        main_window = self.parent()

        while main_window:

            if hasattr(main_window, '_highlight_question_card'):

                main_window._highlight_question_card(question_data)

                return

            parent_widget = main_window.parent() if hasattr(main_window, 'parent') else None

            if parent_widget is None or parent_widget == main_window:

                break

            main_window = parent_widget
