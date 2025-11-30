# Question Set Grouping Sidebar - 5 Visual Design Options

## Context
- **Location**: New sidebar menu for managing Question Set Groupings
- **Data Storage**: `QuestionSetGroup.json` in `G:\My Drive\Aditya\IITJEE\QuestionAnalysisJsons`
- **Initial Groups**: "JEE Main Practice", "JEE Advanced Practice", "Monthly Test Drives"
- **Special Group**: "Others" (auto-generated for ungrouped question sets, not saved to JSON)
- **Interaction**: Drag-and-drop question sets between groups
- **Reference Style**: Similar to "Question List" tab visual style (modern, card-based)

---

## Option 1: Modern Card-Based Split Panel (Recommended)

### Visual Layout
```
┌─────────────────────────────────────────────────────────┐
│  Question Set Groups                                    │
├─────────────────────────────────────────────────────────┤
│ Left Panel (Groups)      │  Right Panel (Question Sets) │
│                          │                              │
│ [✓] JEE Main Practice    │  📝 "Are You Ready"         │
│     12 question sets     │  📝 "Brush Up Series"       │
│                          │  📝 "Monthly Drive..."      │
│ [ ] JEE Advanced         │  📝 "Practice Questions"    │
│     5 question sets      │                             │
│                          │                             │
│ [ ] Monthly Test Drives  │                             │
│     8 question sets      │                             │
│                          │                             │
│ [ ] Others              │                             │
│     3 question sets      │  (Drag question sets here) │
└─────────────────────────────────────────────────────────┘
```

### Design Details
- **Left Panel (Groups)**:
  - Blue background (#f8fafc - light)
  - Expandable/Collapsible groups with arrow icons
  - Show count next to each group (e.g., "12 question sets")
  - Selected group highlighted with background color (#e0f2fe)
  - Font: 12px, medium weight for titles
  
- **Right Panel (Question Sets)**:
  - White background
  - List of question sets as draggable items
  - Each item has 📝 icon + name
  - Hover effect: light blue background (#f0f9ff)
  - Drag cursor on hover
  - Delete icon appears on hover (to remove from group)

- **Colors**:
  - Group Selected: #e0f2fe (light blue)
  - Group Text: #1e40af (blue)
  - Count: #64748b (gray)
  - Dragging: Opacity 0.6 with ghost effect
  - Divider: #e2e8f0 (light gray)

---

## Option 2: Minimalist Accordion Tabs

### Visual Layout
```
┌─────────────────────────────────────────────────────────┐
│  Question Set Groups                                    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ► JEE Main Practice (12)                              │
│    📝 "Are You Ready"                                  │
│    📝 "Brush Up Series"                                │
│    📝 "Monthly Drive..."                               │
│    📝 "Practice Questions"                             │
│                                                          │
│  ► JEE Advanced (5)                                    │
│                                                          │
│  ► Monthly Test Drives (8)                             │
│                                                          │
│  ► Others (3)                                          │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Design Details
- **Accordion Style**: Tabs expand/collapse to show question sets
- **Single Panel**: Takes less horizontal space
- **Group Header**: 
  - Arrow icon (►/▼ for expand/collapse)
  - Group name + count in parentheses
  - Background: Subtle gradient (#f8fafc to #f1f5f9)
  - Hover: Border bottom with color highlight
  
- **Question Set Items**:
  - Indented (20px from left)
  - 📝 Icon + name
  - Right-click menu for remove/move options
  - Drag handle icon on hover

- **Colors**:
  - Group Header: #334155 (dark slate)
  - Selected Group Background: #e0f2fe
  - Question Set Text: #475569 (slate)
  - Hover Background: #f0f9ff

---

## Option 3: Two-Column Fixed Layout with Buttons

### Visual Layout
```
┌──────────────────────┬──────────────────────────────┐
│ Question Set Groups  │ Question Sets in Group      │
├──────────────────────┼──────────────────────────────┤
│                      │                              │
│ JEE Main Practice    │ "Are You Ready"             │
│     12 items    [+]  │ "Brush Up Series"           │
│                      │ "Monthly Drive..."          │
│ JEE Advanced         │ "Practice Questions"        │
│      5 items    [+]  │                             │
│                      │                             │
│ Monthly Test Drives  │                             │
│      8 items    [+]  │                             │
│                      │                             │
│ Others               │                             │
│      3 items    [+]  │ (Drop here to move)        │
│                      │                             │
└──────────────────────┴──────────────────────────────┘
```

### Design Details
- **Two Fixed Columns** (40/60 split):
  - Left: Groups list with count + [+] button to add question set
  - Right: Question sets in selected group
  
- **Group Item**:
  - Name on top line, count on bottom line
  - [+] Button to add new question set to this group
  - Click to select, highlight with color
  - Right-click for rename/delete group
  
- **Question Set Item**:
  - Clean text with quote mark styling: "Question Set Name"
  - Hover: Shows remove (×) button on right
  - Drag handle on left (⋮⋮)
  
- **Colors**:
  - Divider: #cbd5e1 (medium gray)
  - Group Selected: Background #e0f2fe
  - Button: #3b82f6 (blue) with hover darkening

---

## Option 4: Tree View with Modern Styling

### Visual Layout
```
┌─────────────────────────────────────────────────────────┐
│  📊 Question Set Groups                                 │
├─────────────────────────────────────────────────────────┤
│                                                          │
│ ▼ JEE Main Practice           [12 sets]   [⋯ menu]     │
│   ├─ Are You Ready                        [✓] [÷]      │
│   ├─ Brush Up Series                      [✓] [÷]      │
│   ├─ Monthly Drive Jan                    [✓] [÷]      │
│   └─ Practice Questions                   [✓] [÷]      │
│                                                          │
│ ▶ JEE Advanced                [5 sets]    [⋯ menu]     │
│                                                          │
│ ▶ Monthly Test Drives         [8 sets]    [⋯ menu]     │
│                                                          │
│ ▶ Others                      [3 sets]    [auto]       │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Design Details
- **Tree Structure**: Parent-child hierarchy with expand/collapse
- **Group Header**:
  - Expand arrow (▼/▶)
  - Group name + count in brackets
  - 3-dot menu icon for group actions (rename, delete, etc)
  
- **Question Set Items** (children):
  - Indented under group
  - Checkmark [✓] on left (to toggle active/inactive)
  - Remove icon [÷] on right hover
  - Drag handle on left when hovering
  
- **Styling**:
  - Group header: Bold, #1e40af (blue)
  - Question set: Regular, #475569 (slate)
  - Group Hover: Light background #f0f9ff
  - Separator lines: #e2e8f0

---

## Option 5: Compact Sidebar with Badges

### Visual Layout
```
┌──────────────────────────────────┐
│  Question Set Groups             │
├──────────────────────────────────┤
│                                   │
│ JEE Main Practice  [12]           │
│ ▼                                 │
│  ├─ Are You Ready                │
│  ├─ Brush Up Series              │
│  ├─ Monthly Drive...             │
│  └─ Practice Qst.                │
│                                   │
│ JEE Advanced       [5]            │
│ ▶                                 │
│                                   │
│ Monthly Test       [8]            │
│ ▶                                 │
│                                   │
│ Others             [3]            │
│ ▶                                 │
│                                   │
└──────────────────────────────────┘
```

### Design Details
- **Compact Form**: Minimal spacing, narrow sidebar
- **Group Header**:
  - Name on left + Badge with count on right
  - Badge: Rounded background (#3b82f6, white text)
  - Expand arrow below group name (▼/▶)
  
- **Question Set Items**:
  - Indented with bullet point (├─, └─)
  - Text truncated with ellipsis if too long
  - Hover: Full tooltip shows full name
  - Small delete icon [×] appears on hover
  
- **Colors**:
  - Badge: Blue background (#3b82f6) with white text
  - Group: #1e40af (blue)
  - Text: #334155 (dark slate)
  - Hover: #fef3c7 (yellow-light) for subtle highlight

---

## Recommended Implementation Approach

### Start with Option 1 (Modern Card-Based)
**Reasons:**
1. ✅ Consistent with existing "Question List" tab style
2. ✅ Best UX for drag-and-drop (clear visual separation)
3. ✅ Scales well with many question sets
4. ✅ Professional appearance
5. ✅ Easy to extend with filtering/search later

### Implementation Phases
1. **Phase 1**: Create JSON schema and QuestionSetGroupService
2. **Phase 2**: Build UI with Option 1 layout
3. **Phase 3**: Implement drag-and-drop functionality
4. **Phase 4**: Add save/load from QuestionSetGroup.json
5. **Phase 5**: Integrate into main window

---

## JSON Schema (QuestionSetGroup.json)

```json
{
  "groups": {
    "JEE Main Practice": {
      "display_name": "JEE Main Practice",
      "question_sets": [
        "Are You Ready",
        "Brush Up Series",
        "Monthly Drive...",
        "Practice Questions"
      ],
      "color": "#3b82f6"
    },
    "JEE Advanced Practice": {
      "display_name": "JEE Advanced Practice",
      "question_sets": [...],
      "color": "#8b5cf6"
    },
    "Monthly Test Drives": {
      "display_name": "Monthly Test Drives",
      "question_sets": [...],
      "color": "#ec4899"
    }
  }
}
```

**Notes:**
- "Others" group is not saved (auto-generated from question sets not in any group)
- Colors are optional for future UI enhancement
- Question sets are stored by name for easy reference

