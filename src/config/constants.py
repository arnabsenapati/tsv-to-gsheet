"""
Application constants and configuration values.
Contains file paths, color schemes, and mapping dictionaries.
"""

from pathlib import Path

# ============================================================================
# Base Directories and File Paths
# ============================================================================

# Base directory of the application
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Configuration files
PHYSICS_CHAPTER_FILE = BASE_DIR / "physicsCHapters.txt"
PHYSICS_GROUPING_FILE = BASE_DIR / "PhysicsChapterGrouping.json"
CHEMISTRY_GROUPING_FILE = BASE_DIR / "ChemistryChapterGrouping.json"
MATHEMATICS_GROUPING_FILE = BASE_DIR / "MathematicsChapterGrouping.json"
LAST_SELECTION_FILE = BASE_DIR / "last_selection.json"
QUESTION_LIST_DIR = BASE_DIR / "QuestionList"
TAGS_CONFIG_FILE = BASE_DIR / "tags.cfg"


# ============================================================================
# Magazine to Grouping File Mapping
# ============================================================================

MAGAZINE_GROUPING_MAP = {
    "chemistry today": CHEMISTRY_GROUPING_FILE,
    "physics for you": PHYSICS_GROUPING_FILE,
    "mathematics today": MATHEMATICS_GROUPING_FILE,
}


# ============================================================================
# Month Name Aliases for Date Parsing
# ============================================================================

MONTH_ALIASES = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


# ============================================================================
# Color Palette for Tags (20 colors)
# ============================================================================

TAG_COLORS = [
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


# ============================================================================
# UI Color Constants
# ============================================================================

COLOR_GROUP_HEADER = "#1e40af"  # Blue for group headers
COLOR_MAGAZINE_HIGHLIGHT = "#dbeafe"  # Light blue for magazine column
COLOR_EDITION_WARNING = "#fef3c7"  # Yellow for editions with <5 sets
