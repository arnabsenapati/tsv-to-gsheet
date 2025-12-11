"""
Helper utilities for loading icons with absolute paths.

Using a central helper avoids missing icons when the working
directory changes (e.g., when launched from a packaged build).
"""

from pathlib import Path

from PySide6.QtGui import QIcon

from config.constants import BASE_DIR


ICON_DIR = BASE_DIR / "icons"


def load_icon(name: str) -> QIcon:
    """
    Return a QIcon for the given file name from the shared icons directory.

    Args:
        name: File name inside the icons directory (e.g., 'close.svg').
    """
    path = ICON_DIR / name
    return QIcon(str(path)) if path.exists() else QIcon()
