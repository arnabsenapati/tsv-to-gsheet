"""
Question Set Grouping View Widget

This module contains the QuestionSetGroupingView widget for managing
question set groupings with a modern two-column split panel design.
"""

from PySide6.QtCore import Qt, Signal, QMimeData, QSize
from PySide6.QtGui import QDrag, QColor, QFont
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QScrollArea,
    QFrame,
)


class QuestionSetGroupingView(QWidget):
    """
    Question Set Grouping view with modern two-column split panel design.
    
    Layout:
    - Left Panel: List of Question Set Groups with badge counts
    - Right Panel: Question Sets in selected group
    - Supports drag-and-drop between groups
    
    Features:
    - Modern card-based design consistent with Question List tab
    - Badge-style counts for groups (similar to chapter list)
    - Drag-and-drop functionality to move question sets between groups
    - Auto-generated "Others" group for ungrouped question sets
    - Persistent storage in QuestionSetGroup.json
    """
    
    # MIME type for dragging question sets
    MIME_TYPE = "application/x-question-set"
    
    group_changed = Signal(str)  # Emitted when selected group changes
    question_set_moved = Signal(str, str, str)  # Emitted when QS moved (qs_name, from_group, to_group)
    
    def __init__(self, parent=None):
        """Initialize the Question Set Grouping view."""
        super().__init__(parent)
        
        self.group_service = None  # Will be set by main window
        self.all_question_sets = []  # All question sets from workbook
        self.selected_group = None  # Currently selected group
        
        # Setup UI
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the user interface with two-column layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)
        
        # Title
        title = QLabel("📋 Question Set Grouping")
        title.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #1e40af;
            }
        """)
        main_layout.addWidget(title)
        
        # Two-column container
        content_layout = QHBoxLayout()
        content_layout.setSpacing(12)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # === Left Panel: Groups List ===
        left_panel = QFrame()
        left_panel.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 4px;
            }
        """)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(8)
        
        left_title = QLabel("Groups")
        left_title.setStyleSheet("""
            QLabel {
                font-size: 12px;
                font-weight: 600;
                color: #475569;
            }
        """)
        left_layout.addWidget(left_title)
        
        # Groups list widget
        self.groups_list = QListWidget()
        self.groups_list.setStyleSheet("""
            QListWidget {
                border: none;
                background-color: transparent;
            }
            QListWidget::item {
                padding: 6px 0px;
                border: none;
            }
            QListWidget::item:selected {
                background-color: #e0f2fe;
                border-radius: 4px;
            }
            QListWidget::item:hover:!selected {
                background-color: #f0f9ff;
                border-radius: 4px;
            }
        """)
        self.groups_list.itemSelectionChanged.connect(self._on_group_selected)
        left_layout.addWidget(self.groups_list)
        
        content_layout.addWidget(left_panel, 40)
        
        # === Right Panel: Question Sets List ===
        right_panel = QFrame()
        right_panel.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 4px;
            }
        """)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(8)
        
        right_title = QLabel("Question Sets")
        right_title.setStyleSheet("""
            QLabel {
                font-size: 12px;
                font-weight: 600;
                color: #475569;
            }
        """)
        right_layout.addWidget(right_title)
        
        # Question sets list widget with drag support
        self.question_sets_list = QuestionSetListWidget(self)
        self.question_sets_list.setStyleSheet("""
            QListWidget {
                border: none;
                background-color: transparent;
            }
            QListWidget::item {
                padding: 8px 4px;
                border: none;
            }
            QListWidget::item:hover {
                background-color: #f0f9ff;
                border-radius: 4px;
            }
        """)
        self.question_sets_list.setAcceptDrops(True)
        self.question_sets_list.setDragDropMode(self.question_sets_list.DragDrop)
        
        right_layout.addWidget(self.question_sets_list)
        
        content_layout.addWidget(right_panel, 60)
        
        main_layout.addLayout(content_layout, 1)
    
    def set_group_service(self, service):
        """Set the group service for managing groups."""
        self.group_service = service
        self._refresh_groups_list()
    
    def update_from_workbook(self, question_sets: list[str]):
        """
        Update the view with question sets from workbook.
        
        Args:
            question_sets: List of question set names from workbook
        """
        self.all_question_sets = question_sets
        self._refresh_groups_list()
        
        # Select first group if available
        if self.groups_list.count() > 0:
            self.groups_list.setCurrentRow(0)
    
    def _refresh_groups_list(self):
        """Refresh the groups list with current groups and counts."""
        if not self.group_service:
            return
        
        self.groups_list.clear()
        
        # Get all groups
        groups = self.group_service.get_all_groups()
        
        # Add saved groups
        for group_name, group_data in groups.items():
            question_sets = group_data.get("question_sets", [])
            count = len(question_sets)
            
            # Create group item with badge
            item = QListWidgetItem()
            item.setText(group_name)
            item.setData(Qt.UserRole, group_name)  # Store group name
            item.setData(Qt.UserRole + 1, count)  # Store count
            
            # Style with badge
            self._style_group_item(item, group_name, count, group_data.get("color", "#3b82f6"))
            self.groups_list.addItem(item)
        
        # Add "Others" group
        others_group = self.group_service.get_others_group(self.all_question_sets)
        others_count = len(others_group["question_sets"])
        
        item = QListWidgetItem()
        item.setText("Others")
        item.setData(Qt.UserRole, "Others")
        item.setData(Qt.UserRole + 1, others_count)
        self._style_group_item(item, "Others", others_count, "#94a3b8")
        self.groups_list.addItem(item)
    
    def _style_group_item(self, item: QListWidgetItem, group_name: str, count: int, color: str):
        """Style a group item with name and badge count."""
        # Create widget for custom rendering
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)
        
        # Group name label
        name_label = QLabel(group_name)
        name_label.setStyleSheet(f"""
            QLabel {{
                font-size: 12px;
                color: #1e40af;
                font-weight: 500;
            }}
        """)
        layout.addWidget(name_label)
        
        # Stretch
        layout.addStretch()
        
        # Count badge
        badge_label = QLabel(str(count))
        badge_label.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                color: white;
                border-radius: 10px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: bold;
                min-width: 24px;
                text-align: center;
            }}
        """)
        layout.addWidget(badge_label)
        
        # Set widget for item
        item.setSizeHint(QSize(0, 32))
        self.groups_list.setItemWidget(item, widget)
    
    def _on_group_selected(self):
        """Handle group selection and update question sets list."""
        current_item = self.groups_list.currentItem()
        if not current_item:
            return
        
        group_name = current_item.data(Qt.UserRole)
        self.selected_group = group_name
        self.group_changed.emit(group_name)
        
        # Update question sets list
        self._refresh_question_sets_list()
    
    def _refresh_question_sets_list(self):
        """Refresh the question sets list for selected group."""
        self.question_sets_list.clear()
        
        if not self.selected_group or not self.group_service:
            return
        
        # Get question sets for selected group
        if self.selected_group == "Others":
            question_sets = self.group_service.get_others_group(self.all_question_sets)["question_sets"]
        else:
            question_sets = self.group_service.get_question_sets_in_group(self.selected_group)
        
        # Add items to list
        for qs_name in question_sets:
            item = QListWidgetItem()
            item.setText(f"📝 {qs_name}")
            item.setData(Qt.UserRole, qs_name)  # Store actual name without emoji
            item.setStyleSheet("""
                QListWidgetItem {
                    padding: 6px 0px;
                }
            """)
            self.question_sets_list.addItem(item)
    
    def _on_question_set_dropped_internal(self, qs_name: str, from_group: str, event):
        """Handle drop event when dragging question set between groups."""
        # Only allow drop to regular groups (not "Others")
        if self.selected_group and self.group_service:
            if self.selected_group != "Others":
                # Move from source group to this group
                if self.group_service.move_question_set(qs_name, from_group, self.selected_group):
                    self.question_set_moved.emit(qs_name, from_group, self.selected_group)
                    self._refresh_groups_list()
                    self._refresh_question_sets_list()
                    event.accept()
                    return
        
        event.ignore()


class QuestionSetListWidget(QListWidget):
    """
    Custom list widget for question sets with drag support.
    """
    
    MIME_TYPE = "application/x-question-set"
    
    def __init__(self, parent=None):
        """Initialize the question set list widget."""
        super().__init__(parent)
        self.parent_view = parent
        self.setDragDropMode(self.DragDrop)
    
    def startDrag(self, supported_actions):
        """Start drag operation for question set."""
        current_item = self.currentItem()
        if not current_item:
            return
        
        # Get question set name
        qs_name = current_item.data(Qt.UserRole)
        
        # Create mime data
        mime_data = QMimeData()
        # Store format: "question_set_name|from_group"
        if self.parent_view:
            from_group = self.parent_view.selected_group or ""
            mime_data.setText(f"{qs_name}|{from_group}")
        
        mime_data.setData(self.MIME_TYPE, b"drag")
        
        # Create drag object
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        
        # Set visual feedback (use default which is text)
        drag.exec(supported_actions)
    
    def dragEnterEvent(self, event):
        """Accept drag events with question set data."""
        if event.mimeData().hasFormat(self.MIME_TYPE):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)
    
    def dragMoveEvent(self, event):
        """Allow dragging over the list."""
        if event.mimeData().hasFormat(self.MIME_TYPE):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)
    
    def dropEvent(self, event):
        """Handle drop event when dragging question set."""
        if not event.mimeData().hasFormat(self.MIME_TYPE):
            event.ignore()
            return
        
        # Parse mime data
        try:
            data = event.mimeData().text()
            source_info = data.split("|")
            qs_name = source_info[0]
            from_group = source_info[1] if len(source_info) > 1 else None
        except:
            event.ignore()
            return
        
        # Call parent view's drop handler
        if self.parent_view:
            self.parent_view._on_question_set_dropped_internal(qs_name, from_group, event)
        else:
            event.ignore()
