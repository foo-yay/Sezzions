# Feature: Standardize Time Handling with User Time Zone

## Problem
Timestamps are currently mixed between local time (user-entered dates/times) and UTC (e.g., audit_log timestamp via CURRENT_TIMESTAMP). This causes confusing date filtering and inconsistent display.

## Proposal
Add a user-configurable time zone setting and standardize storage/display:
- Store all timestamps in UTC at write-time.
- Display dates/times in the user’s selected time zone.
- Changing the time zone affects display only; it does not rewrite existing stored UTC values.

## Scope
- Add Settings option for time zone (IANA TZ, e.g., America/Los_Angeles).
- Update time parsing/formatting helpers to convert local time ↔ UTC.
- Apply conversion for all user-entered timestamps (purchases, redemptions, sessions, adjustments, checkpoints, audit logs).
- Update audit log viewer date filtering to use local display while querying UTC range.
- Migration: backfill existing stored times to UTC using the *current* user time zone at migration time.

## Acceptance Criteria
- User can select time zone in Settings and it persists.
- Creating any record stores UTC timestamps.
- UI displays local times based on the selected time zone.
- Changing time zone changes display for all records without mutating stored values.
- Audit log timestamps and filters align with local display.
- Migration script converts existing rows once, preserving perceived local times.

## Test Plan
- Unit tests for conversion helpers (local ↔ UTC).
- Integration tests: create a record in one TZ, switch TZ, display reflects new TZ without data rewrite.
- Audit log filter test for date ranges in local time.

## Out of Scope
- Multi-user or per-record time zones.
- Historical per-entry time zones beyond the global setting.
