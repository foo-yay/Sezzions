Problem / motivation
The live database currently shows an inconsistent but explainable Unrealized outcome for today’s cross-site free-SC sessions:

- `Play Fame` (`site_id=22`, user `fooyay`) has a closed session `game_sessions.id=468` ending with `0.14` total / redeemable SC and `purchase_basis=0`, so it still appears in Unrealized as a profit-only remainder.
- `Hello Millions` (`site_id=7`, user `fooyay`) has a closed session `game_sessions.id=467` ending with `0.34` total / redeemable SC and `purchase_basis=0`, but it does **not** appear in Unrealized.

Investigation findings:
- `Play Fame` appears because that site/user pair has historical purchase history (`purchases.id IN (621, 356)`), so the current Unrealized logic can derive a profit-only position anchor from prior FIFO-attributed purchases.
- `Hello Millions` does not appear because that site/user pair has **no purchase history at all**. The current Unrealized repository requires a purchase-derived anchor/start date before it can materialize a row, so a pure session-only free-SC remainder is skipped.
- The Unrealized close action currently hard-blocks `purchase_basis <= 0` in the UI, so a visible profit-only / no-basis remainder like `Play Fame` cannot be marked dormant and removed from the tab.

This creates a UX gap:
- no-basis residual balances can still clutter Unrealized when historical purchases exist
- users cannot explicitly mark those balances dormant until later activity
- but we should not disturb the existing basis-consuming closeout logic for real purchased positions

Proposed solution
What:
- Add a **separate zero-basis close path** for Unrealized positions where:
  - `purchase_basis <= 0`,
  - `total_sc > threshold`, and
  - no active session exists for the site/user pair.
- Reuse the existing dormant-close marker concept by creating an explicit zero-dollar close marker that hides the position until later activity reopens it.
- Preserve the current purchased-basis close path unchanged.

Why:
- This solves the user-facing clutter problem for rows like `Play Fame` without changing FIFO semantics, realized loss semantics, or tax semantics for normal positions.
- It uses an already-established closure primitive (`Balance Closed` marker / close-event suppression in Unrealized) instead of inventing a second suppression system.

Notes:
- Recommended semantics for the new no-basis close path:
  - create a `$0.00` close marker with `Net Loss: $0.00`
  - do **not** consume FIFO basis
  - do **not** create realized cash-flow loss
  - do **not** create tax impact
  - do hide the Unrealized row until later purchases/sessions/redemptions occur after the close timestamp
- The current `Hello Millions` non-display was investigated and understood, but changing visibility of pure session-only / no-purchase free-SC remainders should be treated as a separate decision unless explicitly included here.

Scope
In-scope:
- Unrealized close action support for zero-basis / profit-only positions that are already visible in the tab
- service-layer implementation for zero-loss dormant close markers
- guardrails so existing purchased-basis close behavior remains unchanged
- regression coverage for zero-basis visible positions
- spec/changelog updates if behavior changes

Out-of-scope:
- changing how purchased-basis positions are closed today
- changing FIFO allocation rules for close markers with non-zero basis
- changing realized/tax semantics for normal closeouts
- automatically surfacing pure session-only / no-purchase free-SC remainders like the current `Hello Millions` example
- adding a brand-new table or persistence system for dormant residual balances if the existing close-marker semantics are sufficient

UX / fields / checkboxes
Screen/Tab:
- Unrealized tab
- Unrealized “View Position” dialog (if it exposes close action there too)

Fields:
- existing row metrics remain the same (`Remaining Basis`, `Total SC (Est.)`, `Redeemable SC (Position)`, `Current Value`, `Est. Unrealized P/L`)

Checkboxes/toggles:
- none required

Buttons/actions:
- existing `Close Position` action should support zero-basis rows, or a clearly-labeled variant should appear for zero-basis rows

Warnings/confirmations:
- confirmation copy must clearly distinguish:
  - basis-bearing closeout: abandons basis / realized cash-flow loss
  - zero-basis closeout: marks bonus/profit-only balance dormant with **$0.00 loss** and **no tax impact**

Implementation notes / strategy
Approach:
- Keep the existing basis-bearing `close_unrealized_position()` path for `purchase_basis > 0`.
- Add a distinct service/facade branch for `purchase_basis <= 0` that writes a zero-loss dormant close marker.
- Let the existing Unrealized close suppression (`Balance Closed` / full-close event datetime >= last activity datetime) hide the row.
- Ensure future activity after the close timestamp still reopens the position naturally.

Data model / migrations (if any):
- Prefer no schema changes.
- Reuse current redemptions-based close markers if possible.

Risk areas:
- accidentally routing zero-basis closes through the existing basis-abandoning path
- accidentally creating realized cash-flow or tax impact for a no-basis close
- regressions in existing Issue #58 / close-marker behavior for profit-only positions with historical purchases
- UI wording confusion between “abandon basis” vs “mark bonus-only balance dormant”

Acceptance criteria
- Given an Unrealized row with `purchase_basis > 0`, when the user closes it, then existing close semantics remain unchanged.
- Given an Unrealized row with `purchase_basis = 0` and `total_sc > 0`, when the user closes it, then the row disappears from Unrealized without creating any realized cash-flow loss or tax effect.
- Given a zero-basis close marker was created, when later activity occurs after that close timestamp, then the position can reappear naturally under the existing reopen rules.
- Given a zero-basis visible position is closed, when related data is inspected, then no FIFO allocations are added and no purchase basis is consumed.
- Given a zero-basis visible position is closed, when the user reviews confirmation/success text, then the UI clearly states this is a dormant marker with `$0.00` loss.
- Existing purchased-basis close workflows, Unrealized filtering, and close-marker suppression logic continue to pass unchanged.

Test plan
Automated tests:
- Happy path:
  - visible profit-only Unrealized position (`basis = 0`, `SC > 0`) can be closed and disappears
  - later post-close activity reopens the position
- Edge cases:
  - zero-basis position with active session cannot be closed
  - zero-basis position near threshold behaves correctly (no false row resurrection)
  - historical purchased-basis close path remains unchanged
- Failure injection / invariants:
  - if zero-basis close creation fails mid-operation, no partial close marker or row-state drift occurs
  - invariant: zero-basis close creates no FIFO allocations and no realized loss rows with non-zero loss

Manual verification:
- reproduce current `Play Fame` scenario and confirm the row can be marked dormant
- confirm the row disappears from Unrealized after refresh
- start a later session/purchase on the same site and verify reopen behavior
- verify an ordinary basis-bearing close still shows the existing loss wording and behavior

Area
- UI
- Services
- Database/Repositories
- Tests

Notes
- This change likely requires updating `docs/PROJECT_SPEC.md`.
- This change likely requires adding/updating scenario-based tests.
- This change includes destructive actions (must add warnings/backup prompts).
