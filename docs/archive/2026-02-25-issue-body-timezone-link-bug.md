## Summary

`rebuild_links_for_pair_from` passes a **local-time** boundary to SQL queries that compare it against **UTC-stored** column values. When the numeric local time is less than the UTC session end-time, the closed session is incorrectly pulled into the "suffix" window, causing its own DELETE+re-INSERT pass to **omit BEFORE purchases** that predate the session start. Compounding this, `get_linked_events_for_session` has an early-return that prevents the self-healing full rebuild from firing when a session already has any links (e.g., a lone AFTER redemption link).

**Known instance:** Session 274 (mrs. fooyay, Stake, 2026-02-23) is missing its BEFORE link for purchase 453.

## Impact / scope

Impact:
- **Data correctness:** BEFORE purchase links are silently dropped for any session whose UTC end-time is numerically greater than its local-time boundary equivalent. The affected session shows "no purchases contributed basis" in the View Session Related tab.
- **Silent / no error:** No exception is raised; the link is simply absent.
- **Accumulating:** Every subsequent scoped rebuild (redemption create, session update nearest that boundary) repeats the incorrect scope and never restores the lost link.

Scope:
- Any user/site pair where session end times differ when compared as local vs. UTC strings (i.e., UTC offset > 0).
- `services/game_session_event_link_service.py` -- `rebuild_links_for_pair_from`
- `app_facade.py` -- `get_linked_events_for_session` (early-return bug)

## Steps to reproduce

**Minimal scenario (timezone-offset environment required; confirmed on America/New_York = UTC-5):**

1. User A, Site X: has a closed session S with start=T, end=T+D (where UTC_end_time > local_end_time numerically due to offset).
2. Create a purchase P at timestamp T-19s (just before session start).
3. Close session S (triggers scoped rebuild -- correctly creates P->S BEFORE link).
4. Immediately create a redemption R at the session end time (triggers another scoped rebuild).
5. Open View Session for session S, Related tab.

**Expected:** Purchase P appears in the Related tab as BEFORE.
**Actual:** Purchase P is absent. Only the redemption appears as AFTER.

**Real instance (reproducible from DB):**

```
Session 274: user_id=2 (mrs. fooyay), site_id=31 (Stake)
  start: 2026-02-23 15:54:52 (UTC, stored)
  end:   2026-02-24 12:15:45 (UTC, stored)

Purchase 453: purchase_date=2026-02-23 purchase_time=15:54:33 (19s before session start)

math confirms: prev_session_269.end (2026-02-22 06:15:00) <= p453 (15:54:33) < session_274.start (15:54:52) -> BEFORE
```

## Expected behavior

- `rebuild_links_for_pair_from` must compare `from_date`/`from_time` against stored column values in a **consistent timezone** (both UTC or both local).
- `get_linked_events_for_session` must not skip the self-healing rebuild just because _some_ links exist; it should only skip if _both_ purchases and redemptions are already populated, or better, always rebuild for closed sessions with basis > 0 and no purchase links.
- After either fix, View Session Related tab for session 274 must show purchase 453 as BEFORE.

## Actual behavior

1. After session 274 closes, `_containing_boundary` returns local boundary `(2026-02-23, 07:54:52)` (UTC-5 of stored `15:54:52`). Scoped rebuild correctly includes session 274, creates `purchase#453 BEFORE` link.
2. Redemption 175 is then created (local 07:16:23 = UTC 12:16:23). No containing session found; boundary = `(2026-02-24, 07:16:23)` (local).
3. `rebuild_links_for_pair_from` runs with LOCAL `from_time="07:16:23"`.
4. Suffix SQL: `COALESCE(end_time,'00:00:00') >= '07:16:23'` -- session 274's UTC end_time `12:15:45 >= 07:16:23` evaluates TRUE. Session 274 is **incorrectly pulled into suffix**.
5. DELETE step removes the just-created `purchase#453 BEFORE` link and `redemption#175 AFTER` link for session 274.
6. session 274 becomes its own checkpoint (`session_date < from_date "2026-02-24"`). `prev_end_dt` = `2026-02-24 12:15:45`.
7. Purchases query: `purchase_date > "2026-02-24"` -- purchase 453 (dated 2026-02-23) is **excluded**.
8. Only `redemption#175 AFTER` is re-inserted. `purchase#453 BEFORE` is lost permanently.
9. `get_linked_events_for_session` sees `redemptions` non-empty, returns early -- self-healing rebuild never fires.

## Logs / traceback

No exception. Silent data loss. Forensic evidence in `game_session_event_links`:

```
[2026-02-24 12:16:23] 1 link for session 274: redemption#175 AFTER
-- purchase#453 BEFORE: absent
```

Full audit log trace attached in [docs/archive/2026-02-25-issue-body-timezone-link-bug.md] investigation notes.

## Severity

Critical (data incorrect / accounting incorrect)

## Environment

macOS 14.x, Python 3.14.2, America/New_York (UTC-5). Bug affects any UTC-offset >= 1 hour when rebuild boundary time (local) < UTC session end time numerically.

## Root cause (precise)

### Bug A -- `rebuild_links_for_pair_from` (timezone mixing)

`_containing_boundary` calls `_find_containing_session_start` which returns a **local-time** boundary pair via `utc_date_time_to_local`. This local boundary is passed verbatim to `rebuild_links_for_pair_from` as `from_date`/`from_time`. Inside that function, the SQL suffix/checkpoint/purchases queries compare the local `from_time` STRING against UTC-stored column values (`end_time`, `session_time`, `purchase_time`). This is a timezone-mixing string comparison.

Conditions for data loss:
- UTC offset >= 1h (affects all US timezones)
- Closed session with UTC `end_time` numerically > local `from_time`
- Purchase exists in the BEFORE window (prev_end < p < session_start)

### Bug B -- `get_linked_events_for_session` (early-return covers up Bug A)

```python
if events.get("purchases") or events.get("redemptions"):
    return events   # fires if EITHER is non-empty; never heals missing purchases
```

Should require both to be non-empty (or always rebuild for closed sessions missing purchase links).

## Acceptance criteria

### Core fix (Bug A)

- [ ] All values stored in `from_date`/`from_time` are compared in a consistent timezone in `rebuild_links_for_pair_from`. Either: (a) convert `from_date`/`from_time` to UTC before the SQL, or (b) store and pass UTC throughout `_rebuild_or_mark_stale` / `_containing_boundary` / scoped rebuild.
- [ ] After fix, a full `rebuild_links_for_pair(site_id=31, user_id=2)` produces `purchase#453 BEFORE` for session 274.
- [ ] DB patch: insert `(274, 'purchase', 453, 'BEFORE')` into `game_session_event_links`.

### Self-healing fix (Bug B)

- [ ] `get_linked_events_for_session` triggers a rebuild when a closed session has no purchase links (regardless of redemption links).

### Tests

#### Happy path
- [ ] Closed session S, purchase P at T-19s: scoped rebuild (triggered by redemption CREATE at session end time) must produce P->S BEFORE link.
- [ ] Full rebuild (`rebuild_links_for_pair`) produces correct BEFORE/DURING/AFTER links matching simulation output.

#### Edge cases
- [ ] **UTC offset day rollover:** Session end is 2026-02-23 23:50:00 UTC (= 2026-02-23 18:50:00 local). Redemption created at local 18:50:30 on same day. Verify BEFORE purchase from earlier that day is not dropped.
- [ ] **No containing session:** Boundary falls outside all sessions (raw event time used). Scoped rebuild must not corrupt links for sessions whose end_time is numerically > the raw boundary time in local.
- [ ] **Active session:** Scoped rebuild with Active session in suffix -- no BEFORE purchases for Active sessions should be incorrectly assigned.
- [ ] **Multiple sessions same pair, same boundary day:** Verify only the correct session absorbs BEFORE purchases; adjacent sessions' links are not disturbed.
- [ ] **get_linked_events_for_session -- lone redemption link:** Closed session with only an AFTER redemption link and purchase in BEFORE window -- must trigger rebuild and return purchase.

#### Failure injection / invariants
- [ ] Mid-rebuild crash (simulated exception after DELETE, before INSERT): rollback must restore prior links intact (SQLite transaction semantics).
- [ ] After any scoped rebuild, no purchase can be linked to two different sessions simultaneously as BEFORE.
- [ ] `INSERT OR IGNORE` uniqueness constraint must never produce duplicate `(session_id, event_type, event_id, relation)` rows.

#### Regression
- [ ] `tests/` full suite (pytest -q) passes green before and after.
- [ ] Headless smoke test: `QT_QPA_PLATFORM=offscreen` app boot + View Session for session 274 shows purchase 453 in Related tab after fix.

## Test plan (scenario-based)

1. **Golden scenario:** Replicate bug exactly in a fresh in-memory SQLite DB:
   - Insert session 269 (prev, closed, ends 2026-02-22 06:15:00 UTC)
   - Insert session 274 (closed, start 2026-02-23 15:54:52, end 2026-02-24 12:15:45 UTC)
   - Insert purchase 453 (2026-02-23 15:54:33 UTC)
   - Insert redemption 175 (2026-02-24 12:16:23 UTC)
   - Call `rebuild_links_for_pair_from(site_id, user_id, from_date="2026-02-24", from_time="07:16:23")` -- simulating the pre-fix (local) call
   - Assert: purchase 453 NOT in links (demonstrates bug)
   - Apply fix
   - Assert: purchase 453 IS in links as BEFORE (demonstrates fix)

2. **Regression scenario:** Existing older closed sessions in the pair must not gain/lose any links after the fix.

## Pitfalls / follow-ups

- `rebuild_links_for_pair` (full, non-scoped) does NOT have this bug because it doesn't use `from_date`/`from_time` boundaries at all -- it always iterates all sessions. The bug is strictly in the scoped variant.
- Consider unifying boundary passing to always use UTC tuples throughout `_rebuild_or_mark_stale` and `_containing_boundary` to prevent recurrence.
- Audit other calls to `rebuild_links_for_pair_from` for the same timezone-mixing pattern.
- Consider adding a schema-level timestamp audit helper to verify no BEFORE link was deleted without a replacement in the same batch.
