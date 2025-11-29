# Custom Lists & Question List Implementation Report

## Executive Summary
This report documents the implementation of Custom Lists page and Question List tab, comparing their architectures, data structures, and UI components.

---

## 1. FILE LOCATIONS & LINE RANGES

### Custom Lists Page (Tab Index 4)
**File:** `src/ui/main_window.py`
- **`_create_lists_page()` method**: Lines 680-760
- **Data initialization**: Lines 119-124
- **Related methods**:
  - `create_new_question_list()`: Lines 2703-2721
  - `rename_question_list()`: Lines 2723-2758
  - `delete_question_list()`: Lines 2760-2781
  - `on_saved_list_selected()`: Lines 2898-2919
  - `_populate_list_question_table()`: Lines 2921-2953
  - `add_selected_to_list()`: Lines 2786-2814
  - `_on_drag_drop_save()`: Lines 2816-2829
  - `remove_selected_from_list()`: Lines 2876-2895
  - `_save_question_list()`: Lines 2669-2701
  - `_load_saved_question_lists()`: Lines 2626-2666

### Question List Tab (Tab Index 2)
**File:** `src/ui/main_window.py`
- **`_create_questions_page()` method**: Lines 407-645
- **Data initialization**: Lines 119-124 (shared with Custom Lists)
- **Related methods**:
  - `on_question_selected()`: Triggered by tree/card selection
  - `on_question_card_selected()`: Handles card view selections
  - `add_selected_to_list()`: Lines 2786-2814 (shared with Custom Lists)
  - `create_random_list_from_filtered()`: Lines 3064-3142

---

## 2. CUSTOM LISTS DATA STRUCTURE

### Primary Data Structure (Main Window)
```python
# Lines 119-124 in main_window.py
self.question_lists: dict[str, list[dict]] = {}
# Structure: { "List Name": [questions_dict, ...] }

self.question_lists_metadata: dict[str, dict] = {}
# Structure: {
#     "List Name": {
#         "magazine": "Magazine Edition",
#         "filters": {
#             "selected_chapter": "Chapter Name",
#             "question_set_search": "Search Term",
#             "selected_tags": ["tag1", "tag2"],
#             "selected_magazine": "Magazine Name"
#         }
#     }
# }

self.current_list_name: str | None = None
self.current_list_questions: list[dict] = []
```

### Question Data Dictionary Structure
```python
{
    "row_number": int,              # Unique identifier
    "qno": str,                     # Question number
    "page": str | int,              # Page number
    "question_set": str,            # Chapter name
    "question_set_name": str,       # Question set display name
    "magazine": str,                # Magazine edition
    "group": str,                   # Group/chapter name
    "question_text": str,           # Full question text
}
```

### File Storage Format (JSON)
**Location:** `QuestionList/` directory (defined in `config/constants.py`)
**Filename:** `{safe_name}.json` (alphanumeric + spaces, underscores, hyphens)

**File Structure:**
```json
{
  "name": "List Name",
  "magazine": "Magazine Edition",
  "questions": [
    {
      "row_number": 1,
      "qno": "Q1",
      "page": 25,
      "question_set": "Mechanics",
      "question_set_name": "JEE Main 2023",
      "magazine": "Physics For You Jan 2023",
      "group": "Mechanics",
      "question_text": "Full question text..."
    }
  ],
  "filters": {
    "selected_chapter": "Mechanics",
    "question_set_search": "JEE Main",
    "selected_tags": ["important", "hard"],
    "selected_magazine": "Physics For You Jan 2023"
  }
}
```

---

## 3. CUSTOM LISTS UI COMPONENTS

### Page Layout Structure
```
Custom Lists Page (Index 4)
├── QVBoxLayout (lists_tab_layout)
│   └── lists_card (QWidget with QVBoxLayout)
│       ├── Header: "Custom Lists" label
│       └── lists_split (QSplitter, Horizontal)
│           ├── Left Side: saved_lists_card
│           │   ├── "Saved Lists" label
│           │   ├── Control buttons
│           │   │   ├── "New List" button
│           │   │   ├── "Rename" button
│           │   │   └── "Delete" button
│           │   └── saved_lists_widget (QListWidget)
│           │       └── Items: "List Name (count) - Magazine"
│           │
│           └── Right Side: list_questions_card
│               ├── list_name_label (QLabel, header)
│               ├── list_filters_label (QLabel, filter display)
│               ├── "Remove Selected from List" button
│               └── list_question_splitter (QSplitter, Vertical)
│                   ├── list_question_table (QTableWidget, 5 columns)
│                   │   └── Columns: "Question No", "Page", "Question Set", "Chapter", "Magazine"
│                   └── list_question_text_view (QTextEdit, readonly)
```

### Key UI Widgets
| Component | Type | Purpose |
|-----------|------|---------|
| `saved_lists_widget` | QListWidget | Lists all saved custom lists |
| `list_question_table` | QTableWidget | Displays questions in selected list (5 cols) |
| `list_question_text_view` | QTextEdit | Shows selected question's full details |
| `list_name_label` | QLabel | Displays selected list name + count |
| `list_filters_label` | QLabel | Shows applied filters (yellow background) |

### UI Properties
- **Question table mode**: Extended selection (multi-select with Ctrl+click)
- **Selection behavior**: SelectRows
- **Edit triggers**: NoEditTriggers (read-only display)
- **Stretch behavior**: Splitter divides horizontally/vertically

---

## 4. QUESTION LIST TAB UI COMPONENTS

### Page Layout Structure
```
Question List Page (Index 2)
├── QVBoxLayout (questions_tab_layout)
│   └── analysis_card (QWidget with QVBoxLayout)
│       └── analysis_split (QSplitter, Horizontal)
│           ├── Left Side: chapter_card
│           │   ├── "Chapters" label
│           │   └── chapter_view (ChapterCardView)
│           │       └── ChapterCardWidget instances (custom painted cards)
│           │
│           └── Right Side: question_card
│               ├── Search & Action Controls
│               │   ├── Search container (light gray background)
│               │   │   ├── question_set_search (QLineEdit)
│               │   │   ├── tag_filter_display (QLineEdit, readonly)
│               │   │   └── tag_filter_btn (QPushButton, 🏷️ emoji)
│               │   │   └── magazine_search (QLineEdit)
│               │   │   └── clear_search_btn (QPushButton, ✕)
│               │   │
│               │   └── Action container (light blue background)
│               │       ├── add_to_list_btn (icon button)
│               │       ├── create_random_list_btn (icon button)
│               │       ├── copy_mode_combo (QComboBox)
│               │       │   └── Options: "Copy: Text", "Copy: Metadata", "Copy: Both"
│               │
│               ├── drag_drop_panel (DragDropQuestionPanel, initially hidden)
│               │   └── Uses custom drag-drop UI for adding questions
│               │
│               └── question_card_view (QuestionListCardView)
│                   └── QuestionAccordionGroup instances
│                       └── QuestionCardWidget instances
```

### Key UI Widgets
| Component | Type | Purpose |
|-----------|------|---------|
| `chapter_view` | ChapterCardView | Scrollable list of chapters (custom painted cards) |
| `question_card_view` | QuestionListCardView | Modern accordion-based question display |
| `drag_drop_panel` | DragDropQuestionPanel | Drag-drop interface for adding to lists |
| `question_set_search` | QLineEdit | Filter by question set name |
| `tag_filter_display` | QLineEdit | Shows selected tags (readonly) |
| `tag_filter_btn` | QPushButton | Opens tag selection dialog |
| `magazine_search` | QLineEdit | Filter by magazine name |
| `copy_mode_combo` | QComboBox | Select what to copy (text/metadata/both) |

### UI Properties
- **Chapter cards**: Custom painted (ChapterCardWidget) with hover effects
- **Questions display**: Modern accordion groups with QuestionCardWidget items
- **Selection mode**: Multi-select via Ctrl+click (handled by QuestionListCardView)
- **Search**: Real-time filtering with three independent criteria

---

## 5. KEY DIFFERENCES BETWEEN TABS

| Aspect | Question List Tab | Custom Lists Tab |
|--------|-------------------|------------------|
| **Primary View** | Modern accordion cards (ChapterCardView + QuestionListCardView) | Traditional table (QTableWidget) |
| **Data Display** | Hierarchical groups with expandable sections | Flat table with 5 columns |
| **Questions Source** | Filtered from current workbook | Stored as persistent list |
| **Edit Capability** | Display only (cards are readonly) | Can remove individual questions |
| **Filters** | Real-time search/tag/magazine filters | Saved with list metadata |
| **Action Buttons** | Add to list, Create random list, Copy mode | Remove from list |
| **Selection Mode** | Multi-select with Ctrl (visual highlight) | Multi-select with rows (standard) |
| **Storage** | In-memory from workbook data | JSON files in QuestionList/ folder |
| **Metadata** | Not directly stored | Stored with list (magazine, filters) |

---

## 6. METHODS COMPARISON

### Custom Lists Methods (Lines with descriptions)

#### List Management
```python
create_new_question_list() [2703]        # Create new empty list
rename_question_list() [2723]            # Rename existing list
delete_question_list() [2760]            # Delete list and file
_save_question_list() [2669]             # Persist to JSON file
_load_saved_question_lists() [2626]      # Load all lists from files
```

#### Data Manipulation
```python
add_selected_to_list() [2786]            # Show drag-drop panel (toggle)
_on_drag_drop_save() [2816]              # Save dragged questions to list
remove_selected_from_list() [2876]       # Remove selected rows from list
_on_drag_drop_cancel() [2830]            # Cancel drag-drop operation
```

#### UI Updates
```python
on_saved_list_selected() [2898]          # Handle list selection in sidebar
_populate_list_question_table() [2921]   # Fill table with list questions
on_list_question_selected() [2972]       # Show selected question in text view
_populate_list_question_table() [2921]   # Display questions in table
```

#### Utility Methods
```python
_get_active_filters() [2950]             # Get current Question tab filters
_highlight_question_card() [2829]        # Flash yellow highlight on card
```

### Question List Tab Methods

#### Navigation
```python
_create_questions_page() [407]           # Create initial page layout
on_chapter_selected() [--]               # Handle chapter card click
on_question_card_selected() [--]         # Handle question card click
```

#### Filtering & Search
```python
on_question_set_search_changed() [--]    # Update questions on search
on_magazine_search_changed() [--]        # Filter by magazine
_show_tag_filter_dialog() [--]           # Open tag selection dialog
clear_question_search() [--]             # Reset all filters
```

#### List Creation
```python
create_random_list_from_filtered() [3064] # Create list from current filtered view
```

---

## 7. DRAG-DROP PANEL DETAILS

### DragDropQuestionPanel Class
**Location:** `src/ui/widgets.py`, Lines 2054-2564

**Purpose:** Allows users to drag questions from Question List tab and add them to Custom Lists

**Structure:**
```
Top Row:
  ├── "Add to list:" label
  ├── list_selector (QComboBox) - dropdown of available lists
  ├── Save button (green)
  └── Cancel button (red)

Existing Questions Section:
  ├── "Existing Questions:" label
  └── existing_chip_scroll (scrollable read-only chips showing current list contents)

Drop Area:
  ├── "← Drag questions here" label (shows when empty)
  └── chip_scroll (scrollable area showing dragged questions as removable chips)
```

### Key Features
- **Drag acceptance:** Accepts MIME type `"application/x-question-data"`
- **Visual feedback:** Highlights on drag-over, shows chip count
- **Duplicate prevention:** Checks `row_number` to avoid duplicates
- **Chip management:** Wrapping layout with max 8 chips per row
- **Existing questions:** Shows inactive chips for current list contents

### DragDropQuestionPanel Methods
```python
dropEvent() [--]                         # Handle dropped questions
dragEnterEvent() [--]                    # Visual feedback on drag enter
dragLeaveEvent() [--]                    # Reset visual on drag leave
_add_chip() [--]                         # Add question as visual chip
_remove_chip() [--]                      # Remove question chip
_on_save() [--]                          # Emit save signal with questions
_on_cancel() [--]                        # Cancel operation
display_existing_questions() [2503]      # Show current list questions
_add_existing_chip() [--]                # Add inactive chip for existing question
update_list_selector() [2483]            # Update dropdown with new lists
```

---

## 8. QUESTION CARD VIEW DETAILS

### QuestionListCardView Class
**Location:** `src/ui/widgets.py`, Lines 1325-1450+

**Purpose:** Modern scrollable container replacing traditional QTreeWidget

**Structure:**
```
QScrollArea (QuestionListCardView)
└── container (QWidget with QVBoxLayout)
    └── Multiple QuestionAccordionGroup widgets
        └── Multiple QuestionCardWidget instances
```

### Key Features
- **Accordion groups:** Collapsible/expandable question groups
- **Multi-select:** Ctrl+click to select multiple questions
- **Visual feedback:** Selected cards highlighted
- **Signals:** Emits `question_selected` when card clicked
- **Data tracking:** Maintains `selected_questions` list

### QuestionListCardView Methods
```python
clear() [--]                             # Remove all groups
add_group() [--]                         # Add accordion group
on_question_card_clicked() [--]          # Handle card click with Ctrl support
```

---

## 9. KEY SIGNALS & CONNECTIONS

### Custom Lists Tab Signals
```python
saved_lists_widget.itemSelectionChanged
  → on_saved_list_selected()
  
list_question_table.itemSelectionChanged
  → on_list_question_selected()

remove_from_list_btn.clicked
  → remove_selected_from_list()

drag_drop_panel.save_clicked
  → _on_drag_drop_save(list_name, questions)

drag_drop_panel.cancel_clicked
  → _on_drag_drop_cancel()
```

### Question List Tab Signals
```python
chapter_view.chapter_selected
  → on_chapter_selected(chapter_key)

question_card_view.question_selected
  → on_question_card_selected(question_data)

add_to_list_btn.clicked
  → add_selected_to_list()

tag_filter_btn.clicked
  → _show_tag_filter_dialog()

question_set_search.textChanged
  → on_question_set_search_changed()

magazine_search.textChanged
  → on_magazine_search_changed()
```

---

## 10. DATA FLOW DIAGRAM

### Adding Questions to Custom List (Drag-Drop Flow)
```
Question List Tab
  │
  ├─→ Drag QuestionCardWidget
  │   │
  │   └─→ Generates MIME data with question data
  │
  ├─→ Drop on DragDropQuestionPanel
  │   │
  │   ├─→ dropEvent() validates MIME type
  │   ├─→ _add_chip() creates visual representation
  │   └─→ pending_questions list updated
  │
  └─→ Click Save button
      │
      ├─→ _on_save() emits save_clicked signal
      │
      ├─→ _on_drag_drop_save() in main_window
      │   │
      │   ├─→ Check for duplicates by row_number
      │   ├─→ Append to question_lists[list_name]
      │   ├─→ _save_question_list(list_name)
      │   └─→ _load_saved_question_lists()
      │
      └─→ Custom Lists Tab refreshed
          │
          ├─→ saved_lists_widget updated
          ├─→ list_question_table populated
          └─→ drag_drop_panel cleared
```

### Viewing Custom List Questions
```
Custom Lists Tab
  │
  ├─→ Click list in saved_lists_widget
  │   │
  │   ├─→ itemSelectionChanged signal
  │   └─→ on_saved_list_selected()
  │
  └─→ _populate_list_question_table()
      │
      ├─→ Get questions from question_lists[list_name]
      ├─→ Get metadata from question_lists_metadata[list_name]
      ├─→ Display filters in list_filters_label
      ├─→ Fill list_question_table with question data
      └─→ Show question_text in list_question_text_view on selection
```

---

## 11. CONFIGURATION & CONSTANTS

### From `config/constants.py`
```python
QUESTION_LIST_DIR          # Path to QuestionList/ folder
TAG_COLORS                 # Color palette for tags
```

### Directory Structure
```
QuestionList/
├── List Name 1.json
├── List Name 2.json
├── Physics Important.json
└── Random 50 Questions.json
```

---

## 12. SUMMARY TABLE: CUSTOM LISTS VS QUESTION LIST TAB

| Feature | Custom Lists (Tab 4) | Question List (Tab 2) |
|---------|---------------------|----------------------|
| **UI Type** | Table-based | Accordion card-based |
| **Data Source** | Persistent JSON files | Current workbook data |
| **Primary Widget** | QTableWidget | QuestionListCardView |
| **Can Add Questions** | Via drag-drop panel | N/A (source tab) |
| **Can Remove Questions** | Yes (row selection) | N/A |
| **Save Filters** | Yes (with list) | N/A |
| **Multi-select** | Ctrl+click rows | Ctrl+click cards |
| **Columns Displayed** | 5 fixed columns | Hierarchical groups |
| **Question Details** | Text view below table | None (cards only) |
| **Search Features** | Via left panel | Real-time filters |
| **Export** | N/A (stored as JSON) | Create new list |

---

## APPENDIX: Line Reference Quick Index

```
CUSTOM LISTS PAGE:
  _create_lists_page() ...................... 680
  Data structures initialization ............ 119-124
  create_new_question_list() ................ 2703
  rename_question_list() .................... 2723
  delete_question_list() .................... 2760
  add_selected_to_list() .................... 2786
  _on_drag_drop_save() ...................... 2816
  _on_drag_drop_cancel() .................... 2830
  remove_selected_from_list() ............... 2876
  on_saved_list_selected() .................. 2898
  on_list_question_selected() ............... 2972
  _populate_list_question_table() ........... 2921
  _save_question_list() ..................... 2669
  _load_saved_question_lists() .............. 2626
  _get_active_filters() ..................... 2950
  _highlight_question_card() ................ 2829
  create_random_list_from_filtered() ........ 3064

QUESTION LIST PAGE:
  _create_questions_page() .................. 407
  DragDropQuestionPanel class ............... 2054
  QuestionListCardView class ................ 1325

WIDGETS FILE:
  QuestionListCardView ...................... 1325
  DragDropQuestionPanel ..................... 2054
  display_existing_questions() .............. 2503
  update_list_selector() .................... 2483
```
