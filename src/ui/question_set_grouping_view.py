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
    QStyledItemDelegate,
)
from config.constants import TAG_COLORS
from ui.dialogs import MultiSelectTagDialog
from ui.widgets import TagBadge


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
        self.question_set_min_pages: dict[str, float] = {}
        self.question_set_magazine: dict[str, str] = {}
        self.selected_group = None  # Currently selected group
        self.group_tags: dict[str, list[str]] = {}
        self.tag_colors: dict[str, str] = {}
        
        # Setup UI
        self._setup_ui()
        self._load_tags_config()
    
    def _setup_ui(self):
        """Setup the user interface with two-column layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)
        
        # Title
        title = QLabel(" Question Set Grouping")
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
        
        left_icon = QLabel("")
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
        add_group_btn = QPushButton("")
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
        # Remove default item painting (focus/selection rectangles) since we render custom widgets.
        self.groups_list.setItemDelegate(NoOutlineDelegate(self.groups_list))
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
            QListWidget::drop-indicator {
                border: none;
                height: 0px;
                background: transparent;
            }
            QListView::dropIndicator {
                border: none;
                height: 0px;
                background: transparent;
            }
            QListView::item {
                outline: 0;
                border: none;
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
        
        right_icon = QLabel("")
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
    
    def update_from_workbook(
        self,
        question_sets: list[str],
        question_set_min_pages: dict[str, float] | None = None,
        question_set_magazine: dict[str, str] | None = None,
    ):
        """
        Update the view with question sets from workbook.
        
        Args:
            question_sets: List of question set names from workbook
        """
        self.all_question_sets = question_sets
        self.question_set_min_pages = question_set_min_pages or {}
        self.question_set_magazine = question_set_magazine or {}
        self._refresh_groups_list()
        
        # Select first group if available
        if self.groups_list.count() > 0:
            self.groups_list.setCurrentRow(0)
    
    def _refresh_groups_list(self):
        """Refresh the groups list with current groups and counts."""
        if not self.group_service:
            return
        
        self.groups_list.clear()
        entries: list[dict] = []

        # Get all groups
        groups = self.group_service.get_all_groups()

        # Add saved groups with computed min page
        for group_name, group_data in groups.items():
            question_sets = group_data.get("question_sets", [])
            count = len(question_sets)
            entries.append({
                "name": group_name,
                "count": count,
                "color": group_data.get("color", "#3b82f6"),
                "min_page": self._compute_group_min_page(question_sets),
            })

        # Add "Others" group (sorted by page too, not pinned to top)
        others_group = self.group_service.get_others_group(self.all_question_sets)
        others_sets = others_group["question_sets"]
        entries.append({
            "name": "Others",
            "count": len(others_sets),
            "color": "#94a3b8",
            "min_page": self._compute_group_min_page(others_sets),
        })

        # Sort by name (alphabetical)
        entries = sorted(entries, key=lambda e: e["name"].lower())

        for entry in entries:
            item = QListWidgetItem()
            # Leave text empty because custom widget renders the name
            item.setText("")
            item.setData(Qt.UserRole, entry["name"])  # Store group name
            item.setData(Qt.UserRole + 1, entry["count"])  # Store count
            self.groups_list.addItem(item)
            self._style_group_item(item, entry["name"], entry["count"], entry["color"])

        # Restore selection to previously selected group if available
        if self.selected_group:
            for idx in range(self.groups_list.count()):
                item = self.groups_list.item(idx)
                if item and item.data(Qt.UserRole) == self.selected_group:
                    self.groups_list.setCurrentRow(idx)
                    break

        # Reapply selection highlight to match current selection
        self._update_group_item_selection()
        # Ensure item widths match viewport after rebuild
        self.groups_list._sync_item_widths()

    def _compute_group_min_page(self, question_sets: list[str]) -> float:
        """Return the smallest page number across question sets; inf if unavailable."""
        min_page = float("inf")
        for qs in question_sets:
            page_val = self.question_set_min_pages.get(qs)
            if page_val is None:
                continue
            try:
                page_num = float(page_val)
            except (ValueError, TypeError):
                continue
            if page_num < min_page:
                min_page = page_num
        return min_page

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
            if group_name in self.group_tags:
                del self.group_tags[group_name]
                self._save_tags_config()
            self._refresh_groups_list()
    
    def _style_group_item(self, item: QListWidgetItem, group_name: str, count: int, color: str):
        """Style a group item with name, badge count, and hover action buttons."""
        # Create widget for custom rendering
        tags = self.group_tags.get(group_name, [])
        widget = GroupItemWidget(group_name, count, color, tags, self.tag_colors, self)
        widget.rename_clicked.connect(lambda name=group_name: self._on_rename_group(name))
        widget.delete_clicked.connect(lambda name=group_name: self._on_delete_group(name))
        widget.tag_edit_clicked.connect(lambda name=group_name: self._on_edit_tags(name))
        
        # Set widget for item with proper sizing
        # Width will be synced to viewport so we only set the height here
        size_hint = widget.sizeHint()
        item.setSizeHint(QSize(self.groups_list.viewport().width(), size_hint.height()))
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
            # Plain text (emoji placeholders caused unreadable "??" on some systems)
            item.setText(qs_name)
            item.setData(Qt.UserRole, qs_name)  # Store actual name without emoji
            magazine = self.question_set_magazine.get(qs_name, "")
            if magazine:
                item.setToolTip(f"Magazine: {magazine}")
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
            event.acceptProposedAction()
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
                # Rename tags mapping
                if group_name in self.group_tags:
                    self.group_tags[new_name] = self.group_tags.pop(group_name)
                    self._save_tags_config()
                
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

    def _on_edit_tags(self, group_name: str):
        """Open tag selection dialog for a group."""
        existing_tags = sorted(set(self.tag_colors.keys()) | set(sum(self.group_tags.values(), [])))
        selected_tags = self.group_tags.get(group_name, [])
        dialog = MultiSelectTagDialog(
            existing_tags=existing_tags,
            selected_tags=selected_tags,
            title=f"Tags for '{group_name}'",
            tag_colors=self.tag_colors,
            available_colors=TAG_COLORS,
            parent=self,
        )
        if dialog.exec():
            chosen = dialog.get_selected_tags()
            self.tag_colors.update(dialog.tag_colors)
            if chosen:
                self.group_tags[group_name] = chosen
            elif group_name in self.group_tags:
                del self.group_tags[group_name]
            self._save_tags_config()
            self._refresh_groups_list()

    def _load_tags_config(self):
        """Load tags from database (provided by main window)."""
        # main window now handles tag persistence; start empty here
        self.tag_colors = getattr(self.parent(), "tag_colors", {}) or {}
        self.group_tags = getattr(self.parent(), "question_set_group_tags", {}) or {}

    def _save_tags_config(self):
        """No-op: main window handles tag persistence."""
        pass


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
        offset = radius * 0.7 / math.sqrt(2)  # components along x/y for 45
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
        self.setDropIndicatorShown(False)
        self.setAlternatingRowColors(False)
        self.setFrameShape(QFrame.NoFrame)
        self._drag_item = None
        self._original_styles = {}  # key: id(item) -> style dict

    def resizeEvent(self, event):
        """Keep item widgets stretched to the viewport width to avoid empty drop-rect area."""
        super().resizeEvent(event)
        self._sync_item_widths()

    def paintEvent(self, event):
        """Skip default painting to avoid any built-in drop/selection outlines."""
        return

    def _sync_item_widths(self):
        """Stretch each item's size hint to the current viewport width."""
        viewport_width = self.viewport().width()
        for idx in range(self.count()):
            item = self.item(idx)
            if item:
                current = item.sizeHint()
                item.setSizeHint(QSize(viewport_width, current.height()))

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(QuestionSetListWidget.MIME_TYPE):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(QuestionSetListWidget.MIME_TYPE):
            self._highlight_item_under(event.position().toPoint())
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        self._clear_highlight()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        if not event.mimeData().hasFormat(QuestionSetListWidget.MIME_TYPE):
            event.ignore()
            return
        self._clear_highlight()

        # Determine target group from drop position
        item = self.itemAt(event.position().toPoint())
        if not item:
            event.ignore()
            return
        target_group = item.data(Qt.UserRole)

        # Parse dragged data
        try:
            payload = json.loads(event.mimeData().text())
            qs_names = payload.get("question_sets", [])
            from_group = payload.get("from_group")
        except Exception:
            event.ignore()
            return

        if self.parent_view:
            self.parent_view._on_question_set_drop_on_group(qs_names, from_group, target_group, event)
        else:
            event.ignore()

    def _highlight_item_under(self, pos):
        item = self.itemAt(pos)
        if item is self._drag_item:
            return
        # Clear previous
        if self._drag_item:
            widget = self.itemWidget(self._drag_item)
            if widget:
                widget.set_drag_over(False)
        self._drag_item = item
        if item:
            widget = self.itemWidget(item)
            if widget:
                widget.set_drag_over(True)
            # Save and apply strong hover style for the list item itself
            item_key = id(item)
            if item_key not in self._original_styles:
                self._original_styles[item_key] = {
                    "bg": item.background(),
                    "fg": item.foreground(),
                    "text": item.text(),
                    "ref": item,
                }
            item.setBackground(QColor("#0b3a83"))  # deep blue highlight
            item.setForeground(QColor("#f8fafc"))  # near-white text
            item.setText(f" {item.text()} ")

    def _clear_highlight(self):
        if self._drag_item:
            widget = self.itemWidget(self._drag_item)
            if widget:
                widget.set_drag_over(False)
            item_key = id(self._drag_item)
            if item_key in self._original_styles:
                orig = self._original_styles.pop(item_key)
                if orig.get("ref") is self._drag_item:
                    self._drag_item.setBackground(orig["bg"])
                    self._drag_item.setForeground(orig["fg"])
                    self._drag_item.setText(orig["text"])
        self._drag_item = None
        # Ensure widths stay synced after drag operations
        self._sync_item_widths()


class NoOutlineDelegate(QStyledItemDelegate):
    """Delegate that suppresses default QListWidget painting (focus/selection rects)."""

    def paint(self, painter, option, index):
        # Skip default painting; custom widgets draw everything needed.
        return


class GroupItemWidget(QWidget):
    """
    Custom widget for displaying a group item with hover action buttons.
    Shows rename button on hover.
    """
    
    rename_clicked = Signal()  # Emitted when rename button is clicked
    delete_clicked = Signal()  # Emitted when delete button is clicked (when count == 0)
    tag_edit_clicked = Signal()  # Emitted when tag edit is requested
    
    def __init__(self, group_name: str, count: int, color: str, tags: list[str], tag_colors: dict[str, str], parent=None):
        """Initialize the group item widget."""
        super().__init__(parent)
        self.group_name = group_name
        self.count = count
        self.color = color
        self.tags = tags or []
        self.tag_colors = tag_colors or {}
        self.setMouseTracking(True)  # Enable mouse tracking for hover
        self.setObjectName("groupItemWidget")
        self.setAutoFillBackground(True)
        self.selected = False
        self.hovered = False
        self.can_delete = count == 0 and group_name != "Others"
        self.drag_over = False
        
        # Main layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignVCenter)
        
        # Container holding label + badge with shared background
        self.pill_container = QWidget()
        pill_layout = QHBoxLayout(self.pill_container)
        pill_layout.setContentsMargins(10, 8, 10, 8)
        pill_layout.setSpacing(6)
        
        # Group name label
        self.name_label = QLabel(group_name)
        self.name_label.setStyleSheet(f"""
            QLabel {{
                font-size: 12px;
                color: #1e40af;
                font-weight: 500;
                background: transparent;
                border: none;
            }}
        """)
        self.name_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        pill_layout.addWidget(self.name_label)
        
        # Count badge
        self.badge_label = QLabel(str(count))
        self.badge_label.setStyleSheet(f"""
            QLabel {{
                background-color: transparent;
                color: {color};
                border: 1px solid {color};
                border-radius: 12px;
                padding: 2px 8px;
                font-size: 10px;
                font-weight: bold;
                min-width: 22px;
                text-align: center;
            }}
        """)
        self.badge_label.setFixedWidth(32)

        # Tag badges
        self.tag_container = QWidget()
        self.tag_container.setStyleSheet("background: transparent;")
        self.tag_layout = QHBoxLayout(self.tag_container)
        self.tag_layout.setContentsMargins(0, 0, 0, 0)
        self.tag_layout.setSpacing(4)
        # Shrink to fit tag badges; don't let this area stretch and show empty outlines.
        self.tag_container.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        pill_layout.addWidget(self.tag_container)
        self._render_tags()

        # Push count badge to the far right: tags before, then stretch, then badge
        pill_layout.addStretch()
        pill_layout.addWidget(self.badge_label, alignment=Qt.AlignRight | Qt.AlignVCenter)
        
        layout.addWidget(self.pill_container, 1)
        
        # Rename button (hidden by default, shown on hover)
        self.rename_btn = QPushButton("")
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
        self.delete_btn = QPushButton("")
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

        # Tag edit button
        self.tag_btn = QPushButton("")
        self.tag_btn.setStyleSheet("""
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
                background-color: #e0f2fe;
                border-radius: 3px;
            }
        """)
        self.tag_btn.hide()
        self.tag_btn.clicked.connect(self.tag_edit_clicked.emit)
        layout.addWidget(self.tag_btn, alignment=Qt.AlignRight | Qt.AlignVCenter)
        
        # Set minimum height
        self.setMinimumHeight(38)
        self.setMaximumHeight(38)  # Slightly taller for pill spacing
        self._update_background()

    def sizeHint(self):
        """Return the preferred size of the widget."""
        return QSize(200, 38)

    def _render_tags(self):
        """Render tag badges inside the pill."""
        # clear existing
        while self.tag_layout.count():
            item = self.tag_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for tag in self.tags[:3]:  # show up to 3
            color = self.tag_colors.get(tag, "#2563eb")
            badge = TagBadge(tag, color)
            self.tag_layout.addWidget(badge)

    def set_selected(self, selected: bool):
        """Update selection state and refresh background."""
        self.selected = selected
        self._update_background()

    def set_tags(self, tags: list[str]):
        """Update displayed tags."""
        self.tags = tags or []
        self._render_tags()
    
    def enterEvent(self, event):
        """Show action buttons on hover."""
        self.rename_btn.show()
        if self.can_delete:
            self.delete_btn.show()
        self.tag_btn.show()
        self.hovered = True
        self._update_background()
        self.update()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Hide action buttons when not hovering."""
        self.rename_btn.hide()
        self.delete_btn.hide()
        self.tag_btn.hide()
        self.hovered = False
        self._update_background()
        self.update()
        super().leaveEvent(event)

    def _update_background(self):
        """Apply hover/selection/drag background without relying on QListWidget painting."""
        if self.drag_over:
            # Dark highlight for drag target
            pill_bg = "#0b3a83"
            pill_border = "#38bdf8"
            name_color = "#f8fafc"
            badge_color = "#f8fafc"
            badge_border = "#38bdf8"
        elif self.selected:
            pill_bg = "#e0f2fe"
            pill_border = "#bfdbfe"
            name_color = "#1e3a8a"
            badge_color = self.color
            badge_border = self.color
        elif self.hovered:
            pill_bg = "#f0f9ff"
            pill_border = "#e0f2fe"
            name_color = "#1e40af"
            badge_color = self.color
            badge_border = self.color
        else:
            pill_bg = "#eef2ff"
            pill_border = "transparent"
            name_color = "#1e40af"
            badge_color = self.color
            badge_border = self.color

        # Container styling
        self.setStyleSheet(f"""
            QWidget#{self.objectName()} {{
                background-color: transparent;
                border-radius: 6px;
            }}
        """)
        self.pill_container.setStyleSheet(f"""
            QWidget {{
                background-color: {pill_bg};
                border-radius: 12px;
                border: 1px solid {pill_border};
            }}
        """)

        # Text/badge styling updates so drag highlight uses light text
        self.name_label.setStyleSheet(f"""
            QLabel {{
                font-size: 12px;
                color: {name_color};
                font-weight: 600;
                background: transparent;
                border: none;
            }}
        """)
        self.badge_label.setStyleSheet(f"""
            QLabel {{
                background-color: transparent;
                color: {badge_color};
                border: 1px solid {badge_border};
                border-radius: 12px;
                padding: 2px 8px;
                font-size: 10px;
                font-weight: bold;
                min-width: 22px;
                text-align: center;
            }}
        """)

    def set_drag_over(self, active: bool):
        """Highlight when a drag is hovering over the item."""
        self.drag_over = active
        self._update_background()

