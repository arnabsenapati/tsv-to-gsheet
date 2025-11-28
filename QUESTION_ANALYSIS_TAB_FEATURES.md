# Question Analysis Tab - Comprehensive Feature Documentation

## Overview
The **Question Analysis Tab** is the main hub for exploring, filtering, and analyzing questions from the Excel workbook. It consists of four interconnected sub-tabs that provide different views and operations on the question database. This tab serves as the primary interface for question discovery before curating them into custom lists.

---

## Tab Location
- **Parent Tab**: Question Analysis (main tab level)
- **Sub-Tabs**:
  1. Magazine Editions
  2. Question List
  3. Chapter Grouping
  4. Custom Lists

---

## Sub-Tab 1: Magazine Editions

### Purpose
Browse questions organized by magazine name, publication date (edition), and question sets. Provides a chronological and hierarchical view of the question database.

### Layout Structure

#### Three-Panel Split View

**Left Panel: Magazine Tree (Hierarchical)**
```
📂 Physics For You (45 editions, 1,234 sets)
  ├── 📅 2024 (12 editions, 456 sets)
  │   ├── Jan 2024 (3 sets)
  │   ├── Feb 2024 (5 sets)
  │   └── Mar 2024 (4 sets)
  ├── 📅 2023 (12 editions, 389 sets)
  └── ⚠️ Missing Editions (3)
      └── Apr 2024
      └── May 2024
      └── Jun 2024
```

**Components**:
- **Search Box**: Filter magazines/editions by text
- **Clear Button**: Reset search filter
- **Tree Widget**: 3-level hierarchy
  - Level 1: Magazine name (e.g., "Physics For You")
  - Level 2: Year grouping (e.g., "2024")
  - Level 3: Individual editions (e.g., "Jan 2024")
  - Special: "Missing Editions" section (non-selectable)

**Right Panel: Question Sets Tree**
- Shows question sets for selected edition
- Expandable tree structure:
  - Parent nodes: Question set names (e.g., "JEE Main 2024 Paper 1")
  - Child nodes: Individual questions with Qno, Page
- Columns: Question Set/Question | Qno | Page

**Bottom Panel: Question Text Viewer**
- Read-only text editor showing full question content
- Dark theme styling
- HTML formatted with metadata

### Features

#### 1. Magazine Edition Navigation

**Hierarchy Browsing**:
- Click magazine → See years
- Click year → See editions in that year
- Click edition → See question sets on right

**Year Color Coding**:
```python
2020: #fef3c7 (light yellow)
2021: #dbeafe (light blue)
2022: #d1fae5 (light green)
2023: #fce7f3 (light pink)
2024: #e0e7ff (light indigo)
2025: #fed7aa (light orange)
...
```

**Missing Editions Detection**:
- Automatically detects gaps in monthly sequence
- Shows red warning icon ⚠️
- Displays missing months (e.g., "Apr 2024 - Jun 2024")
- Non-clickable items (visual indicator only)

#### 2. Magazine Search/Filter

**Search Box Behavior**:
- Real-time filtering as you type
- Case-insensitive search
- Searches across:
  - Magazine names
  - Year labels
  - Edition labels (e.g., "Jan", "2024")

**Filter Logic**:
- Shows/hides items based on match
- Partial matches supported (e.g., "phy" matches "Physics")
- Child items visible if parent matches
- Parent visible if any child matches

**Example**:
```
Search: "2024"
Result: All magazines shown, only 2024 years and their editions visible
```

#### 3. Question Set Viewing

**When Edition Selected**:
1. Header updates: "Physics For You - Jan 2024"
2. Question sets loaded from DataFrame (cached for performance)
3. Tree populated with question set hierarchy
4. Each question set expandable to show individual questions

**Tree Structure**:
```
📖 JEE Main 2024 Paper 1 (25 questions)
  ├── Q1 | Page 45
  ├── Q2 | Page 45
  └── Q3 | Page 46
📖 NEET 2024 Practice (30 questions)
  ├── Q1 | Page 50
  └── Q2 | Page 50
```

**Performance Optimization**:
- Uses cached DataFrame (`self.workbook_df`)
- Filters by magazine name and edition
- Groups by question set name
- O(n) single pass through relevant rows

#### 4. Question Detail Viewer

**Trigger**: Click on any question (child node) in question sets tree

**Display Format**:
```html
<div style="background: #0f172a; color: #e2e8f0;">
  Question No: Q15
  Page: 45
  Question Set: Mechanics
  Magazine: Physics For You - Jan 2024
  Chapter: Laws of Motion
  ─────────────────────────
  [Full question text here...]
</div>
```

**Styling**:
- Background: Dark (`#0f172a`)
- Text: Light gray (`#e2e8f0`)
- Labels: Blue (`#60a5fa`)
- Values: Lighter gray (`#cbd5e1`)

#### 5. Edition Statistics

**Top Summary Card**:
- **Total Editions**: Count of all editions across all magazines
- **Question Sets**: Total number of unique question sets

**Example**: `Total Editions: 45 | Question Sets: 1,234`

---

## Sub-Tab 2: Question List

### Purpose
Main interface for browsing and filtering questions with advanced search capabilities. Primary source for adding questions to custom lists.

### Layout Structure

#### Two-Panel Split View

**Left Panel: Chapters Table**
- 2 columns: Chapter | Questions count
- Sorted by question count (descending), then alphabetically
- Single selection mode
- Shows chapter groups from grouping JSON

**Right Panel: Questions Tree**
- Hierarchical display grouped by question set similarity
- 3 columns: Question | Qno | Page
- Expandable groups
- Multi-select enabled (ExtendedSelection)
- Bottom splitter: Question text viewer

### Search and Filter Controls

#### Search Bar (Top of Right Panel)

**1. Question Set Search**
```
Label: "Question Set:"
Input: QLineEdit with placeholder "Type to search..."
Behavior: Real-time filtering, normalized text matching
```

**2. Tag Filter**
```
Label: "Tags:"
Display: Shows selected tags (e.g., "important, previous year")
Button: "Select Tags" → Opens multi-select dialog
```

**3. Magazine Search**
```
Label: "Magazine:"
Input: QLineEdit with placeholder "Type to search..."
Behavior: Real-time filtering, normalized text matching
```

**4. Clear Button**
```
Button: "Clear Search"
Action: Resets all filters (Question Set, Magazine, Tags)
```

#### List Control Buttons

**1. Add Selected to List**
```
Button: "Add Selected to List"
Action: Opens dialog to select target list
Requirements: Questions must be selected in tree
```

**2. Create Random List from Filtered**
```
Button: "Create Random List from Filtered"
Action: Opens dialog for name and count
Creates: New list with random sample from visible questions
```

### Features

#### 1. Chapter-Based Filtering

**How It Works**:
1. Click chapter in left table (e.g., "Mechanics")
2. System loads all questions with that chapter classification
3. Right panel updates to show filtered questions
4. `self.current_selected_chapter` tracks selection

**Chapter Groups**:
- Loaded from Chapter Grouping JSON
- Each chapter is a high-level group (e.g., "Mechanics", "Thermodynamics")
- Question count shows total questions in that group

**Question Count Display**:
```
Chapter                    | Questions
─────────────────────────────────────
Mechanics                  | 450
Thermodynamics            | 230
Waves and Optics          | 180
```

#### 2. Question Set Search

**Search Mechanism**:
- Normalized text comparison (lowercase, collapsed whitespace)
- Searches in `question_set_name` field
- Partial matches supported

**Example**:
```
Search: "jee main"
Matches:
  - "JEE Main 2024 Paper 1"
  - "JEE Main 2023 Paper 2"
  - "JEE MAIN Practice Set"
```

**State Management**:
- `self.question_set_search_term` stores current search
- Updates on every keystroke (`textChanged` signal)
- Triggers `_apply_question_search()` to refresh tree

#### 3. Tag-Based Filtering (Multi-Select)

**Tag Selection Dialog**:
1. Click "Select Tags" button
2. Dialog shows all available tags with colored badges
3. User selects multiple tags (checkbox list)
4. Click OK to apply

**Tag Display**:
- Selected tags shown in label (e.g., "important, conceptual, previous year")
- If none selected: Shows "None"

**Filter Logic**:
- Question must have ALL selected tags (AND logic, not OR)
- Tags stored in `self.selected_tag_filters` list
- Compares with `question.get("tags", [])` array

**Example**:
```
Selected Tags: ["important", "previous year"]
Question 1 Tags: ["important", "previous year", "numerical"]  → ✅ Shown
Question 2 Tags: ["important", "conceptual"]                   → ❌ Hidden
Question 3 Tags: ["previous year", "mcq"]                      → ❌ Hidden
```

#### 4. Magazine Search

**Search Mechanism**:
- Normalized text comparison
- Searches in `magazine` field
- Partial matches supported

**Example**:
```
Search: "physics"
Matches:
  - "Physics For You - Jan 2024"
  - "Physics For You - Feb 2024"
Does Not Match:
  - "Chemistry Today - Jan 2024"
```

**State Management**:
- `self.magazine_search_term` stores current search
- Updates on every keystroke
- Triggers `_apply_question_search()` to refresh tree

#### 5. Combined Filtering

**Filter Priority** (all applied together):
1. Chapter filter (from left table selection)
2. Question Set search term
3. Tag filters (multi-select)
4. Magazine search term

**Example Workflow**:
```
1. Select chapter: "Mechanics"
2. Type Question Set: "JEE Main"
3. Select Tags: "important", "previous year"
4. Type Magazine: "physics"

Result: Questions that:
  - Belong to Mechanics chapter
  - AND Question set contains "JEE Main"
  - AND Have both "important" AND "previous year" tags
  - AND Magazine contains "physics"
```

#### 6. Question Tree Grouping

**Grouping Strategy**:
Questions are grouped by "similarity" of question set names to reduce clutter.

**Group Key Extraction**:
```python
def _extract_group_key(self, question_set_name: str) -> str:
    # Normalize to lowercase
    # Remove common suffixes (years, paper numbers)
    # Take first 2-3 significant words
    # Return group key
```

**Example Grouping**:
```
📁 jee main (75 questions)
  ├── JEE Main 2024 Paper 1 (Q1, Q2, Q3...)
  ├── JEE Main 2024 Paper 2 (Q1, Q2, Q3...)
  └── JEE Main 2023 Paper 1 (Q1, Q2, Q3...)

📁 neet (50 questions)
  ├── NEET 2024 Practice Set 1 (Q1, Q2...)
  └── NEET 2023 Paper (Q1, Q2...)
```

**Benefits**:
- Easier to browse large question sets
- Related questions stay together
- Reduces visual clutter

#### 7. Question Selection and Viewing

**Selection Modes**:
- Single click: Select one question
- Ctrl+Click: Multi-select individual questions
- Shift+Click: Select range
- Click group header: Selects all questions in group

**Question Detail Viewer** (Bottom Panel):
Same format as Magazine Editions tab:
```
Question No: Q15
Page: 45
Question Set: Mechanics
Magazine: Physics For You
Chapter: Laws of Motion
─────────────────────────
[Full question text here...]
```

#### 8. Context Menu (Right-Click)

**Trigger**: Right-click on question tree item (question or group)

**Menu Options**:

**For Individual Questions**:
- ✏️ **Reassign to Chapter**: Move single question to different chapter
- 🏷️ **Assign Tag to Group**: Add tag to the group this question belongs to

**For Group Headers**:
- 📦 **Reassign All to Chapter**: Bulk move all questions in group to different chapter
- 🏷️ **Assign Tag to Group**: Add tag to the entire group
- 🗑️ **Remove Tag from Group**: Remove tag from the group

**Reassign to Chapter**:
1. Right-click question/group → "Reassign to Chapter"
2. Dialog shows list of available chapters
3. Select target chapter
4. Confirmation prompt
5. Updates Excel workbook (modifies high-level chapter column)
6. Reloads workbook to reflect changes

**Assign Tag to Group**:
1. Right-click → "Assign Tag"
2. Dialog prompts for tag name
3. Tag added to group in `tags.cfg`
4. Tag badge appears next to group in tree
5. Tag color assigned from color palette

**Remove Tag**:
1. Right-click group with tag → "Remove Tag"
2. Submenu shows existing tags
3. Click tag to remove
4. Updated in `tags.cfg`

---

## Sub-Tab 3: Chapter Grouping

### Purpose
Manage the hierarchical organization of chapters. Define and maintain chapter groups for automatic classification.

### Layout Structure

#### Three-Panel Horizontal Split

**Left Panel: Group List**
- Shows all high-level groups from `canonical_order`
- Single selection
- Order matches JSON file

**Middle Panel: Chapter List**
- Shows chapters belonging to selected group
- Sorted alphabetically (case-insensitive)
- Single selection

**Right Panel: Move Controls**
```
Label: "Move chapter to group"
Dropdown: Lists all available groups
Button: "Move Chapter"
```

### Features

#### 1. View Chapter Organization

**Browsing**:
1. Click group in left panel (e.g., "Mechanics")
2. Middle panel shows all chapters in that group
3. Can see which chapters belong where

**Example Display**:
```
Left Panel:          Middle Panel:
─────────────        ─────────────────────────────
Mechanics            motion in a straight line
Thermodynamics       motion in a plane
Waves and Optics     laws of motion
Electricity          work energy and power
Modern Physics       rotational motion
Others               gravitation
```

#### 2. Move Chapters Between Groups

**Process**:
1. Select group in left panel
2. Select chapter in middle panel
3. Choose target group from dropdown
4. Click "Move Chapter"
5. Chapter moved to new group
6. JSON file updated automatically
7. UI refreshed

**Validation**:
- Cannot move to same group (no-op)
- Must have group and chapter selected

**Use Cases**:
- Reclassify misplaced chapters
- Reorganize topic structure
- Clean up "Others" group

#### 3. Auto-Assignment of New Chapters

**Trigger**: When workbook loaded with new chapters

**Process**:
1. Application extracts all unique chapter names
2. For each chapter, checks if it exists in any group
3. If not found, runs matching algorithm:
   - Exact match → Assign to matching group
   - Substring match → Assign to best fit group
   - No match → Assign to "Others"
4. Saves updated grouping JSON
5. Logs assignments

**Example**:
```
New chapter found: "thermodynamic processes"
Best match: "thermodynamics" in Thermodynamics group
Action: Auto-assigned to Thermodynamics
Log: "Auto-assigned chapter 'thermodynamic processes' to 'Thermodynamics'"
```

---

## Sub-Tab 4: Custom Lists

See `QUESTION_LIST_TAB_FEATURES.md` for complete documentation.

**Quick Summary**:
- Create and manage custom question collections
- Add questions from Question List tab
- Create random lists from filtered questions
- View and remove questions from lists
- Preserve filter context

---

## Connection: Question Analysis → Custom Lists

### Workflow Integration

#### Workflow 1: Manual Selection
```
1. Question Analysis → Question List sub-tab
2. Apply filters:
   - Select chapter: "Mechanics"
   - Search question set: "JEE Main"
   - Select tags: "important"
3. Browse filtered questions in tree
4. Multi-select desired questions (Ctrl+Click)
5. Click "Add Selected to List"
6. Choose/create target list
7. Questions added with metadata preserved
```

#### Workflow 2: Random Selection
```
1. Question Analysis → Question List sub-tab
2. Apply comprehensive filters:
   - Chapter: "Thermodynamics"
   - Tags: "conceptual", "previous year"
   - Magazine: "Physics For You"
3. Click "Create Random List from Filtered"
4. Enter list name: "Thermodynamics Practice"
5. Set count: 30 questions
6. System randomly samples from visible questions
7. List created with filters saved in metadata
```

#### Workflow 3: Browse and Curate
```
1. Question Analysis → Magazine Editions sub-tab
2. Browse by magazine and date
3. Select edition: "Physics For You - Jan 2024"
4. Review question sets
5. Switch to Question List sub-tab
6. Search for that magazine's questions
7. Add specific questions to list
8. Result: Curated list from specific edition
```

### Data Flow

```
┌─────────────────────────────────────────────────┐
│           Question Analysis Tab                  │
│                                                  │
│  ┌──────────────┐      ┌──────────────────┐    │
│  │  Magazine    │      │  Question List   │    │
│  │  Editions    │      │  (Main Hub)      │    │
│  │              │      │                  │    │
│  │ - Browse by  │      │ - Filter by:     │    │
│  │   date       │      │   • Chapter      │    │
│  │ - View sets  │      │   • Question Set │    │
│  │              │      │   • Tags         │    │
│  └──────────────┘      │   • Magazine     │    │
│                        │                  │    │
│                        │ - Group similar  │    │
│                        │ - Multi-select   │    │
│                        └──────────────────┘    │
│                                 │               │
│                                 ↓               │
│                  ┌──────────────────────────┐  │
│                  │   Custom Lists Tab       │  │
│                  │                          │  │
│                  │ - Save selected          │  │
│                  │ - Random sampling        │  │
│                  │ - Filter preservation    │  │
│                  └──────────────────────────┘  │
└─────────────────────────────────────────────────┘

Data Source: Excel Workbook DataFrame (cached)
Storage: QuestionList/*.json files
Configuration: Chapter Grouping JSON files
```

### Shared State

**Application-Level Variables**:
```python
# Question data
self.workbook_df: pd.DataFrame              # Cached workbook data
self.chapter_questions: dict[str, list]     # Questions by chapter
self.current_questions: list                # Currently filtered questions
self.all_questions: list                    # All questions (pre-filter)

# Filter state
self.current_selected_chapter: str          # Selected chapter
self.question_set_search_term: str          # Question set filter
self.magazine_search_term: str              # Magazine filter
self.selected_tag_filters: list[str]        # Selected tags

# Chapter grouping
self.canonical_chapters: list[str]          # Group order
self.chapter_groups: dict[str, list]        # Group → chapters mapping
self.chapter_lookup: dict[str, str]         # Chapter → group mapping

# Lists
self.question_lists: dict[str, list]        # List name → questions
self.question_lists_metadata: dict          # List metadata
self.current_list_name: str                 # Selected list
```

### Filter Preservation

**When Creating List from Filtered Questions**:
1. `_get_active_filters()` captures current state:
   ```python
   {
       "selected_chapter": "Mechanics",
       "question_set_search": "JEE Main",
       "selected_tags": ["important", "previous year"],
       "selected_magazine": "physics for you"
   }
   ```

2. Stored in list metadata:
   ```json
   {
       "questions": [...],
       "metadata": {
           "magazine": "physics for you",
           "filters": {
               "selected_chapter": "Mechanics",
               "question_set_search": "JEE Main",
               "selected_tags": ["important", "previous year"],
               "selected_magazine": "physics for you"
           }
       }
   }
   ```

3. Displayed in Custom Lists tab:
   ```
   🔍 Filters: Chapter: 'Mechanics' | Question Set: 'JEE Main' | 
              Tags: important, previous year | Magazine: physics for you
   ```

### Benefits of Integration

1. **Context Preservation**: Filters remembered when creating lists
2. **Reproducibility**: Can recreate the same query later
3. **Documentation**: Know exactly how list was created
4. **Flexibility**: Multiple filtering approaches (manual, random, filtered)
5. **Efficiency**: Cached DataFrame for fast filtering
6. **Traceability**: Question metadata preserved across operations

---

## Performance Optimizations

### 1. DataFrame Caching
```python
self.workbook_df: pd.DataFrame | None = None

# Loaded once when workbook opens
# Reused for all filtering operations
# Invalidated only when workbook changes
```

**Benefits**:
- No repeated file reads
- Fast filtering (pandas operations)
- Memory efficient (single copy)

### 2. Lazy Loading
- Magazine tree populated only when tab opened
- Question sets loaded only when edition selected
- Question text loaded only when question selected

### 3. Incremental Updates
- Search filters update without full reload
- Tree items shown/hidden, not recreated
- Scroll position preserved during filter changes

### 4. Grouping Algorithm
- O(n) single pass through questions
- Hash-based grouping for O(1) lookups
- Group keys cached to avoid recomputation

---

## Technical Implementation

### Key Methods

#### Question List Tab
```python
# Filtering
_apply_question_search()               # Apply all filters and update tree
on_chapter_selected()                  # Handle chapter selection
on_question_set_search_changed(text)   # Handle question set search
on_magazine_search_changed(text)       # Handle magazine search
clear_question_search()                # Reset all filters

# Question tree
_populate_question_table(questions)    # Load questions into tree
_extract_group_key(name)               # Generate grouping key
on_question_selected()                 # Show question details

# List integration
add_selected_to_list()                 # Add to existing list
create_random_list_from_filtered()     # Create new random list
_get_active_filters()                  # Capture current filter state
```

#### Magazine Editions Tab
```python
# Tree population
_populate_magazine_tree(details)       # Build magazine hierarchy
_populate_question_sets(sets)          # Show question sets for edition
on_magazine_select()                   # Handle edition selection
on_mag_tree_search_changed(text)       # Filter magazine tree
on_mag_question_selected()             # Show question details
```

#### Chapter Grouping Tab
```python
# Grouping management
_refresh_grouping_ui()                 # Update group list UI
on_group_selected()                    # Show chapters in group
move_selected_chapter()                # Move chapter to new group
_save_chapter_grouping()               # Save to JSON
_reload_grouping_for_magazine(name)    # Load appropriate JSON
```

### Data Structures

#### Question Object
```python
{
    "row_number": 123,                     # Excel row number (unique ID)
    "qno": "Q15",                          # Question number
    "page": "45",                          # Magazine page
    "question_set": "Mechanics",           # Chapter classification
    "question_set_name": "JEE Main 2024",  # Full set name
    "magazine": "Physics For You",         # Source magazine
    "group": "Mechanics",                  # High-level chapter group
    "question_text": "A particle moves...", # Full question
    "tags": ["important", "numerical"]     # Assigned tags
}
```

#### Magazine Detail Object
```python
{
    "normalized": "2024-01",               # Normalized edition key
    "display_name": "Physics For You",     # Magazine name
    "edition_label": "Jan 2024",           # Human-readable edition
    "question_sets": [                     # List of question set names
        "JEE Main 2024 Paper 1",
        "NEET Practice Set"
    ]
}
```

---

## Common Use Cases

### Use Case 1: Create Topic-Focused Practice Test
```
Goal: Create 30-question test on Mechanics from JEE Main papers

Steps:
1. Question List tab → Select chapter "Mechanics"
2. Search question set: "JEE Main"
3. Select tags: "previous year"
4. Click "Create Random List from Filtered"
5. Name: "JEE Main Mechanics Practice"
6. Count: 30
7. Click OK

Result: List with 30 random JEE Main Mechanics questions, 
        filters saved for reproducibility
```

### Use Case 2: Curate Edition-Specific Collection
```
Goal: Extract all Physics questions from January 2024 edition

Steps:
1. Magazine Editions tab
2. Expand "Physics For You" → "2024" → Click "Jan 2024"
3. Review question sets in right panel
4. Switch to Question List tab
5. Search magazine: "Physics For You"
6. Search question set: "Jan 2024" (if needed)
7. Select all questions (Ctrl+A in group)
8. Click "Add Selected to List"
9. Choose list: "January 2024 Collection"

Result: All questions from that specific edition saved to list
```

### Use Case 3: Reclassify Misplaced Questions
```
Goal: Move thermodynamics questions incorrectly placed in "Others"

Steps:
1. Question List tab → Select chapter "Others"
2. Browse questions, identify thermodynamics ones
3. Right-click question → "Reassign to Chapter"
4. Select "Thermodynamics"
5. Confirm
6. Workbook updated, data reloaded
7. Question now appears under "Thermodynamics"

Result: Question properly classified, available in correct chapter filter
```

### Use Case 4: Tag Important Question Groups
```
Goal: Tag all JEE Advanced questions as "difficult"

Steps:
1. Question List tab
2. Search question set: "JEE Advanced"
3. Questions grouped automatically (e.g., "jee advanced" group)
4. Right-click group header → "Assign Tag to Group"
5. Enter tag: "difficult"
6. Choose color: Red
7. Tag saved to tags.cfg

Result: All JEE Advanced question groups now show "difficult" tag,
        can be filtered by this tag later
```

---

## Best Practices

### 1. Filter Before Creating Lists
Apply specific filters to narrow down questions before creating lists. This ensures lists are focused and relevant.

### 2. Use Descriptive List Names
Include context in list names:
- ✅ "JEE Main 2024 Mechanics - Important"
- ❌ "Test 1"

### 3. Preserve Filters
Use "Create Random List from Filtered" to save filter context for reproducibility.

### 4. Regular Chapter Cleanup
Periodically check "Others" group and reclassify chapters properly.

### 5. Leverage Tags
Tag question groups by difficulty, importance, or exam type for powerful filtering.

### 6. Combine Multiple Filters
Use chapter + tags + question set filters together for highly specific question selection.

### 7. Review Before Adding
Always review filtered questions before adding to lists to ensure quality.

---

## Troubleshooting

### Issue: Questions Not Showing
**Check**:
1. Is workbook loaded? (check top row count label)
2. Are filters too restrictive? (clear and try again)
3. Is chapter classification correct? (check Chapter Grouping tab)

### Issue: Tags Not Filtering
**Check**:
1. Are tags actually assigned to questions? (check context menu)
2. Are you using AND logic? (all selected tags must match)
3. Check tags.cfg file format

### Issue: Random List Empty
**Check**:
1. Are there visible questions after filtering?
2. Is the requested count larger than available questions?
3. Try relaxing filters

### Issue: Chapter Grouping Not Working
**Check**:
1. Is correct magazine detected? (check status bar)
2. Are chapter names in lowercase in JSON?
3. Reload workbook after JSON changes

---

## Summary

The Question Analysis Tab is the core of the application, providing multiple perspectives on the question database:

- **Magazine Editions**: Chronological, hierarchical browsing
- **Question List**: Powerful filtering and selection hub
- **Chapter Grouping**: Organizational structure management
- **Custom Lists**: Curated collections with preserved context

All four sub-tabs work together seamlessly, with the Question List tab serving as the central hub that feeds into Custom Lists for long-term storage and organization.
