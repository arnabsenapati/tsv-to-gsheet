# Question List Tab - Feature Documentation

## Overview
The **Question List Tab** (also called **Custom Lists Tab**) allows users to create, manage, and organize custom collections of questions from the main question database. This feature enables educators to curate specific question sets for exams, practice tests, or topic-focused assignments.

---

## Tab Location
- **Parent Tab**: Question Analysis
- **Sub-Tab**: Custom Lists (4th tab in Question Analysis section)

---

## Layout Structure

### Two-Panel Split View

#### Left Panel: Saved Lists Management
- **Header**: "Saved Lists"
- **Controls**:
  - **New List** button - Create a new empty question list
  - **Rename** button - Rename the selected list
  - **Delete** button - Delete the selected list permanently
- **List Widget**: Displays all saved question lists (loaded from `QuestionList/` directory)

#### Right Panel: List Contents Viewer
- **Header**: Dynamic label showing `"<List Name> (X questions)"` or `"Select a list to view questions"`
- **Filter Info Banner**: Yellow banner showing active filters that were applied when creating the list
- **Remove Button**: "Remove Selected from List" - removes selected questions from the current list
- **Questions Table**: 5-column table displaying:
  1. Question No (Qno)
  2. Page (page number from magazine)
  3. Question Set (the set/exam name)
  4. Chapter (high-level chapter classification)
  5. Magazine (source magazine name)
- **Question Text Viewer**: Bottom panel showing full question text with dark theme styling

---

## Core Features

### 1. Create New Question List

**Trigger**: Click "New List" button

**Process**:
1. Dialog prompts for list name
2. User enters unique name
3. Empty list is created and saved to `QuestionList/<name>.json`
4. List appears in Saved Lists widget
5. Logs: `"Created new question list: <name>"`

**Validation**:
- Name cannot be empty
- Duplicate names prompt "already exists" error

**File Storage**: `QuestionList/<list_name>.json`

**File Format**:
```json
{
  "questions": [],
  "metadata": {
    "magazine": "",
    "filters": {}
  }
}
```

---

### 2. Rename Question List

**Trigger**: Select a list → Click "Rename" button

**Process**:
1. Dialog shows current name pre-filled
2. User enters new name
3. Old file deleted: `QuestionList/<old_name>.json`
4. New file created: `QuestionList/<new_name>.json`
5. Internal dictionary keys updated
6. List widget refreshed
7. Logs: `"Renamed question list from '<old>' to '<new>'"`

**Validation**:
- New name cannot be empty
- Cannot rename to existing list name

---

### 3. Delete Question List

**Trigger**: Select a list → Click "Delete" button

**Process**:
1. Confirmation dialog: `"Delete list '<name>'? This cannot be undone."`
2. If confirmed:
   - File deleted: `QuestionList/<name>.json`
   - Entry removed from internal dictionaries
   - List widget refreshed
   - Right panel cleared
3. Logs: `"Deleted question list: <name>"`

**Safety**: Requires explicit confirmation before deletion

---

### 4. Add Questions to List

**Source**: Questions Tab (Question Analysis → Question List)

**Trigger**: Select questions in question tree → Click "Add Selected to List" button

**Process**:
1. If no lists exist, prompt to create new list first
2. User selects questions from question tree (supports multi-select)
3. Dialog shows dropdown of existing lists
4. User selects target list
5. Selected questions added to list (duplicates skipped based on `row_number`)
6. File updated: `QuestionList/<list_name>.json`
7. Toast message: `"Added X question(s) to '<list_name>'"`
8. Logs: `"Added X question(s) to list '<name>'"`

**Duplicate Detection**:
- Uses `row_number` field from DataFrame
- Prevents same question from being added twice

**Filtering**:
- Only leaf nodes (actual questions) are added
- Group headers are ignored

---

### 5. Remove Questions from List

**Trigger**: Select questions in list table → Click "Remove Selected from List" button

**Process**:
1. User selects one or more rows in the list question table
2. Questions removed from list (processed in reverse order to avoid index shifts)
3. File updated: `QuestionList/<list_name>.json`
4. Table refreshed to reflect changes
5. Logs: `"Removed X question(s) from '<name>'"`

**Multi-Select Support**: Can remove multiple questions simultaneously

---

### 6. Create Random List from Filtered Questions

**Source**: Questions Tab

**Trigger**: Apply filters → Click "Create Random List from Filtered" button

**Process**:
1. System collects all visible questions from current filtered view
2. Dialog prompts for:
   - **List Name** (text input)
   - **Number of Questions** (spinner, max = visible questions count, default = 30)
3. Shows active filters that will be saved with the list:
   - Selected Chapter
   - Question Set search term
   - Selected Tags (multi-tag filter)
   - Selected Magazine
4. User clicks OK
5. System randomly samples specified number of questions from visible set
6. New list created with:
   - Random question selection
   - Filter metadata saved
7. File saved: `QuestionList/<list_name>.json`
8. Toast message: `"Created list '<name>' with X random questions from filtered view"`
9. Logs same message

**Filter Preservation**:
- Filters are saved in list metadata
- Displayed in yellow banner when list is reopened
- Format: `🔍 Filters: Chapter: 'X' | Tags: Y, Z | Magazine: A`

**Overwrite Protection**:
- If list name exists, prompts: `"List '<name>' already exists. Overwrite?"`

---

### 7. View List Questions

**Trigger**: Click on a list name in Saved Lists widget

**Process**:
1. List name displayed in header with question count
2. Filter banner shown if filters exist (yellow background)
3. Questions loaded into table (5 columns)
4. Table columns auto-resized to fit content
5. First question NOT auto-selected

**Empty List Handling**: Shows header but empty table

---

### 8. View Question Details

**Trigger**: Click on a question row in list table

**Process**:
1. Question text viewer populated with formatted HTML
2. Dark theme styling applied (`#0f172a` background, `#e2e8f0` text)
3. Fields displayed:
   - **Question No**: From `qno` field
   - **Page**: From `page` field
   - **Question Set**: From `question_set` field
   - **Magazine**: From `magazine` field
   - **Chapter**: From `group` field (high-level chapter)
   - **Question Text**: Full text with line breaks preserved

**Styling**:
- Field labels: `#60a5fa` (blue)
- Field values: `#cbd5e1` (light gray)
- Separator: `#475569` horizontal rule
- Font: Arial, sans-serif
- Padding: 12px

---

## Data Storage

### File Structure
```
QuestionList/
  ├── Practice Test 1.json
  ├── JEE Main 2024 Physics.json
  └── Mechanics Basics.json
```

### JSON Format
```json
{
  "questions": [
    {
      "qno": "Q1",
      "page": "45",
      "question_set": "Mechanics",
      "question_set_name": "JEE Main 2024 Paper 1",
      "magazine": "Physics for You",
      "group": "Motion in a Straight Line",
      "row_number": 123,
      "question_text": "A particle moves with velocity...",
      "tags": ["kinematics", "motion"]
    }
  ],
  "metadata": {
    "magazine": "physics for you",
    "filters": {
      "selected_chapter": "Mechanics",
      "question_set_search": "JEE",
      "selected_tags": ["important", "conceptual"],
      "selected_magazine": "physics for you"
    }
  }
}
```

---

## Integration with Other Features

### From Questions Tab
1. **Chapter Selection** → Filters questions → Add to list
2. **Question Set Search** → Narrow results → Add to list
3. **Tag Filtering** → Multi-tag filter → Create random list
4. **Magazine Search** → Magazine-specific → Add to list

### Question Data Source
- Questions come from main workbook DataFrame
- Each question contains:
  - `row_number`: Unique identifier from Excel row
  - `qno`: Question number
  - `page`: Magazine page number
  - `question_set`: Chapter classification
  - `question_set_name`: Full exam/set name
  - `magazine`: Source magazine
  - `group`: High-level chapter grouping
  - `question_text`: Full question content

---

## User Workflows

### Workflow 1: Create Custom Practice Test
1. Go to Questions Tab
2. Select chapter "Mechanics"
3. Add tag filter "important" + "previous year"
4. Click "Create Random List from Filtered"
5. Enter name "Practice Test - Mechanics"
6. Set count to 25 questions
7. Click OK → List created with filters preserved

### Workflow 2: Build Topic-Specific Collection
1. Go to Questions Tab
2. Search question set: "JEE Main"
3. Select chapter "Thermodynamics"
4. Browse questions, select 15 manually
5. Click "Add Selected to List"
6. Choose "Thermodynamics - JEE Collection"
7. Questions added to existing list

### Workflow 3: Manage Exam Question Bank
1. Go to Custom Lists Tab
2. Click "New List"
3. Name: "Mock Test 1"
4. Return to Questions Tab
5. Apply filters and add questions
6. Back to Custom Lists Tab
7. Review list, remove unwanted questions
8. Rename to "Mock Test 1 - Final"

---

## Technical Implementation Details

### Methods Involved

#### Creation & Management
- `create_new_question_list()` - Creates empty list with user-provided name
- `rename_question_list()` - Renames list file and updates internal references
- `delete_question_list()` - Deletes list file after confirmation

#### Adding Questions
- `add_selected_to_list()` - Adds selected questions from question tree to chosen list
- `create_random_list_from_filtered()` - Creates new list with random sample from filtered view

#### Removing Questions
- `remove_selected_from_list()` - Removes selected questions from current list

#### Viewing & Loading
- `on_saved_list_selected()` - Handles list selection in left panel
- `_populate_list_question_table()` - Populates right panel table with list questions
- `on_list_question_selected()` - Shows question details in bottom viewer
- `_load_saved_question_lists()` - Loads all lists from QuestionList directory on startup

#### Persistence
- `_save_question_list(list_name, save_filters=False)` - Saves list to JSON file

---

## Filter Preservation Feature

### Filter Types Saved
1. **Selected Chapter**: Chapter selected from left table
2. **Question Set Search**: Text from question set search box
3. **Selected Tags**: List of tags from multi-tag filter dialog
4. **Selected Magazine**: Magazine name from magazine search

### Filter Display
- Shown in yellow banner: `🔍 Filters: <filter1> | <filter2> | ...`
- Background: `#fef3c7` (light yellow)
- Text color: `#92400e` (dark brown)
- Icon: 🔍 magnifying glass emoji

### Use Cases
- **Reproducibility**: Recreate the same filtered view later
- **Documentation**: Know exactly which criteria were used
- **Consistency**: Maintain filter context across sessions

---

## Error Handling

### Validation Errors
- **Empty list name**: "Please enter a list name."
- **Duplicate name**: "List '<name>' already exists."
- **No lists exist**: "No question lists exist. Create a new list?"
- **No selection**: "Please select questions to add."
- **No questions in filtered view**: "No questions available in the current filtered view."

### File System Errors
- **Permission denied**: Logs error, shows message
- **JSON parsing error**: Logs error, skips corrupted file
- **Missing directory**: Creates `QuestionList/` directory automatically

---

## Performance Considerations

### Optimization Strategies
1. **Lazy Loading**: Questions loaded only when list is selected
2. **Duplicate Prevention**: Uses `row_number` hash lookup
3. **Batch Operations**: Remove operations processed in reverse to avoid re-indexing
4. **Table Auto-Resize**: Columns resize only after all data loaded

### Large List Handling
- No pagination (all questions shown)
- Table widget handles 1000+ questions efficiently
- Question text loaded on-demand (only when row selected)

---

## Future Enhancement Possibilities

### Potential Features
1. **Export to PDF**: Generate printable question paper
2. **Import from CSV**: Bulk import questions
3. **List Categories**: Organize lists into folders
4. **Smart Recommendations**: Suggest questions based on difficulty/topic
5. **Collaborative Sharing**: Export/import lists between users
6. **Version History**: Track changes to lists over time
7. **Bulk Edit**: Move/delete multiple questions at once
8. **Answer Key Management**: Store answers alongside questions

---

## Dependencies

### UI Components
- `QListWidget` - Saved lists display
- `QTableWidget` - Question table (5 columns)
- `QTextEdit` - Question text viewer (HTML support)
- `QSplitter` - Resizable panels (horizontal & vertical)
- `QDialog` - Input dialogs for name/count

### Data Classes
- `pandas.DataFrame` - Main workbook data source
- Python `dict` - In-memory list storage (`question_lists`, `question_lists_metadata`)
- Python `list` - Question collections

### File System
- `pathlib.Path` - File path handling
- `json` module - Serialization/deserialization
- `QUESTION_LIST_DIR` constant - Directory path

---

## Chapter Grouping JSON Configuration

### Purpose
Chapter Grouping JSON files define the hierarchical organization of chapters/topics for each subject. They determine how questions are automatically classified into high-level groups based on their chapter names.

### File Locations
```
PhysicsChapterGrouping.json
ChemistryChapterGrouping.json
MathematicsChapterGrouping.json
```

### File Structure
```json
{
  "canonical_order": [
    "Mechanics",
    "Thermodynamics",
    "Waves and Optics",
    "Electricity and Magnetism",
    "Modern Physics",
    "Others"
  ],
  "groups": {
    "Mechanics": [
      "motion in a straight line",
      "motion in a plane",
      "laws of motion",
      "work energy and power",
      "rotational motion",
      "gravitation"
    ],
    "Thermodynamics": [
      "kinetic theory",
      "thermodynamics",
      "thermal properties of matter"
    ],
    "Waves and Optics": [
      "oscillations",
      "waves",
      "ray optics",
      "wave optics"
    ],
    "Electricity and Magnetism": [
      "electrostatics",
      "current electricity",
      "magnetic effects of current",
      "magnetism and matter",
      "electromagnetic induction",
      "alternating current",
      "electromagnetic waves"
    ],
    "Modern Physics": [
      "dual nature of radiation",
      "atoms",
      "nuclei",
      "semiconductor electronics"
    ],
    "Others": []
  }
}
```

### Key Components

#### 1. `canonical_order` Array
- **Purpose**: Defines the display order of high-level chapter groups
- **Type**: Array of strings
- **Rules**:
  - Must include all group names from `groups` object
  - "Others" should be last (catch-all for unclassified chapters)
  - Order determines display in UI (Chapter Grouping tab, Lists)

#### 2. `groups` Object
- **Purpose**: Maps high-level groups to specific chapter topics
- **Type**: Object with group names as keys, arrays of chapters as values
- **Rules**:
  - All chapter names must be **lowercase** for matching
  - Chapters can only belong to one group
  - Empty arrays allowed (e.g., "Others")
  - Duplicates are removed automatically

### Magazine-to-File Mapping

**Configuration** (`src/config/constants.py`):
```python
MAGAZINE_GROUPING_MAP = {
    "chemistry today": CHEMISTRY_GROUPING_FILE,
    "physics for you": PHYSICS_GROUPING_FILE,
    "mathematics today": MATHEMATICS_GROUPING_FILE,
}
```

**How It Works**:
1. Application detects magazine name from workbook
2. Magazine name normalized: `"Physics For You"` → `"physics for you"`
3. Matching grouping file loaded automatically
4. If no match found, defaults to `PhysicsChapterGrouping.json`

### Chapter Matching Algorithm

**Process**:
1. Extract chapter name from question data (e.g., `"Motion In A Straight Line"`)
2. Normalize to lowercase: `"motion in a straight line"`
3. Search through all groups in grouping JSON:
   - **Exact Match**: Direct lookup in `chapter_lookup` dictionary
   - **Substring Match**: Check if normalized chapter contains any group chapter
   - **Prefix Match**: Check if any group chapter starts with normalized chapter
   - **Keyword Match**: Check if normalized chapter starts with any group chapter keyword
4. If no match found → assign to `"Others"` group

**Example Matching**:
```
Question Chapter: "Laws of Motion - Newton's Laws"
Normalized: "laws of motion - newton's laws"
Matches: "laws of motion" in Mechanics group
Result: Assigned to "Mechanics"
```

### Auto-Assignment Feature

**When Questions Loaded**:
1. Application reads all chapter names from workbook
2. For each chapter, attempts to find matching group
3. If chapter not in any group → auto-assigns based on best match
4. Updates grouping JSON file if new chapters added
5. Logs: `"Auto-assigned chapter 'X' to group 'Y'"`

**Manual Override**:
- Go to **Chapter Grouping Tab**
- Select group on left
- See chapters in that group on right
- Use "Move chapter to group" dropdown to reassign
- Changes saved to appropriate grouping JSON file

### Editing Grouping Files

#### Method 1: Through UI (Recommended)

1. **Load Workbook**: Ensure workbook is loaded so chapters appear
2. **Go to Chapter Grouping Tab** (Question Analysis → Chapter Grouping)
3. **View Groups**: Left panel shows all groups in `canonical_order`
4. **View Chapters**: Click a group to see its chapters in middle panel
5. **Move Chapter**:
   - Select chapter in middle panel
   - Choose target group from dropdown
   - Click "Move Chapter"
6. **Auto-Save**: Changes saved to appropriate JSON file immediately

#### Method 2: Direct JSON Editing

1. Open appropriate grouping file (e.g., `PhysicsChapterGrouping.json`)
2. Edit `canonical_order` to change group display order
3. Edit `groups` to add/remove/reorganize chapters
4. **Important**: All chapter names must be lowercase
5. Save file
6. Reload workbook in application to see changes

**Example Edit**:
```json
{
  "canonical_order": ["Mechanics", "Waves", "Others"],
  "groups": {
    "Mechanics": [
      "motion in a straight line",
      "laws of motion",
      "work energy and power"
    ],
    "Waves": [
      "oscillations",
      "waves",
      "sound waves"  // ← New chapter added
    ],
    "Others": []
  }
}
```

### Creating New Subject Grouping

**Steps**:

1. **Create JSON File**: `NewSubjectChapterGrouping.json`
```json
{
  "canonical_order": [
    "Topic 1",
    "Topic 2",
    "Others"
  ],
  "groups": {
    "Topic 1": [
      "chapter one",
      "chapter two"
    ],
    "Topic 2": [
      "chapter three"
    ],
    "Others": []
  }
}
```

2. **Update Constants** (`src/config/constants.py`):
```python
NEW_SUBJECT_GROUPING_FILE = BASE_DIR / "NewSubjectChapterGrouping.json"

MAGAZINE_GROUPING_MAP = {
    "chemistry today": CHEMISTRY_GROUPING_FILE,
    "physics for you": PHYSICS_GROUPING_FILE,
    "mathematics today": MATHEMATICS_GROUPING_FILE,
    "new subject magazine": NEW_SUBJECT_GROUPING_FILE,  # ← Add this
}
```

3. **Reload Application**: Changes take effect on next workbook load

### Use in Question Lists

**Filter by Chapter Group**:
1. Go to **Questions Tab** (Question Analysis → Question List)
2. Click chapter in left table (e.g., "Mechanics")
3. Right panel shows only questions from that group
4. Use "Add Selected to List" or "Create Random List"
5. Filter preserved in list metadata

**Example Workflow**:
```
1. Select "Mechanics" chapter group
2. Click "Create Random List from Filtered"
3. Name: "Mechanics Practice Test"
4. Count: 25 questions
5. Result: List contains only Mechanics questions
6. Filter saved: "Chapter: 'Mechanics'"
```

### Common Issues & Solutions

#### Issue 1: Chapters Not Grouping Correctly
**Problem**: Questions showing in "Others" instead of proper group

**Solution**:
1. Check chapter name in workbook (might have typos)
2. Verify chapter name is lowercase in grouping JSON
3. Check for extra spaces or special characters
4. Use substring matching: add partial chapter name to group

**Example**:
```json
// Instead of exact match:
"motion in a straight line with uniform acceleration"

// Use shorter version:
"motion in a straight line"
```

#### Issue 2: Wrong Grouping File Loaded
**Problem**: Physics chapters using Chemistry grouping

**Solution**:
1. Check magazine name in workbook
2. Verify normalization: Magazine name must match `MAGAZINE_GROUPING_MAP` keys exactly (lowercase)
3. Update mapping in `constants.py` if needed

#### Issue 3: Changes Not Reflected
**Problem**: Edited JSON but UI still shows old groups

**Solution**:
1. Close application completely
2. Reload workbook (File → Browse → Select workbook)
3. Check that JSON file was saved correctly
4. Verify no syntax errors in JSON (use JSON validator)

#### Issue 4: Duplicate Chapters
**Problem**: Same chapter appearing in multiple groups

**Solution**:
Application automatically removes duplicates and keeps chapter in first matching group. To fix:
1. Edit JSON manually to remove duplicate
2. Or use UI to move chapter to correct group

### Best Practices

1. **Lowercase Everything**: Always use lowercase for chapter names in JSON
2. **Hierarchical Naming**: Use broad group names (e.g., "Mechanics" not "Kinematics")
3. **Consistent Naming**: Keep chapter names consistent across workbooks
4. **Regular Updates**: Add new chapters as they appear in workbooks
5. **Backup Files**: Keep backup of working grouping files before major edits
6. **Test After Changes**: Load workbook and verify chapters group correctly
7. **Use Others Sparingly**: Properly classify chapters instead of leaving in "Others"

### Technical Details

**Loading Process** (`_reload_grouping_for_magazine`):
```python
def _reload_grouping_for_magazine(self, magazine_name: str) -> None:
    grouping_file = MAGAZINE_GROUPING_MAP.get(magazine_name, PHYSICS_GROUPING_FILE)
    self.current_magazine_name = magazine_name
    self.canonical_chapters = self._load_canonical_chapters(grouping_file)
    self.chapter_groups = self._load_chapter_grouping(grouping_file)
```

**Saving Process** (`_save_chapter_grouping`):
```python
def _save_chapter_grouping(self) -> None:
    data = {
        "canonical_order": self.canonical_chapters,
        "groups": self.chapter_groups,
    }
    grouping_file = MAGAZINE_GROUPING_MAP.get(self.current_magazine_name, PHYSICS_GROUPING_FILE)
    grouping_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
```

**Chapter Lookup Dictionary**:
- Built at load time: `{normalized_chapter: group_name}`
- Used for O(1) lookup instead of iterating through all groups
- Rebuilt after any changes to groups

---

## Related Features

### Chapter Grouping Tab
- Uses same question data structure
- Chapter groups can be used as filter criteria
- Allows manual reassignment of chapters to groups
- Displays chapters hierarchically by group

### Questions Tab
- Source of all questions
- Provides search/filter capabilities
- Questions added to lists from here
- Chapter filter uses grouping JSON structure

### Tag Management
- Tags can be assigned to question groups
- Tags used for filtering before creating lists
- Tag colors displayed consistently

---

## Summary

The Question List Tab provides a comprehensive solution for creating and managing custom question collections. It seamlessly integrates with the question filtering system, preserves filter context, and offers flexible workflows for both manual curation and automated random selection. The feature is designed for educators who need to organize questions into practice tests, mock exams, or topic-specific assignments while maintaining traceability of selection criteria.
