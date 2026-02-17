-- Sezzions SQLite Schema (generated)
-- Generated from repositories/database.py via DatabaseManager(':memory:')
-- NOTE: This is schema-only (no data).

PRAGMA foreign_keys = ON;

-- TABLE: account_adjustments (table=account_adjustments)
CREATE TABLE account_adjustments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                site_id INTEGER NOT NULL,
                effective_date TEXT NOT NULL,
                effective_time TEXT DEFAULT '00:00:00',
                effective_entry_time_zone TEXT,
                type TEXT NOT NULL CHECK(type IN ('BASIS_USD_CORRECTION', 'BALANCE_CHECKPOINT_CORRECTION')),
                delta_basis_usd TEXT DEFAULT '0.00',
                checkpoint_total_sc TEXT DEFAULT '0.00',
                checkpoint_redeemable_sc TEXT DEFAULT '0.00',
                reason TEXT NOT NULL,
                notes TEXT,
                related_table TEXT,
                related_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                deleted_at TIMESTAMP,
                deleted_reason TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE
            );

-- TABLE: accounting_time_zone_history (table=accounting_time_zone_history)
CREATE TABLE accounting_time_zone_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                effective_utc_timestamp TEXT NOT NULL,
                accounting_time_zone TEXT NOT NULL,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

-- TABLE: audit_log (table=audit_log)
CREATE TABLE audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                table_name TEXT NOT NULL,
                record_id INTEGER,
                details TEXT,
                user_name TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            , old_data TEXT NULL, new_data TEXT NULL, group_id TEXT NULL, summary_data TEXT NULL);

-- TABLE: cards (table=cards)
CREATE TABLE cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                last_four TEXT,
                cashback_rate REAL DEFAULT 0.0,
                is_active INTEGER DEFAULT 1,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

-- TABLE: daily_date_tax (table=daily_date_tax)
CREATE TABLE daily_date_tax (
                session_date TEXT PRIMARY KEY,
                net_daily_pnl REAL DEFAULT 0.0,
                tax_withholding_rate_pct REAL,
                tax_withholding_is_custom INTEGER DEFAULT 0,
                tax_withholding_amount REAL,
                notes TEXT
            );

-- TABLE: daily_sessions (table=daily_sessions)
CREATE TABLE daily_sessions (
                session_date TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                total_other_income REAL DEFAULT 0.0,
                total_session_pnl REAL DEFAULT 0.0,
                net_daily_pnl REAL DEFAULT 0.0,
                status TEXT,
                num_game_sessions INTEGER DEFAULT 0,
                num_other_income_items INTEGER DEFAULT 0,
                PRIMARY KEY (session_date, user_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT
            );

-- TABLE: expenses (table=expenses)
CREATE TABLE "expenses" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    expense_date TEXT NOT NULL,
                    expense_time TEXT,
                    amount TEXT NOT NULL,
                    vendor TEXT NOT NULL,
                    description TEXT,
                    category TEXT,
                    user_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
                );

-- TABLE: game_rtp_aggregates (table=game_rtp_aggregates)
CREATE TABLE "game_rtp_aggregates" (
                        game_id INTEGER PRIMARY KEY REFERENCES games(id) ON DELETE CASCADE,
                        total_wager REAL DEFAULT 0,
                        total_delta REAL DEFAULT 0,
                        session_count INTEGER DEFAULT 0,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );

-- TABLE: game_session_event_links (table=game_session_event_links)
CREATE TABLE game_session_event_links (
                id INTEGER PRIMARY KEY,
                game_session_id INTEGER NOT NULL REFERENCES game_sessions(id) ON DELETE CASCADE,
                event_type TEXT NOT NULL CHECK(event_type IN ('purchase','redemption')),
                event_id INTEGER NOT NULL,
                relation TEXT NOT NULL CHECK(relation IN ('BEFORE','DURING','AFTER','MANUAL')),
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(game_session_id, event_type, event_id, relation)
            );

-- TABLE: game_sessions (table=game_sessions)
CREATE TABLE game_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                site_id INTEGER NOT NULL,
                game_id INTEGER,
                game_type_id INTEGER,
                session_date TEXT NOT NULL,
                session_time TEXT DEFAULT '00:00:00',
                start_entry_time_zone TEXT,
                end_date TEXT,
                end_time TEXT,
                end_entry_time_zone TEXT,
                starting_balance TEXT DEFAULT '0.00',
                ending_balance TEXT DEFAULT '0.00',
                starting_redeemable TEXT DEFAULT '0.00',
                ending_redeemable TEXT DEFAULT '0.00',
                wager_amount TEXT DEFAULT '0.00',
                rtp REAL,
                purchases_during TEXT DEFAULT '0.00',
                redemptions_during TEXT DEFAULT '0.00',
                expected_start_total TEXT,
                expected_start_redeemable TEXT,
                discoverable_sc TEXT,
                delta_total TEXT,
                delta_redeem TEXT,
                session_basis TEXT,
                basis_consumed TEXT,
                net_taxable_pl TEXT,
                status TEXT DEFAULT 'Active',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP, deleted_at TIMESTAMP NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE,
                FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
                FOREIGN KEY (game_type_id) REFERENCES game_types(id) ON DELETE SET NULL
            );

-- TABLE: game_types (table=game_types)
CREATE TABLE game_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                is_active INTEGER DEFAULT 1,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            );

-- TABLE: games (table=games)
CREATE TABLE games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                game_type_id INTEGER NOT NULL,
                rtp REAL,
                actual_rtp REAL DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (game_type_id) REFERENCES game_types(id) ON DELETE CASCADE
            );

-- TABLE: purchases (table=purchases)
CREATE TABLE purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                site_id INTEGER NOT NULL,
                amount TEXT NOT NULL,
                sc_received TEXT DEFAULT '0.00',
                starting_sc_balance TEXT DEFAULT '0.00',
                cashback_earned TEXT DEFAULT '0.00',
                cashback_is_manual INTEGER DEFAULT 0,
                purchase_date TEXT NOT NULL,
                purchase_time TEXT,
                purchase_entry_time_zone TEXT,
                card_id INTEGER,
                remaining_amount TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP, starting_redeemable_balance TEXT DEFAULT '0.00', deleted_at TIMESTAMP NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE,
                FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE SET NULL
            );

-- TABLE: realized_daily_notes (table=realized_daily_notes)
CREATE TABLE realized_daily_notes (
                session_date TEXT PRIMARY KEY,
                notes TEXT
            );

-- TABLE: realized_transactions (table=realized_transactions)
CREATE TABLE realized_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                redemption_date TEXT NOT NULL,
                site_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                redemption_id INTEGER NOT NULL,
                cost_basis TEXT NOT NULL,
                payout TEXT NOT NULL,
                net_pl TEXT NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE RESTRICT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
                FOREIGN KEY (redemption_id) REFERENCES redemptions(id) ON DELETE CASCADE
            );

-- TABLE: redemption_allocations (table=redemption_allocations)
CREATE TABLE redemption_allocations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                redemption_id INTEGER NOT NULL,
                purchase_id INTEGER NOT NULL,
                allocated_amount TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (redemption_id) REFERENCES redemptions(id) ON DELETE CASCADE,
                FOREIGN KEY (purchase_id) REFERENCES purchases(id) ON DELETE CASCADE
            );

-- TABLE: redemption_method_types (table=redemption_method_types)
CREATE TABLE redemption_method_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                is_active INTEGER DEFAULT 1,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            );

-- TABLE: redemption_methods (table=redemption_methods)
CREATE TABLE redemption_methods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                method_type TEXT,
                user_id INTEGER,
                is_active INTEGER DEFAULT 1,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            );

-- TABLE: redemptions (table=redemptions)
CREATE TABLE redemptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                site_id INTEGER NOT NULL,
                amount TEXT NOT NULL,
                fees TEXT DEFAULT '0.00',
                redemption_date TEXT NOT NULL,
                redemption_time TEXT DEFAULT '00:00:00',
                redemption_entry_time_zone TEXT,
                redemption_method_id INTEGER,
                is_free_sc INTEGER DEFAULT 0,
                receipt_date TEXT,
                processed INTEGER DEFAULT 0,
                more_remaining INTEGER DEFAULT 0,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP, deleted_at TIMESTAMP NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE,
                FOREIGN KEY (redemption_method_id) REFERENCES redemption_methods(id) ON DELETE SET NULL
            );

-- TABLE: schema_version (table=schema_version)
CREATE TABLE schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

-- TABLE: settings (table=settings)
CREATE TABLE settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );

-- TABLE: sites (table=sites)
CREATE TABLE sites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                url TEXT,
                sc_rate REAL DEFAULT 1.0,
                is_active INTEGER DEFAULT 1,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            );

-- TABLE: unrealized_positions (table=unrealized_positions)
CREATE TABLE unrealized_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                UNIQUE(site_id, user_id),
                FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

-- TABLE: users (table=users)
CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                email TEXT,
                is_active INTEGER DEFAULT 1,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            );

-- INDEX: idx_accounting_tz_effective (table=accounting_time_zone_history)
CREATE INDEX idx_accounting_tz_effective ON accounting_time_zone_history(effective_utc_timestamp);

-- INDEX: idx_adjustments_date (table=account_adjustments)
CREATE INDEX idx_adjustments_date ON account_adjustments(effective_date, effective_time);

-- INDEX: idx_adjustments_deleted (table=account_adjustments)
CREATE INDEX idx_adjustments_deleted ON account_adjustments(deleted_at);

-- INDEX: idx_adjustments_type (table=account_adjustments)
CREATE INDEX idx_adjustments_type ON account_adjustments(type);

-- INDEX: idx_adjustments_user_site (table=account_adjustments)
CREATE INDEX idx_adjustments_user_site ON account_adjustments(user_id, site_id);

-- INDEX: idx_allocations_purchase (table=redemption_allocations)
CREATE INDEX idx_allocations_purchase ON redemption_allocations(purchase_id);

-- INDEX: idx_allocations_redemption (table=redemption_allocations)
CREATE INDEX idx_allocations_redemption ON redemption_allocations(redemption_id);

-- INDEX: idx_audit_group (table=audit_log)
CREATE INDEX idx_audit_group ON audit_log(group_id);

-- INDEX: idx_audit_table (table=audit_log)
CREATE INDEX idx_audit_table ON audit_log(table_name);

-- INDEX: idx_audit_timestamp (table=audit_log)
CREATE INDEX idx_audit_timestamp ON audit_log(timestamp);

-- INDEX: idx_cards_active (table=cards)
CREATE INDEX idx_cards_active ON cards(is_active);

-- INDEX: idx_cards_user (table=cards)
CREATE INDEX idx_cards_user ON cards(user_id);

-- INDEX: idx_gsel_event (table=game_session_event_links)
CREATE INDEX idx_gsel_event ON game_session_event_links(event_type, event_id);

-- INDEX: idx_gsel_session (table=game_session_event_links)
CREATE INDEX idx_gsel_session ON game_session_event_links(game_session_id);

-- INDEX: idx_purchases_date (table=purchases)
CREATE INDEX idx_purchases_date ON purchases(purchase_date, purchase_time);

-- INDEX: idx_purchases_deleted (table=purchases)
CREATE INDEX idx_purchases_deleted ON purchases(deleted_at);

-- INDEX: idx_purchases_remaining (table=purchases)
CREATE INDEX idx_purchases_remaining ON purchases(remaining_amount);

-- INDEX: idx_purchases_site_user (table=purchases)
CREATE INDEX idx_purchases_site_user ON purchases(site_id, user_id);

-- INDEX: idx_realized_date (table=realized_transactions)
CREATE INDEX idx_realized_date ON realized_transactions(redemption_date);

-- INDEX: idx_realized_redemption (table=realized_transactions)
CREATE INDEX idx_realized_redemption ON realized_transactions(redemption_id);

-- INDEX: idx_realized_site_user (table=realized_transactions)
CREATE INDEX idx_realized_site_user ON realized_transactions(site_id, user_id);

-- INDEX: idx_redemptions_date (table=redemptions)
CREATE INDEX idx_redemptions_date ON redemptions(redemption_date, redemption_time);

-- INDEX: idx_redemptions_deleted (table=redemptions)
CREATE INDEX idx_redemptions_deleted ON redemptions(deleted_at);

-- INDEX: idx_redemptions_site_user (table=redemptions)
CREATE INDEX idx_redemptions_site_user ON redemptions(site_id, user_id);

-- INDEX: idx_sessions_date (table=game_sessions)
CREATE INDEX idx_sessions_date ON game_sessions(session_date, session_time);

-- INDEX: idx_sessions_deleted (table=game_sessions)
CREATE INDEX idx_sessions_deleted ON game_sessions(deleted_at);

-- INDEX: idx_sessions_site_user (table=game_sessions)
CREATE INDEX idx_sessions_site_user ON game_sessions(site_id, user_id);

-- INDEX: idx_sites_active (table=sites)
CREATE INDEX idx_sites_active ON sites(is_active);

-- INDEX: idx_users_active (table=users)
CREATE INDEX idx_users_active ON users(is_active);
