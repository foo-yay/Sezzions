## Problem / motivation

Phase 1 (Setup Entities: Users, Sites, Cards, Redemption Method Types, Redemption Methods, Game Types, Games) is complete. The web app can manage all catalog/reference data but has zero transactional capability.

Before any transaction tab (Purchases, Redemptions, Game Sessions) can be built, the accounting engine infrastructure must exist. This is the highest-risk, highest-complexity phase in the web port plan. Every transaction depends on these four services.

Reference: `docs/WEB_PORT_PLAN.md` Phase 2.

## Proposed solution

Port the four core accounting services from the desktop app to the hosted (web) backend. No frontend work in this issue -- this is pure backend infrastructure + tests.

### 4a. Timestamp Service

Ensures no two events (purchase, redemption, session start/end) for the same (user, site) pair share an exact timestamp. Auto-increments by 1 second on conflict.

- Desktop source: `services/timestamp_service.py`
- Port as a hosted service querying across purchases, redemptions, and sessions
- Postgres timestamp handling (not SQLite ISO strings)

### 4b. FIFO Service

The core cost basis engine. Calculates cost_basis, taxable_profit, and per-purchase allocations for each redemption.

- Desktop source: `services/fifo_service.py`
- PARTIAL vs FULL redemption semantics
- `calculate_cost_basis()`, `apply_allocation()`, `reverse_allocation()`
- Needs `hosted_redemption_allocation_repository` for the junction table
- Must use Decimal (not float) for all monetary calculations
- Backend-only service (never exposed to frontend)

### 4c. Recalculation Service

Orchestrates "suffix rebuilds" -- given a (user_id, site_id, boundary_date, boundary_time), reprocesses all FIFO allocations and session P/L from that point forward.

- Desktop source: `services/recalculation_service.py`
- `rebuild_fifo_for_pair_from()`, `rebuild_all()`
- Must run synchronously within the same DB transaction as the mutation
- Port `_containing_boundary()` logic
- Consider timeout/async implications for `rebuild_all()` on large datasets

### 4d. Event Link Service

Links purchases and redemptions to game sessions with a relation type: BEFORE, DURING, or AFTER.

- Desktop source: `services/game_session_event_link_service.py`
- Needs `HostedGameSessionEventLinkRecord` persistence record
- Rebuild links runs as part of the recalculation chain
- Lower priority than FIFO/recalc -- can be stubbed initially if needed

### 4e. Persistence Records

Audit `services/hosted/persistence.py` and add any missing ORM records:
- `HostedRedemptionAllocationRecord` (FIFO junction: redemption_id -> purchase_id, amount)
- `HostedRealizedTransactionRecord` (cashflow P/L per redemption)
- `HostedGameSessionEventLinkRecord` (event linking)
- `HostedDailySessionRecord` (aggregated daily view)
- `HostedAdjustmentRecord` (basis adjustments and balance checkpoints)

## Scope

In-scope:
- Port Timestamp Service, FIFO Service, Recalculation Service, Event Link Service
- Add any missing persistence records
- Hosted repositories for allocation, event link tables
- Extensive test coverage: golden scenarios, edge cases, failure injection, invariants
- Decimal precision throughout

Out-of-scope:
- Transaction tab UIs (Phase 3)
- API endpoints for transactions (Phase 3)
- Reports / derived views (Phase 4)
- Tools (Phase 5)
- Async job queue for rebuild_all (follow-up)

## Implementation notes / strategy

Approach:
- Study each desktop service thoroughly before porting
- Port in dependency order: persistence records -> timestamp service -> FIFO service -> recalculation service -> event link service
- Each service gets its own test file with golden scenario tests matching desktop behavior
- Use the existing desktop test suite as a reference for expected outputs
- All monetary values use Python Decimal, stored as Postgres NUMERIC

Data model / migrations:
- No new Supabase migrations needed if tables already exist
- Verify existing table schemas match expected columns

Risk areas:
- FIFO partial vs full redemption edge cases
- Decimal precision drift (float contamination)
- Recalculation performance on large datasets
- Postgres vs SQLite timestamp semantics
- Transaction isolation for concurrent suffix rebuilds

## Acceptance criteria

- Given a (user, site) pair with existing events, when a new event is created with a conflicting timestamp, then the timestamp service auto-increments by 1 second until unique
- Given purchases in FIFO order, when a PARTIAL redemption is calculated, then cost_basis equals the sum of consumed lots in chronological order up to the redemption amount
- Given purchases in FIFO order, when a FULL redemption is calculated, then ALL remaining basis is consumed regardless of redemption amount
- Given a FIFO allocation, when reverse_allocation is called, then purchase remaining_amount is fully restored
- Given a mutation at time T, when recalculation runs, then all events from T forward have consistent FIFO allocations and P/L
- Given purchases and redemptions within a game session window, when event links are rebuilt, then each event is classified as BEFORE, DURING, or AFTER correctly
- All services pass golden scenario tests that match desktop behavior
- All monetary calculations use Decimal with no float contamination

## Test plan

Automated tests:
- Timestamp service: conflict resolution, no-conflict passthrough, multi-entity conflicts
- FIFO service: single lot, multi-lot partial, full close-out, zero amount, reverse allocation, re-allocation after reversal
- Recalculation service: suffix rebuild from mid-stream, full rebuild, boundary detection
- Event link service: BEFORE/DURING/AFTER classification, session with no events, overlapping sessions
- At least 2 edge cases per service (empty DB, single event, max precision decimals)
- At least 1 failure injection per service (mid-operation failure -> assert rollback/invariants)

Manual verification:
- Create test data via existing desktop app, verify web services produce identical outputs
