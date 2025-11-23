"""
Main entry point for the TSV to Excel Watcher Application.

Usage:
    python main.py

Note: Currently uses the original append_tsv_to_excel.py until refactoring is complete.
"""

import sys
from pathlib import Path

# Add src directory to path for future refactored modules
sys.path.insert(0, str(Path(__file__).parent / "src"))

from PySide6.QtWidgets import QApplication

# Using refactored main_window module
from ui.main_window import TSVWatcherWindow


def main():
    """Initialize and run the application."""
    app = QApplication(sys.argv)
    
    # Create and show main window
    window = TSVWatcherWindow()
    window.show()
    
    # Start event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
