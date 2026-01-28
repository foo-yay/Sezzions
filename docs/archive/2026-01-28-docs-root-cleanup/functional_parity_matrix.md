# Sezzions Functional Parity Matrix (Legacy qt_app.py)

Status legend: ✅ = parity, ⚠️ = partial/needs verification, ❌ = missing

## Purchases Tab
| Feature | Legacy (qt_app.py) | Sezzions | Notes/Gaps |
|---|---|---|---|
| Add/Edit/Delete/View purchase | ✅ | ✅ | View-first double-click present in Sezzions. |
| Search + Clear + Clear All Filters | ✅ | ✅ | Sezzions matches. |
| Date filter row w/ quick ranges | ✅ | ✅ | DateFilterWidget includes quick-range buttons + All Time. |
| Export visible rows CSV | ✅ | ✅ | Present. |
| FIFO protections on edits/deletes | ✅ | ✅ | Confirm edge cases vs legacy. |
| Card cashback auto-calc | ✅ | ✅ | Implemented in Sezzions purchases dialog + cards cashback %. |
| Linked sessions/redemptions in view | ✅ | ✅ | Related tabs show allocations + linked sessions w/ relation. |

## Redemptions Tab
| Feature | Legacy | Sezzions | Notes/Gaps |
|---|---|---|---|
| Add/Edit/Delete/View redemption | ✅ | ✅ | View-first double-click present. |
| Search + Clear + Clear All Filters | ✅ | ✅ | Present. |
| Date filter row w/ quick ranges | ✅ | ✅ | DateFilterWidget includes quick-range buttons + All Time. |
| Export CSV | ✅ | ✅ | Present. |
| Partial redemption warning | ✅ | ✅ | Warning dialog implemented on add/edit. |
| View Realized Position | ✅ | ✅ | Button present. |
| Allocation detail view | ✅ | ✅ | Allocations + unbased summary verified. |

## Game Sessions Tab
| Feature | Legacy | Sezzions | Notes/Gaps |
|---|---|---|---|
| Start/End/Edit/View sessions | ✅ | ✅ | Present. |
| Expected balances + freebies detection | ✅ | ✅ | Uses legacy-equivalent expected balance calculation. |
| RTP tooling (expected/actual) | ✅ | ✅ | Implemented per RTP doc. |
| Linked purchases/redemptions tables | ✅ | ✅ | Uses explicit link model with relations. |
| Time normalization (now/defaults) | ✅ | ✅ | Dialogs normalize HH:MM to HH:MM:SS. |

## Daily Sessions Tab
| Feature | Legacy | Sezzions | Notes/Gaps |
|---|---|---|---|
| Rollup view + notes | ✅ | ✅ | Present. |
| Expand/Collapse all | ✅ | ✅ | Present. |
| Export CSV | ✅ | ✅ | Present. |
| Search + Clear + Clear All Filters | ✅ | ✅ | Present. |

## Unrealized Tab
| Feature | Legacy | Sezzions | Notes/Gaps |
|---|---|---|---|
| View Position dialog | ✅ | ✅ | Present. |
| Close Position (0 redemption + dormant) | ✅ | ✅ | Implemented. |
| Notes stored per position | ✅ | ✅ | Sezzions uses unrealized_positions table. |
| Export CSV | ✅ | ✅ | Present. |
| Search + Clear + Clear All Filters | ✅ | ✅ | Present. |

## Realized Tab
| Feature | Legacy | Sezzions | Notes/Gaps |
|---|---|---|---|
| View cashflow table | ✅ | ✅ | Present. |
| View Position dialog | ✅ | ✅ | Implemented with allocations + linked sessions. |
| View in Redemptions / Daily Sessions | ✅ | ✅ | Linked to Redemptions + Daily Sessions navigation. |
| Notes editing | ✅ | ✅ | Present. |
| Search + Clear + Clear All Filters | ✅ | ✅ | Search + clear actions implemented. |
| Export CSV | ✅ | ✅ | Present. |

## Expenses Tab
| Feature | Legacy | Sezzions | Notes/Gaps |
|---|---|---|---|
| Add/Edit/Delete/View expense | ✅ | ✅ | Present. |
| Search + Clear + Clear All Filters | ✅ | ✅ | Present. |
| Date filter row w/ quick ranges | ✅ | ✅ | DateFilterWidget includes quick-range buttons + All Time. |
| Export CSV | ✅ | ✅ | Present. |

## Setup Tab (Users/Sites/Cards/Methods/Game Types/Games)
| Feature | Legacy | Sezzions | Notes/Gaps |
|---|---|---|---|
| CRUD per setup entity | ✅ | ✅ | Present. |
| Export CSV per setup list | ✅ | ❌ | Missing in Sezzions. |
| Tools sub-tab (import/export/backups/recalc) | ✅ | ❌ | Missing in Sezzions. |
| Dialog button spacing parity | ✅ | ⚠️ | Documented gap. |
| Redemption methods: user required | ✅ | ⚠️ | Documented gap. |
| Redemption methods: no default type | ✅ | ⚠️ | Documented gap. |
| Cards: cashback % field | ✅ | ✅ | Implemented. |

## Reports Tab
| Feature | Legacy | Sezzions | Notes/Gaps |
|---|---|---|---|
| Reports tab (legacy dashboard/reports) | ✅ | ❌ | Not present in Sezzions UI. |

## Backend Workflow Parity (Purchase → Session → Redemption)
| Behavior | Legacy | Sezzions | Notes/Gaps |
|---|---|---|---|
| FIFO allocation respects redemption timestamp | ✅ | ✅ | Implemented. |
| Scoped recalculation (vs full) | ✅ | ✅ | Scoped FIFO + session recalculation from boundary. |
| Deleting redemption unwinds FIFO + realized | ✅ | ✅ | Reverse allocation + delete realized record. |
| Partial redemption warning vs balance | ✅ | ✅ | Warning dialog implemented. |
| Linked events (purchases/redemptions ↔ sessions) | Implicit | ✅ | Explicit link model rebuilt on changes. |
| Time normalization on create/edit | ✅ | ✅ | Dialogs normalize time input to HH:MM:SS. |

---

## Next Step
Use this matrix to drive parity work without changing behavior until each gap is confirmed and approved.
