# TODO

## High Priority
- [ ] Finalize UI redesign in qt_app.py
- [ ] Remove or deprecate session2.py safely
- [ ] Finish remaining tab incorporations
- [ ] Add a one-click "Recalculate Everything" action in qt_app.py to rebuild FIFO + derived data across the entire database
- [ ] Why does deleting a Purchase appear to take so much time & compute power?

## Medium Priority
- [ ] Add free-tier usage limits
- [ ] Design license key system (no server)
- [ ] Add database backup strategy
- [ ] Determine best way to link transactions to specific sessions (purchases & redemptions)
- [ ] A consolidated balance tracker per account & site similar to Unrealized tab but cleaner and more focused
- [ ] Link cashback amounts to specific transactions
- [ ] Consolidated tax reporting (i.e. how much taxes you need to have set aside, and how much of each redemption needs to be set aside, based not on the money out->money in but based on session outcomes, which is why it's important we can link sessions to redemptions and purchases).  User needs to be able to specify tax withholding rate.
- [ ] Re-integrate the Audit Log
- [ ] Add a field for Redemption Fees, or just assume users will enter the amount they're actually going to get out?
- [ ] Allow different currencies and denominations on Purchases and Redemptions (Fortune Coins 1:100, USDC, Crypto, etc.).  Need assistance strategizing incorporation
- [ ] How do we limit the scope of recalculation when making changes?  Is there a way to do it reliably and automatically?  When we have 10,000 rows, it's going to be a nightmare making changes if we have to update ALL associated sessions with every change.

## Low Priority / Ideas
- [ ] Export reports to CSV
- [ ] Dark mode toggle
- [ ] Settings screen cleanup
- [ ] Add notes for Users/Sites/Cards/Redemption Methods/etc.
- [ ] Daily taxable P/L metric (hourly rate, etc.)
- [ ] Export/Backup to Google Sheets/Drive/etc. for Database and Reports, including automated/scheduled backups?
- [ ] Support ticket/bug submissions/error reporting
- [ ] Web and/or mobile platforms
