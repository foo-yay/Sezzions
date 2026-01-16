# TODO

This file defines the project backlog in a way that separates
**planning decisions** from **implementation work**.

AI agents must follow the role definitions in `AGENTS.md`.

---

## 🧠 PLANNER — Decisions Required (NO CODING)

These items require architectural or accounting decisions
before any code should be written.

### 6. Tax Reporting Logic (Conceptual)
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

---

## 🟠 Medium Priority — IMPLEMENTER TASKS

### Accounting & Reporting
- [ ] Add user-defined tax withholding rate (Settings)
- [ ] Consolidated tax reporting based on session outcomes
- [ ] Consolidated balance tracker per Site/User (cleaner Unrealized-style view)

---

### Platform
- [ ] Add free-tier usage limits
- [ ] Design offline license key system (no server)

---

## 🟢 Low Priority — IMPLEMENTER TASKS / IDEAS

- [ ] Export reports to CSV
- [X] Daily taxable P/L metrics (hourly, etc.)
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

- [ ] Create notifications when played through balances haven't been redeemed in more than 1 week?  72 hours? 96 hours?
- [ ] Create notifications when sessions go longer than 24 hours


## 🐞 Bugs / Issues (Triage Needed)
- [ ] Export CSV's were outputting empty CSV's
- [ ] Unit testing
- [ ] Additional redemption statuses
(No open bugs at this time)