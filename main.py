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

from PySide6.QtWidgets import QApplication, QSplashScreen
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import Qt

# Using refactored main_window module
from ui.main_window import TSVWatcherWindow


def main():
    """Initialize and run the application."""
    app = QApplication(sys.argv)

    # Load app icon and splash image
    assets_dir = Path(__file__).parent / "icons"
    icon_path = assets_dir / "JEE-QB.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
        splash_pix = QPixmap(str(icon_path))
        splash = QSplashScreen(splash_pix, Qt.WindowStaysOnTopHint | Qt.SplashScreen)
        splash.show()
        app.processEvents()
    else:
        splash = None
    
    # Create and show main window
    window = TSVWatcherWindow()
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))
    window.show()

    if splash:
        splash.finish(window)
    
    # Start event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
