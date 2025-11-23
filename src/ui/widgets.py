"""
Custom UI widgets for the TSV to Excel Watcher application.

This module contains all custom widget classes used throughout the application:
- TagBadge: Small clickable tag display for filtering
- ClickableTagBadge: Interactive tag with +/✓ toggle for selection dialogs
- QuestionTreeWidget: Tree widget displaying grouped questions with drag support
- ChapterTableWidget: Table widget for chapter management with drop support
- QuestionTableWidget: Table widget for question display with drag support
- GroupingChapterListWidget: Draggable list of chapters for grouping
- GroupListWidget: Droppable list of groups for chapter organization
"""

import json
from PySide6.QtCore import Qt, QMimeData, Signal
from PySide6.QtGui import QColor, QDrag, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QTableWidget,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
)


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
        ├── Q1  |  25  |  JEE Main 2023  |  Physics For You Jan 2023  [child]
        ├── Q2  |  26  |  JEE Main 2023  |  Physics For You Jan 2023  [child]
        └── ...
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
        Only allows dragging leaf items (actual questions, not groups).
        """
        current = self.currentItem()
        if not current:
            return
        
        # Prevent dragging group headers (items with children)
        if current.childCount() > 0:
            return
        
        # Get question data stored in UserRole
        question_data = current.data(0, Qt.UserRole)
        if not question_data:
            return
        
        # Create JSON payload for drag operation
        payload = json.dumps({
            "row_number": question_data.get("row_number"),
            "qno": question_data.get("qno"),
            "question_set": question_data.get("question_set"),
            "group": question_data.get("group"),
        })
        
        # Create mime data and start drag
        mime = QMimeData()
        mime.setData(self.MIME_TYPE, payload.encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.MoveAction)


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
        Reassigns the dropped question to the chapter at drop position.
        """
        # Validate mime data format
        if not event.mimeData().hasFormat(QuestionTableWidget.MIME_TYPE):
            super().dropEvent(event)
            return
        
        # Parse question data from drag payload
        try:
            payload = bytes(event.mimeData().data(QuestionTableWidget.MIME_TYPE)).decode("utf-8")
            question = json.loads(payload)
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
        
        # Reassign question to this chapter
        self.parent_window.reassign_question(question, target_group)
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
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragOnly)

    def startDrag(self, supportedActions) -> None:
        """
        Handle drag operation start.
        Creates JSON payload with question data for drag operation.
        """
        row = self.currentRow()
        
        # Validate row selection
        if row < 0 or row >= len(self.parent_window.current_questions):
            return
        
        # Get question data for this row
        question = self.parent_window.current_questions[row]
        
        # Create JSON payload
        payload = json.dumps({
            "row_number": question.get("row_number"),
            "qno": question.get("qno"),
            "question_set": question.get("question_set"),
            "group": question.get("group"),
        })
        
        # Create mime data and start drag
        mime = QMimeData()
        mime.setData(self.MIME_TYPE, payload.encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
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
