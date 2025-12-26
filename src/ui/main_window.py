"""
Main application window for TSV to Excel Watcher.

This module contains the TSVWatcherWindow class which is the main UI window
for the application. It handles:
- Database analysis and magazine edition tracking
- Question list management with grouping and tagging
- Chapter grouping and organization
- TSV file monitoring and import
- Custom question list creation
"""

from __future__ import annotations

import datetime as dt
import json
import base64
import queue
import subprocess
import re
import threading
import time
import math
import sqlite3
import shutil
import tempfile
import shlex
import secrets
from io import BytesIO
from pathlib import Path

import pandas as pd
from PySide6.QtCore import Qt, QTimer, QSize, QStringListModel
from PySide6.QtGui import QColor, QFont, QPalette, QTextCursor, QPixmap, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCompleter,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    QSplitter,
    QStyle,
    QStackedLayout,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QPlainTextEdit,
    QFrame,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config.constants import (
    LAST_SELECTION_FILE,
    MAGAZINE_GROUPING_MAP,
    TAG_COLORS,
    DEFAULT_DB_PATH,
)
from services.db_service import DatabaseService
from services.excel_service import process_tsv
from services.question_set_group_service import QuestionSetGroupService
from ui.dialogs import QuestionEditDialog
from services.cbt_package import build_payload, save_cqt, hash_eval_password
from ui.dialogs import MultiSelectTagDialog, PasswordPromptDialog, CQTAuthorPreviewDialog
from ui.question_set_grouping_view import QuestionSetGroupingView
from ui.icon_utils import load_icon
from ui.widgets import (
    ChapterCardView,
    ChapterTableWidget,
    DashboardView,
    GroupingChapterListWidget,
    GroupListWidget,
    NavigationSidebar,
    QuestionCardWidget,
    QuestionCardWithRemoveButton,
    QuestionTreeWidget,
    QuestionListCardView,
    TagBadge,
)
from utils.helpers import (
    _find_high_level_chapter_column,
    _find_magazine_column,
    _find_page_column,
    _find_qno_column,
    _find_question_set_column,
    _find_question_set_name_column,
    _find_question_text_column,
    normalize_magazine_edition,
    normalize_text,
)


class TSVWatcherWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("TSV to Excel Watcher")
        self.resize(1200, 820)

        self.event_queue: queue.Queue[tuple] = queue.Queue()
        self.watch_thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.file_rows: dict[str, int] = {}
        self.file_errors: dict[str, str] = {}
        self.metrics_request_id = 0
        self.chapter_questions: dict[str, list[dict[str, str]]] = {}
        self.current_questions: list[dict[str, str]] = []
        self.all_questions: list[dict[str, str]] = []  # Unfiltered questions
        self.advanced_query_term: str = ""
        self.tag_filter_term: str = ""
        self.selected_tag_filters: list[str] = []  # Multiple selected tags for filtering
        self.current_magazine_name: str = ""  # Track current magazine for grouping
        self.current_selected_chapter: str | None = None  # Track selected chapter
        self.canonical_chapters: list[str] = []
        self.chapter_lookup: dict[str, str] = {}
        self.chapter_groups: dict[str, list[str]] = {}
        self.current_Database_path: Path | None = None
        self.Database_df: pd.DataFrame | None = None  # Cached DataFrame
        self.high_level_column_index: int | None = None
        self.question_lists: dict[str, list[dict]] = {}  # name -> list of questions
        self.question_lists_metadata: dict[str, dict] = {}  # name -> metadata (filters, magazine, etc)
        self.current_list_name: str | None = None
        self.current_selected_chapter: str | None = None  # Track selected chapter for filtering
        self.current_list_questions: list[dict] = []  # Questions in currently selected list
        self.group_tags: dict[str, list[str]] = {}  # group_key -> list of tags
        self.question_set_group_tags: dict[str, list[str]] = {}  # question set group name -> tags
        self.tag_colors: dict[str, str] = {}  # tag -> color
        self.copy_mode: str = "Copy: Text"  # Default copy mode for question cards
        self.list_copy_mode: str = "Copy: Text"  # Default copy mode for custom list cards
        self.mag_heatmap_data: dict[tuple[int, int], dict] = {}  # (year, month) -> info
        self.mag_page_ranges: dict[str, tuple[str, str]] = {}  # normalized edition -> (min, max)
        self.question_set_groups_dirty: bool = False  # Track if groupings changed
        self.pending_auto_watch: bool = False  # deprecated
        self._question_tab_controls: list[QWidget] = []  # widgets to disable during question reload
        self.current_magazine_display_name: str = ""  # Human-friendly magazine name for UI
        self.watch_Database_path: Path | None = None  # deprecated
        self.db_service = DatabaseService(DEFAULT_DB_PATH)
        self.current_db_path: Path = DEFAULT_DB_PATH
        self.current_subject: str | None = None
        self.use_database: bool = False
        
        # Custom list search variables
        self.list_question_set_search_term: str = ""
        self.comparison_target: str | None = None  # List name selected for comparison
        self.comparison_common_ids: set[str] = set()
        
        # JEE Main Papers analysis
        self.jee_papers_df: pd.DataFrame | None = None
        self.jee_papers_file: Path | None = None
        
        # Predefined color palette for tags (20 colors)
        self.available_tag_colors = [
            "#2563eb",  # Blue
            "#10b981",  # Green
            "#f59e0b",  # Amber
            "#ef4444",  # Red
            "#8b5cf6",  # Purple
            "#06b6d4",  # Cyan
            "#ec4899",  # Pink
            "#14b8a6",  # Teal
            "#f97316",  # Orange
            "#6366f1",  # Indigo
            "#84cc16",  # Lime
            "#f43f5e",  # Rose
            "#0ea5e9",  # Sky Blue
            "#a855f7",  # Violet
            "#22c55e",  # Green Light
            "#eab308",  # Yellow
            "#d946ef",  # Fuchsia
            "#3b82f6",  # Blue Light
            "#fb923c",  # Orange Light
            "#38bdf8",  # Sky
        ]

        # Status bar animation state
        self.status_animation_frame = 0
        self.status_animation_timer = QTimer()
        self.status_animation_timer.timeout.connect(self._animate_status)

        # Data quality required fields
        self.data_quality_required = [
            "subject_id",
            "magazine",
            "normalized_magazine",
            "edition",
            "question_set",
            "question_set_name",
            "chapter",
            "high_level_chapter",
            "question_number",
            "question_text",
            "page_range",
        ]

        # Backup DB before any reads on startup
        self._backup_current_database()
        self._load_group_tags()

        self._build_ui()
        self._load_last_selection()
        self._setup_timer()
        # Delay initial load to ensure UI is ready and timer is running
        QTimer.singleShot(100, self.update_row_count)

    def _build_ui(self) -> None:
        self._apply_palette()
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(10)

        # Create horizontal splitter for sidebar + content
        main_splitter = QSplitter(Qt.Horizontal)
        root_layout.addWidget(main_splitter, 1)

        # Left: Navigation sidebar
        self.sidebar = NavigationSidebar()
        self.sidebar.navigation_changed.connect(self._on_navigation_changed)
        main_splitter.addWidget(self.sidebar)

        # Right: Stacked widget for content pages
        self.content_stack = QStackedWidget()
        main_splitter.addWidget(self.content_stack)

        # Set splitter sizes (sidebar: 200px, content: remaining)
        main_splitter.setSizes([200, 1000])
        main_splitter.setCollapsible(0, False)  # Don't allow sidebar to collapse to 0

        # Create all view pages
        self._create_dashboard_page()           # Index 0
        self._create_magazine_page()            # Index 1
        self._create_questions_page()           # Index 2
        self._create_grouping_page()            # Index 3
        self._create_lists_page()               # Index 4
        self._create_question_set_grouping_page()  # Index 5
        self._create_import_page()              # Index 6
        self._create_jee_page()                 # Index 7
        self._create_exams_page()               # Index 8
        self._create_data_quality_page()        # Index 9

        # Status bar and log toggle row
        status_log_layout = QHBoxLayout()
        
        # Status label with animation
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("""
            QLabel {
                padding: 8px 16px;
                background-color: #f1f5f9;
                border-radius: 6px;
                color: #475569;
                font-size: 13px;
            }
        """)
        self.status_label.setVisible(True)
        self.status_label.setWordWrap(False)
        self.status_label.setMinimumWidth(200)
        status_log_layout.addWidget(self.status_label, 1)
        
        status_log_layout.addSpacing(10)
        
        self.log_toggle = QPushButton("Show Log")
        self.log_toggle.setCheckable(True)
        self.log_toggle.toggled.connect(self.toggle_log_visibility)
        status_log_layout.addWidget(self.log_toggle)
        
        root_layout.addLayout(status_log_layout)

        # Log card (collapsible)
        self.log_card = self._create_card()
        log_layout = QVBoxLayout(self.log_card)
        log_layout.addWidget(self._create_label("Log"))
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setObjectName("logView")
        log_layout.addWidget(self.log_view)
        root_layout.addWidget(self.log_card, 0)
        self.log_card.setVisible(False)
        
        self._refresh_grouping_ui()
        self._load_saved_question_lists()

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            else:
                child = item.layout()
                if child:
                    self._clear_layout(child)
        layout.update()

    def _on_navigation_changed(self, index: int):
        """Handle navigation sidebar item selection."""
        self.content_stack.setCurrentIndex(index)
        
        # If returning to Question List and a rebuild is needed, show loading overlay and refresh
        if index == 2 and (self.question_set_groups_dirty or not self.current_questions):
            self._refresh_question_tab_with_loading()
            self.question_set_groups_dirty = False
        if index == 8:
            self._load_exam_list()
        if index == 9:
            self._load_data_quality_table()

    def _create_dashboard_page(self):
        """Create Dashboard page (index 0)."""
        dashboard_container = QWidget()
        dashboard_layout = QVBoxLayout(dashboard_container)
        dashboard_layout.setContentsMargins(20, 20, 20, 20)
        dashboard_layout.setSpacing(20)
        
        # Database selector card
        Database_card = self._create_card()
        Database_layout = QVBoxLayout(Database_card)
        Database_layout.setSpacing(12)
        
        self.output_edit = QLineEdit()
        self.output_edit.editingFinished.connect(self.update_row_count)
        output_row = QHBoxLayout()
        output_row.addWidget(self._create_label("Database"))
        output_row.addWidget(self.output_edit)
        browse_output = QPushButton("Browse")
        browse_output.clicked.connect(self.select_output_file)
        output_row.addWidget(browse_output)
        Database_layout.addLayout(output_row)
        
        # Create compatibility labels (hidden, used for logging/status updates)
        self.row_count_label = QLabel("Total rows: N/A")
        self.row_count_label.setVisible(False)
        self.mag_summary_label = QLabel("Magazines: N/A")
        self.mag_summary_label.setVisible(False)
        self.mag_missing_label = QLabel("Missing ranges: N/A")
        self.mag_missing_label.setVisible(False)
        
        # Database UI no longer used (DB-only); hide the card.
        Database_card.setVisible(False)
        dashboard_layout.addWidget(Database_card)
        
        # Database selector card
        db_card = self._create_card()
        db_layout = QVBoxLayout(db_card)
        db_layout.setSpacing(12)

        # DB path row
        db_row = QHBoxLayout()
        db_row.addWidget(self._create_label("Database"))
        self.db_path_edit = QLineEdit(str(DEFAULT_DB_PATH))
        self.db_path_edit.setToolTip("SQLite database path")
        db_row.addWidget(self.db_path_edit, 1)
        browse_db = QPushButton("Browse")
        browse_db.clicked.connect(self.select_db_file)
        db_row.addWidget(browse_db)
        db_layout.addLayout(db_row)

        # Subject toggle row
        subject_row = QHBoxLayout()
        subject_row.addWidget(self._create_label("Subject"))
        self.subject_combo = QComboBox()
        self.subject_combo.addItems(["Physics", "Chemistry", "Mathematics"])
        self.subject_combo.setCurrentIndex(0)
        subject_row.addWidget(self.subject_combo, 1)

        load_db_btn = QPushButton("Load from DB")
        load_db_btn.clicked.connect(self.load_subject_from_db)
        subject_row.addWidget(load_db_btn)
        db_layout.addLayout(subject_row)

        dashboard_layout.addWidget(db_card)
        
        # Add the new DashboardView for statistics
        self.dashboard_view = DashboardView(self)
        dashboard_layout.addWidget(self.dashboard_view, 1)
        
        self.content_stack.addWidget(dashboard_container)

    def _create_magazine_page(self):
        """Create Magazine Editions page (index 1)."""
        magazine_page = QWidget()
        magazine_tab_layout = QVBoxLayout(magazine_page)
        
        # Top summary card
        mag_summary_card = self._create_card()
        mag_summary_layout = QHBoxLayout(mag_summary_card)
        self.mag_total_editions_label = QLabel("Total Editions: 0")
        self.mag_total_editions_label.setObjectName("headerLabel")
        self.mag_total_sets_label = QLabel("Question Sets: 0")
        self.mag_total_sets_label.setObjectName("infoLabel")
        mag_summary_layout.addWidget(self.mag_total_editions_label)
        mag_summary_layout.addStretch()
        mag_summary_layout.addWidget(self.mag_total_sets_label)
        magazine_tab_layout.addWidget(mag_summary_card)
        
        mag_split = QSplitter(Qt.Horizontal)
        magazine_tab_layout.addWidget(mag_split, 1)
        
        # Left side - Magazine heatmap
        mag_heatmap_card = self._create_card()
        mag_heatmap_layout = QVBoxLayout(mag_heatmap_card)
        mag_heatmap_layout.addWidget(self._create_label("Magazine Editions (Heatmap)"))
        
        # Heatmap scroll area
        self.mag_heatmap_scroll = QScrollArea()
        self.mag_heatmap_scroll.setWidgetResizable(True)
        self.mag_heatmap_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.mag_heatmap_container = QWidget()
        self.mag_heatmap_layout = QVBoxLayout(self.mag_heatmap_container)
        self.mag_heatmap_layout.setContentsMargins(0, 0, 0, 0)
        self.mag_heatmap_layout.setSpacing(12)
        self.mag_heatmap_layout.addStretch()
        self.mag_heatmap_scroll.setWidget(self.mag_heatmap_container)
        mag_heatmap_layout.addWidget(self.mag_heatmap_scroll)
        mag_split.addWidget(mag_heatmap_card)

        # Right side - Question sets detail with tree
        detail_card = self._create_card()
        detail_layout = QVBoxLayout(detail_card)
        detail_layout.addWidget(self._create_label("Question Sets"))
        self.question_label = QLabel("Select an edition to view question sets")
        self.question_label.setObjectName("infoLabel")
        self.question_label.setStyleSheet(
            "padding: 8px; background-color: #f1f5f9; border-radius: 6px; color: #475569;"
        )
        detail_layout.addWidget(self.question_label)
        
        # Accordion-style question view (reuse card view)
        self.mag_question_card_view = QuestionListCardView(self)
        detail_layout.addWidget(self.mag_question_card_view)
        mag_split.addWidget(detail_card)
        
        mag_split.setSizes([500, 400])
        
        self.content_stack.addWidget(magazine_page)

    def _create_questions_page(self):
        """Create Question List page (index 2)."""
        questions_page = QWidget()
        questions_tab_layout = QVBoxLayout(questions_page)
        analysis_card = self._create_card()
        questions_tab_layout.addWidget(analysis_card)
        analysis_layout = QVBoxLayout(analysis_card)
        analysis_split = QSplitter(Qt.Horizontal)
        analysis_layout.addWidget(analysis_split, 1)

        chapter_card = self._create_card()
        chapter_layout = QVBoxLayout(chapter_card)
        chapter_layout.addWidget(self._create_label("Chapters"))
        self.chapter_view = ChapterCardView(self)
        self.chapter_view.chapter_selected.connect(self.on_chapter_selected)
        chapter_layout.addWidget(self.chapter_view)
        analysis_split.addWidget(chapter_card)

        # Wrap the question card in a stacked layout to show a loading overlay when rebuilding
        question_card = self._create_card()
        self.question_card = question_card
        question_layout = QVBoxLayout(question_card)
        
        # Search and action controls in single row
        search_layout = QHBoxLayout()
        search_layout.setSpacing(8)
        
        # Search controls container with visual grouping
        search_container = QWidget()
        search_container.setStyleSheet("""
            QWidget {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 6px;
            }
            QLabel {
                color: #1e40af;
                font-weight: 600;
                background: transparent;
            }
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 4px 8px;
                color: #0f172a;
            }
            QLineEdit:focus {
                border: 1px solid #3b82f6;
            }
        """)
        search_container_layout = QHBoxLayout(search_container)
        search_container_layout.setContentsMargins(8, 4, 8, 4)
        search_container_layout.setSpacing(8)
        
        # Advanced query input
        self.advanced_query_input = QLineEdit()
        self.advanced_query_input.setPlaceholderText('Query: text ~ "roots" AND magazine ~ "Nov"')
        self.advanced_query_input.setToolTip("Advanced query across text, magazine, question set. Use = or ~, AND/OR.")
        self.advanced_query_input.setMinimumHeight(28)
        self.advanced_query_input.setMaximumHeight(28)
        self.advanced_query_input.returnPressed.connect(self._on_advanced_query_submit)
        # Autocomplete for fields/operators
        self.advanced_query_completer_model = QStringListModel()
        self.advanced_query_completer = QCompleter(self.advanced_query_completer_model, self)
        self.advanced_query_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.advanced_query_completer.setFilterMode(Qt.MatchContains)
        self.advanced_query_input.setCompleter(self.advanced_query_completer)
        self.advanced_query_input.textEdited.connect(self._update_advanced_query_completions)
        search_container_layout.addWidget(self.advanced_query_input, 3)  # Stretch factor 3

        # Go button
        self.advanced_query_go_btn = QPushButton("")
        self.advanced_query_go_btn.setToolTip("Run query")
        self.advanced_query_go_btn.setIcon(load_icon("navigation.png"))
        self.advanced_query_go_btn.setIconSize(QSize(16, 16))
        self.advanced_query_go_btn.setMinimumHeight(28)
        self.advanced_query_go_btn.setMaximumHeight(28)
        self.advanced_query_go_btn.setMinimumWidth(32)
        self.advanced_query_go_btn.setMaximumWidth(32)
        self.advanced_query_go_btn.clicked.connect(self._on_advanced_query_submit)
        search_container_layout.addWidget(self.advanced_query_go_btn)
        
        # Tags filter
        self.tag_filter_display = QLineEdit()
        self.tag_filter_display.setPlaceholderText("No tags selected")
        self.tag_filter_display.setToolTip("Selected tags for filtering")
        self.tag_filter_display.setReadOnly(True)
        self.tag_filter_display.setMinimumHeight(28)
        self.tag_filter_display.setMaximumHeight(28)
        self.tag_filter_display.setStyleSheet("""
            QLineEdit {
                background-color: #0f172a;
                color: #ffffff;
                border: 1px solid #334155;
                padding: 4px 8px;
                border-radius: 4px;
            }
        """)
        search_container_layout.addWidget(self.tag_filter_display, 2)  # Stretch factor 2
        
        # Tag filter button (same style as accordion tag button)
        self.tag_filter_btn = QPushButton("")
        self.tag_filter_btn.setToolTip("Select tags to filter questions")
        self.tag_filter_btn.setIcon(load_icon("tag.svg"))
        self.tag_filter_btn.setIconSize(QSize(16, 16))
        self.tag_filter_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #3b82f6;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 14px;
                min-width: 30px;
                min-height: 28px;
                max-height: 28px;
            }
            QPushButton:hover {
                background-color: #3b82f6;
            }
        """)
        self.tag_filter_btn.clicked.connect(self._show_tag_filter_dialog)
        search_container_layout.addWidget(self.tag_filter_btn)
        
        # Clear button with icon
        clear_search_btn = QPushButton("")
        clear_search_btn.setToolTip("Clear all search filters")
        clear_search_btn.setMinimumHeight(28)
        clear_search_btn.setMaximumHeight(28)
        clear_search_btn.setMinimumWidth(32)
        clear_search_btn.setMaximumWidth(32)
        clear_search_btn.setIcon(load_icon("close.svg"))
        clear_search_btn.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
        """)
        clear_search_btn.clicked.connect(self.clear_question_search)
        search_container_layout.addWidget(clear_search_btn)
        
        search_layout.addWidget(search_container, 1)  # Stretch to fill space

        # Inline error for query parsing
        self.advanced_query_error = QLabel("")
        self.advanced_query_error.setStyleSheet("color: #dc2626; font-size: 12px;")
        self.advanced_query_error.setVisible(False)
        search_layout.addWidget(self.advanced_query_error, 0, Qt.AlignVCenter)
        
        # Action buttons container with different visual style
        action_container = QWidget()
        action_container.setStyleSheet("""
            QWidget {
                background-color: #dbeafe;
                border: 1px solid #93c5fd;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        action_layout = QHBoxLayout(action_container)
        action_layout.setContentsMargins(8, 4, 8, 4)
        action_layout.setSpacing(8)
        
        # Action buttons with icons
        add_to_list_btn = QPushButton()
        add_to_list_btn.setIcon(load_icon("add.svg"))
        add_to_list_btn.setToolTip("Add selected questions to list")
        add_to_list_btn.setMinimumHeight(28)
        add_to_list_btn.setMaximumHeight(28)
        add_to_list_btn.setMinimumWidth(32)
        add_to_list_btn.setMaximumWidth(32)
        add_to_list_btn.clicked.connect(self.add_selected_to_list)
        action_layout.addWidget(add_to_list_btn)
        
        create_random_list_btn = QPushButton()
        create_random_list_btn.setIcon(load_icon("random.png"))
        create_random_list_btn.setToolTip("Create random list from filtered questions")
        create_random_list_btn.setMinimumHeight(28)
        create_random_list_btn.setMaximumHeight(28)
        create_random_list_btn.setMinimumWidth(32)
        create_random_list_btn.setMaximumWidth(32)
        create_random_list_btn.clicked.connect(self.create_random_list_from_filtered)
        action_layout.addWidget(create_random_list_btn)
        
        # Copy mode selector
        action_layout.addSpacing(8)  # Visual separator
        self.copy_mode_combo = QComboBox()
        self.copy_mode_combo.addItems(["Copy: Text", "Copy: Metadata", "Copy: Both"])
        self.copy_mode_combo.setCurrentIndex(0)  # Default to "Copy: Text"
        self.copy_mode_combo.setToolTip("Select what to copy when double-clicking a question:\n"
                                        " Text: Only the question content\n"
                                        " Metadata: Only question number, page, chapter\n"
                                        " Both: Question text + metadata")
        self.copy_mode_combo.setMinimumHeight(28)
        self.copy_mode_combo.setMaximumHeight(28)
        self.copy_mode_combo.setStyleSheet("""
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #3b82f6;
                border-radius: 4px;
                padding: 4px 8px;
                color: #1e40af;
                font-weight: 600;
            }
            QComboBox:hover {
                background-color: #eff6ff;
            }
            QComboBox::drop-down {
                border: none;
                background: transparent;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #1e40af;
                selection-background-color: #3b82f6;
                selection-color: #ffffff;
            }
        """)
        self.copy_mode_combo.currentTextChanged.connect(self._on_copy_mode_changed)
        action_layout.addWidget(self.copy_mode_combo)
        
        search_layout.addWidget(action_container)

        question_layout.addLayout(search_layout)
        
        # Drag-drop panel (initially hidden)
        from src.ui.widgets import DragDropQuestionPanel
        self.drag_drop_panel = DragDropQuestionPanel(self.question_lists, self)
        self.drag_drop_panel.save_clicked.connect(self._on_drag_drop_save)
        self.drag_drop_panel.cancel_clicked.connect(self._on_drag_drop_cancel)
        self.drag_drop_panel.setVisible(False)
        question_layout.addWidget(self.drag_drop_panel)
        
        # Replace traditional tree with card-based view
        self.question_card_view = QuestionListCardView(self)
        self.question_card_view.question_selected.connect(self.on_question_card_selected)
        
        # Enable keyboard focus for Ctrl detection
        self.question_card_view.setFocusPolicy(Qt.StrongFocus)
        
        # Keep old tree widget reference for compatibility (hidden)
        self.question_tree = QuestionTreeWidget(self)
        self.question_tree.setVisible(False)
        self.question_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.question_tree.customContextMenuRequested.connect(self._show_group_context_menu)
        
        # Add card view directly without the text viewer splitter
        question_layout.addWidget(self.question_card_view)
        
        # Create hidden text view for compatibility with other code
        self.question_text_view = QTextEdit()
        self.question_text_view.setVisible(False)
        self.question_text_view.setReadOnly(True)
        self.question_text_view.setAcceptRichText(True)
        
        # Keep references to disable during loading
        self._question_tab_controls = [
            self.chapter_view,
            self.advanced_query_input,
            self.advanced_query_go_btn,
            self.tag_filter_display,
            self.tag_filter_btn,
            clear_search_btn,
            add_to_list_btn,
            create_random_list_btn,
            self.copy_mode_combo,
            self.question_card_view,
            self.drag_drop_panel,
        ]
        
        # Build loading overlay page for the question tab
        self.question_loading_overlay = QWidget()
        self.question_loading_overlay.setStyleSheet("background-color: rgba(15, 23, 42, 0.35);")
        overlay_layout = QVBoxLayout(self.question_loading_overlay)
        overlay_layout.setContentsMargins(0, 0, 0, 0)
        overlay_layout.setSpacing(8)
        overlay_layout.addStretch()
        overlay_label = QLabel("Loading questions...")
        overlay_label.setAlignment(Qt.AlignCenter)
        overlay_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 16px;
                font-weight: 700;
                padding: 12px 24px;
                background-color: rgba(37, 99, 235, 0.9);
                border-radius: 10px;
            }
        """)
        overlay_layout.addWidget(overlay_label)
        overlay_layout.addStretch()
        
        # Stacked layout to swap between content and overlay
        question_card_container = QWidget()
        self.question_card_stack = QStackedLayout(question_card_container)
        self.question_card_stack.setStackingMode(QStackedLayout.StackAll)
        self.question_card_stack.addWidget(question_card)
        self.question_card_stack.addWidget(self.question_loading_overlay)
        self.question_card_stack.setCurrentWidget(question_card)

        analysis_split.addWidget(question_card_container)

        self.content_stack.addWidget(questions_page)

    def _create_grouping_page(self):
        """Create Chapter Grouping page (index 3)."""
        grouping_page = QWidget()
        grouping_layout = QVBoxLayout(grouping_page)
        grouping_card = self._create_card()
        grouping_layout.addWidget(grouping_card)
        grouping_card_layout = QHBoxLayout(grouping_card)

        self.group_list = GroupListWidget(self)
        self.group_list.itemSelectionChanged.connect(self.on_group_selected)
        grouping_card_layout.addWidget(self.group_list, 1)

        self.group_chapter_list = GroupingChapterListWidget(self)
        grouping_card_layout.addWidget(self.group_chapter_list, 2)

        group_controls = QVBoxLayout()
        group_controls.addWidget(self._create_label("Move chapter to group"))
        self.move_target_combo = QComboBox()
        group_controls.addWidget(self.move_target_combo)
        move_button = QPushButton("Move Chapter")
        move_button.clicked.connect(self.move_selected_chapter)
        group_controls.addWidget(move_button)
        group_controls.addStretch()
        grouping_card_layout.addLayout(group_controls)
        
        self.content_stack.addWidget(grouping_page)

    def _create_lists_page(self):
        """Create Custom Lists page (index 4)."""
        lists_page = QWidget()
        lists_tab_layout = QVBoxLayout(lists_page)
        lists_card = self._create_card()
        lists_tab_layout.addWidget(lists_card)
        lists_card_layout = QVBoxLayout(lists_card)
        
        lists_header_layout = QHBoxLayout()
        lists_card_layout.addWidget(self._create_label("Custom Lists"))
        lists_header_layout.addStretch()
        lists_card_layout.addLayout(lists_header_layout)
        
        lists_split = QSplitter(Qt.Horizontal)
        lists_card_layout.addWidget(lists_split, 1)
        
        # Left side - list of saved lists
        saved_lists_card = self._create_card()
        saved_lists_layout = QVBoxLayout(saved_lists_card)
        saved_lists_layout.addWidget(self._create_label("Saved Lists"))

        list_controls_layout = QHBoxLayout()
        new_list_btn = QPushButton()
        new_list_btn.setIcon(self.style().standardIcon(QStyle.SP_FileIcon))
        new_list_btn.setToolTip("New List")
        new_list_btn.setFixedSize(QSize(32, 28))
        new_list_btn.clicked.connect(self.create_new_question_list)
        rename_list_btn = QPushButton()
        rename_list_btn.setIcon(self.style().standardIcon(QStyle.SP_FileDialogContentsView))
        rename_list_btn.setToolTip("Rename List")
        rename_list_btn.setFixedSize(QSize(32, 28))
        rename_list_btn.clicked.connect(self.rename_question_list)
        delete_list_btn = QPushButton()
        delete_list_btn.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        delete_list_btn.setToolTip("Delete List")
        delete_list_btn.setFixedSize(QSize(32, 28))
        delete_list_btn.clicked.connect(self.delete_question_list)
        theory_btn = QPushButton()
        theory_btn.setIcon(self.style().standardIcon(QStyle.SP_ArrowUp))
        theory_btn.setToolTip("Upload Theory")
        theory_btn.setFixedSize(QSize(32, 28))
        theory_btn.clicked.connect(self._open_theory_dialog)
        theory_pdf_btn = QPushButton()
        theory_pdf_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        theory_pdf_btn.setToolTip("Download Theory PDF")
        theory_pdf_btn.setFixedSize(QSize(32, 28))
        theory_pdf_btn.clicked.connect(self._download_theory_pdf)
        list_controls_layout.addWidget(new_list_btn)
        list_controls_layout.addWidget(rename_list_btn)
        list_controls_layout.addWidget(delete_list_btn)
        list_controls_layout.addWidget(theory_btn)
        list_controls_layout.addWidget(theory_pdf_btn)
        saved_lists_layout.addLayout(list_controls_layout)
        
        self.saved_lists_widget = QListWidget()
        self.saved_lists_widget.itemSelectionChanged.connect(self.on_saved_list_selected)
        saved_lists_layout.addWidget(self.saved_lists_widget)
        lists_split.addWidget(saved_lists_card)
        
        # Right side - questions in selected list
        list_questions_card = self._create_card()
        list_questions_layout = QVBoxLayout(list_questions_card)
        self.list_name_label = QLabel("Select a list to view questions")
        self.list_name_label.setObjectName("headerLabel")
        list_questions_layout.addWidget(self.list_name_label)
        
        # Label to show filters applied to this list
        self.list_filters_label = QLabel("")
        self.list_filters_label.setObjectName("infoLabel")
        self.list_filters_label.setWordWrap(True)
        self.list_filters_label.setStyleSheet(
            "padding: 6px; background-color: #fef3c7; border-radius: 4px; color: #92400e; font-size: 12px;"
        )
        self.list_filters_label.setVisible(False)
        list_questions_layout.addWidget(self.list_filters_label)

        # Comparison controls to highlight overlaps with another list
        compare_container = QWidget()
        compare_container.setStyleSheet("""
            QWidget {
                background-color: #ecfeff;
                border: 1px dashed #06b6d4;
                border-radius: 8px;
                padding: 8px;
            }
            QLabel {
                color: #0f172a;
                background: transparent;
            }
        """)
        compare_layout = QHBoxLayout(compare_container)
        compare_layout.setContentsMargins(8, 4, 8, 4)
        compare_layout.setSpacing(8)
        
        compare_label = QLabel("Compare with:")
        compare_label.setStyleSheet("font-weight: 600;")
        compare_layout.addWidget(compare_label)
        
        self.compare_list_combo = QComboBox()
        self.compare_list_combo.setMinimumHeight(28)
        self.compare_list_combo.setMaximumHeight(28)
        self.compare_list_combo.setStyleSheet("""
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #0ea5e9;
                border-radius: 4px;
                padding: 4px 8px;
                color: #0f172a;
                font-weight: 600;
            }
            QComboBox:hover {
                background-color: #e0f2fe;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #0f172a;
                selection-background-color: #bae6fd;
                selection-color: #0f172a;
            }
        """)
        self.compare_list_combo.currentIndexChanged.connect(self.on_compare_list_changed)
        compare_layout.addWidget(self.compare_list_combo, 1)
        
        self.compare_status_label = QLabel("Select another list to highlight common questions.")
        self.compare_status_label.setWordWrap(True)
        self.compare_status_label.setStyleSheet(
            "color: #0f172a; font-size: 12px; padding: 2px 6px; background-color: #cffafe; border-radius: 4px;"
        )
        self.compare_status_label.setVisible(False)
        compare_layout.addWidget(self.compare_status_label, 1)
        
        list_questions_layout.addWidget(compare_container)
        
        # Search and action controls in single row (similar to Question List tab)
        search_layout = QHBoxLayout()
        search_layout.setSpacing(8)
        
        # Search controls container with visual grouping
        search_container = QWidget()
        search_container.setStyleSheet("""
            QWidget {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 6px;
            }
            QLabel {
                color: #1e40af;
                font-weight: 600;
                background: transparent;
            }
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 4px 8px;
                color: #0f172a;
            }
            QLineEdit:focus {
                border: 1px solid #3b82f6;
            }
        """)
        search_container_layout = QHBoxLayout(search_container)
        search_container_layout.setContentsMargins(8, 4, 8, 4)
        search_container_layout.setSpacing(8)
        
        # Question Set search
        self.list_question_set_search = QLineEdit()
        self.list_question_set_search.setPlaceholderText("Search by question set name")
        self.list_question_set_search.setToolTip("Search by question set name")
        self.list_question_set_search.setMinimumHeight(28)
        self.list_question_set_search.setMaximumHeight(28)
        self.list_question_set_search.textChanged.connect(self.on_list_question_set_search_changed)
        search_container_layout.addWidget(self.list_question_set_search, 1)
        
        # Clear button
        clear_search_btn = QPushButton("")
        clear_search_btn.setToolTip("Clear search filter")
        clear_search_btn.setMinimumHeight(28)
        clear_search_btn.setMaximumHeight(28)
        clear_search_btn.setMinimumWidth(32)
        clear_search_btn.setMaximumWidth(32)
        clear_search_btn.setIcon(load_icon("close.svg"))
        clear_search_btn.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
        """)
        clear_search_btn.clicked.connect(self.clear_list_search)
        search_container_layout.addWidget(clear_search_btn)
        
        search_layout.addWidget(search_container, 1)
        
        # Action buttons container
        action_container = QWidget()
        action_container.setStyleSheet("""
            QWidget {
                background-color: #dbeafe;
                border: 1px solid #93c5fd;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        action_layout = QHBoxLayout(action_container)
        action_layout.setContentsMargins(8, 4, 8, 4)
        action_layout.setSpacing(8)
        
        # Copy mode selector for custom lists
        self.list_copy_mode_combo = QComboBox()
        self.list_copy_mode_combo.addItems(["Copy: Text", "Copy: Metadata", "Copy: Both"])
        self.list_copy_mode_combo.setCurrentIndex(0)
        self.list_copy_mode_combo.setToolTip("Select what to copy when double-clicking a question:\n"
                                             " Text: Only the question content\n"
                                             " Metadata: Only question number, page, chapter\n"
                                             " Both: Question text + metadata")
        self.list_copy_mode_combo.setMinimumHeight(28)
        self.list_copy_mode_combo.setMaximumHeight(28)
        self.list_copy_mode_combo.setStyleSheet("""
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #3b82f6;
                border-radius: 4px;
                padding: 4px 8px;
                color: #1e40af;
                font-weight: 600;
            }
            QComboBox:hover {
                background-color: #eff6ff;
            }
            QComboBox::drop-down {
                border: none;
                background: transparent;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #1e40af;
                selection-background-color: #3b82f6;
                selection-color: #ffffff;
            }
        """)
        self.list_copy_mode_combo.currentTextChanged.connect(self._on_list_copy_mode_changed)
        action_layout.addWidget(self.list_copy_mode_combo)
        
        export_pdf_btn = QPushButton("Export PDF")
        export_pdf_btn.setToolTip("Create a PDF with metadata and question images for this list")
        export_pdf_btn.setMinimumHeight(28)
        export_pdf_btn.setMaximumHeight(28)
        export_pdf_btn.setStyleSheet("""
            QPushButton {
                background-color: #1d4ed8;
                color: #ffffff;
                border: 1px solid #1e3a8a;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #1e40af;
            }
            QPushButton:disabled {
                background-color: #cbd5e1;
                color: #64748b;
                border: 1px solid #cbd5e1;
            }
        """)
        export_pdf_btn.clicked.connect(self.export_current_list_to_pdf)
        action_layout.addWidget(export_pdf_btn)

        export_cbt_btn = QPushButton("Export CBT (.cqt)")
        export_cbt_btn.setToolTip("Create a password-protected CBT package from this list")
        export_cbt_btn.setMinimumHeight(28)
        export_cbt_btn.setMaximumHeight(28)
        export_cbt_btn.setStyleSheet("""
            QPushButton {
                background-color: #0f766e;
                color: #ffffff;
                border: 1px solid #115e59;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #0d9488;
            }
            QPushButton:disabled {
                background-color: #cbd5e1;
                color: #64748b;
                border: 1px solid #cbd5e1;
            }
        """)
        export_cbt_btn.clicked.connect(self.export_current_list_to_cqt)
        action_layout.addWidget(export_cbt_btn)
        
        action_layout.addStretch()
        search_layout.addWidget(action_container)
        
        list_questions_layout.addLayout(search_layout)
        
        # Create a simple scroll area for 2-column card grid (not accordion)
        self.list_question_card_view = QScrollArea()
        self.list_question_card_view.setWidgetResizable(True)
        self.list_question_card_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_question_card_view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.list_question_card_view.setStyleSheet("""
            QScrollArea {
                border: 1px solid #e2e8f0;
                background-color: #ffffff;
            }
        """)
        list_questions_layout.addWidget(self.list_question_card_view)

        # Overlay shown while loading a large list
        self.list_loading_overlay = QLabel("Loading list…", self.list_question_card_view.viewport())
        self.list_loading_overlay.setAlignment(Qt.AlignCenter)
        self.list_loading_overlay.setStyleSheet(
            """
            QLabel {
                background-color: rgba(15, 23, 42, 0.72);
                color: #e2e8f0;
                font-weight: 700;
                border-radius: 8px;
                padding: 12px;
            }
            """
        )
        self.list_loading_overlay.hide()
        
        lists_split.addWidget(list_questions_card)

        self.content_stack.addWidget(lists_page)

    def _create_import_page(self):
        """Create Data Import page (index 5)."""
        import_page = QWidget()
        import_layout = QVBoxLayout(import_page)

        import_form_card = self._create_card()
        import_form_layout = QVBoxLayout(import_form_card)
        self.input_edit = QLineEdit()
        self.input_edit.editingFinished.connect(self.refresh_file_list)
        input_row = QHBoxLayout()
        input_row.addWidget(self._create_label("Input folder"))
        input_row.addWidget(self.input_edit)
        browse_input = QPushButton("Browse")
        browse_input.clicked.connect(self.select_input_folder)
        input_row.addWidget(browse_input)
        import_form_layout.addLayout(input_row)

        control_layout = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh Files")
        self.refresh_button.clicked.connect(self.refresh_file_list)
        self.start_button = QPushButton("Start Watching")
        self.start_button.clicked.connect(self.start_watching)
        self.stop_button = QPushButton("Stop Watching")
        self.stop_button.clicked.connect(self.stop_watching)
        self.clipboard_import_button = QPushButton("Import TSV from Clipboard")
        self.clipboard_import_button.setToolTip("Paste TSV text from the clipboard and import it directly")
        self.clipboard_import_button.clicked.connect(self.import_tsv_from_clipboard)
        control_layout.addWidget(self.refresh_button)
        control_layout.addWidget(self.start_button)
        control_layout.addWidget(self.stop_button)
        control_layout.addWidget(self.clipboard_import_button)
        control_layout.addStretch()
        import_form_layout.addLayout(control_layout)
        import_layout.addWidget(import_form_card)

        clipboard_card = self._create_card()
        clipboard_layout = QVBoxLayout(clipboard_card)
        clipboard_layout.addWidget(self._create_label("Clipboard TSV (review before import)"))

        clipboard_btn_row = QHBoxLayout()
        self.clipboard_paste_button = QPushButton("Paste Clipboard")
        self.clipboard_paste_button.clicked.connect(self.paste_clipboard_to_textarea)
        self.clipboard_clear_button = QPushButton("Clear")
        self.clipboard_clear_button.clicked.connect(self.clear_clipboard_textarea)
        self.clipboard_import_text_button = QPushButton("Import Text Below")
        self.clipboard_import_text_button.clicked.connect(self.import_tsv_from_textarea)
        clipboard_btn_row.addWidget(self.clipboard_paste_button)
        clipboard_btn_row.addWidget(self.clipboard_clear_button)
        clipboard_btn_row.addWidget(self.clipboard_import_text_button)
        clipboard_btn_row.addStretch()
        clipboard_layout.addLayout(clipboard_btn_row)

        self.clipboard_text_edit = QPlainTextEdit()
        self.clipboard_text_edit.setPlaceholderText("Paste TSV content here to review before importing.")
        self.clipboard_text_edit.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.clipboard_text_edit.setMinimumHeight(180)
        self.clipboard_text_edit.setStyleSheet("font-family: Consolas, 'Courier New', monospace; font-size: 12px;")
        clipboard_layout.addWidget(self.clipboard_text_edit)

        import_layout.addWidget(clipboard_card)

        status_card = self._create_card()
        status_layout = QVBoxLayout(status_card)
        status_layout.addWidget(self._create_label("Upload Status"))
        self.file_table = QTableWidget(0, 3)
        self.file_table.setHorizontalHeaderLabels(["File", "Status", "Message"])
        self.file_table.horizontalHeader().setStretchLastSection(True)
        self.file_table.verticalHeader().setVisible(False)
        self.file_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.file_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.file_table.cellDoubleClicked.connect(self.on_file_double_clicked)
        status_layout.addWidget(self.file_table)
        import_layout.addWidget(status_card)

        self.content_stack.addWidget(import_page)

    def _create_question_set_grouping_page(self):
        """Create Question Set Grouping page (index 5)."""
        grouping_page = QWidget()
        grouping_layout = QVBoxLayout(grouping_page)
        grouping_layout.setContentsMargins(0, 0, 0, 0)
        
        # Initialize the Question Set Group Service (DB-backed)
        self.question_set_group_service = QuestionSetGroupService(db_service=self.db_service)
        
        # Create the Question Set Grouping View
        self.question_set_grouping_view = QuestionSetGroupingView()
        self.question_set_grouping_view.set_group_service(self.question_set_group_service)
        self.question_set_grouping_view.question_set_moved.connect(self._on_question_set_moved)
        
        grouping_layout.addWidget(self.question_set_grouping_view, 1)
        
        self.content_stack.addWidget(grouping_page)
    
    def _on_question_set_moved(self, qs_name: str, from_group: str, to_group: str):
        """Handle when a question set is moved between groups."""
        # Mark groupings dirty and refresh immediately if on the Question List tab
        self.question_set_groups_dirty = True
        if self.content_stack.currentIndex() == 2:
            self._refresh_question_tab_with_loading()
            self.question_set_groups_dirty = False

    def _create_jee_page(self):
        """Create JEE Main Papers page (index 7)."""
        jee_page = QWidget()
        jee_layout = QVBoxLayout(jee_page)
        jee_layout.setSpacing(8)
        jee_layout.setContentsMargins(10, 10, 10, 10)
        label_style = "color: #0f172a; font-weight: 600;"
        
        # Compact controls in single row
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(10)
        
        # File selection
        file_label = QLabel("File:")
        file_label.setStyleSheet(label_style)
        file_label.setMaximumWidth(35)
        controls_layout.addWidget(file_label)
        
        self.jee_file_edit = QLineEdit()
        self.jee_file_edit.setReadOnly(True)
        self.jee_file_edit.setMaximumHeight(26)
        controls_layout.addWidget(self.jee_file_edit, 1)  # Stretch factor 1
        
        browse_jee_btn = QPushButton("Browse")
        browse_jee_btn.setMaximumHeight(26)
        browse_jee_btn.setMaximumWidth(75)
        browse_jee_btn.clicked.connect(self.select_jee_db_file)
        controls_layout.addWidget(browse_jee_btn)
        
        # Spacer
        controls_layout.addSpacing(20)
        
        # Subject dropdown
        subject_label = QLabel("Subject:")
        subject_label.setStyleSheet(label_style)
        subject_label.setMaximumWidth(50)
        controls_layout.addWidget(subject_label)
        
        self.jee_subject_combo = QComboBox()
        self.jee_subject_combo.setMinimumWidth(180)
        self.jee_subject_combo.setMaximumWidth(250)
        self.jee_subject_combo.setMaximumHeight(26)
        self.jee_subject_combo.currentTextChanged.connect(self.update_jee_tables)
        controls_layout.addWidget(self.jee_subject_combo)
        
        jee_layout.addLayout(controls_layout)
        
        # Split view: Chapters table on left, Questions table on right
        jee_splitter = QSplitter(Qt.Horizontal)
        
        # Left side - Chapters table
        chapters_widget = QWidget()
        chapters_layout = QVBoxLayout(chapters_widget)
        chapters_layout.setContentsMargins(0, 0, 0, 0)
        chapters_layout.setSpacing(4)
        
        chapters_header = QLabel("Chapters (by Question Count)")
        chapters_header.setStyleSheet("font-weight: bold; padding: 4px; color: #0f172a;")
        chapters_layout.addWidget(chapters_header)
        
        self.jee_chapters_table = QTableWidget(0, 2)
        self.jee_chapters_table.setHorizontalHeaderLabels(["Chapter", "Count"])
        self.jee_chapters_table.horizontalHeader().setStretchLastSection(False)
        self.jee_chapters_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.jee_chapters_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.jee_chapters_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.jee_chapters_table.setSelectionMode(QTableWidget.SingleSelection)
        self.jee_chapters_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.jee_chapters_table.setAlternatingRowColors(True)
        self.jee_chapters_table.itemSelectionChanged.connect(self.on_jee_chapter_selected)
        chapters_layout.addWidget(self.jee_chapters_table)
        
        jee_splitter.addWidget(chapters_widget)
        
        # Right side - Questions table
        questions_widget = QWidget()
        questions_layout = QVBoxLayout(questions_widget)
        questions_layout.setContentsMargins(0, 0, 0, 0)
        questions_layout.setSpacing(4)
        
        self.jee_questions_label = QLabel("Select a chapter to view questions")
        self.jee_questions_label.setStyleSheet("font-weight: bold; padding: 4px; color: #0f172a;")
        questions_layout.addWidget(self.jee_questions_label)
        
        self.jee_questions_table = QTableWidget(0, 0)
        self.jee_questions_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.jee_questions_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.jee_questions_table.setAlternatingRowColors(True)
        self.jee_questions_table.horizontalHeader().setStretchLastSection(True)
        questions_layout.addWidget(self.jee_questions_table)
        
        jee_splitter.addWidget(questions_widget)
        
        jee_splitter.setStretchFactor(0, 1)
        jee_splitter.setStretchFactor(1, 2)
        jee_splitter.setSizes([300, 600])
        
        jee_layout.addWidget(jee_splitter, 1)
        
        self.content_stack.addWidget(jee_page)

    # ------------------------------------------------------------------
    # Exams page (CQT imports)
    # ------------------------------------------------------------------
    def _create_exams_page(self):
        """Create Exams page (index 8)."""
        exams_page = QWidget()
        layout = QHBoxLayout(exams_page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        self.current_exam_id: int | None = None

        # Left: exam list + import
        left_card = self._create_card()
        left_layout = QVBoxLayout(left_card)
        left_layout.setSpacing(8)

        btn_row = QHBoxLayout()
        import_btn = QPushButton()
        import_btn.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        import_btn.setToolTip("Import Exam (.cqt)")
        import_btn.setFixedSize(QSize(32, 28))
        import_btn.clicked.connect(self._import_exam_from_cqt)
        refresh_btn = QPushButton()
        refresh_btn.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        refresh_btn.setToolTip("Refresh")
        refresh_btn.setFixedSize(QSize(32, 28))
        refresh_btn.clicked.connect(self._load_exam_list)
        delete_btn = QPushButton()
        delete_btn.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        delete_btn.setToolTip("Delete selected exam")
        delete_btn.setFixedSize(QSize(32, 28))
        delete_btn.clicked.connect(self._delete_selected_exam)
        btn_row.addWidget(import_btn)
        btn_row.addWidget(refresh_btn)
        btn_row.addWidget(delete_btn)
        btn_row.addStretch()
        left_layout.addLayout(btn_row)

        self.exam_list_widget = QListWidget()
        self.exam_list_widget.itemSelectionChanged.connect(self._on_exam_selected)
        left_layout.addWidget(self.exam_list_widget, 1)

        # Right: details
        right_card = self._create_card()
        right_layout = QVBoxLayout(right_card)
        right_layout.setSpacing(8)

        self.exam_header_label = self._create_label("Select an exam to view details")
        right_layout.addWidget(self.exam_header_label)

        self.exam_stats_label = QLabel("")
        self.exam_stats_label.setStyleSheet("color: #475569; padding: 2px 0;")
        right_layout.addWidget(self.exam_stats_label)

        self.exam_summary_label = QLabel("")
        self.exam_summary_label.setStyleSheet("color: #475569; padding: 2px 0;")
        self.exam_summary_label.setWordWrap(True)
        right_layout.addWidget(self.exam_summary_label)

        # Question detail scroll
        self.exam_detail_container = QWidget()
        self.exam_detail_layout = QVBoxLayout(self.exam_detail_container)
        self.exam_detail_layout.setContentsMargins(0, 0, 0, 0)
        self.exam_detail_layout.setSpacing(10)
        self.exam_detail_layout.addStretch()

        detail_scroll = QScrollArea()
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setWidget(self.exam_detail_container)
        right_layout.addWidget(detail_scroll, 1)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_card)
        splitter.addWidget(right_card)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 680])

        layout.addWidget(splitter)

        self.content_stack.addWidget(exams_page)

    # ------------------------------------------------------------------
    # Data Quality page
    # ------------------------------------------------------------------
    def _create_data_quality_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        card = self._create_card()
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(8)

        header_row = QHBoxLayout()
        header_row.addWidget(self._create_label("Data Quality - Missing Fields"))
        refresh_btn = QPushButton()
        refresh_btn.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        refresh_btn.setToolTip("Refresh")
        refresh_btn.setFixedSize(QSize(32, 28))
        refresh_btn.clicked.connect(self._load_data_quality_table)
        header_row.addStretch()
        header_row.addWidget(refresh_btn)
        card_layout.addLayout(header_row)

        self.data_quality_table = QTableWidget(0, 7)
        self.data_quality_table.setHorizontalHeaderLabels(["ID", "Q#", "Page", "Set", "Magazine", "Missing Fields", "Edit"])
        self.data_quality_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.data_quality_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.data_quality_table.horizontalHeader().setStretchLastSection(True)
        card_layout.addWidget(self.data_quality_table)

        layout.addWidget(card, 1)
        self.content_stack.addWidget(page)

    def _load_data_quality_table(self):
        if not self.db_service:
            return
        rows = self.db_service.get_questions_with_missing(self.data_quality_required)
        table = self.data_quality_table
        table.setRowCount(len(rows))
        for r_idx, row in enumerate(rows):
            qid = row.get("id")
            qno = row.get("question_number", "")
            page = row.get("page_range", "")
            qset = row.get("question_set_name", "")
            mag = row.get("magazine", "")
            missing = ", ".join(row.get("missing", []))
            for c_idx, val in enumerate([qid, qno, page, qset, mag, missing]):
                item = QTableWidgetItem(str(val) if val is not None else "")
                table.setItem(r_idx, c_idx, item)
            edit_btn = QPushButton("Edit")
            edit_btn.setToolTip("Edit question")
            edit_btn.clicked.connect(lambda _, id_val=qid: self._edit_data_quality_question(id_val))
            table.setCellWidget(r_idx, 6, edit_btn)
        table.resizeColumnsToContents()

    def _edit_data_quality_question(self, question_id: int):
        if not self.db_service:
            return
        try:
            q = self.db_service.get_question_by_id(int(question_id))
        except Exception as exc:
            QMessageBox.warning(self, "Load Failed", f"Could not load question:\n{exc}")
            return
        if not q:
            QMessageBox.information(self, "Not Found", "Question not found.")
            return
        q_data = {
            "qno": q.get("question_number", ""),
            "page": q.get("page_range", ""),
            "question_set_name": q.get("question_set_name", ""),
            "magazine": q.get("magazine", ""),
            "text": q.get("question_text", ""),
            "answer_text": q.get("answer_text", ""),
            "chapter": q.get("chapter", ""),
            "high_level_chapter": q.get("high_level_chapter", ""),
        }
        lookups = self.db_service.get_unique_values(
            ["question_set_name", "magazine", "chapter", "high_level_chapter"]
        )
        dlg = QuestionEditDialog(q_data, self, lookups=lookups)
        if dlg.exec() != QDialog.Accepted:
            return
        updates = dlg.get_updates()
        try:
            self.db_service.update_question_fields(int(question_id), updates)
        except Exception as exc:
            QMessageBox.warning(self, "Save Failed", f"Could not save changes:\n{exc}")
            return
        self._load_data_quality_table()

    def _import_exam_from_cqt(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open CBT Package", "", "CBT Package (*.cqt)")
        if not file_path:
            return
        pwd, ok = QInputDialog.getText(self, "Package Password", "Enter package password:", QLineEdit.Password)
        if not ok or not pwd:
            return
        try:
            summary = self.db_service.import_exam_from_cqt(file_path, pwd)
            self.statusBar().showMessage(f"Imported exam: {Path(file_path).name}")
        except Exception as exc:
            QMessageBox.critical(self, "Import Failed", f"Could not import exam:\n{exc}")
            return
        self._load_exam_list()
        QMessageBox.information(
            self,
            "Import Complete",
            f"Imported exam with {summary.get('total',0)} questions.\nCorrect: {summary.get('correct',0)} | Wrong: {summary.get('wrong',0)} | Score: {summary.get('score',0)}",
        )

    def _load_exam_list(self):
        if not hasattr(self, "exam_list_widget"):
            return
        self.exam_list_widget.clear()
        try:
            self.exams_data = self.db_service.list_exams()
        except Exception as exc:
            QMessageBox.warning(self, "Exams Unavailable", f"Could not load exams:\n{exc}")
            self.exams_data = []
            return
        for exam in self.exams_data:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, exam)
            widget = self._build_exam_list_item_widget(exam)
            item.setSizeHint(widget.sizeHint())
            self.exam_list_widget.addItem(item)
            self.exam_list_widget.setItemWidget(item, widget)
        if self.exam_list_widget.count() > 0:
            self.exam_list_widget.setCurrentRow(0)

    def _format_exam_list_text(self, exam: Dict[str, Any]) -> str:
        name = exam.get("name") or "Exam"
        imported = exam.get("imported_at") or ""
        score = exam.get("score") if exam.get("score") is not None else ""
        return f"{name}  ({imported})  Score: {score}"

    def _build_exam_list_item_widget(self, exam: Dict[str, Any]) -> QWidget:
        text = self._format_exam_list_text(exam)
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(6)

        label = QLabel(text)
        label.setStyleSheet("color: #0f172a;")
        layout.addWidget(label, 1)

        container.setLayout(layout)
        return container

    def _on_exam_selected(self):
        items = self.exam_list_widget.selectedItems()
        if not items:
            return
        exam = items[0].data(Qt.UserRole) or {}
        self._render_exam_detail(exam)

    def _render_exam_detail(self, exam: Dict[str, Any]) -> None:
        exam_id = exam.get("id")
        if exam_id is None:
            return
        self.current_exam_id = int(exam_id)
        header = exam.get("name") or "Exam"
        list_name = exam.get("list_name") or ""
        imported = exam.get("imported_at") or ""
        evaluated_at = exam.get("evaluated_at") or "Not evaluated"
        self.exam_header_label.setText(f"{header} | {list_name}")
        stats = f"Imported: {imported} | Evaluated: {evaluated_at}"
        self.exam_stats_label.setText(stats)
        summary = f"Questions: {exam.get('total_questions',0)} | Answered: {exam.get('answered',0)} | Correct: {exam.get('correct',0)} | Wrong: {exam.get('wrong',0)} | Score: {exam.get('score',0)} | Percent: {round(exam.get('percent') or 0,2)}%"
        self.exam_summary_label.setText(summary)
        try:
            questions = self.db_service.get_exam_questions(int(exam_id))
        except Exception as exc:
            QMessageBox.warning(self, "Load Failed", f"Could not load exam questions:\n{exc}")
            return
        evaluated = bool(exam.get("evaluated"))
        self._render_exam_questions(questions, evaluated)

    def _refresh_current_exam_view(self):
        if not self.current_exam_id:
            return
        try:
            exam = self.db_service.get_exam_by_id(int(self.current_exam_id))
            if not exam:
                return
        except Exception as exc:
            QMessageBox.warning(self, "Load Failed", f"Could not refresh exam:\n{exc}")
            return
        self._render_exam_detail(exam)
        self._update_exam_list_item(exam)

    def _update_exam_list_item(self, exam: Dict[str, Any]) -> None:
        if not hasattr(self, "exam_list_widget"):
            return
        for i in range(self.exam_list_widget.count()):
            item = self.exam_list_widget.item(i)
            data = item.data(Qt.UserRole) or {}
            if data.get("id") == exam.get("id"):
                item.setData(Qt.UserRole, exam)
                widget = self._build_exam_list_item_widget(exam)
                item.setSizeHint(widget.sizeHint())
                self.exam_list_widget.setItemWidget(item, widget)
                break

    def _delete_selected_exam(self):
        items = self.exam_list_widget.selectedItems()
        if not items:
            QMessageBox.information(self, "No Selection", "Please select an exam to delete.")
            return
        exam = items[0].data(Qt.UserRole) or {}
        exam_id = exam.get("id")
        if exam_id is None:
            return
        confirm = QMessageBox.question(
            self,
            "Delete Exam",
            f"Delete exam '{exam.get('name') or 'Exam'}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            self.db_service.delete_exam(int(exam_id))
        except Exception as exc:
            QMessageBox.warning(self, "Delete Failed", f"Could not delete exam:\n{exc}")
            return
        self._load_exam_list()
        self._clear_layout(self.exam_detail_layout)
        self.exam_header_label.setText("Select an exam to view details")
        self.exam_stats_label.setText("")
        self.exam_summary_label.setText("")
        self.current_exam_id = None

    def _render_exam_questions(self, questions: List[Dict[str, Any]], evaluated: bool):
        self._clear_layout(self.exam_detail_layout)
        for idx, row in enumerate(questions, start=1):
            widget = self._build_exam_question_widget(row, idx, evaluated)
            self.exam_detail_layout.addWidget(widget)
        self.exam_detail_layout.addStretch()

    def _apply_question_evaluation(self, q_index: int, status: str, comment: str):
        if not self.current_exam_id:
            QMessageBox.warning(self, "No Exam Selected", "Select an exam before updating evaluation.")
            return
        if not comment.strip():
            QMessageBox.warning(self, "Comment Required", "Please enter a comment for this evaluation change.")
            return
        try:
            self.db_service.update_exam_question_evaluation(int(self.current_exam_id), q_index, status, comment.strip())
        except Exception as exc:
            QMessageBox.warning(self, "Update Failed", f"Could not update evaluation:\n{exc}")
            return
        self._refresh_current_exam_view()
    def _build_exam_question_widget(self, row: Dict[str, Any], display_index: int, evaluated: bool) -> QWidget:
        q = row.get("question", {}) or {}
        resp = row.get("response")
        correct = bool(row.get("correct"))
        answered = bool(row.get("answered"))
        score = row.get("score", 0)

        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        wrapper.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px;")

        marker = "✔" if evaluated and correct else ("✘" if evaluated and answered else "•")
        marker_color = "#16a34a" if evaluated and correct else ("#dc2626" if evaluated and answered else "#94a3b8")
        header = QLabel(f"{marker}  Q{display_index} | P{q.get('page','?')} | {q.get('question_set_name','')} | {q.get('magazine','')}")
        header.setStyleSheet(f"color: {marker_color}; font-weight: 700;")
        layout.addWidget(header)

        text_lbl = QLabel(q.get("text", ""))
        text_lbl.setWordWrap(True)
        text_lbl.setStyleSheet("color: #0f172a;")
        layout.addWidget(text_lbl)

        # Question images
        for img in q.get("question_images", []):
            data = base64.b64decode(img.get("data", ""))
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            if not pixmap.isNull():
                pixmap = pixmap.scaledToWidth(420, Qt.SmoothTransformation)
            img_lbl = QLabel()
            img_lbl.setPixmap(pixmap)
            img_lbl.setStyleSheet("border: none;")
            layout.addWidget(img_lbl)

        # Answer images (only show if evaluated)
        if evaluated and q.get("answer_images"):
            divider = QFrame()
            divider.setFrameShape(QFrame.HLine)
            divider.setStyleSheet("color: #cbd5e1;")
            layout.addWidget(divider)
            ans_title = QLabel("Answer Images")
            ans_title.setStyleSheet("font-weight: 600; color: #334155;")
            layout.addWidget(ans_title)
            for img in q.get("answer_images", []):
                data = base64.b64decode(img.get("data", ""))
                pixmap = QPixmap()
                pixmap.loadFromData(data)
                if not pixmap.isNull():
                    pixmap = pixmap.scaledToWidth(420, Qt.SmoothTransformation)
                img_lbl = QLabel()
                img_lbl.setPixmap(pixmap)
                img_lbl.setStyleSheet("border: none;")
                layout.addWidget(img_lbl)

        # Response / result
        qtype = q.get("question_type", "mcq_single") or "mcq_single"
        if qtype == "numerical":
            resp_text = str(resp).strip() if resp is not None else "-"
        else:
            if isinstance(resp, str):
                resp_list = [resp] if resp else []
            else:
                resp_list = resp or []
            resp_text = ", ".join(resp_list) if resp_list else "-"
        resp_lbl = QLabel(f"Response: {resp_text}")
        resp_lbl.setStyleSheet("color: #475569;")
        layout.addWidget(resp_lbl)

        if evaluated:
            result_text = "Correct" if correct else ("Incorrect" if answered else "Unanswered")
            result_color = "#16a34a" if correct else ("#dc2626" if answered else "#94a3b8")
            result_lbl = QLabel(f"Result: {result_text} | Score: {score}")
            result_lbl.setStyleSheet(f"color: {result_color}; font-weight: 600;")
            layout.addWidget(result_lbl)

        # Evaluation override controls
        eval_status = row.get("eval_status") or ("correct" if correct else ("incorrect" if answered else "unanswered"))
        eval_comment = row.get("eval_comment") or ""

        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        status_lbl = QLabel("Evaluation:")
        status_lbl.setStyleSheet("font-weight: 600; color: #0f172a;")
        status_row.addWidget(status_lbl)

        status_combo = QComboBox()
        status_combo.addItem("Correct", "correct")
        status_combo.addItem("Incorrect", "incorrect")
        status_combo.addItem("Unanswered", "unanswered")
        status_combo.setStyleSheet("color: #0f172a;")
        # set current index
        for i in range(status_combo.count()):
            if status_combo.itemData(i) == eval_status:
                status_combo.setCurrentIndex(i)
                break
        status_row.addWidget(status_combo)

        comment_input = QLineEdit()
        comment_input.setPlaceholderText("Enter comment for this change")
        comment_input.setText("")
        comment_input.setStyleSheet("color: #0f172a;")
        status_row.addWidget(comment_input, 1)

        apply_btn = QPushButton()
        apply_btn.setToolTip("Save evaluation and comment")
        apply_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        apply_btn.setFixedSize(QSize(30, 26))
        apply_btn.setEnabled(False)
        status_row.addWidget(apply_btn)
        status_row.addStretch()
        layout.addLayout(status_row)

        comment_lbl = QLabel(f"Last comment: {eval_comment or '-'}")
        comment_lbl.setStyleSheet("color: #0f172a;")
        layout.addWidget(comment_lbl)

        def _toggle_apply():
            apply_btn.setEnabled(bool(comment_input.text().strip()))

        comment_input.textChanged.connect(_toggle_apply)
        apply_btn.clicked.connect(
            lambda: self._apply_question_evaluation(
                row.get("index", display_index - 1),
                status_combo.currentData(),
                comment_input.text(),
            )
        )

        return wrapper

    def _apply_palette(self) -> None:
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor("#f4f5f9"))
        palette.setColor(QPalette.Base, QColor("#ffffff"))
        palette.setColor(QPalette.Text, QColor("#0f172a"))
        palette.setColor(QPalette.Button, QColor("#2563eb"))
        palette.setColor(QPalette.ButtonText, QColor("#ffffff"))
        self.setPalette(palette)
        self.setStyleSheet(
            """
            QWidget#card {
                background-color: #ffffff;
                border-radius: 14px;
                padding: 12px;
            }
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:disabled {
                background-color: #94a3b8;
            }
            QLabel#headerLabel {
                font-weight: 600;
                color: #0f172a;
            }
            QLabel#infoLabel {
                color: #475569;
            }
            QTreeWidget, QTableWidget, QListWidget {
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                background-color: #ffffff;
                color: #0f172a;
                alternate-background-color: #f8fafc;
            }
            QTreeWidget::item:selected, QTableWidget::item:selected, QListWidget::item:selected {
                background-color: #d0e2ff;
                color: #0f172a;
            }
            QTextEdit#logView {
                background-color: #0f172a;
                color: #e2e8f0;
                border-radius: 8px;
                padding: 8px;
                font-family: Consolas, 'Courier New', monospace;
            }
            QTabWidget::pane {
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                background-color: #ffffff;
            }
            QTabBar::tab {
                background-color: #f1f5f9;
                color: #475569;
                border: 1px solid #e2e8f0;
                border-bottom: none;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background-color: #ffffff;
                color: #0f172a;
                border-bottom: 2px solid #2563eb;
                font-weight: 600;
            }
            QTabBar::tab:hover:!selected {
                background-color: #e0e7ff;
                color: #1e40af;
            }
            """
        )

    def select_db_file(self) -> None:
        """Browse for a SQLite database file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select SQLite Database",
            str(self.current_db_path),
            "SQLite DB (*.db *.sqlite);;All files (*.*)",
        )
        if not file_path:
            return
        self.current_db_path = Path(file_path)
        self.db_path_edit.setText(file_path)
        self.db_service.set_db_path(self.current_db_path)
        self._save_last_selection()

    def load_subject_from_db(self) -> None:
        """Load questions for the selected subject from SQLite."""
        db_path = Path(self.db_path_edit.text().strip() or DEFAULT_DB_PATH)
        subject = self.subject_combo.currentText() if hasattr(self, "subject_combo") else ""
        if not subject:
            QMessageBox.warning(self, "Subject Required", "Please select a subject.")
            return
        if not db_path.is_file():
            QMessageBox.critical(self, "Database Missing", f"Database not found:\n{db_path}")
            return
        self.current_db_path = db_path
        self.db_service.set_db_path(db_path)
        self.current_subject = subject
        try:
            df = self.db_service.fetch_questions_df(subject)
        except Exception as exc:
            QMessageBox.critical(self, "Load Failed", f"Unable to load questions: {exc}")
            return
        self.use_database = True
        self.current_Database_path = None
        self._load_dataframe_state(df, f"{subject} from database")

    def _load_dataframe_state(self, df: pd.DataFrame, source_label: str) -> None:
        """Populate UI from a DataFrame (DB-backed)."""
        self._clear_all_question_data()
        self.Database_df = df
        self._save_last_selection()

        if df is None or df.empty:
            self.set_status("No questions found in database.", "error")
            self.row_count_label.setText("Total rows: 0")
            self._set_magazine_summary("Magazines: 0", "Tracked editions: 0")
            return

        row_count = self._compute_row_count_from_df(df)
        magazine_details, warnings = self._collect_magazine_details(df)
        detected_magazine = self._detect_magazine_name(magazine_details)
        grouping_key = MAGAZINE_GROUPING_MAP.get(detected_magazine, "PhysicsChapterGrouping")
        self.current_magazine_name = detected_magazine
        self.canonical_chapters = self._load_canonical_chapters(grouping_key)
        self.chapter_groups = self._load_chapter_grouping(grouping_key)
        self.current_magazine_display_name = self._resolve_magazine_display_name(
            magazine_details, detected_magazine
        )

        chapter_data, qa_warnings, question_col, raw_chapter_inputs = self._collect_question_analysis_data(df)
        warnings.extend(qa_warnings)
        self.high_level_column_index = question_col
        self.mag_page_ranges = self._compute_page_ranges_for_editions(df, magazine_details)

        self.row_count_label.setText(f"Total rows: {row_count}")
        total_editions = sum(len(entry["editions"]) for entry in magazine_details)
        mag_display = self.current_magazine_display_name or (
            self.current_magazine_name.title() if self.current_magazine_name else "Unknown"
        )
        self._set_magazine_summary(
            f"Magazine: {mag_display}",
            f"Tracked editions: {total_editions}",
        )

        self._populate_magazine_heatmap(magazine_details, self.mag_page_ranges)
        self._populate_question_sets([])
        missing_qset_warning = next(
            (msg for msg in warnings if "question set" in msg.lower()), None
        )
        if missing_qset_warning:
            label_message = missing_qset_warning
        elif magazine_details:
            label_message = "Select an edition to view question sets."
        else:
            label_message = warnings[0] if warnings else "No magazine editions found."
        self.question_label.setText(label_message)
        self._auto_assign_chapters(raw_chapter_inputs)
        self._populate_chapter_list(chapter_data)
        self._refresh_grouping_ui()

        # Update dashboard
        if hasattr(self, "dashboard_view"):
            self.dashboard_view.update_dashboard_data(
                self.Database_df,
                self.chapter_groups,
                magazine_details=magazine_details,
                mag_display_name=self.current_magazine_display_name,
                mag_page_ranges=self.mag_page_ranges,
            )

        # Update question set grouping view
        if hasattr(self, "question_set_grouping_view") and hasattr(self, "Database_df"):
            question_sets = self._extract_unique_question_sets(self.Database_df)
            qs_min_pages = self._extract_question_set_min_pages(self.Database_df)
            qs_mag_map = self._extract_question_set_magazines(self.Database_df)
            self.question_set_grouping_view.update_from_workbook(
                question_sets,
                qs_min_pages,
                qs_mag_map,
            )

        for warning in warnings:
            self.log(warning)

        self.set_status(f"Loaded {source_label}", "success")

    def _create_card(self) -> QWidget:
        card = QWidget()
        card.setObjectName("card")
        return card

    def _create_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("headerLabel")
        return label

    def toggle_log_visibility(self, checked: bool) -> None:
        self.log_card.setVisible(checked)
        self.log_toggle.setText("Hide Log" if checked else "Show Log")
    
    def _animate_status(self) -> None:
        """Animate the status spinner icon."""
        spinner_frames = ["", "", "", "", "", "", "", "", "", ""]
        self.status_animation_frame = (self.status_animation_frame + 1) % len(spinner_frames)
        
        # Update the current status text with new spinner frame
        if hasattr(self, "_current_status_text") and hasattr(self, "_current_status_type"):
            if self._current_status_type in ("loading", "importing"):
                icon = spinner_frames[self.status_animation_frame]
                self.status_label.setText(f"{icon} {self._current_status_text}")
    
    def set_status(self, message: str, status_type: str = "info") -> None:
        """Set status bar message with appropriate icon and styling.
        
        Args:
            message: Status message to display
            status_type: Type of status - 'loading', 'importing', 'success', 'error', 'info'
        """
        self._current_status_text = message
        self._current_status_type = status_type
        
        # Stop any existing animation
        self.status_animation_timer.stop()
        
        if status_type == "loading":
            # Animated spinner for loading
            self.status_animation_timer.start(80)  # Update every 80ms
            icon = ""
            self.status_label.setStyleSheet("""
                QLabel {
                    padding: 8px 16px;
                    background-color: #dbeafe;
                    border-radius: 6px;
                    color: #1e40af;
                    font-size: 13px;
                    font-weight: 500;
                }
            """)
        elif status_type == "importing":
            # Animated spinner for importing
            self.status_animation_timer.start(80)
            icon = ""
            self.status_label.setStyleSheet("""
                QLabel {
                    padding: 8px 16px;
                    background-color: #fef3c7;
                    border-radius: 6px;
                    color: #92400e;
                    font-size: 13px;
                    font-weight: 500;
                }
            """)
        elif status_type == "success":
            icon = ""
            self.status_label.setStyleSheet("""
                QLabel {
                    padding: 8px 16px;
                    background-color: #d1fae5;
                    border-radius: 6px;
                    color: #065f46;
                    font-size: 13px;
                    font-weight: 500;
                }
            """)
        elif status_type == "error":
            icon = ""
            self.status_label.setStyleSheet("""
                QLabel {
                    padding: 8px 16px;
                    background-color: #fee2e2;
                    border-radius: 6px;
                    color: #991b1b;
                    font-size: 13px;
                    font-weight: 500;
                }
            """)
        else:  # info
            icon = ""
            self.status_label.setStyleSheet("""
                QLabel {
                    padding: 8px 16px;
                    background-color: #f1f5f9;
                    border-radius: 6px;
                    color: #475569;
                    font-size: 13px;
                    font-weight: 500;
                }
            """)
        
        self.status_label.setText(f"{icon} {message}")
        self.status_label.setVisible(True)
    
    def clear_status(self) -> None:
        """Clear status message but keep label visible to maintain layout."""
        self.status_animation_timer.stop()
        self.status_label.setText("")  # Clear text but keep label visible
        self._current_status_text = ""
        self._current_status_type = ""

    def _backup_current_database(self, log_result: bool = False) -> None:
        """Create a timestamped backup of the active DB, keeping the newest 10 copies."""
        if not self.db_service:
            return
        try:
            backup_path = self.db_service.backup_database()
        except Exception as exc:
            if log_result:
                self.log(f"Database backup skipped: {exc}")
            return

        if log_result and backup_path:
            self.log(f"Database backup created: {backup_path}")

    def _backup_jee_database(self, db_path: Path, max_backups: int = 10, log_result: bool = False) -> None:
        """Backup the JEE DB unless the latest backup already matches the file's mtime."""
        db_path = Path(db_path)
        if not db_path.is_file():
            return
        try:
            src_mtime = db_path.stat().st_mtime
            backup_dir = db_path.parent / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            pattern = f"{db_path.stem}-*{db_path.suffix}"
            backups = sorted(
                (p for p in backup_dir.glob(pattern) if p.is_file()),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if backups and abs(backups[0].stat().st_mtime - src_mtime) < 1e-6:
                if log_result:
                    self.log("JEE DB backup skipped (no change since last backup)")
                return

            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_path = backup_dir / f"{db_path.stem}-{timestamp}{db_path.suffix}"
            shutil.copy2(db_path, backup_path)
            if log_result:
                self.log(f"JEE DB backup created: {backup_path}")

            backups = sorted(
                (p for p in backup_dir.glob(pattern) if p.is_file()),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            for stale in backups[max_backups:]:
                stale.unlink(missing_ok=True)
        except Exception as exc:
            if log_result:
                self.log(f"JEE DB backup skipped: {exc}")

    def _load_last_selection(self) -> None:
        if not LAST_SELECTION_FILE.exists():
            return
        try:
            data = json.loads(LAST_SELECTION_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        input_folder = data.get("input_folder", "")
        if input_folder:
            self.input_edit.setText(input_folder)

        db_path = data.get("db_path", "")
        if db_path:
            self.db_path_edit.setText(db_path)
            self.current_db_path = Path(db_path)
            self.db_service.set_db_path(self.current_db_path)
        subject = data.get("subject", "")
        if subject and hasattr(self, "subject_combo"):
            idx = self.subject_combo.findText(subject, Qt.MatchFixedString)
            if idx >= 0:
                self.subject_combo.setCurrentIndex(idx)
                self.current_subject = subject
        
        # If both paths are valid on startup, auto-start watching after initial load
        if db_path and input_folder and Path(db_path).is_file() and Path(input_folder).is_dir():
            self.pending_auto_watch = True
        jee_papers_file = data.get("jee_papers_file", "")
        if jee_papers_file and Path(jee_papers_file).exists():
            self.jee_papers_file = Path(jee_papers_file)
            self.jee_file_edit.setText(jee_papers_file)
            self.load_jee_papers_data()

    def _save_last_selection(self) -> None:
        input_folder = self.input_edit.text().strip()
        payload = {
            "input_folder": input_folder if input_folder else "",
            "jee_papers_file": str(self.jee_papers_file) if self.jee_papers_file else "",
            "db_path": self.db_path_edit.text().strip() if hasattr(self, "db_path_edit") else "",
            "subject": self.subject_combo.currentText() if hasattr(self, "subject_combo") else "",
        }
        LAST_SELECTION_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _load_group_tags(self) -> None:
        """Load group tags from the database (fallback to tags.cfg)."""
        data = {}
        if self.db_service:
            data = self.db_service.load_config("TagsConfig")
        self.group_tags = data.get("group_tags", {})
        self.question_set_group_tags = data.get("question_set_group_tags", {})
        self.tag_colors = data.get("tag_colors", {})

    def _save_group_tags(self) -> None:
        """Save group tags to the database (and file for compatibility)."""
        payload = {
            "group_tags": self.group_tags,
            "question_set_group_tags": self.question_set_group_tags,
            "tag_colors": self.tag_colors,
        }
        if self.db_service:
            self.db_service.save_config("TagsConfig", payload)

    def _get_or_assign_tag_color(self, tag: str) -> str:
        """Get existing color for tag or assign a new one."""
        if tag not in self.tag_colors:
            # Cycle through available colors
            color_index = len(self.tag_colors) % len(self.available_tag_colors)
            self.tag_colors[tag] = self.available_tag_colors[color_index]
        return self.tag_colors[tag]

    def _load_canonical_chapters(self, config_key: str) -> list[str]:
        """Load canonical chapters from DB config."""
        if self.db_service:
            data = self.db_service.load_config(config_key)
            if data:
                return data.get("canonical_order", [])
        return []

    def _load_chapter_grouping(self, config_key: str) -> dict[str, list[str]]:
        """Load chapter grouping from DB config."""
        data = {}
        if self.db_service:
            data = self.db_service.load_config(config_key)
        groups = data.get("groups", {}) if data else {}
        for group in self.canonical_chapters:
            groups.setdefault(group, [])
        groups.setdefault("Others", [])
        # Remove duplicates while preserving order
        for key, values in list(groups.items()):
            seen = set()
            unique = []
            for value in values:
                if value not in seen:
                    unique.append(value)
                    seen.add(value)
            groups[key] = unique
        self._rebuild_chapter_lookup(groups)
        return groups

    def _reload_grouping_for_magazine(self, magazine_name: str) -> None:
        """Reload chapter grouping based on magazine name."""
        if magazine_name == self.current_magazine_name:
            return  # Already loaded
        
        grouping_key = MAGAZINE_GROUPING_MAP.get(magazine_name, "PhysicsChapterGrouping")
        self.current_magazine_name = magazine_name
        self.canonical_chapters = self._load_canonical_chapters(grouping_key)
        self.chapter_groups = self._load_chapter_grouping(grouping_key)
        self.log(f"Loaded chapter grouping for: {magazine_name or 'default (Physics)'}")

    def _save_chapter_grouping(self) -> None:
        """Save chapter grouping to the appropriate file based on current magazine."""
        data = {
            "canonical_order": self.canonical_chapters,
            "groups": self.chapter_groups,
        }
        grouping_key = MAGAZINE_GROUPING_MAP.get(self.current_magazine_name, "PhysicsChapterGrouping")
        if self.db_service:
            self.db_service.save_config(grouping_key, data)
        self._rebuild_chapter_lookup(self.chapter_groups)

    def _ordered_groups(self) -> list[str]:
        order = list(self.canonical_chapters)
        if "Others" not in order:
            order.append("Others")
        return order

    def _rebuild_chapter_lookup(self, groups: dict[str, list[str]]) -> None:
        lookup: dict[str, str] = {}
        for group, values in groups.items():
            norm_group = self._normalize_label(group)
            if norm_group:
                lookup[norm_group] = group
            for value in values:
                norm_value = self._normalize_label(value)
                if norm_value and norm_value not in lookup:
                    lookup[norm_value] = group
        self.chapter_lookup = lookup

    def _refresh_grouping_ui(self) -> None:
        if not hasattr(self, "group_list"):
            return
        self.group_list.blockSignals(True)
        self.group_list.clear()
        for group in self._ordered_groups():
            chapters = self.chapter_groups.get(group, [])
            item = QListWidgetItem(f"{group} ({len(chapters)})")
            item.setData(Qt.UserRole, group)
            self.group_list.addItem(item)
        self.group_list.blockSignals(False)
        if hasattr(self, "move_target_combo"):
            self.move_target_combo.clear()
            self.move_target_combo.addItems(self._ordered_groups())
        if hasattr(self, "group_chapter_list"):
            self.group_chapter_list.clear()

    def _select_group_in_ui(self, group: str) -> None:
        if not hasattr(self, "group_list"):
            return
        for row in range(self.group_list.count()):
            item = self.group_list.item(row)
            if (item.data(Qt.UserRole) or item.text()).startswith(group):
                self.group_list.setCurrentRow(row)
                break

    def _setup_timer(self) -> None:
        self.queue_timer = QTimer(self)
        self.queue_timer.setInterval(200)
        self.queue_timer.timeout.connect(self._process_queue)
        self.queue_timer.start()

    def update_row_count(self) -> None:
        # Load data from database only
        self.load_subject_from_db()

    def _set_magazine_summary(self, primary: str, secondary: str) -> None:
        self.mag_summary_label.setText(primary)
        self.mag_missing_label.setText(secondary)

    def _invalidate_Database_cache(self) -> None:
        """Invalidate the Database cache and reload data."""
        self.Database_df = None
        self.load_subject_from_db()
    
    def _clear_all_question_data(self) -> None:
        """Clear all question analysis data and UI elements."""
        # Clear data structures
        self.Database_df = None  # Clear cached DataFrame
        self.chapter_questions.clear()
        self.current_questions.clear()
        self.all_questions.clear()
        self.advanced_query_term = ""
        self.current_magazine_display_name = ""
        
        # Clear UI elements
        self._populate_magazine_heatmap([], {})
        self._populate_question_sets([])
        self._populate_chapter_list({})
        
        # Clear search boxes
        if hasattr(self, "advanced_query_input"):
            self.advanced_query_input.clear()
        if hasattr(self, "advanced_query_error"):
            self.advanced_query_error.clear()
            self.advanced_query_error.setVisible(False)
        if hasattr(self, "mag_tree_search"):
            self.mag_tree_search.clear()

    def _detect_magazine_name(self, details: list[dict]) -> str:
        """Detect magazine name from magazine details."""
        if not details:
            return ""
        # Get the first magazine's display name and normalize it
        display_name = details[0].get("display_name", "")
        normalized = self._normalize_label(display_name)
        # Check against known magazines
        for magazine_key in MAGAZINE_GROUPING_MAP.keys():
            if magazine_key in normalized:
                return magazine_key
        return ""

    def _resolve_magazine_display_name(self, details: list[dict], normalized_key: str) -> str:
        """Return human-friendly magazine display name matching the normalized key."""
        if not normalized_key:
            return ""
        for entry in details:
            display = entry.get("display_name", "")
            if self._normalize_label(display) == normalized_key:
                return display
        return normalized_key.title()
    
    def _extract_unique_question_sets(self, df: pd.DataFrame) -> list[str]:
        """
        Extract unique question set names from Database DataFrame.
        
        Returns:
            List of unique question set names
        """
        if df.empty:
            return []
        
        header_row = [None if pd.isna(col) else str(col) for col in df.columns]
        try:
            question_set_col = _find_question_set_column(header_row)
        except ValueError:
            # No question set column found
            return []
        
        # Extract unique question sets
        question_sets = set()
        if question_set_col is not None:
            question_series = df.iloc[:, question_set_col - 1]
            for value in question_series:
                if pd.notna(value):
                    qs_name = str(value).strip()
                    if qs_name:
                        question_sets.add(qs_name)
        
        return sorted(list(question_sets))

    def _extract_question_set_min_pages(self, df: pd.DataFrame) -> dict[str, float]:
        """
        Build a map of question set -> minimum page number (numeric) across the Database.
        Non-numeric pages are ignored. Missing pages yield no entry.
        """
        result: dict[str, float] = {}
        if df.empty:
            return result

        header_row = [None if pd.isna(col) else str(col) for col in df.columns]
        try:
            question_set_col = _find_question_set_column(header_row)
            page_col = _find_page_column(header_row)
        except ValueError:
            return result  # Required columns not found

        qset_series = df.iloc[:, question_set_col - 1]
        page_series = df.iloc[:, page_col - 1]

        for qset_val, page_val in zip(qset_series, page_series):
            if pd.isna(qset_val) or pd.isna(page_val):
                continue
            qset_name = str(qset_val).strip()
            if not qset_name:
                continue
            try:
                page_num = float(page_val)
            except (ValueError, TypeError):
                continue
            current = result.get(qset_name)
            if current is None or page_num < current:
                result[qset_name] = page_num
        return result

    def _extract_question_set_magazines(self, df: pd.DataFrame) -> dict[str, str]:
        """
        Build a map of question set -> most frequent magazine/edition string.
        """
        result: dict[str, str] = {}
        if df.empty:
            return result

        header_row = [None if pd.isna(col) else str(col) for col in df.columns]
        try:
            question_set_col = _find_question_set_column(header_row)
            magazine_col = _find_magazine_column(header_row)
        except ValueError:
            return result

        qset_series = df.iloc[:, question_set_col - 1]
        magazine_series = df.iloc[:, magazine_col - 1]

        counts: dict[str, dict[str, int]] = {}
        for qset_val, mag_val in zip(qset_series, magazine_series):
            if pd.isna(qset_val) or pd.isna(mag_val):
                continue
            qs = str(qset_val).strip()
            mag = str(mag_val).strip()
            if not qs or not mag:
                continue
            counts.setdefault(qs, {})
            counts[qs][mag] = counts[qs].get(mag, 0) + 1

        for qs, mag_counts in counts.items():
            # Pick the most frequent; tie-breaker by alphabetical
            best = sorted(mag_counts.items(), key=lambda kv: (-kv[1], kv[0].lower()))
            if best:
                result[qs] = best[0][0]
        return result

    def _collect_magazine_details(self, df: pd.DataFrame) -> tuple[list[dict], list[str]]:
        warnings: list[str] = []
        if df.empty:
            return [], warnings

        header_row = [None if pd.isna(col) else str(col) for col in df.columns]
        try:
            magazine_col = _find_magazine_column(header_row)
        except ValueError:
            warnings.append("Unable to determine magazine column for summary display.")
            return [], warnings

        question_set_col = None
        try:
            question_set_col = _find_question_set_column(header_row)
        except ValueError:
            warnings.append("Unable to determine question set column; question sets will not be listed.")

        coverage: dict[str, dict[str, object]] = {}
        magazine_series = df.iloc[:, magazine_col - 1]
        question_series = (
            df.iloc[:, question_set_col - 1] if question_set_col is not None else repeat(None, len(df))
        )
        for magazine_value, question_value in zip(magazine_series, question_series):
            if pd.isna(magazine_value):
                continue
            text = str(magazine_value).strip()
            if not text:
                continue
            display_parts = [part.strip() for part in text.split("|", 1)]
            display_name = display_parts[0] or "Unknown"
            display_edition = display_parts[1] if len(display_parts) > 1 else ""
            normalized = normalize_magazine_edition(text)
            norm_parts = normalized.split("|", 1)
            norm_name = norm_parts[0]
            norm_edition = norm_parts[1] if len(norm_parts) > 1 else ""
            entry = coverage.setdefault(
                norm_name,
                {
                    "display_name": display_name,
                    "editions": {},
                    "normalized_editions": set(),
                },
            )
            edition_label = display_edition or "(unspecified)"
            edition_entry = entry["editions"].setdefault(
                norm_edition,
                {
                    "display": edition_label,
                    "question_sets": set(),
                },
            )
            if question_set_col is not None and not pd.isna(question_value):
                q_text = str(question_value).strip()
                if q_text:
                    edition_entry["question_sets"].add(q_text)
            entry["normalized_editions"].add(norm_edition)

        if not coverage:
            return [], warnings

        details: list[dict] = []
        for norm_name in sorted(coverage.keys(), key=lambda key: str(coverage[key]["display_name"]).lower()):
            data = coverage[norm_name]
            edition_items = []
            for norm_edition, edition_data in sorted(
                data["editions"].items(),
                key=lambda item: self._edition_sort_key(item[0], item[1]["display"]),
            ):
                question_sets = sorted(edition_data["question_sets"], key=lambda value: value.lower())
                edition_items.append(
                    {
                        "display": edition_data["display"],
                        "normalized": norm_edition,
                        "question_sets": question_sets,
                    }
                )
            missing_ranges = self._compute_missing_ranges(data["normalized_editions"])
            details.append(
                {
                    "display_name": data["display_name"],
                    "missing_ranges": missing_ranges,
                    "editions": edition_items,
                }
            )
        return details, warnings

    def _compute_page_ranges_for_editions(self, df: pd.DataFrame, details: list[dict]) -> dict[str, tuple[str, str]]:
        """Compute page ranges per normalized edition."""
        ranges: dict[str, tuple[str, str]] = {}
        if df is None or df.empty:
            return ranges
        header_row = [None if pd.isna(col) else str(col) for col in df.columns]
        try:
            magazine_col = _find_magazine_column(header_row)
            page_col = _find_page_column(header_row)
        except ValueError:
            return ranges

        magazine_series = df.iloc[:, magazine_col - 1]
        page_series = df.iloc[:, page_col - 1]
        for mag_value, page_value in zip(magazine_series, page_series):
            if pd.isna(mag_value) or pd.isna(page_value):
                continue
            normalized = normalize_magazine_edition(str(mag_value))
            page_text = str(page_value).strip()
            if not page_text:
                continue
            # Attempt to parse page numbers; allow strings
            try:
                page_num = int(float(page_text))
            except ValueError:
                page_num = None
            low, high = ranges.get(normalized, ("", ""))
            if page_num is None:
                continue
            if not low or page_num < int(low):
                low = str(page_num)
            if not high or page_num > int(high):
                high = str(page_num)
            ranges[normalized] = (low, high)
        return ranges

    def _on_mag_heatmap_button_clicked(self) -> None:
        """Handle heatmap button click to show questions grouped by QuestionSetGroup.json."""
        btn = self.sender()
        if not btn:
            return
        info = btn.property("info")
        if not info:
            self.question_label.setText("Select a populated edition cell to view question sets")
            self.mag_question_card_view.clear()
            return
        normalized = info.get("normalized", "")
        display = info.get("display", "")
        page_min, page_max = info.get("page_range", ("", ""))
        page_text = f"  pp. {page_min}-{page_max}" if page_min and page_max else ""
        self.question_label.setText(f"{display}{page_text}")
        self._load_magazine_questions(normalized, display)

    def _load_magazine_questions(self, normalized_edition: str, display_label: str) -> None:
        """Load questions for a magazine edition and group using QuestionSetGroup.json."""
        self.mag_question_card_view.clear()
        if not normalized_edition or self.Database_df is None:
            return

        df = self.Database_df
        header_row = [None if pd.isna(col) else str(col) for col in df.columns]

        try:
            qno_col = _find_qno_column(header_row)
            page_col = _find_page_column(header_row)
            question_set_col = _find_question_set_column(header_row)
            question_text_col = _find_question_text_column(header_row)
            magazine_col = _find_magazine_column(header_row)
        except ValueError:
            self.question_label.setText(f"{display_label}  columns missing")
            return

        id_col_idx = None
        chapter_col_idx = None
        high_chapter_col_idx = None
        for idx, value in enumerate(header_row, start=1):
            if value is None:
                continue
            text = str(value).strip().lower()
            if text == "questionid":
                id_col_idx = idx
                continue
            if "high" in text and "chapter" in text and high_chapter_col_idx is None:
                high_chapter_col_idx = idx
            elif "chapter" in text and chapter_col_idx is None:
                chapter_col_idx = idx

        questions: list[dict] = []
        magazine_series = df.iloc[:, magazine_col - 1]
        qset_series = df.iloc[:, question_set_col - 1]
        qno_series = df.iloc[:, qno_col - 1]
        page_series = df.iloc[:, page_col - 1]
        qtext_series = df.iloc[:, question_text_col - 1]
        id_series = df.iloc[:, id_col_idx - 1] if id_col_idx else None
        chapter_series = df.iloc[:, chapter_col_idx - 1] if chapter_col_idx else None
        high_series = df.iloc[:, high_chapter_col_idx - 1] if high_chapter_col_idx else None

        for idx, (mag_value, qset_value, qno_value, page_value, qtext_value) in enumerate(
            zip(magazine_series, qset_series, qno_series, page_series, qtext_series)
        ):
            if pd.isna(mag_value) or pd.isna(qset_value):
                continue
            if normalize_magazine_edition(str(mag_value)) != normalized_edition:
                continue
            qs_name = str(qset_value).strip()
            questions.append(
                {
                    "qno": str(qno_value).strip() if not pd.isna(qno_value) else "",
                    "page": str(page_value).strip() if not pd.isna(page_value) else "",
                    "question_text": str(qtext_value).strip() if not pd.isna(qtext_value) else "",
                    "text": str(qtext_value).strip() if not pd.isna(qtext_value) else "",
                    "question_set_name": qs_name,
                    "magazine": display_label,
                    "chapter": (
                        str(chapter_series.iloc[idx]).strip()
                        if chapter_series is not None and not pd.isna(chapter_series.iloc[idx])
                        else ""
                    ),
                    "high_level_chapter": (
                        str(high_series.iloc[idx]).strip()
                        if high_series is not None and not pd.isna(high_series.iloc[idx])
                        else ""
                    ),
                    "question_id": None,
                }
            )
            if id_col_idx:
                raw_id = id_series.iloc[idx] if id_series is not None else None
                if pd.isna(raw_id) or str(raw_id).strip() == "":
                    questions[-1]["question_id"] = None
                else:
                    try:
                        questions[-1]["question_id"] = int(float(raw_id))
                    except Exception:
                        try:
                            questions[-1]["question_id"] = str(raw_id).strip()
                        except Exception:
                            questions[-1]["question_id"] = None
        # Group using QuestionSetGroup.json
        group_mapping = {}
        group_order = []
        if hasattr(self, "question_set_group_service") and self.question_set_group_service:
            groups = self.question_set_group_service.get_all_groups()
            group_order = list(groups.keys())
            for gname, gdata in groups.items():
                for qs in gdata.get("question_sets", []):
                    group_mapping[qs] = gname

        grouped: dict[str, list[dict]] = {}
        for q in questions:
            group_name = group_mapping.get(q["question_set_name"], "Others")
            grouped.setdefault(group_name, []).append(q)

        # Order groups by lowest page number (ascending). Fall back to name.
        def _min_page(qlist: list[dict]) -> float:
            pages = []
            for q in qlist:
                try:
                    pages.append(float(str(q.get("page", "")).strip()))
                except (ValueError, TypeError):
                    continue
            return min(pages) if pages else float("inf")

        ordered_keys = [
            (group_key, _min_page(qlist))
            for group_key, qlist in grouped.items()
        ]
        ordered_keys = [name for name, _ in sorted(ordered_keys, key=lambda kv: (kv[1], kv[0].lower()))]

        if not ordered_keys:
            self.question_label.setText(f"{display_label}  no questions found for this edition")
            return

        for group_key in ordered_keys:
            qlist = grouped.get(group_key, [])
            tags = self.question_set_group_tags.get(group_key, [])
            self.mag_question_card_view.add_group(group_key, qlist, tags, self.tag_colors, show_page_range=True)

    def _collect_question_analysis_data(
        self, df: pd.DataFrame
    ) -> tuple[dict[str, list[dict]], list[str], int | None, list[str]]:
        warnings: list[str] = []
        if df.empty:
            return {}, warnings, None, []

        header_row = [None if pd.isna(col) else str(col) for col in df.columns]
        try:
            question_set_col = _find_high_level_chapter_column(header_row)
            qno_col = _find_qno_column(header_row)
            page_col = _find_page_column(header_row)
        except ValueError as exc:
            warnings.append(f"Question analysis unavailable: {exc}")
            return {}, warnings, None, []

        question_text_col = None
        try:
            question_text_col = _find_question_text_column(header_row)
        except ValueError as exc:
            warnings.append(str(exc))

        question_set_name_col = None
        try:
            question_set_name_col = _find_question_set_name_column(header_row)
        except ValueError as exc:
            warnings.append(str(exc))

        magazine_col = None
        try:
            magazine_col = _find_magazine_column(header_row)
        except ValueError as exc:
            warnings.append(str(exc))

        id_col_idx = None
        for idx, value in enumerate(header_row, start=1):
            if value is None:
                continue
            text = str(value).strip().lower()
            if text == "questionid":
                id_col_idx = idx
                break

        def normalize(value) -> str:
            if pd.isna(value):
                return ""
            text = str(value).strip()
            return text

        chapters: dict[str, list[dict]] = {}
        raw_inputs: set[str] = set()
        for row_number, row in enumerate(df.itertuples(index=False, name=None), start=2):
            values = list(row)
            raw_chapter_name = normalize(values[question_set_col - 1])
            if not raw_chapter_name:
                continue
            raw_inputs.add(raw_chapter_name)
            chapter_name = self._match_chapter_group(raw_chapter_name)
            qno_value = normalize(values[qno_col - 1])
            page_value = normalize(values[page_col - 1])
            question_text = normalize(values[question_text_col - 1]) if question_text_col else ""
            question_set_name = normalize(values[question_set_name_col - 1]) if question_set_name_col else raw_chapter_name
            magazine_value = normalize(values[magazine_col - 1]) if magazine_col else ""
            question_id = None
            if id_col_idx:
                try:
                    question_id = int(values[id_col_idx - 1])
                except Exception:
                    question_id = values[id_col_idx - 1]

            effective_row_number = question_id if self.use_database and question_id is not None else row_number
            
            # Extract group_key for tag lookup (same key used for accordion headers)
            group_key = self._extract_group_key(question_set_name)

            chapters.setdefault(chapter_name, []).append(
                {
                    "group": chapter_name,
                    "question_set": raw_chapter_name,
                    "question_set_name": question_set_name,
                    "group_key": group_key,  # For tag color lookup in chips
                    "qno": qno_value,
                    "page": page_value,
                    "magazine": magazine_value,
                    "text": question_text,
                    "row_number": effective_row_number,
                    "question_id": question_id,
                }
            )

        return chapters, warnings, question_set_col, sorted(raw_inputs)

    def _normalize_label(self, label: str) -> str:
        return re.sub(r"\s+", " ", label.strip().lower())
    
    def _extract_group_key(self, question_set_name: str) -> str:
        """Extract a group key from question set name for similarity grouping.
        
        Methodology:
        1. Normalize the name (lowercase, remove extra spaces)
        2. Extract significant tokens (ignore common words, years, numbers at end)
        3. Return first 2-3 significant words as group key
        
        Examples:
        - 'JEE Main 2023 Paper 1' -> 'jee main'
        - 'NEET-2024' -> 'neet'
        - 'Physics Olympiad 2023' -> 'physics olympiad'
        """
        if not question_set_name:
            return "ungrouped"
        
        # Normalize
        normalized = self._normalize_label(question_set_name)
        
        # Split into tokens
        tokens = normalized.split()
        
        # Remove common suffix patterns (years, paper numbers, etc.)
        significant_tokens = []
        for token in tokens:
            # Skip years (4 digits), paper numbers, common words
            if re.match(r'^(\d{4}|\d+|paper|set|part|section|test|exam)$', token):
                continue
            significant_tokens.append(token)
            # Take first 2-3 significant words
            if len(significant_tokens) >= 3:
                break
        
        if not significant_tokens:
            # If all tokens were filtered, use first 2 tokens
            return ' '.join(tokens[:2]) if len(tokens) >= 2 else normalized
        
        return ' '.join(significant_tokens)

    def _auto_assign_chapters(self, chapters: list[str]) -> None:
        changed = False
        existing = {
            self._normalize_label(ch)
            for values in self.chapter_groups.values()
            for ch in values
        }
        for chapter in chapters:
            normalized = self._normalize_label(chapter)
            if not normalized or normalized in existing:
                continue
            target = self._match_chapter_group(chapter)
            self.chapter_groups.setdefault(target, []).append(chapter)
            existing.add(normalized)
            changed = True
        if changed:
            self._save_chapter_grouping()
            self._refresh_grouping_ui()

    def _match_chapter_group(self, chapter: str) -> str:
        normalized = self._normalize_label(chapter)
        if not normalized:
            return "Others"
        direct = self.chapter_lookup.get(normalized)
        if direct:
            return direct
        for norm_value, group in self.chapter_lookup.items():
            if norm_value in normalized or normalized in norm_value:
                return group
        for group in self.canonical_chapters:
            norm_group = self._normalize_label(group)
            if normalized == norm_group:
                return group
        for group in self.canonical_chapters:
            norm_group = self._normalize_label(group)
            if norm_group in normalized or normalized in norm_group:
                return group
        return "Others"

    def _compute_row_count_from_df(self, df: pd.DataFrame) -> int:
        def row_has_value(row) -> bool:
            for value in row:
                if isinstance(value, str):
                    if value.strip():
                        return True
                    continue
                if pd.isna(value):
                    continue
                return True
            return False

        for idx in range(len(df) - 1, -1, -1):
            if row_has_value(df.iloc[idx]):
                return idx + 2  # DataFrame row index is zero-based, Excel rows start at 2 after header.
        return 1

    def _compute_missing_ranges(self, normalized_editions: set[str]) -> list[str]:
        monthly_tokens = sorted(
            {
                token
                for token in normalized_editions
                if re.fullmatch(r"\d{4}-\d{2}", token)
            }
        )
        if len(monthly_tokens) < 2:
            return []

        months = [dt.date(int(token[:4]), int(token[5:7]), 1) for token in monthly_tokens]
        present_keys = set(monthly_tokens)
        missing_ranges: list[str] = []
        current = months[0]
        last = months[-1]
        missing_start: dt.date | None = None

        while current <= last:
            key = current.strftime("%Y-%m")
            if key not in present_keys:
                if missing_start is None:
                    missing_start = current
            else:
                if missing_start is not None:
                    end = self._previous_month(current)
                    missing_ranges.append(self._format_range(missing_start, end))
                    missing_start = None
            current = self._add_month(current)

        if missing_start is not None:
            missing_ranges.append(self._format_range(missing_start, last))
        return missing_ranges

    def _add_month(self, date_value: dt.date) -> dt.date:
        if date_value.month == 12:
            return dt.date(date_value.year + 1, 1, 1)
        return dt.date(date_value.year, date_value.month + 1, 1)

    def _previous_month(self, date_value: dt.date) -> dt.date:
        if date_value.month == 1:
            return dt.date(date_value.year - 1, 12, 1)
        return dt.date(date_value.year, date_value.month - 1, 1)

    def _format_range(self, start: dt.date, end: dt.date) -> str:
        if start == end:
            return start.strftime("%b %Y")
        return f"{start.strftime('%b %Y')} - {end.strftime('%b %Y')}"

    def _parse_normalized_month(self, normalized: str) -> dt.date | None:
        if normalized and re.fullmatch(r"\d{4}-\d{2}", normalized):
            return dt.date(int(normalized[:4]), int(normalized[5:7]), 1)
        return None

    def _edition_sort_key(self, normalized: str, display_label: str) -> tuple:
        parsed = self._parse_normalized_month(normalized)
        if parsed:
            return (0, -parsed.toordinal(), display_label.lower())
        return (1, display_label.lower(), "")

    def _edition_sort_key(self, normalized: str, display_label: str) -> tuple:
        parsed = self._parse_normalized_month(normalized)
        if parsed:
            return (0, -parsed.toordinal(), display_label.lower())
        return (1, display_label.lower(), "")

    def _populate_magazine_tree(self, details: list[dict]) -> None:
        """Populate magazine editions tree grouped by year with counts."""
        if not hasattr(self, "mag_tree"):
            return
        self.mag_tree.clear()
        
        # Calculate statistics
        total_editions = 0
        total_sets = 0
        
        if not details:
            if hasattr(self, "mag_total_editions_label"):
                self.mag_total_editions_label.setText("Total Editions: 0")
            if hasattr(self, "mag_total_sets_label"):
                self.mag_total_sets_label.setText("Question Sets: 0")
            return

        for entry in details:
            magazine_name = entry["display_name"]
            
            # Create parent node for magazine
            magazine_parent = QTreeWidgetItem([magazine_name, ""])
            magazine_parent.setData(0, Qt.UserRole, {"type": "magazine", "display_name": magazine_name})
            font = QFont()
            font.setBold(True)
            magazine_parent.setFont(0, font)
            self.mag_tree.addTopLevelItem(magazine_parent)
            
            # Group editions by year
            editions_by_year = {}
            missing_by_year = {}
            
            # Process existing editions
            for edition in entry.get("editions", []):
                edition_label = edition["display"] or "(unspecified)"
                question_sets = edition["question_sets"]
                normalized = edition.get("normalized", "")
                
                parsed_date = self._parse_normalized_month(normalized)
                if parsed_date:
                    year = parsed_date.year
                    if year not in editions_by_year:
                        editions_by_year[year] = []
                    editions_by_year[year].append({
                        "date": parsed_date,
                        "label": edition_label,
                        "sets": question_sets,
                        "normalized": normalized
                    })
            
            # Process missing editions
            missing_ranges = entry.get("missing_ranges", [])
            if missing_ranges:
                missing_editions = self._expand_missing_ranges(missing_ranges)
                for missing_date in missing_editions:
                    year = missing_date.year
                    if year not in missing_by_year:
                        missing_by_year[year] = []
                    missing_by_year[year].append(missing_date)
            
            # Get all years and sort in descending order
            all_years = sorted(set(list(editions_by_year.keys()) + list(missing_by_year.keys())), reverse=True)
            
            # Create year nodes
            for year in all_years:
                year_editions = editions_by_year.get(year, [])
                year_missing = missing_by_year.get(year, [])
                year_count = len(year_editions)
                
                # Create year parent node with count
                year_parent = QTreeWidgetItem([f"{year} ({year_count})", ""])
                year_parent.setData(0, Qt.UserRole, {"type": "year", "year": year})
                font_year = QFont()
                font_year.setBold(True)
                year_parent.setFont(0, font_year)
                
                # Year-based background color
                bg_color = QColor(self._get_year_color(year))
                year_parent.setBackground(0, bg_color)
                year_parent.setBackground(1, bg_color)
                
                magazine_parent.addChild(year_parent)
                
                # Add existing editions for this year
                for edition_data in sorted(year_editions, key=lambda x: x["date"].toordinal(), reverse=True):
                    formatted_label = edition_data["date"].strftime("%b '%y")
                    sets_count = len(edition_data["sets"])
                    
                    child = QTreeWidgetItem([formatted_label, str(sets_count)])
                    child.setBackground(0, bg_color)
                    child.setBackground(1, bg_color)
                    
                    data = {
                        "type": "edition",
                        "display_name": magazine_name,
                        "edition_label": edition_data["label"],
                        "question_sets": edition_data["sets"],
                        "is_missing": False
                    }
                    child.setData(0, Qt.UserRole, data)
                    year_parent.addChild(child)
                    
                    total_editions += 1
                    total_sets += sets_count
                
                # Add missing editions for this year
                if year_missing:
                    missing_parent = QTreeWidgetItem([" Missing Editions", ""])
                    missing_parent.setForeground(0, QColor("#dc2626"))
                    font_bold = QFont()
                    font_bold.setBold(True)
                    missing_parent.setFont(0, font_bold)
                    missing_parent.setData(0, Qt.UserRole, {"type": "missing_section"})
                    year_parent.addChild(missing_parent)
                    
                    for missing_date in sorted(year_missing, key=lambda d: d.toordinal(), reverse=True):
                        formatted_label = missing_date.strftime("%b '%y")
                        missing_child = QTreeWidgetItem([formatted_label, "-"])
                        
                        # RED BOLD for missing editions
                        font_red_bold = QFont()
                        font_red_bold.setBold(True)
                        missing_child.setFont(0, font_red_bold)
                        missing_child.setFont(1, font_red_bold)
                        missing_child.setForeground(0, QColor("#dc2626"))
                        missing_child.setForeground(1, QColor("#dc2626"))
                        
                        missing_child.setBackground(0, bg_color)
                        missing_child.setBackground(1, bg_color)
                        
                        missing_child.setData(0, Qt.UserRole, {"type": "missing", "is_missing": True})
                        missing_parent.addChild(missing_child)
                
                year_parent.setExpanded(True)
            
            magazine_parent.setExpanded(True)
        
        # Update summary statistics
        if hasattr(self, "mag_total_editions_label"):
            self.mag_total_editions_label.setText(f"Total Editions: {total_editions}")
        if hasattr(self, "mag_total_sets_label"):
            self.mag_total_sets_label.setText(f"Question Sets: {total_sets}")

    def _populate_magazine_heatmap(self, details: list[dict], page_ranges: dict[str, tuple[str, str]]) -> None:
        """Populate magazine editions heatmap grid."""
        if not hasattr(self, "mag_heatmap_layout"):
            return
        self.mag_heatmap_data.clear()
        # Clear existing year sections
        while self.mag_heatmap_layout.count() > 1:
            item = self.mag_heatmap_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not details:
            if hasattr(self, "mag_total_editions_label"):
                self.mag_total_editions_label.setText("Total Editions: 0")
            if hasattr(self, "mag_total_sets_label"):
                self.mag_total_sets_label.setText("Question Sets: 0")
            return

        entry = details[0]
        editions = entry.get("editions", [])
        edition_dates: dict[tuple[int, int], dict] = {}
        total_editions = 0
        total_sets = 0

        normalized_mag_name = normalize_text(entry.get("display_name", ""))
        for ed in editions:
            normalized = ed.get("normalized", "")
            parsed = self._parse_normalized_month(normalized)
            if not parsed:
                continue
            normalized_full = f"{normalized_mag_name}|{normalized}" if normalized else normalized_mag_name
            page_min, page_max = page_ranges.get(normalized_full, ("", ""))
            edition_dates[(parsed.year, parsed.month)] = {
                "normalized": normalized_full,
                "display": ed.get("display", ""),
                "question_sets": ed.get("question_sets", []),
                "page_range": (page_min, page_max),
            }
            total_editions += 1
            total_sets += len(ed.get("question_sets", []))

        missing_dates = set(self._expand_missing_ranges(entry.get("missing_ranges", [])))
        all_dates = set(dt.date(y, m, 1) for (y, m) in edition_dates.keys()) | missing_dates
        if not all_dates:
            return

        min_date = min(all_dates)
        max_date = max(all_dates)
        years = list(range(max_date.year, min_date.year - 1, -1))

        for year in years:
            year_widget = QWidget()
            year_layout = QHBoxLayout(year_widget)
            year_layout.setContentsMargins(0, 0, 0, 0)
            year_layout.setSpacing(8)

            # Year label vertically oriented using stacked digits
            year_label = QLabel("\n".join(str(year)))
            year_label.setStyleSheet("""
                font-weight: bold;
                color: #0f172a;
                background: #e2e8f0;
                padding: 8px 6px;
                border-radius: 6px;
            """)
            year_label.setAlignment(Qt.AlignCenter)
            year_label.setMinimumWidth(28)
            year_label.setMaximumWidth(28)
            year_layout.addWidget(year_label)

            # Container for months + separator
            months_container = QWidget()
            months_layout = QVBoxLayout(months_container)
            months_layout.setContentsMargins(0, 0, 0, 0)
            months_layout.setSpacing(6)

            sep = QFrame()
            sep.setFrameShape(QFrame.HLine)
            sep.setStyleSheet("color: #e5e7eb;")
            months_layout.addWidget(sep)

            grid = QGridLayout()
            grid.setSpacing(8)
            for idx, month in enumerate(range(1, 13)):
                cell_date = dt.date(year, month, 1)
                date_key = (year, month)
                btn = QPushButton()
                btn.setCursor(Qt.PointingHandCursor)
                btn.setFixedSize(110, 72)
                btn.setProperty("year", year)
                btn.setProperty("month", month)
                btn.setStyleSheet("""
                    QPushButton {
                        border: 1px solid #e2e8f0;
                        border-radius: 8px;
                        background: #f8fafc;
                        color: #1e293b;
                        text-align: left;
                        padding: 6px;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        border: 2px solid #93c5fd;
                        background: #eef2ff;
                        color: #0f172a;
                    }
                    QPushButton:pressed {
                        border: 2px solid #3b82f6;
                        background: #e0f2fe;
                        color: #0f172a;
                    }
                """)

                if date_key in edition_dates:
                    info = edition_dates[date_key]
                    self.mag_heatmap_data[(year, month)] = info
                    page_min, page_max = info.get("page_range", ("", ""))
                    page_text = f"{page_min}-{page_max}" if page_min and page_max else "pp "
                    sets_count = len(info.get("question_sets", []))
                    btn.setText(f"{cell_date.strftime('%b')}\n{page_text}\n{sets_count} set(s)")
                    btn.setToolTip(f"{info.get('display','')}  {sets_count} set(s)\nPages: {page_text}")
                    btn.setProperty("info", info)
                    btn.setStyleSheet(btn.styleSheet() + """
                        QPushButton {
                            border: 1px solid #bfdbfe;
                            background: #e0f2fe;
                            color: #0f172a;
                        }
                    """)
                elif cell_date in missing_dates:
                    btn.setText(f"{cell_date.strftime('%b')}\nMissing")
                    btn.setToolTip("Missing edition")
                    btn.setProperty("info", None)
                    btn.setStyleSheet(btn.styleSheet() + """
                        QPushButton {
                            border: 2px dashed #ef4444;
                            background: #fef2f2;
                            color: #b91c1c;
                        }
                    """)
                else:
                    btn.setText(f"{cell_date.strftime('%b')}\nNo data")
                    btn.setToolTip("No data")
                    btn.setProperty("info", None)

                btn.clicked.connect(self._on_mag_heatmap_button_clicked)
                grid.addWidget(btn, idx // 4, idx % 4)

            months_layout.addLayout(grid)
            year_layout.addWidget(months_container)
            self.mag_heatmap_layout.insertWidget(self.mag_heatmap_layout.count() - 1, year_widget)

        if hasattr(self, "mag_total_editions_label"):
            self.mag_total_editions_label.setText(f"Total Editions: {total_editions}")
        if hasattr(self, "mag_total_sets_label"):
            self.mag_total_sets_label.setText(f"Question Sets: {total_sets}")
    
    def _expand_missing_ranges(self, missing_ranges: list[str]) -> list[dt.date]:
        """Expand missing ranges into individual dates."""
        missing_dates = []
        
        for range_str in missing_ranges:
            if " - " in range_str:
                # Range like "Jan 2023 - Mar 2023"
                start_str, end_str = range_str.split(" - ")
                start_date = dt.datetime.strptime(start_str, "%b %Y").date()
                end_date = dt.datetime.strptime(end_str, "%b %Y").date()
                
                current = start_date
                while current <= end_date:
                    missing_dates.append(current)
                    current = self._add_month(current)
            else:
                # Single month like "Jan 2023"
                missing_dates.append(dt.datetime.strptime(range_str, "%b %Y").date())
        
        return missing_dates
    
    def _get_year_color(self, year: int) -> str:
        """Get a consistent color for a given year."""
        year_colors = {
            2020: "#fef3c7",  # Light amber
            2021: "#dbeafe",  # Light blue
            2022: "#d1fae5",  # Light green
            2023: "#fce7f3",  # Light pink
            2024: "#e0e7ff",  # Light indigo
            2025: "#fed7aa",  # Light orange
            2026: "#e9d5ff",  # Light purple
            2027: "#ccfbf1",  # Light teal
            2028: "#fef08a",  # Light yellow
            2029: "#fbcfe8",  # Light rose
        }
        # For years not in the map, generate a color based on year
        if year not in year_colors:
            # Generate pastel colors using year as seed
            hue = (year * 137) % 360
            return f"hsl({hue}, 70%, 90%)"
        return year_colors[year]

    def _populate_question_sets(self, question_sets: list[str] | None, magazine_name: str = "", edition_label: str = "") -> None:
        """Populate question sets tree with questions as children."""
        if not hasattr(self, "question_sets_tree"):
            return
        self.question_sets_tree.clear()
        if not question_sets or self.Database_df is None:
            return
        
        # Use cached DataFrame for much better performance
        try:
            df = self.Database_df
            self.log(f"Using cached DataFrame ({len(df)} rows) to populate question sets")
            header_row = [None if pd.isna(col) else str(col) for col in df.columns]
            
            # Find required columns
            try:
                qno_col = _find_qno_column(header_row)
                page_col = _find_page_column(header_row)
                question_set_col = _find_question_set_column(header_row)
                magazine_col = _find_magazine_column(header_row)
            except ValueError:
                # If columns not found, just show question sets without children
                for name in question_sets:
                    parent_item = QTreeWidgetItem([f" {name}", "", ""])
                    self.question_sets_tree.addTopLevelItem(parent_item)
                return
            
            # Collect questions by question set for this specific magazine edition
            questions_by_set: dict[str, list[dict]] = {}
            normalized_target = normalize_magazine_edition(f"{magazine_name}|{edition_label}")
            
            # Use pandas vectorized operations for better performance
            magazine_series = df.iloc[:, magazine_col - 1]
            question_set_series = df.iloc[:, question_set_col - 1]
            qno_series = df.iloc[:, qno_col - 1]
            page_series = df.iloc[:, page_col - 1]
            
            for idx, (mag_value, qset_value, qno_value, page_value) in enumerate(zip(
                magazine_series, question_set_series, qno_series, page_series
            )):
                # Skip if magazine value is missing
                if pd.isna(mag_value):
                    continue
                
                # Check if magazine matches
                normalized_mag = normalize_magazine_edition(str(mag_value))
                if normalized_mag != normalized_target:
                    continue
                
                # Get question set
                if pd.isna(qset_value):
                    continue
                    
                qset_name = str(qset_value).strip()
                if qset_name not in question_sets:
                    continue
                
                # Get question details
                qno_str = str(qno_value).strip() if not pd.isna(qno_value) else ""
                page_str = str(page_value).strip() if not pd.isna(page_value) else ""
                
                questions_by_set.setdefault(qset_name, []).append({
                    "qno": qno_str,
                    "page": page_str,
                    "row": idx + 2  # DataFrame is 0-based, Excel rows start at 2
                })
            
            # Create tree items
            for qset_name in question_sets:
                questions = questions_by_set.get(qset_name, [])
                # Sort questions by page number (ascending) for magazine edition view
                def _page_key(q):
                    page_str = str(q.get("page", "")).strip()
                    try:
                        return int(float(page_str))
                    except (ValueError, TypeError):
                        return float("inf")
                questions = sorted(questions, key=_page_key)
                parent_item = QTreeWidgetItem([f" {qset_name}", "", f"({len(questions)} questions)"])
                parent_item.setData(0, Qt.UserRole, {"type": "question_set", "name": qset_name})
                
                # Add questions as children
                for q in questions:
                    child_item = QTreeWidgetItem([f"  Q{q['qno']}", q['qno'], q['page']])
                    child_item.setData(0, Qt.UserRole, {"type": "question", "qno": q['qno'], "page": q['page'], "row": q['row']})
                    parent_item.addChild(child_item)
                
                self.question_sets_tree.addTopLevelItem(parent_item)
                
        except Exception as e:
            self.log(f"Error loading questions for question sets: {e}")
            # Fallback to simple list
            for name in question_sets:
                parent_item = QTreeWidgetItem([f" {name}", "", ""])
                self.question_sets_tree.addTopLevelItem(parent_item)

    def _populate_chapter_list(self, chapters: dict[str, list[dict]]) -> None:
        if not hasattr(self, "chapter_view"):
            return
        self.chapter_questions = chapters or {}
        if hasattr(self, "question_tree"):
            self.question_tree.clear()
        self.question_text_view.clear()
        if not self.chapter_questions:
            self.chapter_view.clear_chapters()
            self._populate_question_table([])
            return
        
        # Sort chapters by question count (descending) then by name (ascending)
        sorted_chapters = sorted(
            self.chapter_questions.items(),
            key=lambda kv: (-len(kv[1]), kv[0].lower()),
        )
        
        # Clear and populate chapter view
        self.chapter_view.clear_chapters()
        
        for chapter_key, questions in sorted_chapters:
            self.chapter_view.add_chapter(
                chapter_name=chapter_key,
                chapter_key=chapter_key,
                question_count=len(questions)
            )
        
        # Do not auto-select; wait for user interaction to avoid eager loading

    def _populate_question_table(self, questions: list[dict]) -> None:
        if not hasattr(self, "question_tree"):
            return
        self.all_questions = questions or []
        self._apply_question_search()

    def _refresh_question_tab_with_loading(self) -> None:
        """Show a loading overlay while rebuilding the question list tab."""
        self._set_question_tab_loading(True)
        QTimer.singleShot(0, self._finish_question_tab_refresh)

    def _finish_question_tab_refresh(self) -> None:
        try:
            self._apply_question_search(preserve_scroll=True)
        finally:
            self._set_question_tab_loading(False)

    def _set_question_tab_loading(self, is_loading: bool) -> None:
        """Toggle loading overlay and disable question tab controls."""
        if not hasattr(self, "question_card_stack"):
            return
        if is_loading:
            self.question_card_stack.setCurrentWidget(self.question_loading_overlay)
        else:
            self.question_card_stack.setCurrentWidget(self.question_card)
        
        for widget in getattr(self, "_question_tab_controls", []):
            if widget:
                widget.setEnabled(not is_loading)

    def _on_advanced_query_submit(self) -> None:
        """Submit the advanced query and refresh results (triggered by Enter/Go)."""
        if hasattr(self, "advanced_query_input"):
            self.advanced_query_term = self.advanced_query_input.text().strip()
        self._apply_question_search()

    def _parse_advanced_query(self, query: str):
        """
        Parse a simple JIRA-like query into an AST.
        Supports fields: text, magazine, question_set (question_set_name).
        Operators: = (equals, case-insensitive), ~ (contains).
        Logical: AND, OR. AND has higher precedence than OR. Parentheses not supported.
        """
        if not query:
            return None, None

        try:
            tokens = shlex.split(query.strip())
        except ValueError as exc:
            return None, f"Invalid query: {exc}"

        terms = []
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            upper = tok.upper()
            if upper in ("AND", "OR"):
                terms.append(("OP", upper))
                i += 1
                continue
            # Expect field op value
            if i + 2 >= len(tokens):
                return None, "Invalid query: expected 'field operator value'."
            field = tok
            op = tokens[i + 1]
            value = tokens[i + 2]
            if op not in ("=", "~"):
                return None, f"Invalid operator '{op}'. Use = or ~."
            terms.append(("TERM", field, op, value))
            i += 3

        # Build AST with simple precedence: AND before OR, left-associative
        def reduce_ops(seq, op_name):
            out = []
            idx = 0
            while idx < len(seq):
                item = seq[idx]
                if item == ("OP", op_name):
                    if not out or idx + 1 >= len(seq):
                        return None
                    left = out.pop()
                    right = seq[idx + 1]
                    out.append(("BIN", op_name, left, right))
                    idx += 2
                else:
                    out.append(item)
                    idx += 1
            return out

        # First handle AND, then OR
        seq = terms
        seq = reduce_ops(seq, "AND")
        if seq is None:
            return None, "Invalid AND expression."
        seq = reduce_ops(seq, "OR")
        if seq is None or len(seq) != 1:
            return None, "Invalid OR expression."
        return seq[0], None

    def _evaluate_advanced_query(self, ast_node, question: dict) -> bool:
        """Evaluate the parsed query AST against a question record."""
        if not ast_node:
            return True
        kind = ast_node[0]
        if kind == "TERM":
            _, field, op, value = ast_node
            val = ""
            field_norm = field.lower()
            if field_norm in ("text", "question", "question_text"):
                val = question.get("question_text") or question.get("text") or ""
            elif field_norm in ("magazine", "magazine_name"):
                val = question.get("magazine", "")
            elif field_norm in ("question_set", "question_set_name", "set"):
                val = question.get("question_set_name") or question.get("question_set") or ""
            else:
                val = ""
            val = str(val).lower()
            comp = value.lower()
            if op == "=":
                return val == comp
            return comp in val
        if kind == "BIN":
            _, op, left, right = ast_node
            if op == "AND":
                return self._evaluate_advanced_query(left, question) and self._evaluate_advanced_query(right, question)
            if op == "OR":
                return self._evaluate_advanced_query(left, question) or self._evaluate_advanced_query(right, question)
        return False

    def _update_advanced_query_completions(self, text: str) -> None:
        """Update autocomplete suggestions for the advanced query box."""
        fields = ["text", "magazine", "question_set"]
        operators = ["=", "~", "AND", "OR"]
        # Basic heuristic: after a field, suggest operators; after an operator, suggest fields; otherwise both
        tokens = text.strip().split()
        suggestions: list[str] = []
        if not tokens:
            suggestions = fields
        else:
            last = tokens[-1]
            last_upper = last.upper()
            if last.lower() in fields:
                suggestions = operators
            elif last_upper in ("AND", "OR", "=", "~"):
                suggestions = fields
            else:
                suggestions = fields + operators
        self.advanced_query_completer_model.setStringList(suggestions)

    def _apply_question_search(self, preserve_scroll: bool = False) -> None:
        """Apply advanced query + tag filters and update the question card view."""
        # Save scroll position if requested
        scroll_value = None
        if preserve_scroll and hasattr(self, "question_card_view"):
            scrollbar = self.question_card_view.verticalScrollBar()
            if scrollbar:
                scroll_value = scrollbar.value()
        
        filtered = self.all_questions

        # Apply advanced query (runs only when submitted)
        if self.advanced_query_term:
            ast, err = self._parse_advanced_query(self.advanced_query_term)
            if err:
                if hasattr(self, "advanced_query_error"):
                    self.advanced_query_error.setText(err)
                    self.advanced_query_error.setVisible(True)
                # Do not alter the list if the query is invalid
            else:
                if hasattr(self, "advanced_query_error"):
                    self.advanced_query_error.clear()
                    self.advanced_query_error.setVisible(False)
                filtered = [q for q in filtered if self._evaluate_advanced_query(ast, q)]
        else:
            if hasattr(self, "advanced_query_error"):
                self.advanced_query_error.clear()
                self.advanced_query_error.setVisible(False)
        
        # Update card view with grouping
        self.current_questions = filtered
        
        # Clear both views
        if hasattr(self, "question_card_view"):
            self.question_card_view.clear()
        if hasattr(self, "question_tree"):
            self.question_tree.clear()
        self.question_text_view.clear()
        
        if not filtered:
            return
        
        # Build mapping of question set -> group from QuestionSetGroup.json
        groups = {}
        qs_to_group = {}
        group_order = []
        if hasattr(self, "question_set_group_service") and self.question_set_group_service:
            config_groups = self.question_set_group_service.get_all_groups()
            group_order = list(config_groups.keys())
            for g_name, g_data in config_groups.items():
                for qs in g_data.get("question_sets", []):
                    qs_to_group[qs] = g_name

        # Determine all question set names to compute Others
        all_qs_names = {q.get("question_set_name", "Unknown") for q in self.all_questions} if hasattr(self, "all_questions") else set()
        others_sets = all_qs_names - set(qs_to_group.keys())

        # Group questions using mapping; unmapped go to Others
        for question in filtered:
            qs_name = question.get("question_set_name", "Unknown")
            group_key = qs_to_group.get(qs_name, "Others")
            groups.setdefault(group_key, []).append(question)

        # Apply tag filtering (multiple tags)
        if self.selected_tag_filters:
            filtered_groups = {}
            for group_key, group_questions in groups.items():
                tags = self.question_set_group_tags.get(group_key, [])
                # Check if any of the selected filter tags match any of the group's tags
                if any(filter_tag in tags for filter_tag in self.selected_tag_filters):
                    filtered_groups[group_key] = group_questions
            groups = filtered_groups
        
        # Build display order: Others first, then config order, then any remaining groups alpha
        ordered_keys = []
        if "Others" in groups:
            ordered_keys.append("Others")
        for g in group_order:
            if g in groups and g != "Others":
                ordered_keys.append(g)
        # Add any remaining groups not in config
        for g in sorted(groups.keys()):
            if g not in ordered_keys:
                ordered_keys.append(g)
        
        # Populate card view with accordion groups
        if hasattr(self, "question_card_view"):
            total_questions = len(filtered)
            for group_key in ordered_keys:
                group_questions = groups.get(group_key, [])
                if not group_questions:
                    continue
                tags = self.question_set_group_tags.get(group_key, [])
                self.question_card_view.add_group(group_key, group_questions, tags, self.tag_colors, show_page_range=False)
        
        # Restore scroll position if it was saved
        if scroll_value is not None and hasattr(self, "question_card_view"):
            scrollbar = self.question_card_view.verticalScrollBar()
            if scrollbar:
                scrollbar.setValue(scroll_value)

    def clear_question_search(self) -> None:
        """Clear all search terms."""
        self.selected_tag_filters = []
        self.advanced_query_term = ""
        if hasattr(self, "advanced_query_input"):
            self.advanced_query_input.clear()
        if hasattr(self, "advanced_query_error"):
            self.advanced_query_error.clear()
            self.advanced_query_error.setVisible(False)
        if hasattr(self, "tag_filter_display"):
            self.tag_filter_display.clear()
        self._apply_question_search()

    def _show_list_loading(self, show: bool) -> None:
        """Toggle loading overlay when switching custom lists."""
        if not hasattr(self, "list_loading_overlay"):
            return
        if show:
            parent = self.list_question_card_view.viewport()
            self.list_loading_overlay.setParent(parent)
            self.list_loading_overlay.setGeometry(0, 0, parent.width(), parent.height())
            self.list_loading_overlay.show()
            self.list_loading_overlay.raise_()
            QApplication.setOverrideCursor(Qt.WaitCursor)
        else:
            self.list_loading_overlay.hide()
            QApplication.restoreOverrideCursor()

    def _show_tag_filter_dialog(self) -> None:
        """Show dialog to select multiple tags for filtering."""
        # Get all existing tags across all groups
        all_tags = sorted(set(tag for tags in self.question_set_group_tags.values() for tag in tags))
        
        if not all_tags:
            QMessageBox.information(self, "No Tags", "No tags have been created yet. Assign tags to groups first.")
            return
        
        # Show multi-select dialog
        dialog = MultiSelectTagDialog(
            all_tags, 
            self.selected_tag_filters, 
            "Filter by Tags",
            self.tag_colors,
            self.available_tag_colors,
            self
        )
        
        if dialog.exec() == QDialog.Accepted:
            self.selected_tag_filters = dialog.get_selected_tags()
            # Update label
            if self.selected_tag_filters:
                self.tag_filter_display.setText(", ".join(self.selected_tag_filters))
            else:
                self.tag_filter_display.clear()
            self._apply_question_search()

    def on_mag_tree_search_changed(self, text: str) -> None:
        """Filter magazine tree based on search text (supports 3-level hierarchy)."""
        search_term = text.strip().lower()
        
        if not hasattr(self, "mag_tree"):
            return
        
        # Show all if search is empty
        if not search_term:
            for i in range(self.mag_tree.topLevelItemCount()):
                magazine = self.mag_tree.topLevelItem(i)
                magazine.setHidden(False)
                for j in range(magazine.childCount()):
                    year = magazine.child(j)
                    year.setHidden(False)
                    for k in range(year.childCount()):
                        year.child(k).setHidden(False)
            return
        
        # Filter tree items (magazine -> year -> edition)
        for i in range(self.mag_tree.topLevelItemCount()):
            magazine = self.mag_tree.topLevelItem(i)
            magazine_text = magazine.text(0).lower()
            magazine_matches = search_term in magazine_text
            
            visible_years = 0
            for j in range(magazine.childCount()):
                year = magazine.child(j)
                year_text = year.text(0).lower()
                year_matches = search_term in year_text
                
                visible_editions = 0
                for k in range(year.childCount()):
                    edition = year.child(k)
                    edition_text = f"{edition.text(0)} {edition.text(1)}".lower()
                    edition_matches = search_term in edition_text
                    
                    # Check grandchildren (missing editions under missing section)
                    visible_missing = 0
                    if edition.childCount() > 0:
                        for m in range(edition.childCount()):
                            missing_edition = edition.child(m)
                            missing_text = f"{missing_edition.text(0)} {missing_edition.text(1)}".lower()
                            missing_matches = search_term in missing_text
                            missing_edition.setHidden(not (magazine_matches or year_matches or edition_matches or missing_matches))
                            if magazine_matches or year_matches or edition_matches or missing_matches:
                                visible_missing += 1
                    
                    # Edition visible if it or its missing children match
                    edition.setHidden(not (magazine_matches or year_matches or edition_matches or visible_missing > 0))
                    if magazine_matches or year_matches or edition_matches or visible_missing > 0:
                        visible_editions += 1
                
                year.setHidden(visible_editions == 0)
                if visible_editions > 0:
                    visible_years += 1
            
            magazine.setHidden(visible_years == 0)
    
    def on_magazine_select(self) -> None:
        """Handle magazine edition selection from tree."""
        if not hasattr(self, "mag_tree"):
            return
        
        selected_items = self.mag_tree.selectedItems()
        if not selected_items:
            self._populate_question_sets([])
            self.question_label.setText("Select an edition to view question sets")
            self.question_label.setStyleSheet(
                "padding: 8px; background-color: #f1f5f9; border-radius: 6px; color: #475569;"
            )
            return
        
        item = selected_items[0]
        data = item.data(0, Qt.UserRole)
        
        if not isinstance(data, dict):
            self._populate_question_sets([])
            self.question_label.setText("Select an edition to view question sets")
            self.question_label.setStyleSheet(
                "padding: 8px; background-color: #f1f5f9; border-radius: 6px; color: #475569;"
            )
            return
        
        # Don't show question sets for missing editions or magazine/missing section/year headers
        if data.get("type") in ["magazine", "missing_section", "missing", "year"] or data.get("is_missing", False):
            self._populate_question_sets([])
            if data.get("type") == "missing" or data.get("is_missing", False):
                self.question_label.setText(" Missing edition - no data available")
                self.question_label.setStyleSheet(
                    "padding: 8px; background-color: #fee2e2; border-radius: 6px; color: #dc2626;"
                )
            else:
                self.question_label.setText("Select an edition to view question sets")
                self.question_label.setStyleSheet(
                    "padding: 8px; background-color: #f1f5f9; border-radius: 6px; color: #475569;"
                )
            return
        
        # Reset label style for valid editions
        self.question_label.setStyleSheet(
            "padding: 8px; background-color: #f1f5f9; border-radius: 6px; color: #475569;"
        )

        question_sets = data.get("question_sets", [])
        magazine_name = data.get("display_name", "")
        edition_label = data.get("edition_label", "")
        label = f"{magazine_name} - {edition_label}"
        
        if question_sets:
            self.question_label.setText(f" {label}  {len(question_sets)} question set(s)")
            self._populate_question_sets(question_sets, magazine_name, edition_label)
        else:
            self.question_label.setText(f" {label}  No question sets found")
            self._populate_question_sets([])

    def on_group_selected(self) -> None:
        if not hasattr(self, "group_list"):
            return
        item = self.group_list.currentItem()
        self.group_chapter_list.clear()
        if not item:
            return
        group = item.data(Qt.UserRole) or item.text()
        for chapter in sorted(self.chapter_groups.get(group, []), key=lambda value: value.lower()):
            chapter_item = QListWidgetItem(chapter)
            chapter_item.setData(Qt.UserRole, chapter)
            self.group_chapter_list.addItem(chapter_item)

    def move_selected_chapter(self) -> None:
        group_item = getattr(self, "group_list", None)
        chapter_list = getattr(self, "group_chapter_list", None)
        target_combo = getattr(self, "move_target_combo", None)
        if (
            not group_item
            or not chapter_list
            or not target_combo
            or not group_item.currentItem()
            or not chapter_list.currentItem()
        ):
            return
        current_group = group_item.currentItem().data(Qt.UserRole)
        chapter_name = chapter_list.currentItem().data(Qt.UserRole)
        target_group = target_combo.currentText()
        if not chapter_name or not target_group or current_group == target_group:
            return
        self.move_chapter_to_group(chapter_name, target_group)

    def move_chapter_to_group(self, chapter_name: str, target_group: str, stay_on_group: str | None = None) -> None:
        if not chapter_name or not target_group:
            return
        for group, values in self.chapter_groups.items():
            if chapter_name in values:
                values.remove(chapter_name)
                break
        self.chapter_groups.setdefault(target_group, [])
        if chapter_name not in self.chapter_groups[target_group]:
            self.chapter_groups[target_group].append(chapter_name)
        self._save_chapter_grouping()
        self._refresh_grouping_ui()
        self._select_group_in_ui(stay_on_group or target_group)
        self.on_group_selected()

    def reassign_question(self, question: dict, target_group: str) -> None:
        """Reassign a single question to a different chapter."""
        if not question or not target_group:
            return
        if self.db_service is None:
            QMessageBox.warning(self, "Unavailable", "Database must be configured before regrouping questions.")
            return
        old_group = question.get("group")
        if old_group == target_group:
            return
        row_number = question.get("question_id") or question.get("row_number")
        if not isinstance(row_number, int):
            QMessageBox.warning(self, "Unavailable", "Question identifier is missing.")
            return
        qno = question.get("qno", "")
        prompt = f"Move question '{qno}' to '{target_group}'?"
        if QMessageBox.question(self, "Confirm Reassignment", prompt) != QMessageBox.Yes:
            return
        try:
            self.db_service.update_questions_chapter([row_number], target_group)
        except Exception as exc:
            QMessageBox.critical(self, "Update Failed", f"Unable to update database: {exc}")
            return
        self.log(f"Question '{qno}' moved to '{target_group}'. Reloading data...")
        self.load_subject_from_db()

    def reassign_questions(self, questions: list[dict], target_group: str) -> None:
        """Reassign multiple questions to a different chapter in bulk."""
        if not questions or not target_group:
            return
        if self.db_service is None:
            QMessageBox.warning(self, "Unavailable", "Database must be configured before regrouping questions.")
            return
        
        # Filter out questions already in target group and validate row numbers
        questions_to_move = []
        for question in questions:
            old_group = question.get("group")
            if old_group == target_group:
                continue
            row_number = question.get("question_id") or question.get("row_number")
            if not isinstance(row_number, int):
                continue
            questions_to_move.append(question)
        
        if not questions_to_move:
            return
        
        count = len(questions_to_move)
        qnos = ", ".join(q.get("qno", "") for q in questions_to_move[:3])
        if count > 3:
            qnos += f" and {count - 3} more"
        
        prompt = f"Move {count} question(s) ({qnos}) to '{target_group}'?"
        if QMessageBox.question(self, "Confirm Reassignment", prompt) != QMessageBox.Yes:
            return
        
        try:
            ids = [
                q.get("question_id") or q.get("row_number")
                for q in questions_to_move
                if isinstance(q.get("question_id") or q.get("row_number"), int)
            ]
            self.db_service.update_questions_chapter(ids, target_group)
        except Exception as exc:
            QMessageBox.critical(self, "Update Failed", f"Unable to update database: {exc}")
            return
        
        self.log(f"{count} question(s) moved to '{target_group}'. Reloading data...")
        self.load_subject_from_db()

    def on_chapter_selected(self, chapter_key: str) -> None:
        if not chapter_key:
            self._populate_question_table([])
            self.current_selected_chapter = None
            return
        self.current_selected_chapter = chapter_key
        questions = self.chapter_questions.get(chapter_key, [])
        self._populate_question_table(questions)

    def on_question_selected(self) -> None:
        if not hasattr(self, "question_tree"):
            return
        selected_items = self.question_tree.selectedItems()
        if not selected_items:
            self.question_text_view.clear()
            return
        
        # Get the first selected item
        item = selected_items[0]
        
        # Skip if it's a group header (has children)
        if item.childCount() > 0:
            self.question_text_view.clear()
            return
        
        # Get question data from UserRole
        question = item.data(0, Qt.UserRole)
        if question:
            html = (
                f"<div style='background-color: #0f172a; color: #e2e8f0; font-family: Arial, sans-serif; padding: 10px;'>"
                f"<span style='color: #60a5fa; font-weight: bold;'>Qno:</span> <span style='color: #cbd5e1;'>{question.get('qno','')}</span> &nbsp;&nbsp;"
                f"<span style='color: #60a5fa; font-weight: bold;'>Page No:</span> <span style='color: #cbd5e1;'>{question.get('page','')}</span> &nbsp;&nbsp;"
                f"<span style='color: #60a5fa; font-weight: bold;'>Question Set:</span> <span style='color: #cbd5e1;'>{question.get('question_set_name','')}</span> &nbsp;&nbsp;"
                f"<span style='color: #60a5fa; font-weight: bold;'>Magazine Edition:</span> <span style='color: #cbd5e1;'>{question.get('magazine','')}</span><br/>"
                f"<hr style='border: none; border-top: 1px solid #334155; margin: 12px 0;'/>"
                f"<div style='color: #e2e8f0; line-height: 1.7; font-size: 14px;'>{question.get('text','').replace(chr(10), '<br/>')}</div>"
                f"</div>"
            )
            self.question_text_view.setHtml(html)
    
    def _on_copy_mode_changed(self, mode: str) -> None:
        """Handle copy mode selection change."""
        self.copy_mode = mode
    
    def on_question_card_selected(self, question: dict) -> None:
        """Handle question card click in card view."""
        if not question:
            self.question_text_view.clear()
            return
        
        # Display question details in the bottom panel
        html = (
            f"<div style='background-color: #0f172a; color: #e2e8f0; font-family: Arial, sans-serif; padding: 10px;'>"
            f"<span style='color: #60a5fa; font-weight: bold;'>Qno:</span> <span style='color: #cbd5e1;'>{question.get('qno','')}</span> &nbsp;&nbsp;"
            f"<span style='color: #60a5fa; font-weight: bold;'>Page No:</span> <span style='color: #cbd5e1;'>{question.get('page','')}</span> &nbsp;&nbsp;"
            f"<span style='color: #60a5fa; font-weight: bold;'>Question Set:</span> <span style='color: #cbd5e1;'>{question.get('question_set_name','')}</span> &nbsp;&nbsp;"
            f"<span style='color: #60a5fa; font-weight: bold;'>Magazine Edition:</span> <span style='color: #cbd5e1;'>{question.get('magazine','')}</span><br/>"
            f"<span style='color: #60a5fa; font-weight: bold;'>Chapter:</span> <span style='color: #cbd5e1;'>{question.get('group','')}</span><br/>"
            f"<hr style='border: none; border-top: 1px solid #334155; margin: 12px 0;'/>"
            f"<div style='color: #e2e8f0; line-height: 1.7; font-size: 14px;'>{question.get('text','').replace(chr(10), '<br/>')}</div>"
            f"</div>"
        )
        self.question_text_view.setHtml(html)
    
    def show_group_context_menu_for_card(self, group_key: str, position):
        """Show context menu for accordion group (from card view)."""
        menu = QMenu(self)
        
        # Add tag action
        add_tag_action = menu.addAction(" Assign Tag to Group")
        
        # Remove tag submenu (if tags exist)
        existing_tags = self.question_set_group_tags.get(group_key, [])
        if existing_tags:
            remove_tag_menu = menu.addMenu(" Remove Tag from Group")
            for tag in existing_tags:
                remove_action = remove_tag_menu.addAction(tag)
                remove_action.setData(("remove", group_key, tag))
        
        # Show menu and handle action
        action = menu.exec(position)
        
        if action == add_tag_action:
            self._assign_tag_to_group(group_key)
        elif action and action.data():
            action_type, grp_key, tag = action.data()
            if action_type == "remove":
                self._remove_tag_from_group(grp_key, tag)
    
    def on_mag_question_selected(self) -> None:
        """Handle question selection in Magazine Editions tab."""
        if not hasattr(self, "question_sets_tree"):
            return
        selected_items = self.question_sets_tree.selectedItems()
        if not selected_items:
            self.mag_question_text_view.clear()
            return
        
        # Get the first selected item
        item = selected_items[0]
        
        # Skip if it's a parent item (question set)
        data = item.data(0, Qt.UserRole)
        if not data or data.get("type") != "question":
            self.mag_question_text_view.clear()
            return
        
        # Get question details from the tree item data
        qno = data.get("qno", "")
        page = data.get("page", "")
        row_num = data.get("row", 0)
        
        # Get full question data from cached DataFrame
        if self.Database_df is not None and row_num > 0:
            try:
                # Row number is 1-based Excel row, DataFrame is 0-based
                df_row_idx = row_num - 2  # Subtract 2 (1 for header, 1 for 0-based)
                
                if 0 <= df_row_idx < len(self.Database_df):
                    row_data = self.Database_df.iloc[df_row_idx]
                    
                    # Get column names
                    header_row = [None if pd.isna(col) else str(col) for col in self.Database_df.columns]
                    
                    # Find columns
                    try:
                        question_text_col = _find_question_text_column(header_row)
                        question_text = str(row_data.iloc[question_text_col - 1]) if not pd.isna(row_data.iloc[question_text_col - 1]) else ""
                    except ValueError:
                        question_text = ""
                    
                    try:
                        question_set_name_col = _find_question_set_name_column(header_row)
                        question_set_name = str(row_data.iloc[question_set_name_col - 1]) if not pd.isna(row_data.iloc[question_set_name_col - 1]) else ""
                    except ValueError:
                        question_set_name = ""
                    
                    try:
                        magazine_col = _find_magazine_column(header_row)
                        magazine = str(row_data.iloc[magazine_col - 1]) if not pd.isna(row_data.iloc[magazine_col - 1]) else ""
                    except ValueError:
                        magazine = ""
                    
                    # Display question details in same format as Question List tab
                    html = (
                        f"<div style='background-color: #0f172a; color: #e2e8f0; font-family: Arial, sans-serif; padding: 10px;'>"
                        f"<span style='color: #60a5fa; font-weight: bold;'>Qno:</span> <span style='color: #cbd5e1;'>{qno}</span> &nbsp;&nbsp;"
                        f"<span style='color: #60a5fa; font-weight: bold;'>Page No:</span> <span style='color: #cbd5e1;'>{page}</span> &nbsp;&nbsp;"
                        f"<span style='color: #60a5fa; font-weight: bold;'>Question Set:</span> <span style='color: #cbd5e1;'>{question_set_name}</span> &nbsp;&nbsp;"
                        f"<span style='color: #60a5fa; font-weight: bold;'>Magazine Edition:</span> <span style='color: #cbd5e1;'>{magazine}</span><br/>"
                        f"<hr style='border: none; border-top: 1px solid #334155; margin: 12px 0;'/>"
                        f"<div style='color: #e2e8f0; line-height: 1.7; font-size: 14px;'>{question_text.replace(chr(10), '<br/>')}</div>"
                        f"</div>"
                    )
                    self.mag_question_text_view.setHtml(html)
                else:
                    self.mag_question_text_view.clear()
            except Exception as e:
                self.log(f"Error loading question text: {e}")
                self.mag_question_text_view.clear()
        else:
            self.mag_question_text_view.clear()

    def _on_tag_badge_clicked(self, tag: str) -> None:
        """Handle tag badge click - add to filter list."""
        if tag not in self.selected_tag_filters:
            self.selected_tag_filters.append(tag)
            if hasattr(self, "tag_filter_display"):
                self.tag_filter_display.setText(", ".join(self.selected_tag_filters))
            self._apply_question_search()

    def _show_group_context_menu(self, position) -> None:
        """Show context menu for group items."""
        item = self.question_tree.itemAt(position)
        if not item:
            return
        
        # Only show menu for group items (items with children)
        if item.childCount() == 0:
            return
        
        group_key = item.data(0, Qt.UserRole + 1)
        if not group_key:
            return
        
        menu = QMenu(self.question_tree)
        
        # Add tag action
        add_tag_action = menu.addAction("Add Tag")
        
        # Remove tag actions
        existing_tags = self.group_tags.get(group_key, [])
        if existing_tags:
            remove_menu = menu.addMenu("Remove Tag")
            for tag in existing_tags:
                remove_menu.addAction(tag)
        
        action = menu.exec(self.question_tree.viewport().mapToGlobal(position))
        
        if action:
            if action.text() == "Add Tag":
                self._assign_tag_to_group(group_key)
            else:
                # Remove tag
                self._remove_tag_from_group(group_key, action.text())

    def _assign_tag_to_group(self, group_key: str) -> None:
        """Show dialog to assign multiple tags to a group."""
        # Get all existing tags across all groups
        all_tags = sorted(set(tag for tags in self.question_set_group_tags.values() for tag in tags))
        
        # Get currently assigned tags for this group
        current_tags = self.question_set_group_tags.get(group_key, [])
        
        # Show multi-select dialog
        dialog = MultiSelectTagDialog(
            all_tags, 
            current_tags, 
            f"Add Tags to '{group_key.title()}'",
            self.tag_colors,
            self.available_tag_colors,
            self
        )
        
        if dialog.exec() == QDialog.Accepted:
            selected_tags = dialog.get_selected_tags()
            if selected_tags:
                self.question_set_group_tags[group_key] = selected_tags
            self._save_group_tags()
            self._apply_question_search(preserve_scroll=True)  # Refresh tree to show new tags

    def _remove_tag_from_group(self, group_key: str, tag: str) -> None:
        """Remove a tag from a group."""
        if group_key in self.question_set_group_tags and tag in self.question_set_group_tags[group_key]:
            self.question_set_group_tags[group_key].remove(tag)
            if not self.question_set_group_tags[group_key]:
                # Remove empty tag list
                del self.question_set_group_tags[group_key]
            self._save_group_tags()
            self._apply_question_search(preserve_scroll=True)  # Refresh tree to update display
        else:
            self.question_text_view.clear()

    def _load_saved_question_lists(self) -> None:
        """Load all saved question lists from QuestionList folder."""
        if not hasattr(self, "saved_lists_widget"):
            return
        
        self.saved_lists_widget.clear()
        self.question_lists.clear()
        self.question_lists_metadata.clear()
        
        lists_data = {}
        metadata = {}
        if self.db_service:
            try:
                lists_data, metadata = self.db_service.load_question_lists()
            except Exception as exc:
                self.log(f"Error loading lists from database: {exc}")
        
        for list_name, questions in sorted(lists_data.items(), key=lambda kv: kv[0].lower()):
            meta = metadata.get(list_name, {})
            self.question_lists[list_name] = questions
            self.question_lists_metadata[list_name] = meta

            display_text = f"{list_name} ({len(questions)})"
            magazine = meta.get("magazine", "")
            if magazine:
                display_text += f" - {magazine}"

            item = QListWidgetItem()
            item.setData(Qt.UserRole, list_name)

            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(6, 2, 6, 2)
            row_layout.setSpacing(6)

            label = QLabel(display_text)
            label.setStyleSheet("color: #0f172a; font-weight: 600;")
            row_layout.addWidget(label, 1)

            reload_btn = QPushButton()
            reload_btn.setToolTip(f"Reload '{list_name}' from database")
            reload_btn.setFixedSize(28, 28)
            reload_btn.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
            reload_btn.setStyleSheet(
                "QPushButton { background-color: #e0f2fe; border: 1px solid #93c5fd; "
                "border-radius: 4px; } QPushButton:hover { background-color: #bfdbfe; }"
            )
            reload_btn.clicked.connect(lambda _, name=list_name: self._reload_question_list(name))
            row_layout.addWidget(reload_btn, 0, Qt.AlignRight)

            self.saved_lists_widget.addItem(item)
            self.saved_lists_widget.setItemWidget(item, row_widget)
            item.setSizeHint(row_widget.sizeHint())
        
        # Trigger selection of first item if any lists loaded
        if self.saved_lists_widget.count() > 0:
            self.saved_lists_widget.setCurrentRow(0)
        
        # Update drag-drop panel dropdown with loaded lists
        self.drag_drop_panel.update_list_selector(self.question_lists)
        self._refresh_compare_options()

    def _reload_question_list(self, list_name: str) -> None:
        """Reload a single custom list from the database and refresh the UI row."""
        target = list_name
        self._load_saved_question_lists()

        # Restore selection to the reloaded list if it still exists
        for idx in range(self.saved_lists_widget.count()):
            item = self.saved_lists_widget.item(idx)
            if item.data(Qt.UserRole) == target:
                self.saved_lists_widget.setCurrentRow(idx)
                self.log(f"Reloaded list '{target}' from database")
                return

        QMessageBox.information(
            self,
            "List Missing",
            f"The list '{target}' no longer exists in the database.",
        )
    
    def _save_question_list(self, list_name: str, save_filters: bool = False) -> None:
        """Save a question list to file.
        
        Args:
            list_name: Name of the list to save
            save_filters: If True, save current active filters with the list
        """
        if list_name not in self.question_lists:
            return
        
        # Get or create metadata
        metadata = self.question_lists_metadata.get(list_name, {})
        
        data = {
            "name": list_name,
            "magazine": metadata.get("magazine", self.current_magazine_name),
            "questions": self.question_lists[list_name],
        }
        
        # Save filters if requested or if they already exist
        if save_filters or metadata.get("filters"):
            filters = self._get_active_filters() if save_filters else metadata.get("filters", {})
            if filters:
                data["filters"] = filters
                metadata["filters"] = filters
        
        try:
            if self.db_service:
                self.db_service.save_question_list(list_name, self.question_lists[list_name], metadata)
            self.log(f"Saved question list: {list_name}")
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", f"Failed to save list: {exc}")
    
    def create_new_question_list(self) -> None:
        """Create a new question list."""
        from PySide6.QtWidgets import QInputDialog
        
        list_name, ok = QInputDialog.getText(self, "New Question List", "Enter list name:")
        if not ok or not list_name.strip():
            return
        
        list_name = list_name.strip()
        if list_name in self.question_lists:
            QMessageBox.warning(self, "Duplicate Name", f"A list named '{list_name}' already exists.")
            return
        
        self.question_lists[list_name] = []
        self._save_question_list(list_name)
        self._load_saved_question_lists()
        self.drag_drop_panel.update_list_selector(self.question_lists)
        self.log(f"Created new question list: {list_name}")
    
    def rename_question_list(self) -> None:
        """Rename selected question list."""
        from PySide6.QtWidgets import QInputDialog
        
        current_item = self.saved_lists_widget.currentItem()
        if not current_item:
            QMessageBox.information(self, "No Selection", "Please select a list to rename.")
            return
        
        old_name = current_item.data(Qt.UserRole)
        new_name, ok = QInputDialog.getText(self, "Rename List", "Enter new name:", text=old_name)
        if not ok or not new_name.strip():
            return
        
        new_name = new_name.strip()
        if new_name == old_name:
            return
        
        if new_name in self.question_lists:
            QMessageBox.warning(self, "Duplicate Name", f"A list named '{new_name}' already exists.")
            return
        
        # Update data structure and persist to DB
        questions = self.question_lists.pop(old_name)
        meta = self.question_lists_metadata.pop(old_name, {})
        self.question_lists[new_name] = questions
        self.question_lists_metadata[new_name] = meta
        if self.db_service:
            try:
                self.db_service.delete_question_list(old_name)
            except Exception:
                pass
        self._save_question_list(new_name)
        self._load_saved_question_lists()
        self.drag_drop_panel.update_list_selector(self.question_lists)
        self.log(f"Renamed list from '{old_name}' to '{new_name}'")
    
    def delete_question_list(self) -> None:
        """Delete selected question list."""
        current_item = self.saved_lists_widget.currentItem()
        if not current_item:
            QMessageBox.information(self, "No Selection", "Please select a list to delete.")
            return
        
        list_name = current_item.data(Qt.UserRole)
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete the list '{list_name}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        
        if self.db_service:
            self.db_service.delete_question_list(list_name)
        
        # Update data structure
        del self.question_lists[list_name]
        self.question_lists_metadata.pop(list_name, None)
        self._load_saved_question_lists()
        self.drag_drop_panel.update_list_selector(self.question_lists)
        self.current_list_name = None
        self.list_name_label.setText("Select a list to view questions")
        self.list_filters_label.setVisible(False)
        if hasattr(self, "_list_card_grid_layout"):
            while self._list_card_grid_layout.count():
                item = self._list_card_grid_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        self._refresh_compare_options()
        self.log(f"Deleted question list: {list_name}")

    def _current_list_name(self) -> str | None:
        item = self.saved_lists_widget.currentItem()
        if not item:
            return None
        return item.data(Qt.UserRole)

    def _open_theory_dialog(self) -> None:
        list_name = self._current_list_name()
        if not list_name:
            QMessageBox.information(self, "No List Selected", "Please select a list first.")
            return
        existing = ""
        try:
            existing = self.db_service.get_list_theory(list_name) if self.db_service else ""
        except Exception as exc:
            QMessageBox.warning(self, "Load Failed", f"Could not load theory text:\n{exc}")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Upload Theory - {list_name}")
        dlg_layout = QVBoxLayout(dialog)

        info_lbl = QLabel("Paste LaTeX content below. It will be saved with this list.")
        info_lbl.setStyleSheet("color: #0f172a; font-weight: 600;")
        dlg_layout.addWidget(info_lbl)

        text_edit = QTextEdit()
        text_edit.setPlainText(existing)
        text_edit.setStyleSheet("font-family: Consolas, 'Courier New', monospace;")
        dlg_layout.addWidget(text_edit, 1)

        btn_row = QHBoxLayout()
        paste_btn = QPushButton("Paste")
        paste_btn.clicked.connect(lambda: text_edit.paste())
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        btn_row.addWidget(paste_btn)
        btn_row.addStretch()
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        dlg_layout.addLayout(btn_row)

        save_btn.clicked.connect(lambda: self._save_theory_text(dialog, list_name, text_edit.toPlainText()))
        cancel_btn.clicked.connect(dialog.reject)

        dialog.resize(620, 520)
        dialog.exec()

    def _save_theory_text(self, dialog: QDialog, list_name: str, text: str) -> None:
        try:
            if self.db_service:
                self.db_service.set_list_theory(list_name, text)
            self.question_lists_metadata.setdefault(list_name, {})["theory_latex"] = text
        except Exception as exc:
            QMessageBox.warning(self, "Save Failed", f"Could not save theory:\n{exc}")
            return
        self.statusBar().showMessage(f"Saved theory for list '{list_name}'", 4000)
        dialog.accept()

    def _download_theory_pdf(self) -> None:
        list_name = self._current_list_name()
        if not list_name:
            QMessageBox.information(self, "No List Selected", "Please select a list first.")
            return
        try:
            tex_source = self.db_service.get_list_theory(list_name) if self.db_service else ""
        except Exception as exc:
            QMessageBox.warning(self, "Load Failed", f"Could not load theory:\n{exc}")
            return
        if not tex_source.strip():
            QMessageBox.information(self, "No Theory", "No theory text available for this list.")
            return

        latex_path = shutil.which("lualatex") or r"C:\Users\senap\AppData\Local\Programs\MiKTeX\miktex\bin\x64\lualatex.exe"
        latex_path = latex_path if latex_path and Path(latex_path).exists() else None
        if not latex_path:
            save_path, _ = QFileDialog.getSaveFileName(self, "Save LaTeX Source", f"{list_name}.tex", "TeX files (*.tex)")
            if not save_path:
                return
            try:
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(tex_source)
            except Exception as exc:
                QMessageBox.warning(self, "Save Failed", f"Could not save .tex file:\n{exc}")
            return

        with tempfile.TemporaryDirectory() as tmpdir:
            tex_path = Path(tmpdir) / "theory.tex"
            try:
                tex_path.write_text(tex_source, encoding="utf-8")
            except Exception as exc:
                QMessageBox.warning(self, "Write Failed", f"Could not write temp .tex:\n{exc}")
                return
            try:
                subprocess.run(
                    [latex_path, "-interaction=nonstopmode", tex_path.name],
                    cwd=tex_path.parent,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception as exc:
                QMessageBox.warning(self, "PDF Failed", f"pdflatex failed:\n{exc}")
                return
            pdf_path = tex_path.with_suffix(".pdf")
            if not pdf_path.exists():
                QMessageBox.warning(self, "PDF Failed", "PDF was not generated.")
                return
            save_path, _ = QFileDialog.getSaveFileName(self, "Save Theory PDF", f"{list_name}.pdf", "PDF files (*.pdf)")
            if not save_path:
                return
            try:
                shutil.copy2(pdf_path, save_path)
                QMessageBox.information(self, "Saved", f"Saved PDF to:\n{save_path}")
            except Exception as exc:
                QMessageBox.warning(self, "Save Failed", f"Could not save PDF:\n{exc}")
    
    def add_selected_to_list(self) -> None:
        """Toggle the drag-drop panel for adding questions to a list."""
        if not self.question_lists:
            reply = QMessageBox.question(
                self,
                "No Lists",
                "No question lists exist. Create a new list?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self.create_new_question_list()
            return
        
        # Toggle drag-drop panel visibility
        self.drag_drop_panel.setVisible(not self.drag_drop_panel.isVisible())
        
        # Update panel with current question lists
        if self.drag_drop_panel.isVisible():
            from src.ui.widgets import DragDropQuestionPanel
            # Recreate panel with updated question lists
            old_panel = self.drag_drop_panel
            self.drag_drop_panel = DragDropQuestionPanel(self.question_lists, self)
            self.drag_drop_panel.save_clicked.connect(self._on_drag_drop_save)
            self.drag_drop_panel.cancel_clicked.connect(self._on_drag_drop_cancel)
            
            # Replace in layout
            question_layout = old_panel.parent().layout()
            for i in range(question_layout.count()):
                if question_layout.itemAt(i).widget() == old_panel:
                    old_panel.deleteLater()
                    question_layout.insertWidget(i, self.drag_drop_panel)
                    break
    
    def _on_drag_drop_save(self, list_name: str, questions: list):
        """Handle save from drag-drop panel."""
        added_count = 0
        for question in questions:
            # Check for duplicates based on row_number
            if not any(q.get("row_number") == question.get("row_number") for q in self.question_lists[list_name]):
                self.question_lists[list_name].append(question.copy())
                added_count += 1
        
        self._save_question_list(list_name)
        self._load_saved_question_lists()
        self.log(f"Added {added_count} question(s) to list '{list_name}'")
        QMessageBox.information(self, "Success", f"Added {added_count} question(s) to '{list_name}'.")
        
        # Hide panel
        self.drag_drop_panel.setVisible(False)
    
    def _on_drag_drop_cancel(self):
        """Handle cancel from drag-drop panel."""
        self.drag_drop_panel.setVisible(False)
    
    def _highlight_question_card(self, question_data: dict):
        """Highlight the corresponding question card with yellow background."""
        from PySide6.QtCore import QTimer
        
        # Find and highlight the card in the question card view
        for group in self.question_card_view.accordion_groups:
            for card in group.get_all_cards():
                if card.question_data.get("row_number") == question_data.get("row_number"):
                    # Expand accordion group if collapsed
                    if not group.is_expanded:
                        group.toggle_expanded()
                    
                    # Temporarily highlight with yellow
                    card.setStyleSheet("""
                        QLabel {
                            background-color: #fef08a;
                            border: 3px solid #eab308;
                            border-radius: 8px;
                            padding: 12px;
                            margin: 4px;
                        }
                    """)
                    
                    # Reset after 2 seconds
                    def reset_card_style():
                        if card.is_selected:
                            card.set_selected(True)
                        else:
                            card.setStyleSheet(card.original_stylesheet)
                    
                    QTimer.singleShot(2000, reset_card_style)
                    
                    # Scroll to make the card visible
                    self.question_card_view.ensureWidgetVisible(card)
                    return
    
    def _remove_question_from_list(self, question: dict) -> None:
        """Remove a single question from current list (called from remove button on card)."""
        if not self.current_list_name:
            QMessageBox.information(self, "No List Selected", "Please select a list first.")
            return
        
        # Find and remove the question by qno
        qno = question.get('qno')
        questions = self.question_lists[self.current_list_name]
        
        for idx, q in enumerate(questions):
            if q.get('qno') == qno:
                del questions[idx]
                self._save_question_list(self.current_list_name)
                self.on_saved_list_selected()  # Refresh display
                self.log(f"Removed question Q{qno} from '{self.current_list_name}'")
                return
        
        QMessageBox.warning(self, "Not Found", f"Question Q{qno} not found in list.")
    
    def _populate_list_card_view(self, questions: list[dict]) -> None:
        """Populate card view with 2-column grid of question cards from custom list using QuestionCardWithRemoveButton wrapper."""
        if not questions:
            return
        
        # Clear existing layout
        if not hasattr(self, '_list_card_grid_widget'):
            # Create a new grid widget for 2-column layout
            self._list_card_grid_widget = QWidget()
            self._list_card_grid_layout = QGridLayout(self._list_card_grid_widget)
            self._list_card_grid_layout.setSpacing(12)
            self._list_card_grid_layout.setContentsMargins(0, 0, 0, 0)
            
            # Set the grid widget in scroll area
            self.list_question_card_view.setWidget(self._list_card_grid_widget)
        else:
            # Clear existing cards from grid
            while self._list_card_grid_layout.count():
                item = self._list_card_grid_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        
        # Add question cards in 2-column grid using QuestionCardWithRemoveButton wrapper
        sorted_questions = sorted(questions, key=self._get_question_sort_key)
        for idx, question in enumerate(sorted_questions):
            card_wrapper = QuestionCardWithRemoveButton(question, self)
            card_wrapper.clicked.connect(lambda q=question: self.on_list_question_card_selected(q))
            card_wrapper.remove_requested.connect(lambda q=question: self._remove_question_from_list(q))
            card_wrapper.column_index = idx % 2

            if self._is_common_question(question):
                self._mark_card_as_common(card_wrapper)

            row = idx // 2
            col = idx % 2
            self._list_card_grid_layout.addWidget(card_wrapper, row, col)
        
        # Add stretch to push cards to top
        self._list_card_grid_layout.addItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding), 
                                           len(questions) // 2 + 1, 0, 1, 2)
    
    def _create_list_question_card(self, question: dict) -> QWidget:
        """Create a single question card widget for custom list (deprecated - use QuestionCardWidget directly)."""
        # This method is deprecated - use QuestionCardWidget from widgets.py instead
        pass
    
    def on_list_question_set_search_changed(self, text: str) -> None:
        """Handle question set search change in custom list."""
        self.list_question_set_search_term = text.strip()
        self._apply_list_search()
    
    def on_list_tag_filter_changed(self) -> None:
        """Handle tag filter change in custom list."""
        self._apply_list_search()
    
    def _apply_list_search(self) -> None:
        """Apply search/filter to custom list questions."""
        if (
            not self.current_list_name
            or self.current_list_name not in self.question_lists
            or not hasattr(self, '_list_card_grid_layout')
        ):
            return
        
        questions = self.question_lists[self.current_list_name]
        if not questions:
            return
        
        filtered = questions
        
        # Apply question set search
        if self.list_question_set_search_term:
            normalized_search = self._normalize_label(self.list_question_set_search_term)
            filtered = [
                q for q in filtered
                if normalized_search in self._normalize_label(q.get("question_set_name", ""))
            ]
        
        # Clear and repopulate card view
        while self._list_card_grid_layout.count():
            item = self._list_card_grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if filtered:
            self._populate_list_card_view(filtered)
    
    def _refresh_compare_options(self) -> None:
        """Populate comparison dropdown with other available lists."""
        if not hasattr(self, "compare_list_combo"):
            return
        
        current_list = self.current_list_name
        previous_target = self.comparison_target if self.comparison_target != current_list else None
        
        self.compare_list_combo.blockSignals(True)
        self.compare_list_combo.clear()
        self.compare_list_combo.addItem("No comparison", None)
        
        for name in sorted(self.question_lists.keys()):
            if name == current_list:
                continue
            self.compare_list_combo.addItem(name, name)
        
        # Restore previous target if still valid
        target_index = 0
        if previous_target:
            for idx in range(self.compare_list_combo.count()):
                if self.compare_list_combo.itemData(idx) == previous_target:
                    target_index = idx
                    break
        
        self.compare_list_combo.setCurrentIndex(target_index)
        self.compare_list_combo.blockSignals(False)
        
        self.comparison_target = self.compare_list_combo.currentData()
        self.comparison_common_ids.clear()
        self.compare_status_label.setVisible(False)
    
    def on_compare_list_changed(self, index: int) -> None:
        """Handle selection of comparison list."""
        if not self.current_list_name:
            self.compare_status_label.setText("Select a list on the left to compare.")
            self.compare_status_label.setVisible(True)
            return
        
        self.comparison_target = self.compare_list_combo.itemData(index)
        self._update_comparison_results()
    
    def _update_comparison_results(self) -> None:
        """Compute and highlight questions common with the comparison list."""
        self.comparison_common_ids.clear()
        
        if (
            not self.current_list_name
            or self.current_list_name not in self.question_lists
            or not self.comparison_target
        ):
            self.compare_status_label.setVisible(False)
            if hasattr(self, "_list_card_grid_layout"):
                self._apply_list_search()
            return
        
        base_questions = self.question_lists.get(self.current_list_name, [])
        target_questions = self.question_lists.get(self.comparison_target, [])
        
        target_ids = {self._get_question_identity(q) for q in target_questions}
        self.comparison_common_ids = {
            self._get_question_identity(q) for q in base_questions
            if self._get_question_identity(q) in target_ids
        }
        
        self.compare_status_label.setText(
            f"Common with '{self.comparison_target}': {len(self.comparison_common_ids)} highlighted."
        )
        self.compare_status_label.setVisible(True)
        
        # Repaint cards to show highlights
        self._apply_list_search()
    
    def _get_question_identity(self, question: dict) -> str:
        """Return a stable identifier for a question for comparisons."""
        row_number = question.get("question_id") or question.get("row_number")
        if row_number is not None:
            return f"row-{row_number}"
        
        qno = question.get("qno", question.get("question_no", ""))
        question_set = self._normalize_label(question.get("question_set_name", ""))
        magazine = self._normalize_label(question.get("magazine", ""))
        return f"{qno}|{question_set}|{magazine}"

    def _parse_magazine_date(self, magazine_label: str) -> tuple[int, int]:
        """
        Extract (year, month) from magazine string like "Physics For You | May '25".
        Returns (9999, 99) when parsing fails to push unknowns to the end.
        """
        year = 9999
        month = 99
        try:
            if "|" in magazine_label:
                parts = magazine_label.split("|", 1)[1].strip()
                # Expect formats like "May '25" or "May 2025"
                tokens = parts.replace("’", "'").split()
                if tokens:
                    month_name = tokens[0][:3].lower()
                    month_map = {
                        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
                        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
                    }
                    month = month_map.get(month_name, 99)
                    for token in tokens[1:]:
                        token_clean = token.strip("' ")
                        if token_clean.isdigit():
                            y = int(token_clean)
                            year = 2000 + y if y < 100 else y
                            break
                    # If month not found, try numeric fallback in tokens
                    if month == 99:
                        for token in tokens:
                            try:
                                m_val = int(token.strip("' "))
                                if 1 <= m_val <= 12:
                                    month = m_val
                                    break
                            except Exception:
                                continue
        except Exception:
            pass
        return (year, month)

    def _get_question_sort_key(self, question: dict):
        """Sort by magazine year, then month, then page number, then question number."""
        magazine_raw = str(question.get("magazine", "")).strip()
        magazine_norm = self._normalize_label(magazine_raw)

        year, month = self._parse_magazine_date(magazine_raw)

        def _to_number(val, default=999999):
            text = str(val or "").strip()
            if "-" in text:
                text = text.split("-")[0].strip()
            try:
                return float(re.sub(r"[^0-9.]", "", text)) if re.search(r"\d", text) else default
            except Exception:
                return default

        page = _to_number(question.get("page"))
        qno = _to_number(question.get("qno"))
        return (year, month, magazine_norm, page, qno)

    def _is_common_question(self, question: dict) -> bool:
        """Check if question is common with comparison target."""
        if not self.comparison_common_ids:
            return False
        return self._get_question_identity(question) in self.comparison_common_ids
    
    def _mark_card_as_common(self, card_wrapper: QuestionCardWithRemoveButton) -> None:
        """Visually distinguish a card that exists in both lists."""
        badge_text = f"Common with {self.comparison_target}" if self.comparison_target else "Common question"
        badge = QLabel(badge_text)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            "background-color: #06b6d4; color: white; border-radius: 10px; padding: 4px 10px; font-weight: 600;"
        )
        badge.setMaximumHeight(26)
        
        # Insert badge above the card
        layout = card_wrapper.layout()
        layout.insertWidget(0, badge)
        
        # Apply a teal highlight style to the underlying card
        card_wrapper.card.setStyleSheet("""
            QLabel {
                background-color: #ecfeff;
                border: 2px dashed #0ea5e9;
                border-radius: 10px;
                padding: 12px;
                margin: 4px;
            }
            QLabel:hover {
                background-color: #cffafe;
                border: 2px solid #0284c7;
            }
        """)
        card_wrapper.card.setToolTip(badge_text)
    
    def clear_list_search(self) -> None:
        """Clear search in custom list."""
        self.list_question_set_search.clear()
        self.list_question_set_search_term = ""
        self._apply_list_search()
    
    def _on_list_copy_mode_changed(self, mode: str) -> None:
        """Handle copy mode selection change in custom list."""
        self.list_copy_mode = mode
    
    def export_current_list_to_pdf(self) -> None:
        """Create a PDF with metadata and embedded question/answer images for the selected list."""
        if not self.current_list_name or self.current_list_name not in self.question_lists:
            QMessageBox.information(self, "No List Selected", "Select a custom list before exporting.")
            return
        
        questions = self.question_lists.get(self.current_list_name, [])
        if not questions:
            QMessageBox.information(self, "Empty List", "The selected list has no questions to export.")
            return
        
        try:
            from fpdf import FPDF
        except ImportError:
            QMessageBox.critical(
                self,
                "Missing Dependency",
                "fpdf2 is required to export PDF files.\nInstall it with: pip install fpdf2",
            )
            return
        
        default_name = f"{self.current_list_name}.pdf"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Question PDF",
            default_name,
            "PDF Files (*.pdf)",
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".pdf"):
            file_path += ".pdf"
        
        def _numeric_sort_value(value) -> float:
            """Convert page/question numbers to numeric values for sorting."""
            if value is None:
                return float("inf")
            text = str(value).strip()
            if not text:
                return float("inf")
            match = re.search(r"[-+]?\d*\.?\d+", text)
            if match:
                try:
                    return float(match.group())
                except ValueError:
                    pass
            return float("inf")

        def _question_sort_key(item: tuple[int, dict]) -> tuple:
            idx, question = item
            magazine_raw = (
                question.get("magazine")
                or question.get("magazine_name")
                or question.get("edition")
                or ""
            )
            magazine_key = normalize_magazine_edition(str(magazine_raw))
            page_value = question.get("page") or question.get("Page") or question.get("page_no")
            qno_value = question.get("qno") or question.get("question_no")
            
            return (
                0 if magazine_key else 1,
                magazine_key,
                _numeric_sort_value(page_value),
                _numeric_sort_value(qno_value),
                idx,  # stable ordering for identical keys
            )

        sorted_questions = [q for _, q in sorted(enumerate(questions), key=_question_sort_key)]

        # Debug: log final sorted metadata to help verify ordering
        self.log("PDF export order (magazine | page -> qno):")
        for pos, q in enumerate(sorted_questions, start=1):
            mag_raw = q.get("magazine") or q.get("magazine_name") or q.get("edition") or ""
            mag_norm = normalize_magazine_edition(str(mag_raw))
            page_raw = q.get("page") or q.get("Page") or q.get("page_no")
            qno_raw = q.get("qno") or q.get("question_no")
            self.log(
                f"{pos:03d}: mag='{mag_raw}' (norm='{mag_norm}') "
                f"page='{page_raw}' (num={_numeric_sort_value(page_raw)}) "
                f"qno='{qno_raw}' (num={_numeric_sort_value(qno_raw)})"
            )

        pdf = FPDF(format="A4")
        pdf.set_auto_page_break(auto=True, margin=15)
        page_width = pdf.w - 2 * pdf.l_margin
        title_font = "Helvetica"
        body_font = "Helvetica"

        # Try to register a Unicode-capable font so we don't choke on en dashes, etc.
        unicode_fonts = [
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("C:/Windows/Fonts/arialuni.ttf"),
        ]
        unicode_font = next((p for p in unicode_fonts if p.exists()), None)
        if unicode_font:
            try:
                pdf.add_font("AppUnicode", "", str(unicode_font), uni=True)
                bold_candidate = Path("C:/Windows/Fonts/arialbd.ttf")
                bold_font = bold_candidate if bold_candidate.exists() else unicode_font
                pdf.add_font("AppUnicode", "B", str(bold_font), uni=True)
                title_font = "AppUnicode"
                body_font = "AppUnicode"
            except Exception as exc:
                self.log(f"Unicode font registration failed, falling back to Helvetica: {exc}")

        def _safe_multicell(
            text: str,
            height: float = 8,
            font: tuple[str, str, int] | None = None,
        ) -> None:
            """Write text safely, forcing a sane width and replacing unsupported chars if needed."""
            if font:
                fname, style, size = font
                pdf.set_font(fname, style, size)
            width = max(20, page_width)  # avoid zero/negative widths
            pdf.set_x(pdf.l_margin)  # reset X so width calculation is correct
            try:
                pdf.multi_cell(width, height, text)
            except Exception:
                sanitized = str(text).encode("latin-1", "replace").decode("latin-1")
                pdf.multi_cell(width, height, sanitized)

        for idx, question in enumerate(sorted_questions, start=1):
            pdf.add_page()
            pdf.set_font(title_font, "B", 14)
            pdf.cell(0, 10, f"Question {idx}", ln=1)

            # Metadata in a single compact line
            pdf.set_font(body_font, "", 8)  # compact metadata
            qno = question.get("qno") or question.get("question_no") or ""
            page_val = question.get("page") or question.get("Page") or question.get("page_no") or ""
            qset = question.get("question_set_name") or question.get("question_set") or ""
            magazine = question.get("magazine") or question.get("magazine_name") or question.get("edition") or ""
            meta_parts = [
                f"Q{qno}" if qno else "Q?",
                f"P{page_val}" if page_val else "P?",
                qset or "Unknown",
                magazine or "Unknown",
            ]
            meta_line = " | ".join(str(p).strip() for p in meta_parts)
            _safe_multicell(meta_line)

            qid = question.get("question_id") or question.get("row_number")
            if qid and self.db_service:
                try:
                    question_images = self.db_service.get_images(int(qid), "question")
                except Exception as exc:
                    self.log(f"Could not load images for question {qid}: {exc}")
                    question_images = []

                def _mime_to_fpdf_type(mime: str) -> str | None:
                    mime = (mime or "").lower()
                    if "png" in mime:
                        return "PNG"
                    if "jpeg" in mime or "jpg" in mime:
                        return "JPEG"
                    return None

                def _add_images(title: str, images: list[dict]) -> None:
                    if not images:
                        return
                    pdf.ln(2)
                    pdf.set_font(body_font, "B", 9)
                    for img in images:
                        img_type = _mime_to_fpdf_type(img.get("mime_type"))
                        if not img_type:
                            self.log(f"Skipping image with unsupported type: {img.get('mime_type')}")
                            continue
                        img_bytes = img.get("data")
                        if not img_bytes:
                            continue
                        stream = BytesIO(img_bytes)
                        stream.seek(0)
                        try:
                            pdf.image(stream, w=0, type=img_type)
                        except Exception as exc:
                            self.log(f"Failed to embed image in PDF: {exc}")
                    pdf.ln(2)

                _add_images("", question_images)

            # Draw a boundary line after each question block
            pdf.ln(2)
            y = pdf.get_y()
            pdf.set_draw_color(180, 180, 180)
            pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
            pdf.ln(2)

        try:
            pdf.output(file_path)
            QMessageBox.information(self, "Exported", f"Saved PDF to:\n{file_path}")
            self.log(f"Exported '{self.current_list_name}' to PDF: {file_path}")
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", f"Could not save PDF: {exc}")

    def export_current_list_to_cqt(self) -> None:
        """Export selected custom list to password-protected .cqt package."""
        if not self.current_list_name or self.current_list_name not in self.question_lists:
            QMessageBox.information(self, "No List Selected", "Select a custom list before exporting.")
            return

        questions = self.question_lists.get(self.current_list_name, [])
        if not questions:
            QMessageBox.information(self, "Empty List", "The selected list has no questions to export.")
            return

        # Auto-generate passwords (6 digits)
        password = f"{secrets.randbelow(900000) + 100000:06d}"
        eval_password = f"{secrets.randbelow(900000) + 100000:06d}"

        # Ask where to save
        default_name = f"{self.current_list_name}.cqt"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save CBT Package",
            default_name,
            "CBT Package (*.cqt)",
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".cqt"):
            file_path += ".cqt"

        # Build questions payload with images
        packaged_questions = []
        import base64
        for q in questions:
            qid = q.get("question_id")
            question_images = []
            answer_images = []
            if qid:
                try:
                    imgs = self.db_service.get_images(int(qid), "question")
                    ans_imgs = self.db_service.get_images(int(qid), "answer")
                    for img in imgs:
                        question_images.append(
                            {
                                "mime": img.get("mime_type", "application/octet-stream"),
                                "data": base64.b64encode(img.get("data") or b"").decode("ascii"),
                            }
                        )
                    for img in ans_imgs:
                        answer_images.append(
                            {
                                "mime": img.get("mime_type", "application/octet-stream"),
                                "data": base64.b64encode(img.get("data") or b"").decode("ascii"),
                            }
                        )
                except Exception:
                    pass

            packaged_questions.append(
                {
                    "question_id": qid,
                    "qno": q.get("qno"),
                    "page": q.get("page"),
                    "question_set_name": q.get("question_set_name"),
                    "magazine": q.get("magazine"),
                    "chapter": q.get("chapter"),
                    "high_level_chapter": q.get("high_level_chapter"),
                    "text": q.get("text", ""),
                    "answer_text": q.get("answer_text", ""),
                    "question_images": question_images,
                    "answer_images": answer_images,
                    "correct_options": q.get("correct_options", []),
                    "numerical_answer": q.get("numerical_answer", ""),
                    "question_type": q.get("question_type", "mcq_single"),
                    "options": [
                        {"label": "A", "text": ""},
                        {"label": "B", "text": ""},
                        {"label": "C", "text": ""},
                        {"label": "D", "text": ""},
                    ],
                }
            )

        # Author preview to set correct options / view answer images
        preview = CQTAuthorPreviewDialog(packaged_questions, self)
        if preview.exec() != QDialog.Accepted:
            return
        packaged_questions = preview.apply_updates()

        payload = build_payload(self.current_list_name, packaged_questions)
        # Add evaluation password hash
        payload_dict = json.loads(payload.decode("utf-8"))
        payload_dict["evaluation_protection"] = hash_eval_password(eval_password)
        payload = json.dumps(payload_dict, ensure_ascii=False, indent=2).encode("utf-8")
        try:
            save_cqt(file_path, payload, password)
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", f"Could not export CBT package:\n{exc}")
            return

        QMessageBox.information(
            self,
            "Export Complete",
            f"Saved CBT package to:\n{file_path}\n\nExam password: {password}\nEvaluation password: {eval_password}",
        )
    
    def on_saved_list_selected(self) -> None:
        """Handle selection of a saved question list."""
        current_item = self.saved_lists_widget.currentItem()
        if not current_item:
            self.list_name_label.setText("Select a list to view questions")
            self.current_list_name = None
            self.list_filters_label.setVisible(False)
            if hasattr(self, "_list_card_grid_layout"):
                while self._list_card_grid_layout.count():
                    item = self._list_card_grid_layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
            self.drag_drop_panel.display_existing_questions([])
            # Hide panel if no list selected
            self.drag_drop_panel.setVisible(False)
            self._refresh_compare_options()
            return

        self._show_list_loading(True)
        list_name = current_item.data(Qt.UserRole)
        try:
            self.current_list_name = list_name
            self._refresh_compare_options()
            self._populate_list_question_table(list_name)
            self._update_comparison_results()

            # Display existing questions in drag-drop panel
            if list_name in self.question_lists:
                questions = self.question_lists[list_name]
                self.drag_drop_panel.display_existing_questions(questions)
                # Show the panel to display existing questions
                self.drag_drop_panel.setVisible(True)
        finally:
            self._show_list_loading(False)
    
    def _populate_list_question_table(self, list_name: str) -> None:
        """Populate the list question card view with questions from the selected list."""
        if list_name not in self.question_lists:
            return
        
        questions = self.question_lists[list_name]
        self.current_list_questions = questions
        self.list_name_label.setText(f"{list_name} ({len(questions)} questions)")
        
        # Show filters if they exist
        metadata = self.question_lists_metadata.get(list_name, {})
        filters = metadata.get("filters", {})
        if filters:
            filter_parts = []
            if filters.get("selected_chapter"):
                filter_parts.append(f"Chapter: '{filters['selected_chapter']}'")
            if filters.get("advanced_query"):
                filter_parts.append(f"Query: {filters['advanced_query']}")
            if filters.get("selected_tags"):
                filter_parts.append(f"Tags: {', '.join(filters['selected_tags'])}")
            
            if filter_parts:
                self.list_filters_label.setText(f" Filters: {' | '.join(filter_parts)}")
                self.list_filters_label.setVisible(True)
            else:
                self.list_filters_label.setVisible(False)
        else:
            self.list_filters_label.setVisible(False)
        
        # Clear existing card grid
        if hasattr(self, '_list_card_grid_layout'):
            while self._list_card_grid_layout.count():
                item = self._list_card_grid_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        
        # Reset search state for custom lists
        self.list_question_set_search_term = ""
        self.list_question_set_search.clear()
        
        if not questions:
            return
        
        # Populate card view with 2-column grid
        self._populate_list_card_view(questions)
        
        # Show drag-drop panel with existing questions
        if list_name in self.question_lists:
            self.drag_drop_panel.display_existing_questions(questions)
            self.drag_drop_panel.setVisible(True)
    
    def on_list_question_selected(self) -> None:
        """Handle selection of a question in the list question table (old method - kept for compatibility)."""
        # This method is no longer used with card view, but kept for reference
        pass
    
    def on_list_question_card_selected(self, question: dict) -> None:
        """Handle question card click in custom list card view."""
        # Card selection used for information only - no separate text view needed
        pass
    
    def _get_active_filters(self) -> dict:
        """Get currently active filters in Question Analysis tab."""
        filters = {}
        
        # Selected chapter filter (from left table)
        if self.current_selected_chapter:
            filters["selected_chapter"] = self.current_selected_chapter
        
        # Advanced query filter
        if getattr(self, "advanced_query_term", ""):
            filters["advanced_query"] = self.advanced_query_term
        
        # Tag filters
        if self.selected_tag_filters:
            filters["selected_tags"] = self.selected_tag_filters.copy()
        
        return filters
    
    def create_random_list_from_filtered(self) -> None:
        """Create a new question list with random questions from currently filtered list."""
        from PySide6.QtWidgets import QInputDialog, QDialog, QVBoxLayout, QLabel, QSpinBox, QDialogButtonBox
        
        # Get all visible questions from current filtered view
        visible_questions = []
        
        # Collect questions from card view instead of tree
        if hasattr(self, 'question_card_view'):
            for group in self.question_card_view.accordion_groups:
                for card in group.get_all_cards():
                    question_data = card.question_data
                    if question_data:
                        visible_questions.append(question_data)
        else:
            # Fallback to old tree method if card view doesn't exist
            root = self.question_tree.invisibleRootItem()
            
            def collect_visible_questions(parent_item):
                for i in range(parent_item.childCount()):
                    child = parent_item.child(i)
                    if not child.isHidden():
                        if child.childCount() == 0:  # Leaf node (question)
                            question_data = child.data(0, Qt.UserRole)
                            if question_data:
                                visible_questions.append(question_data)
                        else:  # Group node, recurse
                            collect_visible_questions(child)
            
            collect_visible_questions(root)
        
        if not visible_questions:
            QMessageBox.warning(self, "No Questions", "No questions available in the current filtered view.")
            return
        
        # Create dialog for list name and question count
        dialog = QDialog(self)
        dialog.setWindowTitle("Create Random Question List")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout(dialog)
        
        # List name input
        layout.addWidget(QLabel("List Name:"))
        name_input = QLineEdit()
        layout.addWidget(name_input)
        
        # Question count input
        layout.addWidget(QLabel(f"Number of Questions (max {len(visible_questions)}):"))
        count_spinner = QSpinBox()
        count_spinner.setMinimum(1)
        count_spinner.setMaximum(len(visible_questions))
        count_spinner.setValue(min(30, len(visible_questions)))  # Default 30
        layout.addWidget(count_spinner)
        
        # Filter info
        active_filters = self._get_active_filters()
        if active_filters:
            filter_info = QLabel("<b>Active filters will be saved with this list:</b>")
            layout.addWidget(filter_info)
            
            filter_parts = []
            if active_filters.get("selected_chapter"):
                filter_parts.append(f" Chapter: '{active_filters['selected_chapter']}'")
            if active_filters.get("advanced_query"):
                filter_parts.append(f" Query: {active_filters['advanced_query']}")
            if active_filters.get("selected_tags"):
                filter_parts.append(f" Tags: {', '.join(active_filters['selected_tags'])}")
            
            if filter_parts:
                filter_label = QLabel("\n".join(filter_parts))
                filter_label.setStyleSheet("padding: 8px; background-color: #fef3c7; border-radius: 4px; color: #92400e;")
                layout.addWidget(filter_label)
        
        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        if dialog.exec() != QDialog.Accepted:
            return
        
        list_name = name_input.text().strip()
        if not list_name:
            QMessageBox.warning(self, "Invalid Name", "Please enter a list name.")
            return
        
        if list_name in self.question_lists:
            reply = QMessageBox.question(
                self,
                "List Exists",
                f"List '{list_name}' already exists. Overwrite?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
        
        # Select random questions
        import random
        num_questions = count_spinner.value()
        selected_questions = random.sample(visible_questions, num_questions)
        
        # Create the list
        self.question_lists[list_name] = [q.copy() for q in selected_questions]
        self.question_lists_metadata[list_name] = {
            "magazine": self.current_magazine_name,
            "filters": active_filters
        }
        
        self._save_question_list(list_name, save_filters=True)
        self._load_saved_question_lists()
        
        self.log(f"Created random list '{list_name}' with {num_questions} questions from filtered view")
        QMessageBox.information(
            self,
            "Success",
            f"Created list '{list_name}' with {num_questions} random questions from filtered view."
        )

    def log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.log_view.append(f"[{timestamp}] {message}")
        self.log_view.moveCursor(QTextCursor.End)

    def select_input_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Input Folder")
        if folder:
            self.input_edit.setText(folder)
            self._save_last_selection()
            self.refresh_file_list()
            self._auto_start_watching()  # Auto-start watching

    def select_output_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select SQLite Database",
            "",
            "Excel files (*.xlsx)",
        )
        if file_path:
            self.output_edit.setText(file_path)
            self._save_last_selection()
            self.load_subject_from_db()

    def import_tsv_from_clipboard(self) -> None:
        """Import TSV content directly from the clipboard."""
        clipboard = QGuiApplication.clipboard()
        tsv_text = clipboard.text() if clipboard else ""
        self.clipboard_text_edit.setPlainText(tsv_text)
        self._import_tsv_content(tsv_text, source_label="clipboard_import")

    def import_tsv_from_textarea(self) -> None:
        """Import TSV content from the on-page text area after review."""
        tsv_text = self.clipboard_text_edit.toPlainText()
        self._import_tsv_content(tsv_text, source_label="textarea_import")

    def paste_clipboard_to_textarea(self) -> None:
        """Paste clipboard text into the review area without importing."""
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            self.clipboard_text_edit.setPlainText(clipboard.text())

    def clear_clipboard_textarea(self) -> None:
        """Clear the review textarea."""
        self.clipboard_text_edit.clear()

    def _import_tsv_content(self, tsv_text: str, source_label: str) -> None:
        """Common TSV import flow from provided text."""
        if not tsv_text or not tsv_text.strip():
            QMessageBox.warning(self, "TSV Empty", "No TSV content to import.")
            return
        if "\t" not in tsv_text:
            QMessageBox.warning(self, "Invalid TSV", "Provided text does not look like TSV data (no tab characters found).")
            return

        db_path = Path(self.db_path_edit.text().strip() or DEFAULT_DB_PATH)
        subject = self.subject_combo.currentText() if hasattr(self, "subject_combo") else ""
        if not subject:
            QMessageBox.critical(self, "Invalid Subject", "Please select a subject before importing.")
            return
        if not db_path.is_file():
            QMessageBox.critical(self, "Invalid Database", f"Database file not found:\n{db_path}")
            return

        self.current_db_path = db_path
        self.db_service.set_db_path(db_path)
        self.current_subject = subject

        timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{source_label}_{timestamp}.tsv"
        self.update_file_status(filename, "Processing", "Validating TSV...")
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                delete=False,
                suffix=".tsv",
                newline="",
                encoding="utf-8",
            ) as tmp_file:
                tmp_file.write(tsv_text)
                tmp_path = Path(tmp_file.name)

            self.set_status(f'Importing data from "{filename}"', "importing")
            result_message = process_tsv(tmp_path, self.db_service, subject)
            self.update_file_status(filename, "Completed", result_message)
            self.log(f"Imported TSV ({filename}): {result_message}")
            self.set_status(f'TSV imported from "{filename}" {result_message}', "success")
            self.load_subject_from_db()
            QMessageBox.information(self, "Import Complete", f"TSV imported.\n{result_message}")
        except Exception as exc:
            error_message = str(exc)
            self.update_file_status(filename, "Error", error_message)
            self.log(f"Error importing TSV ({filename}): {error_message}")
            self.set_status(f"Error importing TSV: {error_message}", "error")
            QMessageBox.critical(self, "Import Failed", f"Could not import TSV:\n{error_message}")
            if tmp_path and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass
        finally:
            if tmp_path and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass

    def refresh_file_list(self) -> None:
        input_path = Path(self.input_edit.text().strip())
        if not input_path.exists():
            self.log("Input folder does not exist.")
            return

        tsv_files = sorted(input_path.glob("*.tsv"))
        for tsv_file in tsv_files:
            self._ensure_row(tsv_file.name)
        self.log(f"Found {len(tsv_files)} TSV file(s) in input folder.")

    def _ensure_row(self, filename: str) -> int:
        row = self.file_rows.get(filename)
        if row is not None:
            return row
        row = self.file_table.rowCount()
        self.file_table.insertRow(row)
        self.file_table.setItem(row, 0, QTableWidgetItem(filename))
        self.file_table.setItem(row, 1, QTableWidgetItem("Pending"))
        self.file_table.setItem(row, 2, QTableWidgetItem("Awaiting processing"))
        self.file_rows[filename] = row
        return row

    def update_file_status(self, filename: str, status: str, message: str) -> None:
        row = self._ensure_row(filename)
        for col, value in enumerate((filename, status, message)):
            item = self.file_table.item(row, col)
            if item is None:
                item = QTableWidgetItem(value)
                self.file_table.setItem(row, col, item)
            else:
                item.setText(value)
        if status.lower() == "error":
            self.file_errors[filename] = message
        else:
            self.file_errors.pop(filename, None)

    def on_file_double_clicked(self, row: int, column: int) -> None:  # noqa: ARG002
        filename_item = self.file_table.item(row, 0)
        status_item = self.file_table.item(row, 1)
        message_item = self.file_table.item(row, 2)
        if not filename_item or not status_item:
            return
        if status_item.text().lower() != "error":
            return
        filename = filename_item.text()
        detail = self.file_errors.get(filename, message_item.text() if message_item else "")
        QMessageBox.critical(self, "Validation Error", f"{filename}\n\n{detail}")

    def start_watching(self) -> None:
        if self.watch_thread and self.watch_thread.is_alive():
            QMessageBox.information(self, "Watcher", "Watcher is already running.")
            return

        input_path = Path(self.input_edit.text().strip())
        if not input_path.is_dir():
            QMessageBox.critical(self, "Invalid Input", "Please select a valid input folder.")
            return

        db_path = Path(self.db_path_edit.text().strip() or DEFAULT_DB_PATH)
        subject = self.subject_combo.currentText() if hasattr(self, "subject_combo") else ""
        if not subject:
            QMessageBox.critical(self, "Invalid Subject", "Please select a subject.")
            return
        if not db_path.is_file():
            QMessageBox.critical(self, "Invalid Database", f"Database file not found:\n{db_path}")
            return

        self.current_db_path = db_path
        self.db_service.set_db_path(db_path)
        self.current_subject = subject

        self.stop_event.clear()
        self.watch_thread = threading.Thread(
            target=self._watch_loop, args=(input_path,), daemon=True
        )
        self.watch_thread.start()
        self.start_button.setEnabled(False)
        self.log("Started watching for TSV files.")
    
    def _auto_start_watching(self) -> None:
        """Automatically start watching if both input folder and Database are valid."""
        if self.watch_thread and self.watch_thread.is_alive():
            return  # Already watching
        
        input_path = Path(self.input_edit.text().strip())
        if input_path.is_dir():
            self.stop_event.clear()
            self.watch_thread = threading.Thread(
                target=self._watch_loop, args=(input_path,), daemon=True
            )
            self.watch_thread.start()
            self.start_button.setEnabled(False)
            self.log("Auto-started watching for TSV files.")

    def stop_watching(self) -> None:
        self.stop_event.set()
        if self.watch_thread and self.watch_thread.is_alive():
            self.watch_thread.join(timeout=0.1)
        self.start_button.setEnabled(True)
        self.watch_thread = None
        self.watch_Database_path = None
        self.log("Stopped watching.")

    def _restart_watching_for_new_Database(self, Database_path: Path) -> None:
        """Deprecated: Database no longer used."""
        return

    def _watch_loop(self, input_dir: Path) -> None:
        poll_interval = 3.0
        while not self.stop_event.is_set():
            tsv_files = sorted(input_dir.glob("*.tsv"))
            if not tsv_files:
                time.sleep(poll_interval)
                continue

            for tsv_file in tsv_files:
                if self.stop_event.is_set():
                    break
                self.event_queue.put(("status", tsv_file.name, "Processing", "Validating..."))
                self.event_queue.put(("status_importing", tsv_file.name))
                try:
                    subject = self.current_subject or (self.subject_combo.currentText() if hasattr(self, "subject_combo") else "")
                    result_message = process_tsv(tsv_file, self.db_service, subject)
                except Exception as exc:
                    self.event_queue.put(("status", tsv_file.name, "Error", str(exc)))
                    self.event_queue.put(("log", f"Error processing {tsv_file.name}: {exc}"))
                    self.event_queue.put(("status_error", f"Failed to import {tsv_file.name}: {exc}"))
                else:
                    self.event_queue.put(("status", tsv_file.name, "Completed", result_message))
                    self.event_queue.put(("log", f"Processed {tsv_file.name}: {result_message}"))
                    self.event_queue.put(("rowcount",))
                    self.event_queue.put(("status_success", tsv_file.name, result_message))

            time.sleep(poll_interval)

    def _process_queue(self) -> None:
        while True:
            try:
                event = self.event_queue.get_nowait()
            except queue.Empty:
                break

            event_type = event[0]
            if event_type == "status":
                _, filename, status, message = event
                self.update_file_status(filename, status, message)
            elif event_type == "log":
                _, message = event
                self.log(message)
            elif event_type == "metrics":
                _, req_id, row_count, details, warnings, chapter_data, question_col, raw_chapter_inputs, detected_magazine = event
                if req_id != self.metrics_request_id:
                    continue
                self.high_level_column_index = question_col
                
                # Magazine grouping already loaded in worker thread, just log it
                if detected_magazine:
                    self.log(f"Loaded chapter grouping for: {detected_magazine or 'default (Physics)'}")
                
                self.row_count_label.setText(f"Total rows: {row_count}")
                # Show success status after Database loads
                self.set_status(f'Loaded Database "{self.current_Database_path.name}"', "success")
                total_editions = sum(len(entry["editions"]) for entry in details)
                mag_display = self.current_magazine_display_name or (
                    self.current_magazine_name.title() if self.current_magazine_name else "Unknown"
                )
                self._set_magazine_summary(
                    f"Magazine: {mag_display}",
                    f"Tracked editions: {total_editions}",
                )
                
                self.mag_page_ranges = self._compute_page_ranges_for_editions(self.Database_df, details)
                self._populate_magazine_heatmap(details, self.mag_page_ranges)
                self._populate_question_sets([])
                missing_qset_warning = next(
                    (msg for msg in warnings if "question set" in msg.lower()), None
                )
                if missing_qset_warning:
                    label_message = missing_qset_warning
                elif details:
                    label_message = "Select an edition to view question sets."
                else:
                    label_message = warnings[0] if warnings else "No magazine editions found."
                self.question_label.setText(label_message)
                self._auto_assign_chapters(raw_chapter_inputs)
                self._populate_chapter_list(chapter_data)
                self._refresh_grouping_ui()
                
                # Update dashboard with statistics
                if hasattr(self, 'dashboard_view') and hasattr(self, 'Database_df'):
                    self.dashboard_view.update_dashboard_data(
                        self.Database_df,
                        self.chapter_groups,
                        magazine_details=details,
                        mag_display_name=self.current_magazine_display_name,
                        mag_page_ranges=self.mag_page_ranges,
                    )
                
                # Update question set grouping view with question sets from Database
                if hasattr(self, 'question_set_grouping_view') and hasattr(self, 'Database_df'):
                    # Extract unique question sets and their min pages from Database
                    question_sets = self._extract_unique_question_sets(self.Database_df)
                    qs_min_pages = self._extract_question_set_min_pages(self.Database_df)
                    qs_mag_map = self._extract_question_set_magazines(self.Database_df)
                    self.question_set_grouping_view.update_from_workbook(
                        question_sets,
                        qs_min_pages,
                        qs_mag_map,
                    )
                
                for warning in warnings:
                    self.log(warning)
                
                # If startup requested auto-watch, start it only after Database loads successfully
                if self.pending_auto_watch:
                    self._auto_start_watching()
                    self.pending_auto_watch = False
            elif event_type == "metrics_error":
                _, req_id, error_message = event
                if req_id != self.metrics_request_id:
                    continue
                self.high_level_column_index = None
                self.row_count_label.setText("Total rows: Error")
                self._set_magazine_summary("Magazines: Error", "Missing ranges: Error")
                self._populate_magazine_heatmap([], {})
                self._populate_question_sets([])
                self._populate_chapter_list({})
                self._refresh_grouping_ui()
                self.question_label.setText("Unable to load editions.")
                self.log(f"Unable to read Database rows: {error_message}")
            elif event_type == "status_error":
                _, error_msg = event
                self.set_status(f"Error: {error_msg}", "error")
            elif event_type == "status_importing":
                _, filename = event
                self.set_status(f'Importing data from "{filename}"', "importing")
            elif event_type == "status_success":
                _, filename, result_msg = event
                self.set_status(f'Data imported from "{filename}"  {result_msg}', "success")
            elif event_type == "rowcount":
                self.load_subject_from_db()
        # Timer will trigger this method again; no manual reschedule needed.

    # ============================================================================
    # JEE Main Papers Methods
    # ============================================================================
    
    def select_jee_db_file(self) -> None:
        """Open file dialog to select JEE papers SQLite file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select JEE Papers Database",
            "",
            "SQLite DB (*.db *.sqlite);;All files (*.*)",
        )
        if file_path:
            self.jee_papers_file = Path(file_path)
            self.jee_file_edit.setText(file_path)
            self._save_last_selection()
            self.load_jee_papers_data()

    def load_jee_papers_data(self) -> None:
        """Load and process JEE papers data from SQLite file (table: jee_questions)."""
        if not self.jee_papers_file or not self.jee_papers_file.exists():
            self.log("JEE papers DB not found.")
            return
        
        try:
            self._backup_jee_database(self.jee_papers_file, log_result=True)
            with sqlite3.connect(self.jee_papers_file) as conn:
                df = pd.read_sql_query(
                    "SELECT question_number, jee_session, year, subject, chapter FROM jee_questions",
                    conn,
                )
            # Normalize column names to match existing UI expectations
            df = df.rename(
                columns={
                    "question_number": "Question Number",
                    "jee_session": "JEE Main Session",
                    "year": "Year",
                    "subject": "Subject",
                    "chapter": "Chapter",
                }
            )
            self.jee_papers_df = df
            # Validate required columns
            required_columns = ['Question Number', 'JEE Main Session', 'Year', 'Subject', 'Chapter']
            missing_columns = [col for col in required_columns if col not in self.jee_papers_df.columns]
            
            if missing_columns:
                self.log(f"Error: Missing required columns in JEE DB: {', '.join(missing_columns)}")
                QMessageBox.warning(
                    self,
                    "Invalid Database",
                    f"Missing required columns in table 'jee_questions': {', '.join(missing_columns)}\nExpected columns: {', '.join(required_columns)}"
                )
                return
            
            # Populate subject dropdown
            subjects = sorted(self.jee_papers_df['Subject'].unique())
            self.jee_subject_combo.clear()
            self.jee_subject_combo.addItems(subjects)
            
            self.log(f"Loaded {len(self.jee_papers_df)} questions from JEE papers database.")
            
            # Update tables if a subject is selected
            if subjects:
                self.update_jee_tables()
                
        except Exception as e:
            self.log(f"Error loading JEE papers database: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load file: {e}")
    
    def update_jee_tables(self) -> None:
        """Update the chapters table based on selected subject."""
        if self.jee_papers_df is None or self.jee_papers_df.empty:
            return
        
        subject = self.jee_subject_combo.currentText()
        if not subject:
            return
        
        try:
            # Filter by subject
            subject_df = self.jee_papers_df[self.jee_papers_df['Subject'] == subject]
            
            if subject_df.empty:
                self.log(f"No data found for subject: {subject}")
                return
            
            # Count questions per chapter
            chapter_counts = subject_df['Chapter'].value_counts().sort_values(ascending=False)
            
            # Populate chapters table
            self.jee_chapters_table.setRowCount(len(chapter_counts))
            for row, (chapter, count) in enumerate(chapter_counts.items()):
                chapter_item = QTableWidgetItem(chapter)
                count_item = QTableWidgetItem(str(count))
                count_item.setTextAlignment(Qt.AlignCenter)
                self.jee_chapters_table.setItem(row, 0, chapter_item)
                self.jee_chapters_table.setItem(row, 1, count_item)
            
            # Clear questions table
            self.jee_questions_table.setRowCount(0)
            self.jee_questions_table.setColumnCount(0)
            self.jee_questions_label.setText(f"Select a chapter to view questions ({subject})")
            
            self.log(f"Updated tables for {subject}: {len(chapter_counts)} chapters, {subject_df.shape[0]} total questions")
            
        except Exception as e:
            self.log(f"Error updating JEE tables: {e}")
    
    def on_jee_chapter_selected(self) -> None:
        """Handle chapter selection to show questions for that chapter."""
        if self.jee_papers_df is None or self.jee_papers_df.empty:
            return
        
        selected_items = self.jee_chapters_table.selectedItems()
        if not selected_items:
            return
        
        # Get selected chapter name
        row = selected_items[0].row()
        chapter_item = self.jee_chapters_table.item(row, 0)
        if not chapter_item:
            return
        
        chapter_name = chapter_item.text()
        subject = self.jee_subject_combo.currentText()
        
        try:
            # Filter questions by subject and chapter
            filtered_df = self.jee_papers_df[
                (self.jee_papers_df['Subject'] == subject) & 
                (self.jee_papers_df['Chapter'] == chapter_name)
            ]
            
            if filtered_df.empty:
                self.jee_questions_label.setText(f"No questions found for {chapter_name}")
                self.jee_questions_table.setRowCount(0)
                return
            
            # Update label
            self.jee_questions_label.setText(f"{chapter_name} - {len(filtered_df)} Questions")
            
            # Setup columns (all columns from Excel)
            columns = list(filtered_df.columns)
            self.jee_questions_table.setColumnCount(len(columns))
            self.jee_questions_table.setHorizontalHeaderLabels(columns)
            
            # Populate rows
            self.jee_questions_table.setRowCount(len(filtered_df))
            for row_idx, (_, row_data) in enumerate(filtered_df.iterrows()):
                for col_idx, col_name in enumerate(columns):
                    value = str(row_data[col_name]) if pd.notna(row_data[col_name]) else ""
                    item = QTableWidgetItem(value)
                    self.jee_questions_table.setItem(row_idx, col_idx, item)
            
            # Auto-resize columns to content
            self.jee_questions_table.resizeColumnsToContents()
            
            self.log(f"Showing {len(filtered_df)} questions for {chapter_name}")
            
        except Exception as e:
            self.log(f"Error displaying chapter questions: {e}")

    def closeEvent(self, event) -> None:
        self.stop_watching()
        super().closeEvent(event)
