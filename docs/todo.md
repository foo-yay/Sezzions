# TODO

This file defines the project backlog in a way that separates
**planning decisions** from **implementation work**.

AI agents must follow the role definitions in `AGENTS.md`.

---

## 🧠 PLANNER — Decisions Required (NO CODING)

These items require architectural or accounting decisions
before any code should be written.

### 1. Multi-Currency / Denominations Model
- Support alternate units on Purchases and Redemptions:
  - Fortune Coins (1:100)
  - USDC / crypto
- Ensure:
  - basis logic remains correct
  - reporting stays consistent
- Strategy only — no schema changes until approved.

---

### 2. Redemption Fees Accounting Treatment
- Decide between:
  - net-only redemption entry
  - explicit fee tracking
- Define:
  - tax treatment
  - basis impact
  - reconciliation expectations
- Do not implement without a clear decision.

---

### 6. Tax Reporting Logic (Conceptual)
- Define:
  - when profit becomes taxable
  - how withholding rate is applied
  - session-based vs cash-based reporting
- Identify authoritative reports.

---

### 7. Unit testing
- Determine unit tests to test all functionality
- May require several dozen or more tests to test all logic
- Purchases - adding, editing, deleting purchases
  - with sessions, without sessions, with redemptions, without redemptions
- Redemptions - same thing
- Sessions - editing session content, start DT, end DT, ending values, amounts, etc.  Need to ensure data integrity across a massive number of potential scenarios and edits.

### 8. Code Consolidation
- Top-down, and ground-up review of all code with edits to enforce modularity, re-use, class-based code, removal of deprecated logic, use of globally accessible parameters and methods where possible, etc.

## 🛠️ IMPLEMENTER — Approved for Coding

Only items in this section may be implemented without further approval.
Follow the Planner’s decisions and keep changes minimal.

---

## 🔴 High Priority — IMPLEMENTER TASKS

### UI & Structure
- [ ] Finalize UI redesign in `qt_app.py`
- [ ] Safely deprecate `session2.py` (no breaking imports)
- [ ] Finish incorporating all remaining tabs into the new UI

---

### Recalculation Engine
- [X] Add a one-click **“Recalculate Everything”** action in `qt_app.py`
- [X] Narrow recalculation scope so only affected sessions and downstream records are recomputed
- [X] Ensure editing receipt dates does NOT trigger full site recompute
- [X] Preserve global recompute as a fallback only

---

### Game RTP System
- [X] Rename existing `RTP` → **Expected RTP**
- [X] Add `actual_rtp` to `game_names` table (derived, not editable)
- [X] Incrementally update Actual RTP when:
  - a session is closed
  - a session is edited
- [X] Display Expected + Actual RTP in Games setup
- [X] Show both values as a tooltip in Game selection dialogs
- [X] Add “Recalculate RTP” button (game-scoped, not global)

---

### Sessions & Data Integrity
- [X] Add ability to “Start a New Session” after a purchase
- [X] Implement CSV upload with duplicate detection (additive only)
- [X] Fix Unrealized basis not updating correctly when redemptions are backdated
      (Fixed by scoped recalculation - boundary detection + FIFO rebuild)

---

## 🟠 Medium Priority — IMPLEMENTER TASKS

### Payments & Cards
- [ ] Evaluate whether `method_type` in redemption methods is used; remove if unused
- [X] Add “Last 4” field to Cards
- [X] Display cards as `<Card Name> – x####` in dropdowns
- [X] Ensure full CRUD works everywhere cards are referenced

---

### Accounting & Reporting
- [ ] Add user-defined tax withholding rate (Settings)
- [ ] Consolidated tax reporting based on session outcomes
- [ ] Consolidated balance tracker per Site/User (cleaner Unrealized-style view)
- [ ] Determine best method to link transactions to sessions (after Planner approval)

---

### Platform
- [ ] Add free-tier usage limits
- [ ] Design offline license key system (no server)
- [X] Add database backup strategy
- [ ] Re-integrate Audit Log

---

## 🟢 Low Priority — IMPLEMENTER TASKS / IDEAS

- [ ] Export reports to CSV
- [ ] Daily taxable P/L metrics (hourly, etc.)
- [ ] Export/backup to Google Sheets / Drive (optional automation)
- [ ] Support ticket / bug submission system
- [ ] Web and/or mobile platform exploration
- [ ] Automation ideas:
  - outstanding redemptions > 1 week
  - redeemable balances not acted on
- [ ] Additional redemption statuses:
  - Pending
  - Completed
  - Canceled (should recalc as if nonexistent, but preserve history)

---

## 🧭 Notes for AI Agents

- Do not refactor working code unless explicitly instructed.
- Do not perform global recalculations unless explicitly triggered.
- Prefer incremental, scoped updates.
- Historical correctness is more important than elegance or performance.

## Backlog Intake Rules
- New ideas go in TODO → Ideas / Parking Lot
- Bugs go in TODO → Bugs / Issues
- Only items in IMPLEMENTER sections may be coded
- PLANNER sections are design-only

## 📝 Ideas / Parking Lot (Not Approved)

- [ ] Idea: Auto-detect abandoned sessions after X days
- [ ] Feature: Per-game volatility tracking
- [ ] UX: Warn before editing transactions that trigger recalculation


## 🐞 Bugs / Issues (Triage Needed)

(No open bugs at this time)