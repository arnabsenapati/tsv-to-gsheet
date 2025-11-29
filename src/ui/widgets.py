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
- QuestionCardWidget: Individual question card with inline preview
- QuestionAccordionGroup: Collapsible group for question cards
- QuestionListCardView: Scrollable container for accordion groups
- DashboardView: Dashboard with workbook selector and statistics
- NavigationSidebar: Collapsible sidebar navigation for main views
"""

import json
from PySide6.QtCore import Qt, QMimeData, Signal, QRect, QPoint, QTimer
from PySide6.QtGui import QColor, QDrag, QDragEnterEvent, QDropEvent, QPixmap, QPainter, QFont, QGuiApplication
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
        ┌──────────────────────────────────────────────────┐
        │ Q15  📄 Page 45    🏷️ important · prev-year    │
        │ ───────────────────────────────────────────────  │
        │ A particle of mass 2kg moves under a force...   │
        │ Calculate the acceleration when velocity is...  │
        │                                                  │
        │ 📖 JEE Main 2024 Paper 1 | Physics For You     │
        └──────────────────────────────────────────────────┘
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
        self.is_selected = False
        self.original_stylesheet = ""
        
        # Build card HTML
        self._build_card()
        
        # Card styling
        self.setTextFormat(Qt.RichText)
        self.setWordWrap(True)
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
        
        # Build card HTML
        html = f"""
        <div style="line-height: 1.4;">
            <div style="margin-bottom: 8px;">
                <span style="color: #1e40af; font-size: 16px; font-weight: bold;">{qno}</span>
                <span style="color: #64748b; font-size: 12px; margin-left: 12px;">📄 Page {page}</span>
                {tag_html}
            </div>
            <div style="border-top: 1px solid #cbd5e1; padding-top: 8px; margin-bottom: 8px;">
                <p style="color: #1f2937; font-size: 13px; margin: 0; line-height: 1.5;">
                    {preview}
                </p>
            </div>
            <div style="font-size: 11px; color: #94a3b8;">
                📖 <span style="color: #475569;">{question_set}</span> | 
                📰 <span style="color: #475569;">{magazine}</span>
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
    
    def mousePressEvent(self, event):
        """Handle card click - toggle selection or copy metadata."""
        if event.button() == Qt.LeftButton:
            # Emit signal for selection handling (parent will handle multi-select logic)
            self.clicked.emit(self.question_data)
        super().mousePressEvent(event)
    
    def mouseDoubleClickEvent(self, event):
        """Handle double-click - copy metadata to clipboard."""
        if event.button() == Qt.LeftButton:
            # Copy metadata to clipboard
            q = self.question_data
            qno = q.get("qno", "?")
            page = q.get("page", "?")
            question_set = q.get("question_set_name", "Unknown")
            magazine = q.get("magazine", "Unknown")
            
            # Format: Q15 | P34 | Question set name | Magazine edition
            metadata_text = f"Q{qno} | P{page} | {question_set} | {magazine}"
            
            # Copy to clipboard
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(metadata_text)
            
            # Visual feedback - flash green
            self._show_copy_feedback()
        super().mouseDoubleClickEvent(event)
    
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
        if selected:
            self.setStyleSheet("""
                QLabel {
                    background-color: #dbeafe;
                    border: 2px solid #3b82f6;
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
        🔽 JEE Main 2024                    📚 75 Questions
           [Tag badges if any]
        ───────────────────────────────────────────────────
        [QuestionCardWidget]
        [QuestionCardWidget]
        [QuestionCardWidget]
    """
    
    def __init__(self, group_key: str, questions: list[dict], tags: list[str] = None, tag_colors: dict = None, parent=None):
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
        self.expand_btn = QPushButton("▶️")
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
        self.tag_btn = QPushButton("🏷️")
        self.tag_btn.setToolTip("Manage tags for this group")
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
        
        # Question count badge
        count_label = QLabel(f"📚 {len(self.questions)} Questions")
        count_label.setStyleSheet("""
            QLabel {
                background-color: #3b82f6;
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
            }
        """)
        header_layout.addWidget(count_label)
        
        # Make entire header clickable
        header_widget.mousePressEvent = lambda e: self.toggle_expanded()
        
        return header_widget
    
    def toggle_expanded(self):
        """Toggle expand/collapse state."""
        self.is_expanded = not self.is_expanded
        self.content_widget.setVisible(self.is_expanded)
        self.expand_btn.setText("🔽" if self.is_expanded else "▶️")
    
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
    
    def add_group(self, group_key: str, questions: list[dict], tags: list[str] = None, tag_colors: dict = None):
        """
        Add an accordion group to the view.
        
        Args:
            group_key: Group identifier
            questions: List of question data dicts
            tags: List of tags for this group
            tag_colors: Dict mapping tag names to color hex codes
        """
        group = QuestionAccordionGroup(group_key, questions, tags, tag_colors, self)
        
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
    Dashboard view with workbook selector and statistics.
    
    Displays:
    - Workbook path selector
    - Total row count
    - Magazine summary
    - Missing ranges information
    """
    
    def __init__(self, parent=None):
        """Initialize dashboard view."""
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Title
        title = QLabel("📊 Dashboard")
        title.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #1e40af;
                padding-bottom: 10px;
            }
        """)
        layout.addWidget(title)
        
        # Card container for workbook info
        card = QWidget()
        card.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)
        
        # Workbook selector row (will be connected by main window)
        self.output_edit = None
        self.browse_btn = None
        self.row_count_label = None
        self.mag_summary_label = None
        self.mag_missing_label = None
        
        layout.addWidget(card)
        layout.addStretch()


class NavigationSidebar(QWidget):
    """
    Collapsible sidebar navigation for main application views.
    
    Features:
    - 7 navigation items organized hierarchically
    - Visual grouping for Question Analysis sub-items
    - Collapse/expand functionality (150px ↔ 40px)
    - Selected item highlighting
    - Hover effects
    - Icon-only mode when collapsed
    
    Navigation structure:
        📊 Dashboard
        📰 Magazine Editions (Question Analysis group)
        📝 Question List (Question Analysis group)
        📚 Chapter Grouping (Question Analysis group)
        📋 Custom Lists (Question Analysis group)
        📥 Data Import
        🎓 JEE Main Papers
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
            ("📊", "Dashboard", 0, False),
            ("📰", "Magazine Editions", 1, True),
            ("📝", "Question List", 2, True),
            ("📚", "Chapter Grouping", 3, True),
            ("📋", "Custom Lists", 4, True),
            ("📥", "Data Import", 5, False),
            ("🎓", "JEE Main Papers", 6, False),
        ]
        
        for icon, text, index, is_indented in nav_items:
            btn = self._create_nav_button(icon, text, index, is_indented)
            self.nav_buttons.append(btn)
            self.nav_layout.addWidget(btn)
        
        self.nav_layout.addStretch()
        scroll.setWidget(nav_container)
        layout.addWidget(scroll, 1)
        
        # Collapse/expand button at bottom
        self.toggle_btn = QPushButton("◀")
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
        btn = QPushButton(f"{icon}  {text}")
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
            self.toggle_btn.setText("◀")
            self.toggle_btn.setToolTip("Collapse sidebar")
            
            # Show text on buttons
            nav_items = [
                ("📊", "Dashboard"),
                ("📰", "Magazine Editions"),
                ("📝", "Question List"),
                ("📚", "Chapter Grouping"),
                ("📋", "Custom Lists"),
                ("📥", "Data Import"),
                ("🎓", "JEE Main Papers"),
            ]
            for i, btn in enumerate(self.nav_buttons):
                icon, text = nav_items[i]
                btn.setText(f"{icon}  {text}")
        else:
            # Collapse
            self.setMinimumWidth(50)
            self.setMaximumWidth(50)
            self.toggle_btn.setText("▶")
            self.toggle_btn.setToolTip("Expand sidebar")
            
            # Show only icons
            icons = ["📊", "📰", "📝", "📚", "📋", "📥", "🎓"]
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
