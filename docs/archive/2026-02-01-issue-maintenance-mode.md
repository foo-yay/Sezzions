# Issue: Add Maintenance Mode for Data Integrity Issues

## Problem

When data integrity violations are detected at startup (e.g., `remaining_amount > amount` on purchases), the application crashes with a ValueError before the user can take corrective action.

This occurs commonly during:
- Partial CSV imports (user hasn't imported all data yet)
- CSV imports without running "Recalculate Everything"
- Manual CSV edits that create inconsistencies

## Current Behavior

Application fails to start with:
```
ValueError: Remaining amount cannot exceed purchase amount
```

User cannot access the app to fix the data or complete imports.

## Proposed Solution

Add a **Maintenance Mode** that activates when data integrity issues are detected at startup.

### Detection at Startup

Scan for common integrity violations:
- Purchases: `remaining_amount > amount`
- Orphaned FK references
- Null required fields
- Date inconsistencies

### Maintenance Mode Restrictions

**Allow:**
- CSV Import/Export
- Database Tools (Backup/Restore/Reset)
- Recalculate Everything
- Settings

**Block:**
- Normal operational tabs (Purchases, Redemptions, Game Sessions, etc.)
- Creating/editing records through UI

### User Experience

1. Show dialog at startup:
   ```
   Data Integrity Issues Detected
   
   Found 29 purchases with invalid remaining amounts.
   
   Maintenance Mode has been activated. You can:
   - Complete CSV imports, then recalculate
   - Restore from a backup
   - Reset database and reimport
   
   [View Details] [Continue in Maintenance Mode]
   ```

2. Main window shows:
   - Banner: "⚠️ MAINTENANCE MODE - Data integrity issues detected"
   - Only maintenance-related tabs visible
   - Help text explaining next steps

3. After recalculation or restore:
   - Re-check integrity
   - If clean, exit maintenance mode and restar   - If clean, exit maintenance ia

- [ ] Startup integrity check detects common violations
- [ ] Maintenance mode activates when issues found
- [ ] Only whitelisted operations allowed in maintenance mode
- [ ] User can complete CSV imports in maintenance mode
- [ ] User can run recalculate/restore/reset in maintenance mode
- [ ] After fixing issues, app can restart normally
- [ ] Error details shown to user (what issues, how many)

## Edge Cases

- User imports data in multiple sessions (incomplete dataset)
  - Solution: Allow imports to continue, defer validation until user runs recalculate
- Recalculate fails due to missing data
  - Solution: Show error, suggest restoring from backup or continuing imports
- User wants to bypass maintenance mode
  - Solution: Settings option to "Ignore integrity warnings (advanced)"

## Implementation Notes

- Add integrity check module: `services/data_integrity_service.py`
- Modify `MainWindow.__init__()` to run check before creating tabs
- Create `MaintenanceModeDialog` to explain status
- Add `MainWindow._create_maintenance_tabs()` for restricted mode
- Store integrity check results for display

## Testing

- Unit tests for integrity checks
- Integration test: import partial data, verify maintenance mode activates
- Integration test: recalculate in maintenance mode, verify exit
- UI test: verify only allowed tabs visible in maintenance mode
