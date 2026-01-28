# CRUD Scenario Matrix (100 cases)

Temporary DB path: /var/folders/4l/s65vmp9d7fn6x1pgm6_ghm600000gn/T/sezzions_crud_qwrec4k5/crud_scenarios.db
Generated on: 2026-01-23

## Summary

- Total scenarios: 100
- Failures: 5
- Final Game Session P/L total: $600.00
- Final Unrealized P/L total: $-2530.71
- Final Realized P/L total: $30.94
- Counts: purchases=82, redemptions=40, sessions=20, realized=39, unrealized_positions=4

## Scenarios

| ID | Type | Status | Steps | Game Session P/L | Unrealized P/L | Realized P/L |
|---:|------|:------:|-------|-----------------:|--------------:|------------:|
| 001 | purchase_create | PASS | Create purchase $35.48 at 2026-01-02 10:07:00. | $0.00 | $0.00 | $0.00 |
| 002 | purchase_edit_notes | PASS | Create purchase then edit notes. | $0.00 | $0.00 | $0.00 |
| 003 | purchase_edit_amount | PASS | Create purchase then edit amount. | $0.00 | $-10.00 | $0.00 |
| 004 | purchase_delete | PASS | Create purchase then delete. | $0.00 | $-10.00 | $0.00 |
| 005 | redemption_fifo_create | PASS | Create purchase then FIFO redemption. | $0.00 | $60.56 | $0.00 |
| 006 | redemption_no_fifo | PASS | Create redemption without FIFO. | $0.00 | $60.56 | $0.00 |
| 007 | redemption_edit_reprocess | PASS | Create FIFO redemption then edit w/ reprocess. | $0.00 | $154.37 | $0.00 |
| 008 | redemption_delete | PASS | Create FIFO redemption then delete. | $0.00 | $154.37 | $0.00 |
| 009 | session_create_close | PASS | Create session and close it. | $20.00 | $118.72 | $0.00 |
| 010 | session_mid_events | PASS | Create two purchases, session, and FIFO redemption during session. | $60.00 | $-62.66 | $0.00 |
| 011 | purchase_create | PASS | Create purchase $35.05 at 2026-01-12 12:17:00. | $60.00 | $-62.66 | $0.00 |
| 012 | purchase_edit_notes | PASS | Create purchase then edit notes. | $60.00 | $-62.66 | $0.00 |
| 013 | purchase_edit_amount | PASS | Create purchase then edit amount. | $60.00 | $-72.66 | $0.00 |
| 014 | purchase_delete | PASS | Create purchase then delete. | $60.00 | $-72.66 | $0.00 |
| 015 | redemption_fifo_create | PASS | Create purchase then FIFO redemption. | $60.00 | $-77.66 | $0.00 |
| 016 | redemption_no_fifo | PASS | Create redemption without FIFO. | $60.00 | $-77.66 | $0.00 |
| 017 | redemption_edit_reprocess | PASS | Create FIFO redemption then edit w/ reprocess. | $60.00 | $16.21 | $0.00 |
| 018 | redemption_delete | PASS | Create FIFO redemption then delete. | $60.00 | $16.21 | $0.00 |
| 019 | session_create_close | PASS | Create session and close it. | $80.00 | $-356.69 | $0.00 |
| 020 | session_mid_events | PASS | Create two purchases, session, and FIFO redemption during session. | $120.00 | $-426.69 | $0.00 |
| 021 | purchase_create | PASS | Create purchase $35.78 at 2026-01-22 14:27:00. | $120.00 | $-462.47 | $0.00 |
| 022 | purchase_edit_notes | PASS | Create purchase then edit notes. | $120.00 | $-508.45 | $0.00 |
| 023 | purchase_edit_amount | PASS | Create purchase then edit amount. | $120.00 | $-573.74 | $0.00 |
| 024 | purchase_delete | PASS | Create purchase then delete. | $120.00 | $-573.74 | $0.00 |
| 025 | redemption_fifo_create | PASS | Create purchase then FIFO redemption. | $120.00 | $-578.74 | $0.00 |
| 026 | redemption_no_fifo | PASS | Create redemption without FIFO. | $120.00 | $-578.74 | $0.00 |
| 027 | redemption_edit_reprocess | PASS | Create FIFO redemption then edit w/ reprocess. | $120.00 | $-580.74 | $0.00 |
| 028 | redemption_delete | PASS | Create FIFO redemption then delete. | $120.00 | $-600.65 | $0.00 |
| 029 | session_create_close | PASS | Create session and close it. | $140.00 | $-600.65 | $0.00 |
| 030 | session_mid_events | PASS | Create two purchases, session, and FIFO redemption during session. | $180.00 | $-712.33 | $15.67 |
| 031 | purchase_create | PASS | Create purchase $35.10 at 2026-01-07 16:37:00. | $180.00 | $-747.43 | $15.67 |
| 032 | purchase_edit_notes | PASS | Create purchase then edit notes. | $180.00 | $-793.16 | $15.67 |
| 033 | purchase_edit_amount | FAIL |  | $180.00 | $-848.53 | $15.67 |
| 034 | purchase_delete | PASS | Create purchase then delete. | $180.00 | $-848.53 | $15.67 |
| 035 | redemption_fifo_create | PASS | Create purchase then FIFO redemption. | $180.00 | $-853.53 | $15.67 |
| 036 | redemption_no_fifo | PASS | Create redemption without FIFO. | $180.00 | $-853.53 | $15.67 |
| 037 | redemption_edit_reprocess | PASS | Create FIFO redemption then edit w/ reprocess. | $180.00 | $-855.53 | $15.67 |
| 038 | redemption_delete | PASS | Create FIFO redemption then delete. | $180.00 | $-961.43 | $15.67 |
| 039 | session_create_close | PASS | Create session and close it. | $200.00 | $-961.43 | $15.67 |
| 040 | session_mid_events | PASS | Create two purchases, session, and FIFO redemption during session. | $240.00 | $-1031.43 | $15.67 |
| 041 | purchase_create | PASS | Create purchase $35.26 at 2026-01-17 10:47:00. | $240.00 | $-1066.69 | $15.67 |
| 042 | purchase_edit_notes | PASS | Create purchase then edit notes. | $240.00 | $-1112.40 | $15.67 |
| 043 | purchase_edit_amount | PASS | Create purchase then edit amount. | $240.00 | $-1178.27 | $15.67 |
| 044 | purchase_delete | PASS | Create purchase then delete. | $240.00 | $-1178.27 | $15.67 |
| 045 | redemption_fifo_create | PASS | Create purchase then FIFO redemption. | $240.00 | $-1183.27 | $15.67 |
| 046 | redemption_no_fifo | PASS | Create redemption without FIFO. | $240.00 | $-1183.27 | $15.67 |
| 047 | redemption_edit_reprocess | PASS | Create FIFO redemption then edit w/ reprocess. | $240.00 | $-1185.27 | $15.67 |
| 048 | redemption_delete | PASS | Create FIFO redemption then delete. | $240.00 | $-1290.34 | $15.67 |
| 049 | session_create_close | PASS | Create session and close it. | $260.00 | $-1290.34 | $15.67 |
| 050 | session_mid_events | PASS | Create two purchases, session, and FIFO redemption during session. | $300.00 | $-1204.48 | $30.81 |
| 051 | purchase_create | PASS | Create purchase $35.15 at 2026-01-02 12:57:00. | $300.00 | $-1239.63 | $30.81 |
| 052 | purchase_edit_notes | PASS | Create purchase then edit notes. | $300.00 | $-1285.30 | $30.81 |
| 053 | purchase_edit_amount | FAIL |  | $300.00 | $-1340.43 | $30.81 |
| 054 | purchase_delete | FAIL | Create purchase then delete. | $300.00 | $-1340.43 | $50.73 |
| 055 | redemption_fifo_create | PASS | Create purchase then FIFO redemption. | $300.00 | $-1345.43 | $50.73 |
| 056 | redemption_no_fifo | PASS | Create redemption without FIFO. | $300.00 | $-1345.43 | $50.73 |
| 057 | redemption_edit_reprocess | PASS | Create FIFO redemption then edit w/ reprocess. | $300.00 | $-1347.43 | $50.73 |
| 058 | redemption_delete | PASS | Create FIFO redemption then delete. | $300.00 | $-1453.34 | $50.73 |
| 059 | session_create_close | PASS | Create session and close it. | $320.00 | $-1453.34 | $50.73 |
| 060 | session_mid_events | PASS | Create two purchases, session, and FIFO redemption during session. | $360.00 | $-1487.75 | $15.14 |
| 061 | purchase_create | PASS | Create purchase $35.05 at 2026-01-12 14:07:00. | $360.00 | $-1522.80 | $15.14 |
| 062 | purchase_edit_notes | PASS | Create purchase then edit notes. | $360.00 | $-1568.09 | $15.14 |
| 063 | purchase_edit_amount | PASS | Create purchase then edit amount. | $360.00 | $-1633.33 | $15.14 |
| 064 | purchase_delete | PASS | Create purchase then delete. | $360.00 | $-1633.33 | $15.14 |
| 065 | redemption_fifo_create | PASS | Create purchase then FIFO redemption. | $360.00 | $-1638.33 | $15.14 |
| 066 | redemption_no_fifo | PASS | Create redemption without FIFO. | $360.00 | $-1638.33 | $15.14 |
| 067 | redemption_edit_reprocess | PASS | Create FIFO redemption then edit w/ reprocess. | $360.00 | $-1640.33 | $15.14 |
| 068 | redemption_delete | PASS | Create FIFO redemption then delete. | $360.00 | $-1745.48 | $15.14 |
| 069 | session_create_close | PASS | Create session and close it. | $380.00 | $-1745.48 | $15.14 |
| 070 | session_mid_events | PASS | Create two purchases, session, and FIFO redemption during session. | $420.00 | $-1815.48 | $15.14 |
| 071 | purchase_create | PASS | Create purchase $35.34 at 2026-01-22 16:17:00. | $420.00 | $-1850.82 | $15.14 |
| 072 | purchase_edit_notes | PASS | Create purchase then edit notes. | $420.00 | $-1896.76 | $15.14 |
| 073 | purchase_edit_amount | PASS | Create purchase then edit amount. | $420.00 | $-1962.47 | $15.14 |
| 074 | purchase_delete | PASS | Create purchase then delete. | $420.00 | $-1962.47 | $15.14 |
| 075 | redemption_fifo_create | PASS | Create purchase then FIFO redemption. | $420.00 | $-1967.47 | $15.14 |
| 076 | redemption_no_fifo | PASS | Create redemption without FIFO. | $420.00 | $-1967.47 | $15.14 |
| 077 | redemption_edit_reprocess | PASS | Create FIFO redemption then edit w/ reprocess. | $420.00 | $-1969.47 | $15.14 |
| 078 | redemption_delete | PASS | Create FIFO redemption then delete. | $420.00 | $-1989.09 | $15.14 |
| 079 | session_create_close | PASS | Create session and close it. | $440.00 | $-1989.09 | $15.14 |
| 080 | session_mid_events | PASS | Create two purchases, session, and FIFO redemption during session. | $480.00 | $-1973.89 | $15.14 |
| 081 | purchase_create | PASS | Create purchase $35.04 at 2026-01-07 10:27:00. | $480.00 | $-2008.93 | $15.14 |
| 082 | purchase_edit_notes | PASS | Create purchase then edit notes. | $480.00 | $-2054.42 | $15.14 |
| 083 | purchase_edit_amount | FAIL |  | $480.00 | $-2109.56 | $15.14 |
| 084 | purchase_delete | FAIL | Create purchase then delete. | $480.00 | $-2175.20 | $15.14 |
| 085 | redemption_fifo_create | PASS | Create purchase then FIFO redemption. | $480.00 | $-2180.20 | $15.14 |
| 086 | redemption_no_fifo | PASS | Create redemption without FIFO. | $480.00 | $-2180.20 | $15.14 |
| 087 | redemption_edit_reprocess | PASS | Create FIFO redemption then edit w/ reprocess. | $480.00 | $-2182.20 | $15.14 |
| 088 | redemption_delete | PASS | Create FIFO redemption then delete. | $480.00 | $-2287.75 | $15.14 |
| 089 | session_create_close | PASS | Create session and close it. | $500.00 | $-2287.75 | $15.14 |
| 090 | session_mid_events | PASS | Create two purchases, session, and FIFO redemption during session. | $540.00 | $-2357.75 | $15.14 |
| 091 | purchase_create | PASS | Create purchase $35.43 at 2026-01-17 12:37:00. | $540.00 | $-2393.18 | $15.14 |
| 092 | purchase_edit_notes | PASS | Create purchase then edit notes. | $540.00 | $-2438.72 | $15.14 |
| 093 | purchase_edit_amount | PASS | Create purchase then edit amount. | $540.00 | $-2504.63 | $15.14 |
| 094 | purchase_delete | PASS | Create purchase then delete. | $540.00 | $-2504.63 | $15.14 |
| 095 | redemption_fifo_create | PASS | Create purchase then FIFO redemption. | $540.00 | $-2509.63 | $15.14 |
| 096 | redemption_no_fifo | PASS | Create redemption without FIFO. | $540.00 | $-2509.63 | $15.14 |
| 097 | redemption_edit_reprocess | PASS | Create FIFO redemption then edit w/ reprocess. | $540.00 | $-2511.63 | $15.14 |
| 098 | redemption_delete | PASS | Create FIFO redemption then delete. | $540.00 | $-2616.68 | $15.14 |
| 099 | session_create_close | PASS | Create session and close it. | $560.00 | $-2616.68 | $15.14 |
| 100 | session_mid_events | PASS | Create two purchases, session, and FIFO redemption during session. | $600.00 | $-2530.71 | $30.94 |

## Failures

- 033 (purchase_edit_amount): ValueError: Cannot change amount on a purchase that has been consumed. Consumed: $2.36
- 053 (purchase_edit_amount): ValueError: Cannot change amount on a purchase that has been consumed. Consumed: $55.13
- 054 (purchase_delete): ValueError: Cannot delete purchase that has been consumed. Consumed: $65.22
- 083 (purchase_edit_amount): ValueError: Cannot change amount on a purchase that has been consumed. Consumed: $55.14
- 084 (purchase_delete): ValueError: Cannot delete purchase that has been consumed. Consumed: $45.97

## Remedy Notes

- Review errors above and correct the underlying inputs or workflow.
- For consumed purchases, amount/date edits and deletion are blocked by design.
	- Remedy: reverse or delete downstream redemptions to restore remaining_amount, then edit/delete the purchase.
	- Alternatively, create an offsetting purchase or adjustment rather than altering the original amount.
- If errors are due to active sessions, ensure sessions are closed before creating another.
- If errors are due to guarded edits, use reprocess update paths or create new records.