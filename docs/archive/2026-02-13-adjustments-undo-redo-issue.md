# Feature: Audit + Undo/Redo for Adjustments & Checkpoints

## Problem
Adjustments and balance checkpoints currently do not participate in the audit log or undo/redo stack. This leaves a visibility gap for accounting-critical changes and makes reversibility inconsistent with other core entities.

## Proposal
Add audit log entries and undo/redo operations for:
- Creating a Basis Adjustment
- Creating a Balance Checkpoint
- Soft-deleting an adjustment/checkpoint
- Restoring a soft-deleted adjustment/checkpoint

## Scope
- Services: AdjustmentService (create/delete/restore) should log to audit and push undo/redo operations.
- Repositories: no schema changes required if `audit_log` already covers generic CRUD.
- UI: no UI changes required; behavior is backend-only.

## Acceptance Criteria
- Creating a basis adjustment writes an audit_log CREATE entry and pushes an undo/redo operation.
- Creating a balance checkpoint writes an audit_log CREATE entry and pushes an undo/redo operation.
- Deleting an adjustment/checkpoint writes an audit_log DELETE entry and pushes an undo/redo operation.
- Restoring an adjustment/checkpoint writes an audit_log RESTORE entry and pushes an undo/redo operation.
- Undo/redo operations correctly revert and reapply adjustments/checkpoints without corrupting recalculation.

## Test Plan
- Unit tests for AdjustmentService audit + undo/redo hooks (create/delete/restore).
- Integration test verifying audit_log row creation and undo/redo stack entries for adjustment flows.
- Failure injection: simulate audit write failure and assert no partial adjustment persisted.

## Out of Scope
- UI changes or new dialogs.
- Any modification to audit log schema.

## Notes
This aligns adjustments/checkpoints with existing audit/undo behavior for purchases, redemptions, and sessions.
