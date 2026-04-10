## Problem / motivation

After closing a game session in the desktop app, if the ending balance is below a configurable threshold and the user is NOT doing "End & Start New", the app prompts: "Close the position now?" This shows the impact (dormant SC, basis loss, realized P/L) and if confirmed calls `close_unrealized_position()`.

This feature prevents users from forgetting to close out small remaining positions that would otherwise sit as unrealized indefinitely.

## Proposed solution

Port the low-balance close prompt to web:
1. **Backend**: `get_low_balance_close_prompt_data()` service method + API endpoint — returns threshold check result, dormant SC amount, basis impact, and P/L impact
2. **Backend**: `close_unrealized_position()` service method + API endpoint — executes the position close (marks purchases dormant, records basis loss)
3. **Frontend**: After closing a session via End Session form, if prompt data indicates low balance, show a confirmation dialog with impact details and "Close Position" / "Keep Open" buttons

Desktop reference: `app_facade.py` (`get_low_balance_close_prompt_data`, `close_unrealized_position`)

## Scope

In-scope:
- Low-balance threshold check service method + endpoint
- Position close execution method + endpoint
- Post-close prompt dialog in frontend
- Tests for threshold check + position close logic

Out-of-scope:
- Configurable threshold settings UI (use default for now)
- Unrealized position reporting/dashboard

## Acceptance criteria

- After closing a session with low ending balance, user sees a prompt with impact details
- Confirming the prompt closes the unrealized position (purchases marked dormant, basis recorded)
- Declining the prompt leaves everything unchanged
- Prompt does NOT appear when ending balance is above threshold
- Prompt does NOT appear during "End & Start New" flow

## Test plan

Automated tests:
- Low-balance check returns prompt data when below threshold
- Low-balance check returns empty when above threshold
- Position close marks correct purchases dormant
- Position close records correct basis loss

Manual verification:
- Close session with low balance, verify prompt appears and executes correctly
