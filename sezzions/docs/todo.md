# Sezzions TODO

## Phase 4 UI Integration (TOOLS_IMPLEMENTATION_PLAN.md)
- [X] Task 1: Add transaction API to DatabaseManager (was already implemented)
- [X] Task 2: Create Qt background workers (RecalculationWorker + WorkerSignals)
- [X] Task 3: Create progress dialogs (ProgressDialog hierarchy)
- [X] Task 4: Wire Tools tab buttons (Recalculate Everything + scoped)
- [X] Task 5: Add post-import recalculation prompts (PostImportPromptDialog)
- [X] Task 6: End-to-end testing of Phase 4 UI integration

**Status:** 5/6 tasks complete, ready for testing. See `POST_IMPORT_RECALC_IMPLEMENTATION.md` for details.

## CRITICAL Architecture Items
- [ ] **Implement ViewModels/DTOs for UI display data** - Currently UI layer has direct access to repositories (e.g., `facade.game_repo`) and performs data fetching. This violates separation of concerns and prevents proper multi-platform architecture. Service layer should return enriched ViewModels with all display data (game_name, game_type_name, etc.) so UI only displays, never fetches. This is essential for web/mobile portability.

## Active Items
- [ ] Phase 5: Notification System (next after Phase 4 testing)
- [ ] Legacy app's redeemable check isn't detecting a problem when I enter 0.42 SC on an expected 0.41 redeemable.  is there a threshhold?  It recognizes it if I put 0.92
- [ ] Prompt the user to back-up the database before deleting Sessions or items that could cascade.
- [X] Delete Game and Game Type have issues with foreign keys.
- [ ] Session P/L looks accurate, but basis/consumption does not
- [ ] Get consistency between Starting SC and Post-Purchase SC as well as displaying it on the table.
- [ ] Purchase balance checks are showing off by the amount of the purchase on the new app.
- [ ] Finish updating the Tools tab using TOOLS_IMPLEMENTATION_PLAN.md - left off at Phase 4 manual UI testing.
- [ ] Edge case for editing purchases:
a Buy $200/205 205 starting SC Stake
b Buy $300/300 505 starting SC Stake
c Buy $100/100 605 starting SC Stake
If we edit purchase B and change it to $400/400 starting 605, then suddenly the data in Purchase C is not accurate.  Purchase C says 605 starting SC, but purchase B now has a starting SC of 605 -> meaning purchase C should be 705 now.

We get a warning when the amount differs from what's expected but should it be allowed?  Since starting SC is something we input manually and is "estimated" by the app based on that input, is it something we should control for?  Or is the warning acceptable and just leave it ot the user to enter accurate data?  The issue is what if it's a string of 10 purchases and we edit one in the middle?  How does that work out for starting balances?  Again, is it just soething we need to count on the user to reliably input and prompt/warn for?
- Edge case:
a Buy $200/205 205 starting SC Stake
b Buy $300/300 505 starting SC Stake
c Buy $100/100 605 starting SC Stake
- [ ] When submitting a redemption, next to the "Amount" field, show the total redeemable balance, and the total SC balance for the site/user pair as of the last purchase/sesssion/redemption/etc. (the most recenlty available balance) like "125.00 R / 150.00 T" with a "?" helper button to click on next to it explaining what they are. --> alternatively, add a realtime balance check like we have in Purchases/Sessions to give a "Go/No-Go" based on the redemption amount the user types in.
- [ ] Add a "?" helper button to explain what the "Processed" checkbox is on the redemption dialog (it's just an internal accounting flag with no impact on anything)
- [ ] Redemption methods can't have unique names.  Some might be the same, but they are assigned independently to Method Types and users so they should still be unique in that sense.  But multiple useres could have a "USAA Checking" account, so we need to allow that and account for it in ALL of our logic (CSV, CRUD, etc.).



## Completed Items
- [X] Scenario:  1 SC starting redeemable on Stake.  Buy in 2500 for 2506.25.  Gamble and end with 2500.89.  It's showing -0.11 loss because it's counting the 1 SC as part of the loss, but since I never session'd that 1 SC to begin with, it shouldn't be counted. (Fixed on the OOP app)
- [X] Prevent or warn from deleting sessions that have affiliated redemptions -> warn instead of blcok in case of data entry errors that the user is trying to fix.  Ensure recalculation (scoped or full) can fix the issues after the user has made changes.  We need to prevent lawless deletion of sessions when redemptions exist because it creates validation errors where Redemptions exist with unsessioned basis and could create tax reporting problems (user has redemptions but no sessions to justify the P/L).
- [X] Implement controls preventing Redemption of Unsessioned SC, prevent $0 redemptions.
- [X] Need to account for multi-day closed sessions on the day they close, not the day they start.
- [X] Add Site grouping to the Daily Sessions tab so when one site has multiple sessions in a day they are consolidated and expandable/collapsable
- [X] View Position in the Realized tab should be a mirror of the View Redemption dialog.
- [X] Multi-selection delete controls
- [X] Recover dormant SC on close-balance delete
- [X] Realized tab parity updates
- [X] Setup tab CSV export buttons
- [X] Fix Setup dialog button spacing
- [X] Redemption methods: no default type
- [X] Redemption methods: require user
- [X] Card cashback % field
- [X] Session+purchase timing conflict
- [X] Warn on partial redemption vs balance
- [X] Redemption delete/recalc parity
- [X] Implement legacy partial redemption warning
- [X] Implement scoped recalculation parity with debug output
- [X] Decide explicit linked-events model vs legacy parity
- [X] Ensure redemption delete parity (FIFO + realized unwind)
- [X] Normalize time handling on edits (legacy parity)
- [X] Full Realized tab parity port
- [X] Update the "View Redemption" dialog with our new style next.
- [X] View Position in Unrealized tab is next to update styles for.
- [X] Update the Add/Edit Expenses dialog
- [X] Cascading updates to Users/Sites/Cards/Method Types/Methods/Game Types/Games Add/Edit/View dialogs.  Will need to formalize the style we want and have Claude take license to do them all in teh same fashion.- [X] Update the Add/Edit Expenses dialog
- [X] Cascading updates to Users/Sites/Cards/Method Types/Methods/Game Types/Games Add/Edit/View dialogs.  Will need to formalize the style we want and have Claude take license to do them all in teh same fashion.