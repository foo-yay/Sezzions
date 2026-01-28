# Post-Import Recalculation Implementation

## Overview
Implemented automatic post-import recalculation prompts that track affected user/site pairs and offer to rebuild FIFO allocations after CSV imports.

## Changes Made

### 1. Enhanced ImportResult DTO (`services/tools/dtos.py`)
**Added fields:**
- `affected_user_ids: List[int]` - Track which users were affected by import
- `affected_site_ids: List[int]` - Track which sites were affected by import

**Purpose:** Enable targeted recalculation of only affected pairs instead of full rebuild.

### 2. Updated CSVImportService (`services/tools/csv_import_service.py`)
**Modified `execute_import()` method:**
- Extract user_ids and site_ids from all imported/updated records
- Populate `affected_user_ids` and `affected_site_ids` in ImportResult
- Works for purchases, redemptions, and game_sessions

**Logic:**
```python
affected_user_ids = set()
affected_site_ids = set()

all_records = records_to_insert + records_to_update
for record in all_records:
    if 'user_id' in record and record['user_id']:
        affected_user_ids.add(record['user_id'])
    if 'site_id' in record and record['site_id']:
        affected_site_ids.add(record['site_id'])
```

### 3. Created PostImportPromptDialog (`ui/tools_dialogs.py`)
**New dialog class:**
- Shows import success summary
- Lists affected users/sites count
- Displays recommendation: "⚠️ Recommended: Recalculating ensures accurate cost basis and P/L calculations"
- Two buttons: "Recalculate Now" (default) and "Later"

**UX Design:**
- Modal dialog blocks interaction until user decides
- Clear recommendation encourages recalculation
- Non-intrusive "Later" option for users who want to batch operations

### 4. Added Post-Import Methods to ToolsTab (`ui/tabs/tools_tab.py`)
**New public method:**
```python
def prompt_recalculate_after_import(self, import_result):
    """Show post-import recalculation prompt and trigger if user confirms."""
```

**New private method:**
```python
def _trigger_post_import_recalculation(
    self,
    entity_type: str,
    user_ids: list,
    site_ids: list
):
    """Trigger recalculation for affected pairs after import."""
```

**Integration:**
- Uses existing RecalculationWorker with operation="after_import"
- Reuses existing progress dialogs and result dialogs
- Triggers database change notifications to refresh all tabs

## Usage Flow

### When CSV Import Completes:
1. CSV import service populates ImportResult with affected IDs
2. UI calls `tools_tab.prompt_recalculate_after_import(import_result)`
3. PostImportPromptDialog shows with import statistics
4. If user clicks "Recalculate Now":
   - RecalculationWorker starts with operation="after_import"
   - Progress dialog shows real-time updates
   - Result dialog shows completion statistics
   - All tabs refresh automatically

### Example Integration (future CSV Import UI):
```python
# After successful import
import_result = csv_import_service.execute_import(
    csv_path=file_path,
    entity_type="purchases",
    skip_conflicts=False,
    overwrite_conflicts=True
)

if import_result.success:
    # Show import results
    result_dialog = ImportResultDialog(self, import_result)
    result_dialog.exec()
    
    # Prompt for recalculation
    main_window.tools_tab.prompt_recalculate_after_import(import_result)
```

## Benefits

### 1. Targeted Recalculation
- Only rebuilds affected user/site pairs
- Faster than full recalculation for small imports
- Scales well with large databases

### 2. User Control
- User decides when to recalculate
- Can batch multiple imports before recalculation
- Clear recommendation guides best practice

### 3. Data Consistency
- Ensures FIFO allocations accurate after imports
- Prevents stale cost basis from causing errors
- Maintains audit trail integrity

### 4. Reusable Architecture
- Uses existing worker/dialog infrastructure
- No code duplication
- Easy to extend for other import types

## Testing Checklist

### Manual Testing Scenarios:
- [ ] Import purchases CSV → verify prompt shows
- [ ] Import redemptions CSV → verify prompt shows
- [ ] Import game_sessions CSV → verify prompt shows
- [ ] Click "Recalculate Now" → verify progress dialog
- [ ] Click "Later" → verify no recalculation
- [ ] Import affecting 1 user/1 site → verify prompt details
- [ ] Import affecting 5 users/3 sites → verify prompt details
- [ ] Cancel recalculation mid-process → verify warning
- [ ] Complete recalculation → verify result dialog
- [ ] Verify all tabs refresh after recalculation

### Integration Testing:
- [ ] Import → Recalculate → Verify purchases tab updated
- [ ] Import → Recalculate → Verify unrealized balances updated
- [ ] Import → Recalculate → Verify daily sessions updated
- [ ] Import → Skip recalc → Import again → Recalculate both
- [ ] Import with errors → Verify no prompt (import failed)

## Future Enhancements

### Batch Recalculation:
- Track multiple imports in session
- Offer to recalculate all at once
- "Recalculate All Pending" button in Tools tab

### Smart Scheduling:
- Auto-recalculate after X imports
- Schedule recalculation for low-activity times
- Background recalculation option

### Notification Integration (Phase 5):
- Create notification: "Import complete, recalculation recommended"
- Allow clicking notification to trigger recalculation
- Track pending recalculations in notification center

## Notes

### Thread Safety:
- Worker opens own database connection (SQLite not thread-safe)
- UI signals use Qt's thread-safe Signal/Slot mechanism
- Progress callbacks check cancellation flag atomically

### Transaction Safety:
- RecalculationService uses transactions for atomicity
- Cancel triggers InterruptedError → rollback
- Database left in consistent state even if cancelled

### Performance:
- Affected IDs extracted in O(n) time during import
- Set operations ensure unique IDs only
- Sorted lists for deterministic testing

## Related Files
- `services/tools/dtos.py` - ImportResult dataclass
- `services/tools/csv_import_service.py` - CSV import logic
- `ui/tools_dialogs.py` - PostImportPromptDialog
- `ui/tabs/tools_tab.py` - Post-import orchestration
- `ui/tools_workers.py` - RecalculationWorker (unchanged)

## Status
✅ **COMPLETE** - All code implemented, ready for testing

Next: Task 6 - End-to-end testing of complete Phase 4 UI integration
