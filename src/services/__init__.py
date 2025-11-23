"""
Services layer for business logic.

Contains:
- excel_service: Excel workbook operations (read TSV, append rows, detect duplicates)
- tag_service: Tag management (load/save tags, color assignment, filtering)
- data_service: Data management (chapter groupings, question organization)
"""

from .excel_service import (
    read_tsv_rows,
    collect_existing_triplets,
    extract_file_metadata,
    append_rows_to_excel,
    infer_column_types,
    process_tsv,
)
from .tag_service import TagService, get_tag_service
from .data_service import DataService, get_data_service, set_data_service

__all__ = [
    'read_tsv_rows',
    'collect_existing_triplets',
    'extract_file_metadata',
    'append_rows_to_excel',
    'infer_column_types',
    'process_tsv',
    'TagService',
    'get_tag_service',
    'DataService',
    'get_data_service',
    'set_data_service',
]
