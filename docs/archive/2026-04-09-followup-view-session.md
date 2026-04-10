## Problem / motivation

The desktop app has a detailed "View Session" dialog with three tabs: Details (full session info, game stats, balance grid, P/L, tax withholding, linked events), Related (linked purchases and redemptions with clickable navigation), and Adjustments (period adjustments and boundary checkpoints). The web app currently has no read-only detail view for game sessions.

## Proposed solution

Build a View Session detail dialog/panel for the web app:
1. **Details tab**: Session metadata, game stats (type/name/wager/RTP with Expected/Actual/Session), balance grid (Start/End/Delta for Total/Redeemable/Basis), Net P/L, notes
2. **Related tab**: Linked purchases and redemptions that fall within the session period, with click-to-navigate
3. **Adjustments tab**: Period adjustments and boundary checkpoints (depends on Adjustments CRUD being ported)

Action buttons: End Session (if active), Delete, Edit, Close

## Scope

In-scope:
- View Session dialog/panel with Details tab
- Related tab showing linked purchases/redemptions
- Action buttons (End, Edit, Delete)

Out-of-scope:
- Adjustments tab (depends on Adjustments CRUD issue)
- "View in Daily Sessions" navigation (depends on Daily Sessions tab)
- Tax withholding display (depends on tax system)

## Acceptance criteria

- Clicking a game session row opens a detail view
- Details tab shows all session fields, balance grid, and P/L
- Related tab shows purchases and redemptions linked to this session
- Action buttons (End/Edit/Delete) work from the detail view
- Dialog matches existing modal CSS patterns

## Test plan

Manual verification:
- Open detail view for active and closed sessions
- Verify all fields display correctly
- Verify Related tab shows correct linked events
- Verify action buttons work (End, Edit, Delete)
