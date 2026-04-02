## Problem / Motivation

The hosted web app currently has Setup > Users and Setup > Sites. The next entity to port is **Cards** — a user-owned entity with a cashback rate that drives automatic cashback calculations on purchases. Cards is the first hosted entity with a **foreign key to another business entity** (users), which introduces new patterns: user-selector dropdown in the modal, user-name display in the table row, and cross-entity data fetching.

The desktop Cards tab has nuanced features (cashback %, last-four masking, user-FK autocomplete, display name formatting, multi-select delete with FK protection, and integration into the purchase cashback pipeline) that must reach parity in the hosted web app.

## Proposal

Implement full **Setup > Cards** CRUD in the hosted web app following the established Users/Sites pattern, with all desktop-parity features.

### Scope

**In scope:**
- Hosted backend: HostedCard model, repository, service, 5 API endpoints
- Frontend: CardsTab, CardModal, cardsConstants, cardsUtils
- User dropdown in Card create/edit modal (foreign-key selector)
- Cashback rate field with percent formatting and 0-100 validation
- Last-four field with 4-character mask
- Table row display: Name, User, Last Four, Cashback %, Status, Notes
- View/Edit/Delete from view dialog
- Multi-row delete with batch endpoint
- Desktop parity for: search, sort, filter, export CSV
- Tests (backend unit + frontend integration)

**Out of scope (follow-up issues):**
- Purchase cashback auto-calculation (depends on Purchases tab, Issue TBD)
- Cashback recalculation service (depends on Purchases + FIFO)
- CSV import of cards (depends on import infrastructure)
- Card deletion FK protection (no purchases table yet — trivially deletable for now)

## Detailed Implementation Plan

---

### Phase 1 — Backend (Hosted Card Model + Repository + Service + API)

#### 1A. HostedCard Model (`services/hosted/models.py`)

Add `HostedCard` dataclass following the HostedSite pattern:

```python
@dataclass
class HostedCard:
    name: str                              # Required, stripped, non-empty
    user_id: str                           # Required, FK to hosted_users.id
    workspace_id: Optional[str] = None
    last_four: Optional[str] = None        # Exactly 4 numeric chars if provided
    cashback_rate: float = 0.0             # 0-100 range, 2 decimal display
    is_active: bool = True
    notes: Optional[str] = None
    id: Optional[str] = None
    user_name: Optional[str] = None        # Denormalized from FK join (read-only)
```

**Validation rules (parity with desktop `models/card.py`):**
- `name`: required, strip whitespace, non-empty after strip
- `user_id`: required, non-empty string
- `cashback_rate`: must be 0 ≤ rate ≤ 100
- `last_four`: if provided, must be exactly 4 characters (numeric-only check optional — desktop enforces in UI, not model)
- `notes`: strip whitespace, coerce empty to None

**Method:** `as_dict()` — returns dict for API serialization; includes `user_name`.

**Note:** Unlike desktop Card (which has `display_name()` returning `"Name -- x1234"`), the hosted model keeps this as a frontend concern — the API returns raw fields and the frontend formats.

---

#### 1B. HostedCard Repository (`repositories/hosted_card_repository.py`)

Follow the `HostedSiteRepository` pattern. Methods:

| Method | Signature | Notes |
|--------|-----------|-------|
| `list_by_workspace_id()` | `(session, workspace_id, *, limit, offset)` → `list[HostedCard]` | LEFT JOIN `hosted_users` for `user_name`. Order by `name ASC, id ASC`. |
| `count_by_workspace_id()` | `(session, workspace_id)` → `int` | Count for pagination. |
| `get_by_id_and_workspace_id()` | `(session, *, card_id, workspace_id)` → `HostedCard \| None` | Single fetch with user_name join. |
| `create()` | `(session, *, workspace_id, user_id, name, last_four, cashback_rate, is_active, notes)` → `HostedCard` | Insert, flush, return model. |
| `update()` | `(session, *, card_id, workspace_id, user_id, name, last_four, cashback_rate, is_active, notes)` → `HostedCard \| None` | Full update. |
| `delete()` | `(session, *, card_id, workspace_id)` → `bool` | Single delete. |
| `delete_many()` | `(session, *, card_ids, workspace_id)` → `int` | Batch delete. |

**Key difference from Sites:** Cards requires a LEFT JOIN to `hosted_users` for `user_name` in list/get queries (same pattern as desktop `card_repository.py`). The `_record_to_model()` helper must map `user_name` from the joined user record.

**FK validation:** `create()` and `update()` should validate that `user_id` exists in `hosted_users` for the same workspace (prevent cross-workspace user references). This can be done via a query or by relying on the FK constraint + catching IntegrityError.

---

#### 1C. Hosted Workspace Card Service (`services/hosted/workspace_card_service.py`)

Follow `HostedWorkspaceSiteService` pattern:

| Method | Parameters | Returns | Notes |
|--------|------------|---------|-------|
| `list_cards()` | `supabase_user_id, *, limit, offset` | `(list[HostedCard], int)` | Returns (cards, total_count) |
| `create_card()` | `supabase_user_id, *, name, user_id, last_four, cashback_rate, notes` | `HostedCard` | Validates via HostedCard model, then persists |
| `update_card()` | `supabase_user_id, card_id, *, name, user_id, last_four, cashback_rate, is_active, notes` | `HostedCard` | Returns None → 404 |
| `delete_card()` | `supabase_user_id, card_id` | `bool` | Single delete |
| `delete_cards()` | `supabase_user_id, card_ids` | `int` | Batch delete, returns count |

All methods resolve workspace from `supabase_user_id` via `_require_workspace()`.

---

#### 1D. API Endpoints (`api/app.py`)

5 endpoints following the Sites pattern:

| Method | Path | Request | Response |
|--------|------|---------|----------|
| `GET` | `/v1/workspace/cards?limit=100&offset=0` | Query params | `{ cards: [...], total: N }` |
| `POST` | `/v1/workspace/cards` | `{ name, user_id, last_four?, cashback_rate?, notes? }` | `201` + card object |
| `PATCH` | `/v1/workspace/cards/{card_id}` | `{ name, user_id, last_four?, cashback_rate?, is_active, notes? }` | `200` + card object |
| `DELETE` | `/v1/workspace/cards/{card_id}` | — | `204` |
| `POST` | `/v1/workspace/cards/batch-delete` | `{ ids: [...] }` | `200` + `{ deleted: N }` |

**Card response shape:**
```json
{
  "id": "uuid",
  "workspace_id": "uuid",
  "user_id": "uuid",
  "user_name": "Elliot",
  "name": "Chase Sapphire",
  "last_four": "1234",
  "cashback_rate": 2.0,
  "is_active": true,
  "notes": null
}
```

**Note:** `user_name` is denormalized in the response so the frontend doesn't need a separate users fetch for display (same pattern as desktop `card_repository.get_by_id()` joining `users.name`).

---

### Phase 2 — Frontend (CardsTab + CardModal)

#### 2A. File Structure

```
web/src/components/CardsTab/
├── CardsTab.jsx         # Main tab component (follows SitesTab pattern)
├── CardModal.jsx        # View / Create / Edit modal
├── cardsConstants.js    # Form defaults, column defs, page sizes
└── cardsUtils.js        # Card-specific display/filter helpers
```

#### 2B. `cardsConstants.js`

```javascript
export const initialCardForm = {
  name: "",
  user_id: "",        // FK — populated from user dropdown
  last_four: "",
  cashback_rate: "",   // String for input; parsed on submit
  notes: "",
  is_active: true,
};

export const initialCardColumnFilters = {
  name: [],
  user_name: [],
  last_four: [],
  cashback_rate: [],
  status: [],
  notes: [],
};

export const cardTableColumns = [
  { key: "name", label: "Name", sortable: true },
  { key: "user_name", label: "User", sortable: true },
  { key: "last_four", label: "Last Four", sortable: true },
  { key: "cashback_rate", label: "Cashback %", sortable: true, numeric: true, align: "right" },
  { key: "status", label: "Status", sortable: true },
  { key: "notes", label: "Notes", sortable: true },
];

export const cardsPageSize = 100;
export const cardsFallbackPageSize = 500;
```

#### 2C. `CardModal.jsx`

**View mode:** Read-only display of all fields including user name, cashback formatted as `X.XX%`, last four as `x1234`, status as Active/Inactive. Action buttons: Edit, Delete, Close.

**Create/Edit mode:** Form with:
1. **User** (required) — `<select>` or searchable dropdown populated from `GET /v1/workspace/users?limit=500` (active users). Shows user name, stores user_id. This is the **first cross-entity dropdown** in the hosted web app.
2. **Card Name** (required) — text input
3. **Cashback %** (optional) — numeric input, placeholder "0.00", validated 0-100
4. **Last Four** (optional) — text input, maxLength=4, placeholder "Optional"
5. **Active** toggle (edit mode only)
6. **Notes** — collapsible textarea (matches desktop pattern)

**Validation (inline + submit):**
- User required (non-empty user_id)
- Name required (non-empty after trim)
- Cashback: if provided, numeric and 0-100
- Last four: if provided, exactly 4 characters

**Dirty tracking:** Same `formBaseline` comparison pattern as Users/Sites for unsaved-changes confirmation on close.

#### 2D. `CardsTab.jsx`

Follows SitesTab exactly for:
- Paginated fetch with `GET /v1/workspace/cards?limit=100&offset=0`
- Search across: name, user_name, last_four, cashback_rate (formatted), notes
- Column sorting with numeric sort for cashback_rate
- Column filters via HeaderFilterMenu
- Selection state, multi-select, batch delete
- Export CSV with columns: Name, User, Last Four, Cashback %, Status, Notes
- Toolbar: Add, View, Edit, Delete, Export, Refresh
- Double-click row → View modal
- Keyboard: Cmd+F for search focus

**Card-specific display:**
- Cashback: `{rate.toFixed(2)}%` (right-aligned)
- Last Four: show as-is or "—" if null
- User: show `user_name` or "—" if null/orphaned
- Status: "Active" / "Inactive" with gray styling for inactive

#### 2E. AppShell Registration

- Enable the cards tab: `{ key: "cards", label: "Cards", icon: "cards", enabled: true }`
- Import `CardsTab` and render when `setupTab === "cards"`

---

### Phase 3 — Cascading Dependencies & Future Integration Points

These are **not in scope for this issue** but must be documented because Cards implementation choices affect them:

#### 3A. Purchases → Cards FK (Future: Purchases Tab)

When Purchases are implemented:
- Purchase create/edit modal needs a **card dropdown** filtered by the selected user (same user-scoped FK pattern as desktop)
- Card dropdown only populated after user is selected
- `card_id` is optional on purchases (`ON DELETE SET NULL`)
- Cashback auto-calculation: `amount × (cashback_rate / 100)` when card has a rate
- `cashback_is_manual` flag: if user overrides cashback, skip auto-recalculation on future edits

**Design implication for this issue:** The card API response already includes `cashback_rate` so the frontend can compute display cashback without extra API calls. No cashback calculation logic is needed in the Cards tab itself.

#### 3B. Card-User Cascade

- Deleting a hosted user cascades to delete their cards (`ON DELETE CASCADE` on `hosted_cards.user_id`)
- The Cards tab must handle the case where a listed card's user was deleted between fetch and display (show "Unknown User" or re-fetch)
- The Users tab delete confirmation should ideally warn about cascading card deletions (future enhancement)

#### 3C. Cashback Recalculation Pipeline (Future)

Desktop has `RecalculationService._recalculate_cashback_for_pair()` that:
1. Joins purchases → cards
2. Skips manually-set cashback
3. Recalculates `amount × (rate / 100)` for auto-calculated purchases
4. Called during full rebuild and pair rebuild

The hosted equivalent will need:
- A hosted recalculation service
- Same `cashback_is_manual` guard
- Triggered by: card cashback_rate update, purchase amount update, card reassignment

#### 3D. CSV Import/Export (Future)

Desktop supports CSV import/export for cards with user-scoped FK resolution:
- Export: Name, User, Last Four, Cashback %, Status, Notes
- Import: resolves user by name, scoped to avoid cross-user ambiguity

#### 3E. Data Migration (Future)

The migration upload plan already inventories cards from the desktop SQLite. When import-execute is built, cards will need:
- Desktop `cards.user_id` (integer) → hosted `hosted_cards.user_id` (UUID) mapping via user name/email match
- Cashback rates preserved as-is
- Active/inactive status preserved

---

## Acceptance Criteria

- [ ] `GET /v1/workspace/cards` returns paginated cards with `user_name` from FK join
- [ ] `POST /v1/workspace/cards` creates a card with user_id FK validation
- [ ] `PATCH /v1/workspace/cards/{id}` updates all card fields including user reassignment
- [ ] `DELETE /v1/workspace/cards/{id}` and `POST /v1/workspace/cards/batch-delete` work
- [ ] Cards tab renders in Setup navigation and displays the 6-column table
- [ ] Card create/edit modal has user dropdown populated from hosted users endpoint
- [ ] Cashback % field validates 0-100 range and displays with 2 decimal places
- [ ] Last Four field validates maxLength=4
- [ ] View modal shows all fields read-only with Edit/Delete actions
- [ ] Multi-row delete works with confirmation dialog
- [ ] Search filters across name, user_name, last_four, cashback_rate, notes
- [ ] Column sorting works (numeric sort for cashback_rate)
- [ ] Export CSV exports visible rows with headers
- [ ] Deleting a user cascades to delete their cards (verified via DB constraint)

## Test Plan

**Backend unit tests:**
- HostedCard model validation (name, user_id, cashback_rate range, last_four length)
- Repository CRUD + user_name join
- Service layer with workspace isolation
- API endpoint responses + error cases

**Frontend integration tests (in App.test.jsx):**
- Cards tab renders after bootstrap with empty state
- Create card via modal with user dropdown
- Edit card (modify name, cashback, user)
- Delete card with confirmation
- Cashback % display formatting
- User name display from FK

## Cascading Implementation Summary

```
                    ┌──────────────┐
                    │  hosted_users │  ← Already implemented
                    └──────┬───────┘
                           │ ON DELETE CASCADE
                           ▼
                    ┌──────────────┐
     THIS ISSUE ──▶ │ hosted_cards │  ← Cards CRUD + user FK dropdown
                    └──────┬───────┘
                           │ ON DELETE SET NULL (future)
                           ▼
                    ┌────────────────┐
     FUTURE ──────▶ │hosted_purchases│  ← card_id FK, cashback auto-calc
                    └────────┬───────┘
                             │
                             ▼
                    ┌────────────────────────┐
     FUTURE ──────▶ │cashback recalculation  │  ← rate changes, amount changes
                    └────────────────────────┘
```

**Blocking order:**
1. **Cards** (this issue) — no blockers, depends only on Users (done)
2. **Purchases** — depends on Cards + Sites (both done after this issue)
3. **Cashback pipeline** — depends on Purchases + Cards
4. **FIFO / Recalculation** — depends on Purchases + Cards + full accounting chain

---

## Labels

enhancement
