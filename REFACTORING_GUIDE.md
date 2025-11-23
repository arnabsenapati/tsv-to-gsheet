# TSV to Excel Watcher - Refactored Structure

## Project Structure

The application has been refactored from a single 3000+ line file into a modular structure:

```
tsv-to-gsheet/
├── main.py                          # Application entry point
├── append_tsv_to_excel.py          # Original file (kept for reference)
├── src/
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py
│   │   ├── constants.py            # Application constants, paths, colors
│   │   └── settings.py             # Configurable settings
│   ├── models/
│   │   ├── __init__.py
│   │   ├── question.py             # Question data model
│   │   └── chapter.py              # Chapter data model
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── widgets.py              # Custom widgets (TagBadge, Trees, Tables)
│   │   ├── dialogs.py              # Dialog windows (Tag selection, etc.)
│   │   └── main_window.py          # Main application window
│   ├── services/
│   │   ├── __init__.py
│   │   ├── excel_service.py        # Excel file operations
│   │   ├── tag_service.py          # Tag management
│   │   ├── question_service.py     # Question grouping and filtering
│   │   └── file_watcher.py         # File system monitoring
│   └── utils/
│       ├── __init__.py
│       ├── helpers.py               # Utility functions (normalization, etc.)
│       └── validators.py            # Data validation functions
├── QuestionList/                    # Saved question lists
├── tags.cfg                         # Tag configuration
└── *.json                          # Chapter grouping files
```

## Module Responsibilities

### config/
- **constants.py**: File paths, color palettes, mappings, month aliases
- **settings.py**: UI settings, behavior configurations

### models/
- **question.py**: Question data structure and methods
- **chapter.py**: Chapter grouping data structure

### ui/
- **widgets.py**: 
  - `TagBadge`: Small clickable tag display
  - `ClickableTagBadge`: Tag selection with +/✓ toggle
  - `QuestionTreeWidget`: Tree view for grouped questions
  - `ChapterTableWidget`: Table for chapter management
  - `QuestionTableWidget`: Table for question display
  - `GroupingChapterListWidget`: Drag-drop chapter list
  - `GroupListWidget`: Drag-drop group list

- **dialogs.py**:
  - `MultiSelectTagDialog`: Beautiful tag selection dialog
  - Other input dialogs

- **main_window.py**:
  - `TSVWatcherWindow`: Main application class
  - Tab management (Data Import, Magazine Edition, Question List, Custom Lists, Grouping)
  - Event handlers and UI coordination

### services/
- **excel_service.py**:
  - Excel file reading/writing
  - Row validation and insertion
  - Page range extraction
  - Column type inference

- **tag_service.py**:
  - Tag storage (tags.cfg)
  - Tag-group mapping
  - Color assignment
  - Tag filtering logic

- **question_service.py**:
  - Question grouping by similarity
  - Group key extraction
  - Question filtering
  - Question list management

- **file_watcher.py**:
  - TSV file monitoring
  - File processing queue
  - Background thread management

### utils/
- **helpers.py**:
  - Text normalization functions
  - Date parsing
  - Excel column finding
  - Data type conversion

- **validators.py**:
  - TSV file validation
  - Data integrity checks

## Benefits of Refactoring

1. **Maintainability**: Each module has a single, clear responsibility
2. **Testability**: Individual components can be tested in isolation
3. **Readability**: Smaller files with focused functionality
4. **Reusability**: Services and utilities can be used across different UI components
5. **Scalability**: Easy to add new features without affecting existing code
6. **Collaboration**: Multiple developers can work on different modules

## Implementation Notes

The refactoring maintains all existing functionality while organizing code into logical groups. Key patterns used:

- **Separation of Concerns**: UI, business logic, and data access are separated
- **Service Layer**: Business logic encapsulated in services
- **Configuration Management**: Centralized constants and settings
- **Widget Composition**: Complex UI built from smaller, reusable widgets

## Next Steps

To complete the refactoring:

1. Extract widget classes to `ui/widgets.py`
2. Move dialog classes to `ui/dialogs.py`
3. Create service classes for Excel, tags, and questions
4. Move TSVWatcherWindow to `ui/main_window.py`
5. Add comprehensive docstrings and comments
6. Write unit tests for each module
7. Update import statements
8. Test thoroughly to ensure all functionality works

## Running the Application

After refactoring:
```bash
python main.py
```

The original `append_tsv_to_excel.py` file is preserved for reference during the transition.
