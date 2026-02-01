"""Integration tests for RecalculationService."""

import pytest
from contextlib import contextmanager
from decimal import Decimal

from services.recalculation_service import RecalculationService
from repositories.database import DatabaseManager


class DB:
    """Integration test database with full schema."""
    
    def __init__(self, db_path=':memory:'):
        self._db = DatabaseManager(db_path)
        self._connection = self._db._connection
    
    def fetch_all(self, query, params=None):
        return self._db.fetch_all(query, params or ())
    
    def fetch_one(self, query, params=None):
        return self._db.fetch_one(query, params or ())
    
    def execute(self, query, params=None):
        return self._db.execute(query, params or ())
    
    def executemany_no_commit(self, query, params_seq):
        return self._db.executemany_no_commit(query, params_seq)
    
    @contextmanager
    def transaction(self):
        with self._db.transaction():
            yield
    
    def populate_scenario_1(self):
        """
        Scenario 1: Simple lifecycle
        - User 1, Site 1
        - Purchase $100 on 2024-01-01
        - Redeem $50 on 2024-01-02
        - Redeem $30 on 2024-01-03
        """
        cursor = self._connection.cursor()
        cursor.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")
        cursor.execute("INSERT INTO sites (id, name) VALUES (1, 'CasinoX')")
        cursor.execute("""
            INSERT INTO purchases (user_id, site_id, amount, purchase_date, remaining_amount)
            VALUES (1, 1, 100.0, '2024-01-01', 100.0)
        """)
        cursor.execute("""
            INSERT INTO redemptions (user_id, site_id, amount, redemption_date, more_remaining)
            VALUES (1, 1, 50.0, '2024-01-02', 1)
        """)
        cursor.execute("""
            INSERT INTO redemptions (user_id, site_id, amount, redemption_date, more_remaining)
            VALUES (1, 1, 30.0, '2024-01-03', 1)
        """)
        self._connection.commit()
    
    def populate_scenario_2(self):
        """
        Scenario 2: Multi-user, multi-site
        - User 1, Site 1: $100 purchase, $50 redemption
        - User 1, Site 2: $75 purchase, $25 redemption
        - User 2, Site 1: $50 purchase, $20 redemption
        """
        cursor = self._connection.cursor()
        cursor.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")
        cursor.execute("INSERT INTO users (id, name) VALUES (2, 'Bob')")
        cursor.execute("INSERT INTO sites (id, name) VALUES (1, 'CasinoX')")
        cursor.execute("INSERT INTO sites (id, name) VALUES (2, 'LuckyY')")
        
        # User 1, Site 1
        cursor.execute("INSERT INTO purchases (user_id, site_id, amount, purchase_date, remaining_amount) VALUES (1, 1, 100.0, '2024-01-01', 100.0)")
        cursor.execute("INSERT INTO redemptions (user_id, site_id, amount, redemption_date, more_remaining) VALUES (1, 1, 50.0, '2024-01-02', 1)")
        
        # User 1, Site 2
        cursor.execute("INSERT INTO purchases (user_id, site_id, amount, purchase_date, remaining_amount) VALUES (1, 2, 75.0, '2024-01-03', 75.0)")
        cursor.execute("INSERT INTO redemptions (user_id, site_id, amount, redemption_date, more_remaining) VALUES (1, 2, 25.0, '2024-01-04', 1)")
        
        # User 2, Site 1
        cursor.execute("INSERT INTO purchases (user_id, site_id, amount, purchase_date, remaining_amount) VALUES (2, 1, 50.0, '2024-01-05', 50.0)")
        cursor.execute("INSERT INTO redemptions (user_id, site_id, amount, redemption_date, more_remaining) VALUES (2, 1, 20.0, '2024-01-06', 1)")
        
        self._connection.commit()
    
    def close(self):
        self._db.close()


@pytest.fixture
def test_db(tmp_path):
    """Create integration test database."""
    db_path = tmp_path / "test.db"
    db = DB(str(db_path))
    yield db
    db.close()


@pytest.fixture
def service(test_db):
    """Create recalculation service."""
    return RecalculationService(test_db)


class TestCompleteLifecycle:
    """Test complete FIFO rebuild lifecycle."""
    
    def test_simple_rebuild_workflow(self, test_db, service):
        """Test simple purchase → redemption workflow."""
        test_db.populate_scenario_1()
        
        # Rebuild
        result = service._rebuild_fifo_for_pair(1, 1)
        
        # Verify results
        assert result.pairs_processed == 1
        assert result.redemptions_processed == 2
        assert result.allocations_written == 2
        assert result.purchases_updated == 1
        
        # Verify database state
        cursor = test_db._connection.cursor()
        
        # Check allocations
        cursor.execute("SELECT COUNT(*) FROM redemption_allocations")
        assert cursor.fetchone()[0] == 2
        
        # Check realized transactions
        cursor.execute("SELECT * FROM realized_transactions ORDER BY redemption_date")
        realized = cursor.fetchall()
        assert len(realized) == 2
        
        # First redemption: $50 payout, $50 basis, $0 P/L
        assert float(realized[0]['payout']) == 50.0
        assert float(realized[0]['cost_basis']) == 50.0
        assert float(realized[0]['net_pl']) == 0.0
        
        # Second redemption: $30 payout, $30 basis, $0 P/L
        assert float(realized[1]['payout']) == 30.0
        assert float(realized[1]['cost_basis']) == 30.0
        assert float(realized[1]['net_pl']) == 0.0
        
        # Check remaining amount
        cursor.execute("SELECT remaining_amount FROM purchases")
        remaining = cursor.fetchone()
        assert float(remaining['remaining_amount']) == 20.0
    
    def test_rebuild_all_multi_user_multi_site(self, test_db, service):
        """Test rebuilding all pairs with multiple users and sites."""
        test_db.populate_scenario_2()
        
        # Rebuild all
        result = service.rebuild_all()
        
        # Should process 3 pairs
        assert result.pairs_processed == 3
        assert result.redemptions_processed == 3
        assert result.allocations_written == 3
        assert result.purchases_updated == 3
        
        # Verify all pairs have realized transactions
        cursor = test_db._connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM realized_transactions")
        assert cursor.fetchone()[0] == 3
        
        # Verify user 1, site 1
        cursor.execute("""
            SELECT * FROM realized_transactions 
            WHERE user_id = 1 AND site_id = 1
        """)
        rt = cursor.fetchone()
        assert float(rt['payout']) == 50.0
        assert float(rt['cost_basis']) == 50.0
        
        # Verify user 1, site 2
        cursor.execute("""
            SELECT * FROM realized_transactions 
            WHERE user_id = 1 AND site_id = 2
        """)
        rt = cursor.fetchone()
        assert float(rt['payout']) == 25.0
        assert float(rt['cost_basis']) == 25.0
        
        # Verify user 2, site 1
        cursor.execute("""
            SELECT * FROM realized_transactions 
            WHERE user_id = 2 AND site_id = 1
        """)
        rt = cursor.fetchone()
        assert float(rt['payout']) == 20.0
        assert float(rt['cost_basis']) == 20.0


class TestRebuildAfterImport:
    """Test rebuild_after_import functionality."""
    
    def test_rebuild_specific_user_site(self, test_db, service):
        """Test rebuilding only affected pairs after import."""
        test_db.populate_scenario_2()
        
        # Simulate import affecting only user 1, site 1
        result = service.rebuild_after_import(
            entity_type='purchases',
            user_ids=[1],
            site_ids=[1]
        )
        
        # Should only process 1 pair
        assert result.pairs_processed == 1
        assert result.redemptions_processed == 1
        
        # Verify only user 1, site 1 has realized transactions
        cursor = test_db._connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM realized_transactions WHERE user_id = 1 AND site_id = 1")
        assert cursor.fetchone()[0] == 1
        
        # Others should not be processed yet
        cursor.execute("SELECT COUNT(*) FROM realized_transactions WHERE user_id != 1 OR site_id != 1")
        assert cursor.fetchone()[0] == 0
    
    def test_rebuild_all_users_one_site(self, test_db, service):
        """Test rebuilding all users for one site."""
        test_db.populate_scenario_2()
        
        # Rebuild all users for site 1
        result = service.rebuild_after_import(
            entity_type='redemptions',
            site_ids=[1]
        )
        
        # Should process 2 pairs (user 1 + user 2 on site 1)
        assert result.pairs_processed == 2
        assert result.redemptions_processed == 2
        
        # Verify site 1 pairs processed
        cursor = test_db._connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM realized_transactions WHERE site_id = 1")
        assert cursor.fetchone()[0] == 2
        
        # Site 2 should not be processed
        cursor.execute("SELECT COUNT(*) FROM realized_transactions WHERE site_id = 2")
        assert cursor.fetchone()[0] == 0


class TestProgressTracking:
    """Test progress tracking with callbacks."""
    
    def test_progress_tracking_all_pairs(self, test_db, service):
        """Test progress callback during rebuild_fifo_all."""
        test_db.populate_scenario_2()
        
        progress_calls = []
        def track_progress(current, total, message):
            progress_calls.append((current, total, message))
        
        service.rebuild_all(progress_callback=track_progress)
        
        # Should have progress updates for 3 pairs
        assert len(progress_calls) >= 3
        
        # Check progress messages
        messages = [msg for _, _, msg in progress_calls]
        assert any("[1/3]" in msg for msg in messages)
        assert any("[2/3]" in msg for msg in messages)
        assert any("[3/3]" in msg for msg in messages)
    
    def test_progress_tracking_after_import(self, test_db, service):
        """Test progress callback during rebuild_after_import."""
        test_db.populate_scenario_2()
        
        progress_calls = []
        def track_progress(current, total, message):
            progress_calls.append((current, total, message))
        
        service.rebuild_after_import(
            entity_type='purchases',
            user_ids=[1],
            progress_callback=track_progress
        )
        
        # Should have progress for 2 pairs (user 1 on both sites)
        assert len(progress_calls) >= 2
        assert any("Recalculating after purchases import" in msg for _, _, msg in progress_calls)


class TestGetStats:
    """Test statistics gathering."""
    
    def test_get_stats_empty(self, test_db, service):
        """Test stats with no data."""
        stats = service.get_stats()
        
        assert stats['pairs'] == 0
        assert stats['purchases'] == 0
        assert stats['redemptions'] == 0
        assert stats['allocations'] == 0
        assert stats['realized_transactions'] == 0
    
    def test_get_stats_after_rebuild(self, test_db, service):
        """Test stats after rebuild."""
        test_db.populate_scenario_1()
        
        # Before rebuild
        stats_before = service.get_stats()
        assert stats_before['allocations'] == 0
        assert stats_before['realized_transactions'] == 0
        
        # Rebuild
        service._rebuild_fifo_for_pair(1, 1)
        
        # After rebuild
        stats_after = service.get_stats()
        assert stats_after['pairs'] == 1
        assert stats_after['purchases'] == 1
        assert stats_after['redemptions'] == 2
        assert stats_after['allocations'] == 2
        assert stats_after['realized_transactions'] == 2


class TestIdempotency:
    """Test that rebuilds are idempotent."""
    
    def test_multiple_rebuilds_same_result(self, test_db, service):
        """Test running rebuild multiple times produces same result."""
        test_db.populate_scenario_1()
        
        # First rebuild
        result1 = service._rebuild_fifo_for_pair(1, 1)
        cursor = test_db._connection.cursor()
        cursor.execute("SELECT * FROM realized_transactions ORDER BY id")
        realized1 = cursor.fetchall()
        cursor.execute("SELECT remaining_amount FROM purchases")
        remaining1 = cursor.fetchone()['remaining_amount']
        
        # Second rebuild
        result2 = service._rebuild_fifo_for_pair(1, 1)
        cursor.execute("SELECT * FROM realized_transactions ORDER BY id")
        realized2 = cursor.fetchall()
        cursor.execute("SELECT remaining_amount FROM purchases")
        remaining2 = cursor.fetchone()['remaining_amount']
        
        # Results should be identical
        assert result1.redemptions_processed == result2.redemptions_processed
        assert result1.allocations_written == result2.allocations_written
        assert len(realized1) == len(realized2)
        assert float(remaining1) == float(remaining2)
        
        # Values should match
        for r1, r2 in zip(realized1, realized2):
            assert float(r1['cost_basis']) == float(r2['cost_basis'])
            assert float(r1['payout']) == float(r2['payout'])
            assert float(r1['net_pl']) == float(r2['net_pl'])
