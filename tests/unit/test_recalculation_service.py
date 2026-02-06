"""Unit tests for RecalculationService."""

import pytest
from decimal import Decimal

from services.recalculation_service import RecalculationService, RebuildResult
from repositories.database import DatabaseManager


@pytest.fixture
def test_db():
    """Create test database."""
    db = DatabaseManager(':memory:')
    
    # Add test data
    cursor = db._connection.cursor()
    cursor.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")
    cursor.execute("INSERT INTO users (id, name) VALUES (2, 'Bob')")
    cursor.execute("INSERT INTO sites (id, name) VALUES (1, 'CasinoX')")
    cursor.execute("INSERT INTO sites (id, name) VALUES (2, 'LuckyY')")
    db._connection.commit()
    
    yield db
    db.close()


@pytest.fixture
def service(test_db):
    """Create recalculation service."""
    return RecalculationService(test_db)


class TestIterPairs:
    """Test pair iteration."""
    
    def test_iter_pairs_empty(self, service):
        """Test with no data."""
        pairs = service.iter_pairs()
        assert pairs == []
    
    def test_iter_pairs_from_purchases(self, test_db, service):
        """Test pairs from purchases."""
        cursor = test_db._connection.cursor()
        cursor.execute("INSERT INTO purchases (user_id, site_id, amount, purchase_date, remaining_amount) VALUES (1, 1, 100.0, '2024-01-01', 100.0)")
        test_db._connection.commit()
        
        pairs = service.iter_pairs()
        assert (1, 1) in pairs
    
    def test_iter_pairs_from_redemptions(self, test_db, service):
        """Test pairs from redemptions."""
        cursor = test_db._connection.cursor()
        cursor.execute("INSERT INTO redemptions (user_id, site_id, amount, redemption_date) VALUES (2, 1, 50.0, '2024-01-02')")
        test_db._connection.commit()
        
        pairs = service.iter_pairs()
        assert (2, 1) in pairs

    def test_iter_pairs_from_account_adjustments(self, test_db, service):
        """Test pairs from account_adjustments (non-deleted only)."""
        cursor = test_db._connection.cursor()
        cursor.execute(
            """
            INSERT INTO account_adjustments (
                user_id, site_id, effective_date, effective_time, type, reason,
                delta_basis_usd, checkpoint_total_sc, checkpoint_redeemable_sc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (1, 2, "2024-01-01", "00:00:00", "BASIS_USD_CORRECTION", "test", "1.00", "0.00", "0.00"),
        )
        test_db._connection.commit()

        pairs = service.iter_pairs()
        assert (1, 2) in pairs
    
    def test_iter_pairs_multiple(self, test_db, service):
        """Test multiple pairs."""
        cursor = test_db._connection.cursor()
        cursor.execute("INSERT INTO purchases (user_id, site_id, amount, purchase_date, remaining_amount) VALUES (1, 1, 100.0, '2024-01-01', 100.0)")
        cursor.execute("INSERT INTO purchases (user_id, site_id, amount, purchase_date, remaining_amount) VALUES (2, 2, 50.0, '2024-01-02', 50.0)")
        cursor.execute("INSERT INTO redemptions (user_id, site_id, amount, redemption_date) VALUES (1, 2, 25.0, '2024-01-03')")
        test_db._connection.commit()
        
        pairs = service.iter_pairs()
        assert len(pairs) == 3
        assert (1, 1) in pairs
        assert (2, 2) in pairs
        assert (1, 2) in pairs


class TestRebuildFIFOForPair:
    """Test FIFO rebuild for single pair."""
    
    def test_simple_purchase_redemption(self, test_db, service):
        """Test simple purchase followed by redemption."""
        cursor = test_db._connection.cursor()
        
        # Purchase $100
        cursor.execute("""
            INSERT INTO purchases (user_id, site_id, amount, purchase_date, remaining_amount)
            VALUES (1, 1, 100.0, '2024-01-01', 100.0)
        """)
        purchase_id = cursor.lastrowid
        
        # Redeem $50
        cursor.execute("""
            INSERT INTO redemptions (user_id, site_id, amount, redemption_date, more_remaining)
            VALUES (1, 1, 50.0, '2024-01-02', 1)
        """)
        test_db._connection.commit()
        
        # Rebuild
        result = service._rebuild_fifo_for_pair(1, 1)
        
        assert result.pairs_processed == 1
        assert result.redemptions_processed == 1
        assert result.allocations_written == 1
        assert result.purchases_updated == 1
        
        # Verify allocation
        cursor.execute("SELECT * FROM redemption_allocations")
        allocs = cursor.fetchall()
        assert len(allocs) == 1
        assert allocs[0]['purchase_id'] == purchase_id
        assert float(allocs[0]['allocated_amount']) == 50.0
        
        # Verify realized transaction
        cursor.execute("SELECT * FROM realized_transactions")
        realized = cursor.fetchall()
        assert len(realized) == 1
        assert float(realized[0]['cost_basis']) == 50.0
        assert float(realized[0]['payout']) == 50.0
        assert float(realized[0]['net_pl']) == 0.0
        
        # Verify remaining amount updated
        cursor.execute("SELECT remaining_amount FROM purchases WHERE id = ?", (purchase_id,))
        remaining = cursor.fetchone()
        assert float(remaining['remaining_amount']) == 50.0
    
    def test_multiple_purchases_fifo_order(self, test_db, service):
        """Test FIFO allocates oldest first."""
        cursor = test_db._connection.cursor()
        
        # Two purchases
        cursor.execute("INSERT INTO purchases (user_id, site_id, amount, purchase_date, remaining_amount) VALUES (1, 1, 100.0, '2024-01-01', 100.0)")
        purchase1_id = cursor.lastrowid
        cursor.execute("INSERT INTO purchases (user_id, site_id, amount, purchase_date, remaining_amount) VALUES (1, 1, 75.0, '2024-01-03', 75.0)")
        purchase2_id = cursor.lastrowid
        
        # Redeem $120 (should allocate $100 from first, $20 from second)
        cursor.execute("INSERT INTO redemptions (user_id, site_id, amount, redemption_date, more_remaining) VALUES (1, 1, 120.0, '2024-01-05', 1)")
        test_db._connection.commit()
        
        # Rebuild
        result = service._rebuild_fifo_for_pair(1, 1)
        
        assert result.allocations_written == 2
        
        # Verify allocations
        cursor.execute("SELECT * FROM redemption_allocations ORDER BY purchase_id ASC")
        allocs = cursor.fetchall()
        assert len(allocs) == 2
        assert allocs[0]['purchase_id'] == purchase1_id
        assert float(allocs[0]['allocated_amount']) == 100.0
        assert allocs[1]['purchase_id'] == purchase2_id
        assert float(allocs[1]['allocated_amount']) == 20.0
        
        # Verify remaining amounts
        cursor.execute("SELECT remaining_amount FROM purchases WHERE id = ?", (purchase1_id,))
        assert float(cursor.fetchone()['remaining_amount']) == 0.0
        cursor.execute("SELECT remaining_amount FROM purchases WHERE id = ?", (purchase2_id,))
        assert float(cursor.fetchone()['remaining_amount']) == 55.0
    
    def test_free_sc_redemption(self, test_db, service):
        """Test free SC redemptions don't allocate cost basis."""
        cursor = test_db._connection.cursor()
        
        cursor.execute("INSERT INTO purchases (user_id, site_id, amount, purchase_date, remaining_amount) VALUES (1, 1, 100.0, '2024-01-01', 100.0)")
        cursor.execute("INSERT INTO redemptions (user_id, site_id, amount, redemption_date, is_free_sc, more_remaining) VALUES (1, 1, 50.0, '2024-01-02', 1, 1)")
        test_db._connection.commit()
        
        result = service._rebuild_fifo_for_pair(1, 1)
        
        # No allocations for free SC
        assert result.allocations_written == 0
        
        # Realized transaction shows all profit
        cursor.execute("SELECT * FROM realized_transactions")
        realized = cursor.fetchone()
        assert float(realized['cost_basis']) == 0.0
        assert float(realized['payout']) == 50.0
        assert float(realized['net_pl']) == 50.0
        
        # Purchase remaining unchanged
        cursor.execute("SELECT remaining_amount FROM purchases")
        assert float(cursor.fetchone()['remaining_amount']) == 100.0
    
    def test_zero_payout_with_loss_note(self, test_db, service):
        """Test zero payout redemption with Net Loss note."""
        cursor = test_db._connection.cursor()
        
        cursor.execute("INSERT INTO purchases (user_id, site_id, amount, purchase_date, remaining_amount) VALUES (1, 1, 100.0, '2024-01-01', 100.0)")
        cursor.execute("""
            INSERT INTO redemptions (user_id, site_id, amount, redemption_date, notes)
            VALUES (1, 1, 0.0, '2024-01-02', 'Session closed. Net Loss: $75.50')
        """)
        test_db._connection.commit()
        
        result = service._rebuild_fifo_for_pair(1, 1)
        
        # No allocations for zero payout
        assert result.allocations_written == 0
        
        # Realized transaction shows loss
        cursor.execute("SELECT * FROM realized_transactions")
        realized = cursor.fetchone()
        assert float(realized['cost_basis']) == 75.50
        assert float(realized['payout']) == 0.0
        assert float(realized['net_pl']) == -75.50


class TestRebuildFIFOAll:
    """Test rebuilding FIFO for all pairs."""
    
    def test_rebuild_all_multiple_pairs(self, test_db, service):
        """Test rebuilding multiple pairs."""
        cursor = test_db._connection.cursor()
        
        # User 1, Site 1
        cursor.execute("INSERT INTO purchases (user_id, site_id, amount, purchase_date, remaining_amount) VALUES (1, 1, 100.0, '2024-01-01', 100.0)")
        cursor.execute("INSERT INTO redemptions (user_id, site_id, amount, redemption_date, more_remaining) VALUES (1, 1, 50.0, '2024-01-02', 1)")
        
        # User 2, Site 1
        cursor.execute("INSERT INTO purchases (user_id, site_id, amount, purchase_date, remaining_amount) VALUES (2, 1, 75.0, '2024-01-03', 75.0)")
        cursor.execute("INSERT INTO redemptions (user_id, site_id, amount, redemption_date, more_remaining) VALUES (2, 1, 25.0, '2024-01-04', 1)")
        
        test_db._connection.commit()
        
        # Rebuild all
        result = service.rebuild_all()
        
        assert result.pairs_processed == 2
        assert result.redemptions_processed == 2
        assert result.allocations_written == 2
        assert result.purchases_updated == 2
        
        # Verify both pairs processed
        cursor.execute("SELECT COUNT(*) FROM realized_transactions")
        assert cursor.fetchone()[0] == 2


class TestProgressTracking:
    """Test progress callbacks."""
    
    def test_progress_callback_single_pair(self, test_db, service):
        """Test progress callback for single pair."""
        cursor = test_db._connection.cursor()
        cursor.execute("INSERT INTO purchases (user_id, site_id, amount, purchase_date, remaining_amount) VALUES (1, 1, 100.0, '2024-01-01', 100.0)")
        cursor.execute("INSERT INTO redemptions (user_id, site_id, amount, redemption_date, more_remaining) VALUES (1, 1, 50.0, '2024-01-02', 1)")
        test_db._connection.commit()
        
        progress_calls = []
        def track_progress(current, total, message):
            progress_calls.append((current, total, message))
        
        service._rebuild_fifo_for_pair(1, 1, progress_callback=track_progress)
        
        assert len(progress_calls) == 2
        assert progress_calls[0] == (0, 1, "Rebuilding FIFO for user 1, site 1")
        assert progress_calls[1] == (1, 1, "Completed FIFO rebuild for user 1, site 1")
    
    def test_progress_callback_all_pairs(self, test_db, service):
        """Test progress callback for all pairs."""
        cursor = test_db._connection.cursor()
        cursor.execute("INSERT INTO purchases (user_id, site_id, amount, purchase_date, remaining_amount) VALUES (1, 1, 100.0, '2024-01-01', 100.0)")
        cursor.execute("INSERT INTO purchases (user_id, site_id, amount, purchase_date, remaining_amount) VALUES (2, 1, 50.0, '2024-01-02', 50.0)")
        test_db._connection.commit()
        
        progress_calls = []
        def track_progress(current, total, message):
            progress_calls.append((current, total, message))
        
        service.rebuild_all(progress_callback=track_progress)
        
        # Should have progress updates for both pairs
        assert len(progress_calls) >= 2
        messages = [msg for _, _, msg in progress_calls]
        assert any("[1/2]" in msg for msg in messages)
        assert any("[2/2]" in msg for msg in messages)
