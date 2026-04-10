## Problem / motivation

The desktop app supports "travel mode" — when a user enters session times from a timezone different from their accounting timezone, the app shows a globe icon, converts times to UTC correctly, and warns if end time < start time after UTC conversion. The web app stores timezone fields in the data model but has no UI for timezone selection, conversion display, or travel mode indicators.

This is a cross-cutting concern that affects game sessions, purchases, and redemptions.

## Proposed solution

Add timezone awareness to the web frontend:
1. **Timezone selector**: Add timezone dropdown to session/purchase/redemption forms (default to workspace accounting TZ)
2. **Travel mode indicator**: Show globe icon on table rows where entry timezone differs from accounting timezone
3. **UTC conversion validation**: Block saves where end UTC < start UTC with clear error message
4. **Multi-day indicator**: Show `(+Nd)` badge on sessions spanning multiple calendar days
5. **Timezone update prompt**: When editing an entry whose original TZ differs from current selection, prompt for which timestamps to update

## Scope

In-scope:
- Timezone dropdown in session create/edit forms
- Travel mode badge in game sessions table
- UTC validation on session save
- Multi-day session indicator
- Timezone update prompt on edit

Out-of-scope:
- Workspace-level timezone settings management
- Automatic timezone detection from browser
- Timezone display in purchases/redemptions (can follow same pattern later)

## Acceptance criteria

- User can select a timezone when creating/editing sessions
- Travel mode globe appears on sessions entered in non-accounting timezone
- UTC conversion prevents invalid end-before-start scenarios
- Multi-day badge shows for sessions spanning >1 calendar day
- Editing a travel-mode session prompts about timezone updates

## Test plan

Automated tests:
- UTC conversion validation (end < start detection)
- Travel mode detection (entry TZ != accounting TZ)

Manual verification:
- Create session in different timezone, verify globe icon
- Try to save session where end UTC < start UTC, verify error
