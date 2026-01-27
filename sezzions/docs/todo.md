# Sezzions TODO

## CRITICAL Architecture Items
- [ ] **Implement ViewModels/DTOs for UI display data** - Currently UI layer has direct access to repositories (e.g., `facade.game_repo`) and performs data fetching. This violates separation of concerns and prevents proper multi-platform architecture. Service layer should return enriched ViewModels with all display data (game_name, game_type_name, etc.) so UI only displays, never fetches. This is essential for web/mobile portability.

## Active Items
- [ ] Setup Tools tab (import/export/backup/recalc)
- [ ] Legacy app's redeemable check isn't detecting a problem when I enter 0.42 SC on an expected 0.41 redeemable.  is there a threshhold?  It recognizes it if I put 0.92



## Completed Items
- [X] Scenario:  1 SC starting redeemable on Stake.  Buy in 2500 for 2506.25.  Gamble and end with 2500.89.  It's showing -0.11 loss because it's counting the 1 SC as part of the loss, but since I never session'd that 1 SC to begin with, it shouldn't be counted. (Fixed on the OOP app)
- [X] Prevent or warn from deleting sessions that have affiliated redemptions -> warn instead of blcok in case of data entry errors that the user is trying to fix.  Ensure recalculation (scoped or full) can fix the issues after the user has made changes.  We need to prevent lawless deletion of sessions when redemptions exist because it creates validation errors where Redemptions exist with unsessioned basis and could create tax reporting problems (user has redemptions but no sessions to justify the P/L).
- [ ] Prompt the user to back-up the database before deleting Sessions or items  that could cascade.
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