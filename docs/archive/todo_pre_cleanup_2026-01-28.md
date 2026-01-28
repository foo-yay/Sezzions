# Archived: Sezzions TODO (Pre-cleanup)

Archived on: 2026-01-28

This file is retained for historical context only.
The active TODO is: [docs/TODO.md](../TODO.md)

---

## Phase 4 UI Integration (TOOLS_IMPLEMENTATION_PLAN.md)
- [X] Task 1: Add transaction API to DatabaseManager (was already implemented)
- [X] Task 2: Create Qt background workers (RecalculationWorker + WorkerSignals)
- [X] Task 3: Create progress dialogs (ProgressDialog hierarchy)
- [X] Task 4: Wire Tools tab buttons (Recalculate Everything + scoped)
- [X] Task 5: Add post-import recalculation prompts (PostImportPromptDialog)
- [X] Task 6: End-to-end testing of Phase 4 UI integration

**Status:** 5/6 tasks complete, ready for testing. See `POST_IMPORT_RECALC_IMPLEMENTATION.md` for details.

## CRITICAL Architecture Items
- [ ] **Implement ViewModels/DTOs for UI display data** - Currently UI layer has direct access to repositories (e.g., `facade.game_repo`) and performs data fetching. This violates separation of concerns and prevents proper multi-platform architecture. Service layer should return enriched ViewModels with all display data (game_name, game_type_name, etc.) so UI only displays, never fetches.

## Active Items
- [ ] Phase 5: Notification System (next after Phase 4 testing)
- [ ] Legacy app's redeemable check isn't detecting a problem when I enter 0.42 SC on an expected 0.41 redeemable. is there a threshhold? It recognizes it if I put 0.92
- [ ] Prompt the user to back-up the database before deleting Sessions or items that could cascade.
- [ ] Session P/L looks accurate, but basis/consumption does not
- [ ] Get consistency between Starting SC and Post-Purchase SC as well as displaying it on the table.
- [ ] Purchase balance checks are showing off by the amount of the purchase on the new app.
- [ ] Finish updating the Tools tab using TOOLS_IMPLEMENTATION_PLAN.md
- [ ] Edge case for editing purchases (starting SC drift when editing a middle purchase)
- [ ] On redemption dialog, show latest balances (redeemable/total) or realtime balance check
- [ ] Add helper explaining “Processed” checkbox on redemption dialog

## Completed Items
- (Many completed items were listed in the original file; retained snapshot ended here.)
