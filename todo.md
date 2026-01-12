# TODO

## High Priority
- [ ] Finalize UI redesign in qt_app.py
- [ ] Remove or deprecate session2.py safely
- [ ] Finish remaining tab incorporations
- [X] Add a one-click "Recalculate Everything" action in qt_app.py to rebuild FIFO + derived data across the entire database
- [X] Add a feature to "Start a New Session" after a purchase, or is it best to keep these as manual inputs?
- [X] Implement the upload CSV functionality.  This should account for duplicate entries and prompt for adding them or excluding them.  It should NOT be a complete overwrite but a way to add entries.

## Medium Priority
- [ ] Add free-tier usage limits
- [ ] Add RTP calculation to Game Sessions based on wager and return
- [ ] What is the "method type" field in redemption methods used for?  Can we get rid of it?
- [ ] Where is "last four" of cards used?  Should we keep it?  It's not in any input forms
- [ ] Design license key system (no server)
- [X] Add database backup strategy
- [ ] Determine best way to link transactions to specific sessions (purchases & redemptions)
- [ ] A consolidated balance tracker per account & site similar to Unrealized tab but cleaner and more focused
- [X] Link cashback amounts to specific transactions
- [ ] Consolidated tax reporting (i.e. how much taxes you need to have set aside, and how much of each redemption needs to be set aside, based not on the money out->money in but based on session outcomes, which is why it's important we can link sessions to redemptions and purchases).  User needs to be able to specify tax withholding rate.
- [ ] Re-integrate the Audit Log
- [ ] Add a field for Redemption Fees, or just assume users will enter the amount they're actually going to get out?
- [ ] Allow different currencies and denominations on Purchases and Redemptions (Fortune Coins 1:100, USDC, Crypto, etc.).  Need assistance strategizing incorporation
- [X] How do we limit the scope of recalculation when making changes?  Is there a way to do it reliably and automatically?  When we have 10,000 rows, it's going to be a nightmare making changes if we have to update ALL associated sessions with every change.

## Low Priority / Ideas
- [ ] Export reports to CSV
- [X] Dark mode toggle
- [X] Settings screen cleanup
- [X] Add notes for Users/Sites/Cards/Redemption Methods/etc.
- [ ] Daily taxable P/L metric (hourly rate, etc.)
- [ ] Export/Backup to Google Sheets/Drive/etc. for Database and Reports, including automated/scheduled backups?
- [ ] Support ticket/bug submissions/error reporting
- [ ] Web and/or mobile platforms
- [ ] Change Game table to have an "Expected RTP" that the User inputs (currently it's the "RTP" column), and then an automatically calculated "Actual RTP" column that is derived from actual wager activity and output from the game as it's played on the app.  So whenever a User finishes a Session or updates a session with that game, automatically recompute the RTP and update that field for the game.  Need to do this in a way that doesn't require a complete recompute of the entire database worth of entries for that game though.  Presumably if the Wager & RTP are known previously, then if we have a new Wager amount and result from a new single session, we should be able to factor that in without a global database recompute, I think.  We should also add a button similar to in the Card dialog (cashback recalculate) that recalculates the game's actual RTP via a global database recalculation.
- [ ] Other worthwhile automation notifications ideas: outstanding redeems > 1 week.  "Remind me again in X days" feature?  Sites with redeemable balances but not redeemed > 1 week?
