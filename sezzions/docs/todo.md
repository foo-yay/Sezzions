# Sezzions TODO

## Active Items
- [X] Multi-selection delete controls
- [X] Recover dormant SC on close-balance delete
- [X] Realized tab parity updates
- [X] Setup tab CSV export buttons
- [ ] Setup Tools tab (import/export/backup/recalc)
- [X] Fix Setup dialog button spacing
- [X] Redemption methods: no default type
- [X] Redemption methods: require user
- [X] Card cashback % field
- [X] Session+purchase timing conflict
- [X] Warn on partial redemption vs balance
- [X] Redemption delete/recalc parity

## Upcoming Items (documented only)
- [X] Implement legacy partial redemption warning
- [X] Implement scoped recalculation parity with debug output
- [X] Decide explicit linked-events model vs legacy parity
- [X] Ensure redemption delete parity (FIFO + realized unwind)
- [X] Normalize time handling on edits (legacy parity)
- [X] Full Realized tab parity port

##

- [ ] Need to account for multi-day closed sessions on the day they close, not the day they start.
- [ ] Scenario:  1 SC starting redeemable on Stake.  Buy in 2500 for 2506.25.  Gamble and end with 2500.89.  It's showing -0.11 loss because it's counting the 1 SC as part of the loss, but since I never session'd that 1 SC to begin with, it shouldn't be counted.