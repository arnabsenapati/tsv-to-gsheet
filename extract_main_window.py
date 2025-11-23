"""
Helper script to extract TSVWatcherWindow class from append_tsv_to_excel.py
to src/ui/main_window.py with proper imports and structure.

Run this script to complete the refactoring:
    python extract_main_window.py
"""

import re
from pathlib import Path


def extract_main_window():
    """Extract TSVWatcherWindow class to main_window.py"""
    
    # Read original file
    original_file = Path("append_tsv_to_excel.py")
    lines = original_file.read_text(encoding="utf-8").split('\n')
    
    # Find class start
    class_start = None
    for i, line in enumerate(lines):
        if line.startswith('class TSVWatcherWindow(QMainWindow):'):
            class_start = i
            break
    
    if class_start is None:
        print("ERROR: Could not find TSVWatcherWindow class")
        return False
    
    # Find class end (next non-indented line or if __name__)
    class_end = None
    for i in range(class_start + 1, len(lines)):
        line = lines[i]
        # Check for end of class (non-indented line that's not blank)
        if line and not line[0].isspace() and not line.startswith('#'):
            class_end = i
            break
    
    if class_end is None:
        class_end = len(lines)
    
    # Extract class code
    class_code = '\n'.join(lines[class_start:class_end])
    
    # Create main_window.py with proper imports
    main_window_code = '''"""
Main application window for TSV to Excel Watcher.

This module contains the TSVWatcherWindow class which is the main UI window
for the application. It handles:
- Workbook analysis and magazine edition tracking
- Question list management with grouping and tagging
- Chapter grouping and organization
- TSV file monitoring and import
- Custom question list creation
"""

from __future__ import annotations

import datetime as dt
import json
import queue
import re
import threading
import time
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPalette, QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
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
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config.constants import (
    LAST_SELECTION_FILE,
    MAGAZINE_GROUPING_MAP,
    PHYSICS_GROUPING_FILE,
    QUESTION_LIST_DIR,
    TAGS_CONFIG_FILE,
    TAG_COLORS,
)
from services.excel_service import process_tsv
from ui.dialogs import MultiSelectTagDialog
from ui.widgets import (
    ChapterTableWidget,
    GroupingChapterListWidget,
    GroupListWidget,
    QuestionTreeWidget,
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
)


'''
    
    main_window_code += class_code
    main_window_code += "\n"
    
    # Write to main_window.py
    output_file = Path("src/ui/main_window.py")
    output_file.write_text(main_window_code, encoding="utf-8")
    
    print(f"✓ Extracted TSVWatcherWindow to {output_file}")
    print(f"  Class size: {len(class_code)} characters, {class_code.count(chr(10))} lines")
    
    return True


def update_main_py():
    """Update main.py to use refactored structure"""
    
    main_py = Path("main.py")
    content = main_py.read_text(encoding="utf-8")
    
    # Replace imports
    new_content = content.replace(
        "from append_tsv_to_excel import TSVWatcherWindow",
        "from ui.main_window import TSVWatcherWindow"
    )
    
    # Update comment
    new_content = new_content.replace(
        "# TODO: Replace with refactored main_window once extraction is complete\n# For now, import from original file\n",
        "# Using refactored main_window module\n"
    )
    
    main_py.write_text(new_content, encoding="utf-8")
    print(f"✓ Updated {main_py} to use refactored imports")


if __name__ == "__main__":
    print("=" * 60)
    print("TSV to Excel Watcher - Main Window Extraction")
    print("=" * 60)
    print()
    
    if extract_main_window():
        print()
        update_main_py()
        print()
        print("=" * 60)
        print("✓ Refactoring complete!")
        print("=" * 60)
        print()
        print("Next steps:")
        print("  1. Test the application: python main.py")
        print("  2. Check for any import errors")
        print("  3. Verify all functionality works correctly")
        print()
    else:
        print()
        print("ERROR: Extraction failed. Please check the error messages above.")
