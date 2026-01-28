# Dialog Design Paradigm
**Sezzions Application - Consistent Dialog UI/UX Standards**

*Version 1.0 - January 2026*

---

## Table of Contents
1. [Overview](#overview)
2. [Dialog Types](#dialog-types)
3. [Layout Architecture](#layout-architecture)
4. [Visual Design System](#visual-design-system)
5. [Component Standards](#component-standards)
6. [Validation & Error Handling](#validation--error-handling)
7. [Naming Conventions](#naming-conventions)
8. [Workflow Patterns](#workflow-patterns)
9. [Implementation Checklist](#implementation-checklist)

---

## Overview

This paradigm defines the standard approach for all dialog interfaces in the Sezzions application. It ensures consistency, usability, and maintainability across Add, Edit, and View dialogs for all entity types.

**Core Principles:**
- **Consistency**: Users should experience identical patterns across all dialogs
- **Clarity**: Visual hierarchy guides users through required actions
- **Efficiency**: Tab order and keyboard navigation optimize data entry
- **Feedback**: Real-time validation with visual indicators
- **Accessibility**: All text is selectable in View dialogs; clear visual states

---

## Dialog Types

### 1. Add Dialog
**Purpose:** Create new entity records  
**Characteristics:**
- Starts with empty/default values
- Save button initially disabled if validation required
- Optional "Clear" button to reset form
- Default focus on first required field

### 2. Edit Dialog
**Purpose:** Modify existing entity records  
**Characteristics:**
- Pre-populated with current values
- Must handle NULL values gracefully
- Updates trigger real-time validation
- Changes compared against original for save optimization

### 3. View Dialog
**Purpose:** Display entity details with optional navigation to related records  
**Characteristics:**
- Read-only, non-editable
- All text selectable for copying
- Optional Edit/Delete buttons
- May include tabs for related data
- Larger minimum size to accommodate details

---

## Layout Architecture

### Window Structure

```
┌─────────────────────────────────────────────────────┐
│ Dialog Title                                    [×] │
├─────────────────────────────────────────────────────┤
│  Padding: 20px all sides                            │
│  ┌───────────────────────────────────────────────┐  │
│  │ Date/Time Section (Single Row)               │  │
│  │ ObjectName: "SectionBackground"              │  │
│  │ Margins: (12, 10, 12, 10)                    │  │
│  └───────────────────────────────────────────────┘  │
│                                                      │
│  Section Header (e.g., "💳 Purchase Details")       │
│  ObjectName: "SectionHeader"                        │
│                                                      │
│  ┌───────────────────────────────────────────────┐  │
│  │ Main Data Section                             │  │
│  │ ObjectName: "SectionBackground"              │  │
│  │ 2-Column Grid Layout                         │  │
│  │ Margins: (12, 12, 12, 12)                    │  │
│  │ HSpacing: 30px | VSpacing: 10px              │  │
│  │                                               │  │
│  │ Left Column        │ Right Column            │  │
│  │ Label: Value       │ Label: Value            │  │
│  │ Label: Value       │ Label: Value            │  │
│  └───────────────────────────────────────────────┘  │
│                                                      │
│  📝 Notes Section (Collapsible or Always Visible)   │
│                                                      │
│  [Stretch Zone - Pushes buttons to bottom]          │
│                                                      │
│  ┌───────────────────────────────────────────────┐  │
│  │        [Delete]  [Stretch]  [Save] [Close]   │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### Container Hierarchy

**Add/Edit Dialogs:**
1. **Main VBoxLayout** (20px margins, 16px spacing)
2. **Date/Time Section** (SectionBackground widget, HBoxLayout)
3. **Section Header** (SectionHeader label with emoji)
4. **Main Data Section** (SectionBackground widget, GridLayout)
5. **Notes Section** (Collapsible button + SectionBackground)
6. **Stretch** (pushes buttons to bottom)
7. **Button Row** (HBoxLayout with right-aligned buttons)

**View Dialogs:**
1. **Main VBoxLayout** (20px margins, 12px spacing)
2. **Tabs** (if multiple sections, ObjectName: "SetupSubTabs")
3. **Details Tab Content:**
   - Section widgets with headers (SectionBackground)
   - Two-column layout for balanced presentation
   - Notes section at bottom
4. **Stretch**
5. **Button Row**

---

## Visual Design System

### Object Names & Styling

**Section Backgrounds:**
```python
widget.setObjectName("SectionBackground")
# Applied to containers that group related fields
# Provides subtle background differentiation
```

**Section Headers:**
```python
label.setObjectName("SectionHeader")
# Applied to section title labels
# Includes emoji prefix for visual categorization
# Examples: "📅 When", "💳 Purchase Details", "📝 Notes"
```

**Field Labels:**
```python
label.setObjectName("FieldLabel")
# Applied to input field labels
# Subtle muted color, right-aligned in grids
```

**Helper Text:**
```python
label.setObjectName("HelperText")
# Applied to contextual hints/validation messages
# Can have property "status": "neutral", "valid", "invalid"
```

**Primary Button:**
```python
button.setObjectName("PrimaryButton")
# Applied to Save/Confirm buttons
# Visually emphasized for primary action
```

### Color Coding

**Validation States:**
- **Invalid Field**: Red border/background via `widget.setProperty("invalid", True)`
- **Valid Field**: Default/green via `widget.setProperty("invalid", False)`
- **Neutral Helper**: Mid-tone gray text
- **Success Helper**: Green text with property("status", "valid")
- **Error Helper**: Red text with property("status", "invalid")

**Text Colors (View Dialogs):**
```python
label.setStyleSheet("color: palette(mid);")  # For field labels
# Values use default text color, selectable
```

### Spacing Standards

**Dialog-level:**
- Outer margins: `20px`
- Main layout spacing: `16px` (Add/Edit), `12px` (View)

**Section-level:**
- SectionBackground margins: `(12, 10, 12, 10)` for compact rows
- SectionBackground margins: `(12, 12, 12, 12)` for grids
- Section spacing: `6px` (View), `10px` between sections

**Grid-level:**
- Horizontal spacing: `30px` (separates columns clearly)
- Vertical spacing: `10px` (between rows)
- Between sections: `12px`

**View Dialog Grids:**
- Horizontal spacing: `12px`
- Vertical spacing: `6px`
- Column stretch: Equal (1, 1) for balanced columns

### Sizing

**Add/Edit Dialogs:**
- Minimum width: `700-750px`
- Minimum height: `420-520px`
- Resize: Fixed height when notes collapsed; expandable when notes shown
- Field widths:
  - Date input: `110px`
  - Time input: `90px`
  - Calendar button: `44px`
  - Amount fields: `140px` (fixed)
  - Combo boxes: `180px` (minimum)

**View Dialogs:**
- Minimum width: `700px`
- Minimum height: `350-550px` (depends on content)
- No maximum - allow window resize
- All content should reflow gracefully

---

## Component Standards

### Date/Time Input Section

**Always appears first** in Add/Edit dialogs as a horizontal row.

**Structure:**
```python
datetime_section = QtWidgets.QWidget()
datetime_section.setObjectName("SectionBackground")
datetime_layout = QtWidgets.QHBoxLayout(datetime_section)
datetime_layout.setContentsMargins(12, 10, 12, 10)
datetime_layout.setSpacing(12)

# Pattern: Label + Input + Calendar + Helper Button + Spacing + Label + Input + Helper Button + Stretch
# Date: | FieldLabel | LineEdit(110px) | 📅(44px) | Today | <30px> | FieldLabel | LineEdit(90px) | Now | Stretch |
```

**Required Elements:**
- Date LineEdit with placeholder "MM/DD/YY"
- Calendar button (📅) 44px width, opens QCalendarWidget
- "Today" helper button (optional but recommended)
- Time LineEdit with placeholder "HH:MM"
- "Now" helper button (optional but recommended)

**Behavior:**
- Date/time parsing via `ui.input_parsers` module functions
- Real-time validation on textChanged
- Helper buttons populate current date/time

### Main Data Grid Section

**Two-column balanced layout** for optimal visual scanning.

**Structure:**
```python
main_section = QtWidgets.QWidget()
main_section.setObjectName("SectionBackground")
main_grid = QtWidgets.QGridLayout(main_section)
main_grid.setContentsMargins(12, 12, 12, 12)
main_grid.setHorizontalSpacing(30)
main_grid.setVerticalSpacing(10)
```

**Field Placement Strategy:**
1. **Left column**: Primary identifiers, core required fields
2. **Right column**: Secondary attributes, optional fields, amounts
3. **Balance**: Aim for equal row count in both columns
4. **Grouping**: Logically related fields in same column when possible

**Label Styling:**
```python
label = QtWidgets.QLabel("Field Name:")
label.setObjectName("FieldLabel")
label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
```

**Column Stretch:**
```python
main_grid.setColumnStretch(1, 1)  # Left value column
main_grid.setColumnStretch(3, 1)  # Right value column
```

### Input Components

**Text Input (LineEdit):**
- Use `setPlaceholderText()` for format hints
- Connect `textChanged` to `_validate_inline()`
- Fixed width for numeric/date fields
- Minimum width for text fields

**Combo Boxes:**
```python
combo = QtWidgets.QComboBox()
combo.setEditable(True)  # Allow typing
combo.lineEdit().setPlaceholderText("Choose...")
# For optional fields, add blank first item:
combo.addItem("")
# Then add actual items with data
for item in items:
    combo.addItem(item.name, item.id)
```

**Multi-line Text (PlainTextEdit):**
- Fixed height: `80px`
- Placeholder text: "Optional..."
- `setSizePolicy(Expanding, Fixed)`

### Notes Section

**Add/Edit Dialogs** - Collapsible:
```python
self.notes_collapsed = True
self.notes_toggle = QtWidgets.QPushButton("📝 Add Notes...")
self.notes_toggle.setObjectName("SectionHeader")
self.notes_toggle.setCursor(QtCore.Qt.PointingHandCursor)
self.notes_toggle.setFlat(True)
self.notes_toggle.clicked.connect(self._toggle_notes)

self.notes_section = QtWidgets.QWidget()
self.notes_section.setObjectName("SectionBackground")
self.notes_section.setVisible(False)
```

**Toggle Behavior:**
```python
def _toggle_notes(self):
    self.notes_collapsed = not self.notes_collapsed
    self.notes_section.setVisible(not self.notes_collapsed)
    if self.notes_collapsed:
        self.notes_toggle.setText("📝 Add Notes...")
        self.setMinimumHeight(420)
        self.setMaximumHeight(420)
        self.resize(self.width(), 420)
    else:
        self.notes_toggle.setText("📝 Hide Notes")
        self.setMinimumHeight(500)
        self.setMaximumHeight(16777215)
        self.resize(self.width(), 500)
```

**View Dialogs** - Always Visible:
```python
notes_section, notes_layout = self._create_section("📝 Notes")
notes_value = entity.notes or ""

if notes_value:
    notes_display = QtWidgets.QTextEdit()
    notes_display.setReadOnly(True)
    notes_display.setPlainText(notes_value)
    notes_display.setMaximumHeight(80)
    notes_display.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
    notes_layout.addWidget(notes_display)
else:
    notes_empty = QtWidgets.QLabel("—")
    notes_empty.setStyleSheet("color: palette(mid); font-style: italic;")
    notes_layout.addWidget(notes_empty)
```

### Button Arrangement

**Add/Edit Dialogs:**
```python
btn_row = QtWidgets.QHBoxLayout()
btn_row.addStretch(1)  # Push buttons to right

# Optional clear button (left side before stretch)
# self.cancel_btn comes first if present
self.cancel_btn = QtWidgets.QPushButton("✖️ Cancel")
btn_row.addWidget(self.cancel_btn)

# Optional clear button
self.clear_btn = QtWidgets.QPushButton("🧹 Clear")
btn_row.addWidget(self.clear_btn)

# Primary action always rightmost
self.save_btn = QtWidgets.QPushButton("💾 Save")
self.save_btn.setObjectName("PrimaryButton")
btn_row.addWidget(self.save_btn)
```

**View Dialogs:**
```python
btn_row = QtWidgets.QHBoxLayout()

# Delete on far left if available
if self._on_delete:
    delete_btn = QtWidgets.QPushButton("🗑️ Delete")
    btn_row.addWidget(delete_btn)

btn_row.addStretch(1)

# Edit and Close on right
if self._on_edit:
    edit_btn = QtWidgets.QPushButton("✏️ Edit")
    btn_row.addWidget(edit_btn)

close_btn = QtWidgets.QPushButton("✖️ Close")
btn_row.addWidget(close_btn)
```

---

## Validation & Error Handling

### Real-Time Inline Validation

**Pattern:**
```python
def _validate_inline(self) -> bool:
    """Validate all fields and return True if all valid"""
    valid = True
    
    # Validate each field
    if not self.field.text().strip():
        self._set_invalid(self.field, "Field is required.")
        valid = False
    else:
        # Additional validation logic
        self._set_valid(self.field)
    
    # Enable/disable save button
    self.save_btn.setEnabled(valid)
    return valid
```

**Helper Methods:**
```python
def _set_invalid(self, widget, message):
    widget.setProperty("invalid", True)
    widget.setToolTip(message)
    widget.style().unpolish(widget)
    widget.style().polish(widget)

def _set_valid(self, widget):
    widget.setProperty("invalid", False)
    widget.setToolTip("")
    widget.style().unpolish(widget)
    widget.style().polish(widget)
```

### Validation Rules

**Required Fields:**
- Highlight red immediately when empty on blur
- Show tooltip with specific requirement
- Disable Save button until valid

**Optional Fields:**
- Never show error state for empty
- Validate format if value entered
- Example: User field - blank OK, but if typed must match valid user

**Format Validation:**
- Date: MM/DD/YY format, not in future
- Time: HH:MM or HH:MM:SS 24-hour format
- Currency: Max 2 decimals, positive only
- Combo boxes: Must match existing item or be blank (if optional)

**Signal Connections:**
```python
self.field_edit.textChanged.connect(self._validate_inline)
self.combo_box.currentTextChanged.connect(self._validate_inline)
```

### Validation Timing

1. **On Load**: If editing, validate immediately to show any issues
2. **On Change**: Real-time validation via textChanged/currentTextChanged
3. **On Save**: Final validation in collect_data() before accepting dialog
4. **Tab Order**: Logical flow through fields for keyboard users

---

## Naming Conventions

### Dialog Class Names
- Pattern: `{Entity}{Action}Dialog`
- Examples: `PurchaseDialog`, `ExpenseViewDialog`, `UserDialog`
- View dialogs: `{Entity}ViewDialog`

### Method Names

**Standard Methods:**
- `__init__`: Constructor with signature `(parent, entity=None, on_edit=None, on_delete=None)`
- `_validate_inline()`: Returns bool, enables/disables Save
- `collect_data()`: Returns `(dict, error_message)` tuple
- `_load_{entity}()`: Populates form with entity data
- `_clear_form()`: Resets all fields to defaults
- `_set_today()` / `_set_now()`: Helper button actions
- `_pick_date()`: Calendar picker
- `_toggle_notes()`: Show/hide notes section
- `_set_valid()` / `_set_invalid()`: Apply validation styling

**View Dialog Methods:**
- `_create_details_tab()`: Build main details view
- `_create_related_tab()`: Build related records view (if applicable)
- `_create_section()`: Helper to build section with header
- `_make_selectable_label()`: Create copiable text label
- `_format_date()` / `_format_time()`: Display formatting

### Variable Names

**Widgets:**
- Pattern: `{field}_edit`, `{field}_combo`, `{field}_btn`
- Examples: `date_edit`, `user_combo`, `today_btn`, `save_btn`

**Data Storage:**
- Pattern: `self.{entity}` for current entity
- Pattern: `{field}_id` for foreign keys
- Examples: `self.purchase`, `self.user_id`

**Lookups:**
- Pattern: `_{entity}_lookup` for combo validation
- Example: `self._user_lookup = {u.name.lower(): u.id for u in users}`

---

## Workflow Patterns

### Tab Order

**Critical for keyboard navigation efficiency.**

**Pattern:**
```python
# Define order explicitly via setTabOrder
self.setTabOrder(self.date_edit, self.time_edit)
self.setTabOrder(self.time_edit, self.first_main_field)
# ... through all input fields in logical order
self.setTabOrder(self.last_main_field, self.notes_edit)
self.setTabOrder(self.notes_edit, self.save_btn)
```

**Order Priority:**
1. Date
2. Time
3. Primary identifiers (User, Site, etc.)
4. Secondary attributes
5. Optional fields
6. Notes
7. Save button

### Data Flow

**Add/Edit Dialog Flow:**
```
1. User opens dialog
2. If editing: _load_entity() populates fields
3. If adding: Default values set, focus on first field
4. User enters data
5. _validate_inline() runs on each change
6. User clicks Save (only enabled if valid)
7. Dialog accepts, caller invokes collect_data()
8. Caller passes data to service layer
9. Success: Refresh data, show confirmation
10. Error: Show error dialog (not tooltip)
```

**View Dialog Flow:**
```
1. User opens dialog with entity
2. Dialog builds readonly view with formatted data
3. User reads/copies text
4. Optional: User clicks Edit → Close view, open edit dialog
5. Optional: User clicks Delete → Confirm, delete, close
6. User clicks Close → Accept dialog
```

### Edit Dialog Close on Edit Button

**Pattern to prevent multiple dialogs:**
```python
def _handle_edit(self):
    """Close dialog before triggering edit callback"""
    self.accept()
    if self._on_edit:
        self._on_edit()
```

Connect button: `edit_btn.clicked.connect(self._handle_edit)`

---

## Implementation Checklist

### For Each New Add/Edit Dialog

**Setup Phase:**
- [ ] Create class: `{Entity}Dialog(QtWidgets.QDialog)`
- [ ] Constructor signature: `(users/sites/etc, entity=None, parent=None)`
- [ ] Set window title: "Edit {Entity}" if entity else "Add {Entity}"
- [ ] Set minimum size: 700-750px width, 420-520px height
- [ ] Create main VBoxLayout with 20px margins, 16px spacing

**Date/Time Section:**
- [ ] Create SectionBackground widget with HBoxLayout
- [ ] Add Date input (110px) with calendar button (44px)
- [ ] Add Time input (90px) with Now button
- [ ] Connect helper buttons to _set_today() and _set_now()
- [ ] Add proper spacing (30px between date and time groups)

**Main Data Section:**
- [ ] Add SectionHeader label with emoji
- [ ] Create SectionBackground widget with GridLayout
- [ ] Set margins (12,12,12,12), hspacing 30, vspacing 10
- [ ] Plan two-column layout (required fields left, secondary right)
- [ ] Create widgets for each field
- [ ] Add FieldLabel labels with right alignment
- [ ] Set appropriate field widths
- [ ] Apply column stretch to value columns

**Notes Section:**
- [ ] Create collapsible toggle button (SectionHeader)
- [ ] Create hidden notes_section (SectionBackground)
- [ ] Add PlainTextEdit (80px height, Fixed size policy)
- [ ] Implement _toggle_notes() with resize logic
- [ ] If editing and notes exist, expand on load

**Buttons:**
- [ ] Create HBoxLayout with right-side stretch
- [ ] Add Cancel button (connects to reject)
- [ ] Add Clear button (connects to _clear_form, optional)
- [ ] Add Save button (ObjectName: "PrimaryButton", connects to accept)
- [ ] Arrange: Cancel, Clear, Save from left to right

**Validation:**
- [ ] Implement _validate_inline() returning bool
- [ ] Implement _set_valid() and _set_invalid()
- [ ] Connect textChanged/currentTextChanged to _validate_inline
- [ ] Handle required vs optional field logic
- [ ] Enable/disable Save button based on valid state
- [ ] Handle special cases (e.g., combo boxes with validation)

**Data Handling:**
- [ ] Implement collect_data() returning (dict, error) tuple
- [ ] Implement _load_{entity}() for edit mode
- [ ] Implement _clear_form() for reset functionality
- [ ] Parse dates/times using ui.input_parsers functions
- [ ] Handle NULL values gracefully in edits
- [ ] Look up IDs by text for combo boxes (not currentData)

**Tab Order:**
- [ ] Define explicit tab order with setTabOrder()
- [ ] Start with date, end with save button
- [ ] Test keyboard navigation flows logically

**Final Testing:**
- [ ] Add: All fields start empty/default, validation works
- [ ] Edit: All fields populate correctly, updates save
- [ ] Clear button resets form properly
- [ ] Tab order flows logically
- [ ] Validation messages are clear
- [ ] Save button enables/disables correctly
- [ ] Notes collapse/expand without breaking layout

### For Each New View Dialog

**Setup Phase:**
- [ ] Create class: `{Entity}ViewDialog(QtWidgets.QDialog)`
- [ ] Constructor signature: `(entity, parent=None, on_edit=None, on_delete=None)`
- [ ] Set window title: "View {Entity}" or "{Entity} Details (ID: {id})"
- [ ] Set minimum size: 700px width, 350-550px height
- [ ] Create main VBoxLayout with 20px margins, 12px spacing

**Content Structure:**
- [ ] Use tabs if multiple sections (ObjectName: "SetupSubTabs")
- [ ] Create Details tab with _create_details_tab()
- [ ] Create Related tab if applicable with _create_related_tab()

**Details Tab:**
- [ ] Create sections with _create_section() helper
- [ ] Use two-column HBoxLayout for balanced presentation
- [ ] Left column: Primary fields with GridLayout
- [ ] Right column: Secondary fields with GridLayout
- [ ] Set grid spacing: hspacing 12, vspacing 6
- [ ] Add labels with palette(mid) color
- [ ] Add values with _make_selectable_label()
- [ ] Apply equal column stretch (1, 1)

**Notes Section:**
- [ ] Always visible in view mode
- [ ] If notes exist: ReadOnly QTextEdit (80px max height)
- [ ] If no notes: Styled label with "—" and italic gray text

**Buttons:**
- [ ] Delete button on far left (if on_delete provided)
- [ ] Stretch in middle
- [ ] Edit button right side (if on_edit provided, use _handle_edit)
- [ ] Close button rightmost (connects to accept)

**Helpers:**
- [ ] Implement _create_section() returning (widget, layout) tuple
- [ ] Implement _make_selectable_label() with IBeamCursor
- [ ] Implement _format_date() and _format_time() for display
- [ ] Implement _handle_edit() to close before opening edit dialog

**Final Testing:**
- [ ] All fields display correctly
- [ ] Text is selectable throughout
- [ ] Buttons work as expected
- [ ] Edit button closes view before opening edit
- [ ] Tabs switch properly (if applicable)
- [ ] Related records load correctly (if applicable)

---

## Contextual Considerations for Setup Entities

When implementing dialogs for Setup tab entities (Users, Sites, Cards, Method Types, Methods, Game Types, Games), consider:

### Relationship Dependencies

**Users:**
- Independent entity, no parent dependencies
- Cards are child records (must select user first in Card dialog)

**Sites:**
- Independent entity
- Games may reference sites for site-specific configurations

**Cards:**
- **Depends on**: User (required)
- In Add/Edit: User combo must be populated
- Validation: User required, must be valid

**Redemption Method Types:**
- Independent entity (enum-like)
- Methods reference this as parent

**Redemption Methods:**
- **Depends on**: Method Type (required), User (optional)
- In Add/Edit: Method Type combo required
- User combo optional (some methods are shared)

**Game Types:**
- Independent entity (slots, table games, etc.)
- Games reference this as category

**Games:**
- **Depends on**: Game Type (required), Site (optional)
- In Add/Edit: Game Type combo required
- Site combo optional (multi-site games)
- RTP field: Decimal validation (0-100)

### Field Characteristics

**Common Required Fields:**
- Name (all entities)
- Active status (usually checkbox, default True)

**Optional Fields:**
- Notes (all entities can have notes)
- User association (Methods, Cards)
- Parent category (Games → Game Type, Methods → Method Type)

**Special Fields:**
- **RTP** (Games): Numeric, 0-100 range, 2 decimals
- **Method Type** (Methods): Dropdown, cash/check/gift card/crypto/etc
- **Last Four** (Cards): 4 digits, display formatting

### Validation Specific to Setup

**Names:**
- Unique within entity type (check on save)
- Not empty
- Reasonable length (e.g., 1-100 chars)

**Parent Dependencies:**
- Must exist when referenced
- Use combo with validation (like User in Expenses)

**Active Status:**
- Checkbox, always present
- Affects dropdown population in other dialogs

### Layout Suggestions

**Simple Entities** (Users, Sites, Method Types, Game Types):
- Single section: Name, Active, Notes
- No date/time section needed
- Minimal fields = smaller dialog (600px width OK)

**Complex Entities** (Cards, Methods, Games):
- Date/Time section if timestamps relevant
- Main section with dependencies in left column
- Attributes in right column
- Standard notes section

**Example - Card Dialog Layout:**
```
Date/Time: Created date (if tracking)
Main Section:
  Left: User (required), Card Type
  Right: Last Four, Active
Notes: Optional notes
```

**Example - Game Dialog Layout:**
```
Main Section:
  Left: Name (required), Game Type (required)
  Right: Site (optional), RTP (optional)
  Full width: Active checkbox
Notes: Optional notes
```

---

## Conclusion

This paradigm provides a comprehensive blueprint for creating consistent, user-friendly dialogs throughout the Sezzions application. By adhering to these standards:

- **Users** experience predictable, learnable interfaces
- **Developers** follow clear patterns reducing implementation time
- **Maintenance** becomes simpler with consistent structure
- **Accessibility** improves through standardized keyboard navigation and visual feedback

All future dialogs should reference this document during design and implementation phases. Deviations should be documented with justification.

---

*End of Dialog Design Paradigm Document*
