from decimal import Decimal

from ui.tabs.redemptions_tab import classify_redemption_confirmation


def test_partial_redeems_all_redeemable_but_total_remains_is_not_full_cashout_warning():
    # User scenario:
    # - Total balance exists (purchase recently added)
    # - Redeemable balance is lower (playthrough verified)
    # - Redemption amount matches redeemable, so it's "full redeemable" but still partial overall.
    decision = classify_redemption_confirmation(
        amount=Decimal("82.60"),
        expected_total_balance=Decimal("388.60"),
        expected_redeemable_balance=Decimal("82.60"),
        is_partial=True,
    )
    assert decision in {"ok", "info_redeems_all_redeemable_but_balance_remains"}
    assert decision != "warn_partial_selected_but_looks_like_full_cashout"


def test_partial_selected_but_amount_matches_total_balance_warns_full_cashout():
    decision = classify_redemption_confirmation(
        amount=Decimal("82.60"),
        expected_total_balance=Decimal("82.60"),
        expected_redeemable_balance=Decimal("82.60"),
        is_partial=True,
    )
    assert decision == "warn_partial_selected_but_looks_like_full_cashout"


def test_full_selected_but_amount_below_total_balance_warns_balance_remaining():
    decision = classify_redemption_confirmation(
        amount=Decimal("50.00"),
        expected_total_balance=Decimal("100.00"),
        expected_redeemable_balance=Decimal("50.00"),
        is_partial=False,
    )
    assert decision == "warn_full_selected_but_balance_remaining"
