Problem / motivation
Closing a session with an effectively empty leftover balance does not currently offer a direct close-out step for the still-open position. This can leave prior purchase basis open across a later rebuy cycle, causing Unrealized to reopen with old still-open basis and making the row look like a massive loss.

The desired workflow is:
- if a closed session leaves less than $1.00 equivalent on-site, prompt the user to close the position immediately
- reuse the existing close-position semantics so basis-bearing closes still abandon basis and zero-basis closes still write only a dormant close marker
- preserve the recently added zero-basis Unrealized close behavior for profit-only / no-basis rows

Proposed solution
What:
- After a normal session close (not the “End & Start New” flow), detect whether the ending total balance is below a configurable-equivalent threshold of $1.00 using the site’s `sc_rate`
- If below threshold and there is still an open position for that site/user pair, prompt the user to close the position now
- If the user confirms, route through the existing `close_unrealized_position()` flow so:
  - `Remaining Basis > 0` keeps the current basis-abandoning close behavior
  - `Remaining Basis = 0` keeps the zero-basis dormant close-marker behavior with no FIFO / realized loss row

Why:
- prevents silent carry-forward of stale basis into a new cycle after a near-zero bust-out
- preserves explicit user intent instead of auto-closing without confirmation
- keeps the current two close semantics intact instead of inventing a third accounting path

Notes:
- The prompt threshold must use dollar-equivalent value, not raw SC count
- Example: `sc_rate = 1.0` => prompt when ending balance < 1 SC
- Example: `sc_rate = 0.01` (100 SC = $1) => prompt when ending balance < 100 SC
- Preserve the zero-basis close path added recently for Unrealized positions

Scope
In-scope:
- Game Sessions tab normal end-session flow
- Threshold check based on ending balance × `sc_rate`
- Prompt-to-close UX after successful session close
- Reuse of existing basis-bearing vs zero-basis close semantics
- Regression coverage for basis-bearing and zero-basis prompt flows
- Spec/changelog updates

Out-of-scope:
- Auto-closing positions without user confirmation
- Changing FIFO accounting semantics for ordinary close-position behavior
- Changing the “End & Start New” workflow unless necessary for guardrails
- Changing how pure session-only/no-purchase remainders become visible in Unrealized

UX / fields / checkboxes
Screen/Tab:
- Game Sessions tab
- End Session dialog follow-up flow after successful close

Fields:
- uses existing ending total SC / ending redeemable SC fields

Checkboxes/toggles:
- none

Buttons/actions:
- after a qualifying session close, show a follow-up confirmation to close the position now
- confirmed action reuses existing close-position service logic

Warnings/confirmations:
- confirmation text must distinguish:
  - basis-bearing closeout: abandons remaining basis and records realized cash-flow loss
  - zero-basis closeout: writes dormant close marker only with $0.00 loss and no tax impact

Implementation notes / strategy
Approach:
- add a service/facade helper that determines whether a just-closed session qualifies for low-balance close prompting and returns the data needed for the prompt
- trigger the prompt from the normal end-session UI flow after the session close succeeds and the UI refreshes
- use the existing `close_unrealized_position()` implementation for the actual closeout
- skip prompting on “End & Start New” because the user is explicitly continuing the cycle immediately

Data model / migrations (if any):
- no schema changes expected

Risk areas:
- breaking the zero-basis close path added recently
- prompting when there is no meaningful open position left to close
- prompting on raw SC instead of dollar-equivalent value
- double prompts or prompt timing issues during end-session UI flows

Acceptance criteria
- Given a site with `sc_rate = 1.0`, when a session is closed with ending total balance < 1.00 SC and open basis remains, then the app prompts to close the position
- Given a site with `sc_rate = 0.01`, when a session is closed with ending total balance < 100.00 SC and open basis remains, then the app prompts to close the position
- Given the user confirms a qualifying prompt and remaining basis > 0, then existing basis close behavior runs unchanged
- Given the user confirms a qualifying prompt and remaining basis = 0, then the existing zero-basis dormant close-marker behavior runs unchanged
- Given the user declines the prompt, then the session remains closed and no close marker / realized close row is created
- Given the user uses “End & Start New”, then no low-balance close prompt interrupts the continuation workflow

Test plan
Automated tests:
- UI/integration test for end-session low-balance prompt on a 1:1 site with remaining basis
- UI/integration test for end-session low-balance prompt on a non-1:1 site (e.g. `sc_rate = 0.01`)
- Regression test proving confirmed zero-basis prompt reuses dormant close-marker path
- Regression test proving declined prompt leaves session close intact without position close
- Regression test proving “End & Start New” skips the low-balance prompt
- Headless smoke coverage for touched UI flows

Manual verification:
- End a low-balance Modo session and confirm the follow-up close prompt appears
- Confirm yes/no behavior for both basis-bearing and zero-basis cases
- Confirm a later rebuy after confirmed close starts a fresh cycle in Unrealized

Area
UI

Notes
- This change likely requires updating `docs/PROJECT_SPEC.md`.
- This change likely requires adding/updating scenario-based tests.
- This change includes destructive actions (must add warnings/backup prompts).
