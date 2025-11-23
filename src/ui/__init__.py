"""
UI components package.

Contains:
- widgets: Custom widget classes (badges, trees, tables, lists)
- dialogs: Dialog windows (tag selection, etc.)
"""

from .dialogs import MultiSelectTagDialog
from .widgets import (
    TagBadge,
    ClickableTagBadge,
    QuestionTreeWidget,
    ChapterTableWidget,
    QuestionTableWidget,
    GroupingChapterListWidget,
    GroupListWidget,
)

__all__ = [
    'MultiSelectTagDialog',
    'TagBadge',
    'ClickableTagBadge',
    'QuestionTreeWidget',
    'ChapterTableWidget',
    'QuestionTableWidget',
    'GroupingChapterListWidget',
    'GroupListWidget',
]
