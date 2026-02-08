# Feature: Warn + link purchase when active session exists

## Problem
When a user saves a Purchase for a (user, site) pair that currently has an **Active** Game Session, it’s easy to accidentally record a post-purchase balance that includes additional play (the “Current SC is a moving target” problem). Also, session-event linking for **active** sessions does not reliably produce a `DURING` link for purchases because the link builder uses `end_dt` to classify DURING, and `end_dt` is `None` for active sessions.

This creates:
- Higher chance of incorrect data entry without explicit acknowledgement.
- Confusing UX where the Purchase may not appear in the Active Session “Related” view immediately.

## Proposal
On purchase save (create + edit, when derived fields changed):
1. If there is an **Active session** for the selected User + Site, show a blocking confirmation dialog:
   - Copy: "There is an active session for this Site/User. Continue saving this purchase?"
   - Include brief session details (at minimum): session start date/time, status, and optionally starting balance + game/game type if available.
2. If the user confirms, proceed with save and **explicitly link** the purchase to that active session.
3. Show a post-save message/toast: "Purchase linked to active session" with an action to open/view that session in the Game Sessions tab.
4. Ensure rebuild behavior keeps links consistent (scoped rebuild). Additionally, update the link builder logic so purchases can be classified as `DURING` for active sessions when the purchase timestamp is >= session start timestamp.

## Scope
In scope:
- Purchase UI flow warning + confirm when active session exists.
- Add/ensure a session-event link for the purchase when confirmed.
- Update link rebuild logic so active sessions can produce `DURING` purchase links.
- Navigation affordance to open the linked session.

Out of scope:
- Any accounting / FIFO / P&L algorithm changes.
- Disabling purchases outright.
- Adding new persisted fields (e.g., "observed balance timestamp").

## Acceptance Criteria
- Saving a purchase for a pair with an active session shows the confirmation dialog.
- Declining the dialog cancels the save with no DB changes.
- Confirming the dialog saves the purchase and results in an explicit link to the active session.
- The active session’s “Related” view shows the purchase immediately (without requiring a manual rebuild).
- For active sessions, purchases occurring after session start are linked as `DURING` by rebuild logic.
- Non-active-session purchase flows remain unchanged.

## Test Matrix (required)
Happy path:
- Create purchase when an active session exists → confirm → purchase saved + link exists + session related events include purchase.

Edge cases:
- Create purchase when active session exists → cancel → purchase NOT created.
- Active session exists but purchase timestamp is BEFORE session start → ensure relation is `BEFORE` (or not linked to that session, depending on intended legacy parity; define expected behavior explicitly).

Failure injection:
- Force an exception between purchase save and link creation (e.g., stub repo/service) → assert transaction rolls back: no purchase row and no link row.

Invariants:
- Only the affected (user, site) pair is rebuilt/linked.
- No changes to FIFO allocations/P&L logic beyond the usual scoped rebuild.

## Implementation Notes
- Linking should be done in the service/facade layer (UI triggers it, but UI does not write to DB directly).
- Link builder currently only classifies purchases as `DURING` when `end_dt` exists; active sessions should treat purchases with `p_dt >= start_dt` as `DURING`.

## Pitfalls / Follow-ups
- If multiple active sessions are possible (shouldn’t be), the UI must choose deterministically or prompt.
- Timestamp precision: if purchase time is missing/00:00, classification may be surprising; consider messaging in the dialog.
