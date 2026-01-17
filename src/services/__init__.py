"""
Services layer for business logic.

Contains:
- excel_service: TSV import helpers (DB-backed)
- tag_service: Tag management (load/save tags, color assignment, filtering)
- data_service: Data management (chapter groupings, question organization)
- question_set_group_service: Question set grouping management
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

__all__ = [
    "read_tsv_rows",
    "process_tsv",
    "TagService",
    "get_tag_service",
    "DataService",
    "get_data_service",
    "set_data_service",
    "DatabaseService",
    "QuestionSetGroupService",
]

_LAZY_EXPORTS = {
    "read_tsv_rows": ("services.excel_service", "read_tsv_rows"),
    "process_tsv": ("services.excel_service", "process_tsv"),
    "TagService": ("services.tag_service", "TagService"),
    "get_tag_service": ("services.tag_service", "get_tag_service"),
    "DataService": ("services.data_service", "DataService"),
    "get_data_service": ("services.data_service", "get_data_service"),
    "set_data_service": ("services.data_service", "set_data_service"),
    "DatabaseService": ("services.db_service", "DatabaseService"),
    "QuestionSetGroupService": ("services.question_set_group_service", "QuestionSetGroupService"),
}


def __getattr__(name: str):
    target = _LAZY_EXPORTS.get(name)
    if not target:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = target
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


if TYPE_CHECKING:
    from .excel_service import process_tsv, read_tsv_rows
    from .tag_service import TagService, get_tag_service
    from .data_service import DataService, get_data_service, set_data_service
    from .db_service import DatabaseService
    from .question_set_group_service import QuestionSetGroupService
