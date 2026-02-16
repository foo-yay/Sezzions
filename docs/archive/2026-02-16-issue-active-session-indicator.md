# Feature Request: Active Session Indicator on Unrealized Tab

## Problem Statement

When viewing the Unrealized tab, users cannot quickly identify which sites have active game sessions currently in progress. This makes it harder to:
- See what's currently being played
- Prioritize where to play next among sites with unrealized positions
- Understand the current state of their gaming activity at a glance

## Proposed Solution

Add a visual indicator (emoji) to unrealized position entries that have active (not yet ended) game sessions associated with that site/user combination.

**Suggested indicator:** ⏳ (hourglass) or 🎮 (game controller) or ▶️ (play button)

The indicator should appear in the unrealized positions table row for any position that has one or more active sessions.

## Scope

**In scope:**
- Add active session detection logic to unrealized position data loading
- Display indicator emoji in the unrealized table for positions with active sessions
- Tooltip on hover explaining the indicator (e.g., "Has active session")

**Out of scope:**
- Detailed session information in tooltip (keep it simple)
- Clickable indicator to navigate to sessions tab
- Filtering by active/inactive positions

## UI/UX Considerations

- Indicator should be subtle but noticeable
- Placement: likely in the first column or as a prefix to the site/user name
- Should not disrupt existing table layout or sorting
- Tooltip should clarify meaning for new users

## Acceptance Criteria

1. Unrealized positions with active sessions display an indicator emoji
2. Positions without active sessions show no indicator
3. Indicator updates when sessions are started/ended and the tab is refreshed
4. Tooltip provides brief explanation of the indicator
5. Table sorting and filtering still work correctly
6. No performance degradation on large unrealized position lists

## Test Plan

- Verify indicator appears for positions with active sessions
- Verify indicator disappears when session is ended
- Test with multiple active sessions for the same position
- Test with no active sessions (indicator should not appear)
- Verify tooltip displays correctly
- Test table sorting with indicator present
- Load test with 50+ unrealized positions including some with active sessions

## Additional Context

This feature helps users manage their gaming activity more effectively by providing at-a-glance awareness of where they're currently playing.
