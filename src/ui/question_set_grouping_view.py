"""
Question Set Grouping View Widget

This module contains the QuestionSetGroupingView widget for managing
question set groupings with a modern two-column split panel design.
"""

import json
import math

from PySide6.QtCore import Qt, Signal, QMimeData, QSize, QEvent, QPoint
from PySide6.QtGui import QDrag, QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QScrollArea,
    QFrame,
    QAbstractItemView,
    QPushButton,
    QInputDialog,
    QSizePolicy,
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
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        
        # Left Panel Header (Banner)
        left_header = QWidget()
        left_header_layout = QHBoxLayout(left_header)
        left_header_layout.setContentsMargins(12, 10, 12, 10)
        left_header_layout.setSpacing(8)
        left_header.setStyleSheet("""
            QWidget {
                background-color: #1e40af;
                border-radius: 4px 4px 0px 0px;
            }
        """)
        
        left_icon = QLabel("📂")
        left_icon.setStyleSheet("font-size: 18px;")
        left_header_layout.addWidget(left_icon)
        
        left_title = QLabel("Question Set Groups")
        left_title.setStyleSheet("""
            QLabel {
                font-size: 13px;
                font-weight: bold;
                color: white;
            }
        """)
        left_header_layout.addWidget(left_title)
        left_header_layout.addStretch()
        
        # Add Group button
        add_group_btn = QPushButton("➕")
        add_group_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: white;
                font-size: 14px;
                padding: 0px 4px;
                min-width: 20px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.2);
                border-radius: 3px;
            }
        """)
        add_group_btn.clicked.connect(self._on_add_new_group)
        left_header_layout.addWidget(add_group_btn)
        
        left_layout.addWidget(left_header)
        
        # Container for groups list with padding
        groups_container = QWidget()
        groups_container.setStyleSheet("background-color: transparent;")
        groups_container_layout = QVBoxLayout(groups_container)
        groups_container_layout.setContentsMargins(12, 12, 12, 12)
        groups_container_layout.setSpacing(8)
        
        self.groups_list = GroupListWidget(self)
        self.groups_list.setStyleSheet("""
            QListWidget {
                border: none;
                background-color: transparent;
                outline: 0;
                selection-background-color: transparent;
            }
            QListWidget::item {
                padding: 6px 0px;
                border: none;
                outline: 0;
                selection-background-color: transparent;
            }
            QListWidget::item:selected {
                background-color: transparent;
                outline: none;
                border: none;
                selection-background-color: transparent;
            }
            QListWidget::item:hover:!selected {
                background-color: transparent;
            }
            QListWidget::item:selected:active {
                background-color: transparent;
                outline: none;
                border: none;
            }
            QListWidget::item:selected:!active {
                background-color: transparent;
                outline: none;
                border: none;
            }
        """)
        self.groups_list.setFocusPolicy(Qt.NoFocus)
        self.groups_list.itemSelectionChanged.connect(self._on_group_selected)
        groups_container_layout.addWidget(self.groups_list)
        
        left_layout.addWidget(groups_container)
        
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
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        
        # Right Panel Header (Banner)
        right_header = QWidget()
        right_header_layout = QHBoxLayout(right_header)
        right_header_layout.setContentsMargins(12, 10, 12, 10)
        right_header_layout.setSpacing(8)
        right_header.setStyleSheet("""
            QWidget {
                background-color: #7c3aed;
                border-radius: 4px 4px 0px 0px;
            }
        """)
        
        right_icon = QLabel("📝")
        right_icon.setStyleSheet("font-size: 18px;")
        right_header_layout.addWidget(right_icon)
        
        right_title = QLabel("Question Sets")
        right_title.setStyleSheet("""
            QLabel {
                font-size: 13px;
                font-weight: bold;
                color: white;
            }
        """)
        right_header_layout.addWidget(right_title)
        right_header_layout.addStretch()
        
        right_layout.addWidget(right_header)
        
        # Container for question sets list with padding
        sets_container = QWidget()
        sets_container.setStyleSheet("background-color: transparent;")
        sets_container_layout = QVBoxLayout(sets_container)
        sets_container_layout.setContentsMargins(12, 12, 12, 12)
        sets_container_layout.setSpacing(0)
        
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
        self.question_sets_list.setDragDropMode(QAbstractItemView.DragDrop)
        self.question_sets_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        
        sets_container_layout.addWidget(self.question_sets_list)
        
        right_layout.addWidget(sets_container)
        
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
            # Leave text empty because custom widget renders the name
            item.setText("")
            item.setData(Qt.UserRole, group_name)  # Store group name
            item.setData(Qt.UserRole + 1, count)  # Store count
            
            self.groups_list.addItem(item)
            # Style with badge
            self._style_group_item(item, group_name, count, group_data.get("color", "#3b82f6"))
        
        # Add "Others" group
        others_group = self.group_service.get_others_group(self.all_question_sets)
        others_count = len(others_group["question_sets"])
        
        item = QListWidgetItem()
        item.setText("")
        item.setData(Qt.UserRole, "Others")
        item.setData(Qt.UserRole + 1, others_count)
        self.groups_list.addItem(item)
        self._style_group_item(item, "Others", others_count, "#94a3b8")

        # Restore selection to previously selected group if available
        if self.selected_group:
            for idx in range(self.groups_list.count()):
                item = self.groups_list.item(idx)
                if item and item.data(Qt.UserRole) == self.selected_group:
                    self.groups_list.setCurrentRow(idx)
                    break

        # Reapply selection highlight to match current selection
        self._update_group_item_selection()

    def _on_delete_group(self, group_name: str):
        """Delete a group when empty."""
        if not self.group_service or group_name == "Others":
            return
        group_data = self.group_service.get_group(group_name)
        if not group_data:
            return
        if group_data.get("question_sets"):
            return  # Safety: only allow delete when empty
        if self.group_service.delete_group(group_name):
            # Clear selection if we deleted the selected group
            if self.selected_group == group_name:
                self.selected_group = None
            self._refresh_groups_list()
    
    def _style_group_item(self, item: QListWidgetItem, group_name: str, count: int, color: str):
        """Style a group item with name, badge count, and hover action buttons."""
        # Create widget for custom rendering
        widget = GroupItemWidget(group_name, count, color, self)
        widget.rename_clicked.connect(lambda name=group_name: self._on_rename_group(name))
        widget.delete_clicked.connect(lambda name=group_name: self._on_delete_group(name))
        
        # Set widget for item with proper sizing
        item.setSizeHint(widget.sizeHint())
        self.groups_list.setItemWidget(item, widget)

        # Set initial selection state
        is_selected = self.groups_list.currentItem() is item or group_name == self.selected_group
        widget.set_selected(is_selected)

    def _update_group_item_selection(self):
        """Sync custom group widgets with QListWidget selection."""
        current_item = self.groups_list.currentItem()
        for index in range(self.groups_list.count()):
            item = self.groups_list.item(index)
            widget = self.groups_list.itemWidget(item)
            if widget:
                widget.set_selected(item is current_item)

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
        self._update_group_item_selection()

    def _on_question_set_drop_on_group(self, qs_names: list[str], from_group: str, target_group: str, event):
        """Handle drop of one or more question sets onto a group item."""
        if not self.group_service or not target_group or not qs_names:
            event.ignore()
            return

        # No-op if dropping onto the same group
        if target_group == from_group:
            event.ignore()
            return

        current_group = self.selected_group
        moved_any = False

        if target_group == "Others":
            if from_group and from_group != "Others":
                for qs_name in qs_names:
                    if self.group_service.remove_question_set_from_group(from_group, qs_name):
                        self.question_set_moved.emit(qs_name, from_group, target_group)
                        moved_any = True
        else:
            for qs_name in qs_names:
                if self.group_service.move_question_set(qs_name, from_group, target_group):
                    self.question_set_moved.emit(qs_name, from_group, target_group)
                    moved_any = True

        if moved_any:
            self._refresh_groups_list()
            # Restore selection to the original group to keep its list visible
            if current_group:
                for idx in range(self.groups_list.count()):
                    item = self.groups_list.item(idx)
                    if item and item.data(Qt.UserRole) == current_group:
                        self.groups_list.setCurrentRow(idx)
                        break
            self._refresh_question_sets_list()
            event.acceptProposedAction()
            return

        event.ignore()

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
            self.question_sets_list.addItem(item)
    
    def _on_question_sets_dropped_internal(self, qs_names: list[str], from_group: str, event):
        """Handle drop event when dragging question sets onto the current list."""
        if not qs_names or not self.group_service or not self.selected_group:
            event.ignore()
            return

        # Can't drop into Others list
        if self.selected_group == "Others":
            event.ignore()
            return

        moved_any = False
        for qs_name in qs_names:
            if self.group_service.move_question_set(qs_name, from_group, self.selected_group):
                self.question_set_moved.emit(qs_name, from_group, self.selected_group)
                moved_any = True

        if moved_any:
            self._refresh_groups_list()
            self._refresh_question_sets_list()
            event.accept()
            return

        event.ignore()
    
    def _on_rename_group(self, group_name: str):
        """Handle renaming a group."""
        if group_name == "Others":
            # Can't rename the Others group
            return
        
        # Show input dialog
        new_name, ok = QInputDialog.getText(
            self,
            "Rename Group",
            f"Enter new name for '{group_name}':",
            text=group_name
        )
        
        if ok and new_name and new_name != group_name:
            # Rename in service
            if self.group_service.rename_group(group_name, new_name):
                # Update selected group if it was the one being renamed
                if self.selected_group == group_name:
                    self.selected_group = new_name
                
                # Refresh the list
                self._refresh_groups_list()
    
    def _on_add_new_group(self):
        """Handle adding a new group."""
        # Show input dialog
        group_name, ok = QInputDialog.getText(
            self,
            "Add New Group",
            "Enter group name:",
        )
        
        if ok and group_name:
            # Create new group in service
            if self.group_service.create_group(group_name):
                current_group = self.selected_group
                # Refresh the list
                self._refresh_groups_list()
                # Restore previous selection
                if current_group:
                    for idx in range(self.groups_list.count()):
                        item = self.groups_list.item(idx)
                        if item and item.data(Qt.UserRole) == current_group:
                            self.groups_list.setCurrentRow(idx)
                            break


class QuestionSetListWidget(QListWidget):
    """
    Custom list widget for question sets with drag support.
    """
    
    MIME_TYPE = "application/x-question-set"
    
    def __init__(self, parent=None):
        """Initialize the question set list widget."""
        super().__init__(parent)
        self.parent_view = parent
        # Drag/drop mode is set by parent during setup
    
    def startDrag(self, supported_actions):
        """Start drag operation for one or more question sets."""
        items = self.selectedItems()
        if not items:
            return
        
        qs_names = [i.data(Qt.UserRole) for i in items if i.data(Qt.UserRole)]
        if not qs_names:
            return
        
        # Create mime data with JSON payload
        mime_data = QMimeData()
        from_group = self.parent_view.selected_group if self.parent_view else ""
        payload = {"question_sets": qs_names, "from_group": from_group}
        mime_data.setText(json.dumps(payload))
        mime_data.setData(self.MIME_TYPE, b"drag")
        
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        # Visual: show how many items are being moved
        count = len(qs_names)
        text = str(count)
        diameter = 32  # doubled from the previous size
        pixmap = QPixmap(diameter, diameter)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        # Subtle 3D effect: shadow + radial highlight
        # Shadow
        painter.setBrush(QColor(0, 0, 0, 60))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(pixmap.rect().translated(2, 3).adjusted(1, 1, -1, -1))
        # Main circle with gradient
        gradient_color = QColor("#2563eb")
        painter.setBrush(QColor(gradient_color.red(), gradient_color.green(), gradient_color.blue(), 235))
        painter.drawEllipse(pixmap.rect().adjusted(1, 1, -2, -2))
        # Highlight
        painter.setBrush(QColor(255, 255, 255, 60))
        painter.drawEllipse(pixmap.rect().adjusted(6, 5, -12, -14))
        painter.setPen(Qt.white)
        font = painter.font()
        font.setPointSize(11)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, text)
        painter.end()
        drag.setPixmap(pixmap)
        # Place hotspot so pointer tip is 0.7 * radius away from center (at 45 degrees)
        radius = diameter / 2
        offset = radius * 0.7 / math.sqrt(2)  # components along x/y for 45°
        hotspot = QPoint(int(pixmap.width() / 2 + offset), int(pixmap.height() / 2 + offset))
        drag.setHotSpot(hotspot)
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
            payload = json.loads(event.mimeData().text())
            qs_names = payload.get("question_sets", [])
            from_group = payload.get("from_group")
        except Exception:
            event.ignore()
            return
        
        if self.parent_view:
            self.parent_view._on_question_sets_dropped_internal(qs_names, from_group, event)
        else:
            event.ignore()

class GroupListWidget(QListWidget):
    """
    Custom list widget for groups that accepts drops of question sets.
    """

    def __init__(self, parent_view=None):
        super().__init__(parent_view)
        self.parent_view = parent_view
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DropOnly)
        self.setDefaultDropAction(Qt.MoveAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(QuestionSetListWidget.MIME_TYPE):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(QuestionSetListWidget.MIME_TYPE):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if not event.mimeData().hasFormat(QuestionSetListWidget.MIME_TYPE):
            event.ignore()
            return

        # Determine target group from drop position
        item = self.itemAt(event.position().toPoint())
        if not item:
            event.ignore()
            return
        target_group = item.data(Qt.UserRole)

        # Parse dragged data
        try:
            data = event.mimeData().text()
            qs_name, from_group = data.split("|", 1)
        except Exception:
            event.ignore()
            return

        if self.parent_view:
            self.parent_view._on_question_set_drop_on_group(qs_names, from_group, target_group, event)
        else:
            event.ignore()


class GroupItemWidget(QWidget):
    """
    Custom widget for displaying a group item with hover action buttons.
    Shows rename button on hover.
    """
    
    rename_clicked = Signal()  # Emitted when rename button is clicked
    delete_clicked = Signal()  # Emitted when delete button is clicked (when count == 0)
    
    def __init__(self, group_name: str, count: int, color: str, parent=None):
        """Initialize the group item widget."""
        super().__init__(parent)
        self.group_name = group_name
        self.count = count
        self.color = color
        self.setMouseTracking(True)  # Enable mouse tracking for hover
        self.setObjectName("groupItemWidget")
        self.setAutoFillBackground(True)
        self.selected = False
        self.hovered = False
        self.can_delete = count == 0 and group_name != "Others"
        
        # Main layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignVCenter)
        
        # Group name label
        self.name_label = QLabel(group_name)
        self.name_label.setStyleSheet(f"""
            QLabel {{
                font-size: 12px;
                color: #1e40af;
                font-weight: 500;
                background: transparent;
            }}
        """)
        self.name_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self.name_label)
        
        # Count badge
        self.badge_label = QLabel(str(count))
        self.badge_label.setStyleSheet(f"""
            QLabel {{
                background-color: #ffffff;
                color: {color};
                border: 1px solid {color};
                border-radius: 10px;
                padding: 2px 6px;
                font-size: 10px;
                font-weight: bold;
                min-width: 20px;
                text-align: center;
            }}
        """)
        self.badge_label.setFixedWidth(32)
        layout.addWidget(self.badge_label, alignment=Qt.AlignRight | Qt.AlignVCenter)
        
        # Rename button (hidden by default, shown on hover)
        self.rename_btn = QPushButton("✏️")
        self.rename_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                padding: 0px 2px;
                min-width: 24px;
                min-height: 24px;
                max-width: 24px;
                max-height: 24px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #dbeafe;
                border-radius: 3px;
            }
        """)
        self.rename_btn.hide()  # Hide by default
        self.rename_btn.clicked.connect(self.rename_clicked.emit)
        layout.addWidget(self.rename_btn, alignment=Qt.AlignRight | Qt.AlignVCenter)

        # Delete button (only relevant when count == 0)
        self.delete_btn = QPushButton("🗑")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                padding: 0px 2px;
                min-width: 24px;
                min-height: 24px;
                max-width: 24px;
                max-height: 24px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #fee2e2;
                border-radius: 3px;
            }
        """)
        self.delete_btn.hide()
        self.delete_btn.clicked.connect(self.delete_clicked.emit)
        layout.addWidget(self.delete_btn, alignment=Qt.AlignRight | Qt.AlignVCenter)
        
        # Set minimum height
        self.setMinimumHeight(32)
        self.setMaximumHeight(32)  # Constrain height to prevent button escape
        self._update_background()
    
    def sizeHint(self):
        """Return the preferred size of the widget."""
        return QSize(200, 32)

    def set_selected(self, selected: bool):
        """Update selection state and refresh background."""
        self.selected = selected
        self._update_background()
    
    def enterEvent(self, event):
        """Show action buttons on hover."""
        self.rename_btn.show()
        if self.can_delete:
            self.delete_btn.show()
        self.hovered = True
        self._update_background()
        self.update()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Hide action buttons when not hovering."""
        self.rename_btn.hide()
        self.delete_btn.hide()
        self.hovered = False
        self._update_background()
        self.update()
        super().leaveEvent(event)

    def _update_background(self):
        """Apply hover/selection background without relying on QListWidget painting."""
        if self.selected:
            bg = "#e0f2fe"
        elif self.hovered:
            bg = "#f0f9ff"
        else:
            bg = "transparent"
        self.setStyleSheet(f"""
            QWidget#{self.objectName()} {{
                background-color: {bg};
                border-radius: 6px;
            }}
        """)
