#!/usr/bin/env python3
"""
Session - Social Casino Tracker
Main Application

Run this file: python3 casino_main_app.py

Required files in same folder:
- database.py
- business_logic.py
- gui_tabs.py
- table_helpers.py
- casino_main_app.py (this file)

CRITICAL DATA INTEGRITY FIXES (Dec 19, 2025):
-----------------------------------------------
The following fixes prevent data corruption during edit/delete operations:

FIX 1.1 (save_purchase): Block site/user changes if purchase partially consumed
  - Prevents orphaning redemptions when changing purchase site/user
  - Shows clear error with consumed amount

FIX 1.2 (save_purchase): Properly update session totals on ALL purchase edits
  - Handles site/user changes by moving purchase between sessions
  - Handles amount changes by adjusting session total_buyin
  - Prevents session total corruption

FIX 1.3 (save_redemption): Update site_session_id when editing redemptions
  - Ensures redemption always points to correct session
  - Prevents orphaned session references

FIX 1.4 (save_redemption): Update new session totals when editing
  - When redemption moves to new session, updates that session's total_redeemed
  - Prevents session totals from becoming incorrect

FIX 1.5 (delete_purchase): Protect session deletion from orphaning redemptions
  - Only deletes session if: no buyin, no redeemed amount, AND no redemption records
  - Prevents catastrophic orphaning of redemption data
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date

# Import modules
from database import Database
from business_logic import FIFOCalculator, SessionManager
from gui_tabs import (parse_date, build_purchases_tab, build_redemptions_tab, 
                      build_game_sessions_tab, build_daily_tax_tab,
                      build_unrealized_positions_tab, build_setup_tab)


def validate_currency(value_str):
    """
    Validate and normalize currency input.
    Accepts: 100, 100.5, 100.50
    Auto-converts: 100 -> 100.00, 100.5 -> 100.50
    Returns: (True, 100.00) or (False, error_message)
    """
    value_str = str(value_str).strip()
    
    if not value_str:
        return False, "Amount cannot be empty"
    
    try:
        value = float(value_str)
        
        if value < 0:
            return False, "Amount cannot be negative"
        
        # Check decimal places (reject 3+ decimal places)
        decimal_str = str(value)
        if '.' in decimal_str:
            decimal_places = len(decimal_str.split('.')[1])
            # Handle floating point representation (e.g., 100.5 might be 100.50000001)
            if decimal_places > 2 and not decimal_str.split('.')[1].rstrip('0')[:2] == decimal_str.split('.')[1].rstrip('0'):
                if len(decimal_str.split('.')[1].rstrip('0')) > 2:
                    return False, "Amount cannot have more than 2 decimal places (e.g., use 100.50 not 100.505)"
        
        # Round to 2 decimal places and return
        normalized = round(value, 2)
        return True, normalized
        
    except ValueError:
        return False, "Please enter a valid number"




def _rowv(row, key, default=None):
    """Safe getter for sqlite3.Row or dict-like objects."""
    try:
        if row is None:
            return default
        # sqlite3.Row supports keys()
        if hasattr(row, 'keys') and key not in row.keys():
            return default
        val = row[key]
        return default if val is None else val
    except Exception:
        return default
class CasinoApp:
    """Main casino accounting application"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Session - Social Casino Tracker")
        self.root.geometry("1400x900")
        
        # Initialize backend
        self.db = Database()
        self.fifo_calc = FIFOCalculator(self.db)
        self.session_mgr = SessionManager(self.db, self.fifo_calc)
        
        # Auto-backup on startup
        self.auto_backup()
        
        self.create_ui()
    
    def create_ui(self):
        """Create user interface"""
        # Menu bar
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Backup Database", command=self.backup_database)
        file_menu.add_command(label="Restore from Backup", command=self.restore_database)
        file_menu.add_separator()
        file_menu.add_command(label="View Audit Log", command=self.view_audit_log)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Global P/L stats bar - redesigned
        stats_frame = ttk.Frame(self.root, relief='sunken', borderwidth=1)
        stats_frame.pack(fill='x', padx=5, pady=(5, 0))
        
        # Filter row 1: Date range
        filter_row1 = ttk.Frame(stats_frame)
        filter_row1.pack(fill='x', padx=10, pady=(5, 2))
        
        ttk.Label(filter_row1, text="Stats Period:", font=('Arial', 9, 'bold')).pack(side='left', padx=(0, 10))
        
        # Date range inputs
        ttk.Label(filter_row1, text="From:").pack(side='left', padx=(0, 5))
        self.stats_filter_start = ttk.Entry(filter_row1, width=12)
        self.stats_filter_start.pack(side='left')
        
        def pick_stats_filter_start():
            try:
                from tkcalendar import Calendar
                top = tk.Toplevel(self.root)
                top.title("Select Start Date")
                top.geometry("300x300")
                cal = Calendar(top, selectmode='day', date_pattern='y-mm-dd')
                cal.pack(pady=20)
                def select():
                    self.stats_filter_start.delete(0, tk.END)
                    self.stats_filter_start.insert(0, cal.get_date())
                    top.destroy()
                ttk.Button(top, text="Select", command=select).pack(pady=10)
                ttk.Button(top, text="Cancel", command=top.destroy).pack()
            except ImportError:
                pass
        
        ttk.Button(filter_row1, text="📅", width=3, command=pick_stats_filter_start).pack(side='left', padx=2)
        
        ttk.Label(filter_row1, text="To:").pack(side='left', padx=(10, 5))
        self.stats_filter_end = ttk.Entry(filter_row1, width=12)
        self.stats_filter_end.pack(side='left')
        
        def pick_stats_filter_end():
            try:
                from tkcalendar import Calendar
                top = tk.Toplevel(self.root)
                top.title("Select End Date")
                top.geometry("300x300")
                cal = Calendar(top, selectmode='day', date_pattern='y-mm-dd')
                cal.pack(pady=20)
                def select():
                    self.stats_filter_end.delete(0, tk.END)
                    self.stats_filter_end.insert(0, cal.get_date())
                    top.destroy()
                ttk.Button(top, text="Select", command=select).pack(pady=10)
                ttk.Button(top, text="Cancel", command=top.destroy).pack()
            except ImportError:
                pass
        
        ttk.Button(filter_row1, text="📅", width=3, command=pick_stats_filter_end).pack(side='left', padx=(2, 10))
        
        # Quick filter buttons
        ttk.Button(filter_row1, text="Last 30 Days", 
                  command=lambda: self._set_stats_filter_last_n_days(30), width=12).pack(side='left', padx=2)
        ttk.Button(filter_row1, text="This Month", 
                  command=self._set_stats_filter_this_month, width=12).pack(side='left', padx=2)
        ttk.Button(filter_row1, text="This Year", 
                  command=self._set_stats_filter_this_year, width=12).pack(side='left', padx=2)
        ttk.Button(filter_row1, text="All Time", 
                  command=self._set_stats_filter_all_time, width=12).pack(side='left', padx=2)
        
        # Filter row 2: Site and User
        filter_row2 = ttk.Frame(stats_frame)
        filter_row2.pack(fill='x', padx=10, pady=(2, 2))
        
        ttk.Label(filter_row2, text="Site:", font=('Arial', 9, 'bold')).pack(side='left', padx=(0, 5))
        self.stats_filter_site = ttk.Combobox(filter_row2, width=20, state='readonly')
        self.stats_filter_site.pack(side='left', padx=(0, 15))
        
        ttk.Label(filter_row2, text="User:", font=('Arial', 9, 'bold')).pack(side='left', padx=(0, 5))
        self.stats_filter_user = ttk.Combobox(filter_row2, width=20, state='readonly')
        self.stats_filter_user.pack(side='left', padx=(0, 15))
        
        ttk.Button(filter_row2, text="Apply Filters", 
                  command=self.refresh_global_stats, width=15).pack(side='left', padx=5)
        ttk.Button(filter_row2, text="Clear All", 
                  command=lambda: (
                      self.stats_filter_start.delete(0, tk.END),
                      self.stats_filter_end.delete(0, tk.END),
                      self.stats_filter_site.set(''),
                      self.stats_filter_user.set(''),
                      self.refresh_global_stats()
                  ), width=15).pack(side='left', padx=5)
        
        # Display label showing current period
        self.stats_period_label = ttk.Label(filter_row2, text="", font=('Arial', 8, 'italic'), foreground='gray')
        self.stats_period_label.pack(side='left', padx=(10, 0))
        
        # Populate site and user filters
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Get all sites
        c.execute("SELECT name FROM sites ORDER BY name")
        sites = ['All Sites'] + [row['name'] for row in c.fetchall()]
        self.stats_filter_site['values'] = sites
        self.stats_filter_site.set('All Sites')
        
        # Get all users
        c.execute("SELECT name FROM users ORDER BY name")
        users = ['All Users'] + [row['name'] for row in c.fetchall()]
        self.stats_filter_user['values'] = users
        self.stats_filter_user.set('All Users')
        
        conn.close()
        
        # Row 1: Main financial metrics
        row1 = ttk.Frame(stats_frame)
        row1.pack(fill='x', padx=10, pady=5)
        
        self._invested_var = tk.StringVar(value='Invested: $0')
        self._redeemed_var = tk.StringVar(value='Redeemed: $0')
        self._cashback_var = tk.StringVar(value='Cashback: $0')
        self._expenses_var = tk.StringVar(value='Expenses: $0')
        self._play_pl_var = tk.StringVar(value='Play P/L: $0 (0%)')
        self._unrealized_var = tk.StringVar(value='Unrealized Cost: $0')
        self._net_pl_var = tk.StringVar(value='Net P/L: $0 (0%)')
        
        ttk.Label(row1, textvariable=self._invested_var, font=('Arial', 10)).pack(side='left', padx=(0, 20))
        ttk.Label(row1, textvariable=self._redeemed_var, font=('Arial', 10)).pack(side='left', padx=(0, 20))
        ttk.Label(row1, textvariable=self._cashback_var, font=('Arial', 10), foreground='green').pack(side='left', padx=(0, 20))
        ttk.Label(row1, textvariable=self._expenses_var, font=('Arial', 10), foreground='red').pack(side='left', padx=(0, 20))
        ttk.Label(row1, textvariable=self._play_pl_var, font=('Arial', 10, 'bold')).pack(side='left', padx=(0, 20))
        ttk.Label(row1, textvariable=self._unrealized_var, font=('Arial', 10), foreground='orange').pack(side='left', padx=(0, 20))
        ttk.Label(row1, textvariable=self._net_pl_var, font=('Arial', 10, 'bold')).pack(side='left')
        
        # Row 2: Secondary metrics
        row2 = ttk.Frame(stats_frame)
        row2.pack(fill='x', padx=10, pady=(0, 5))
        
        self._sessions_var = tk.StringVar(value='Sessions: 0')
        self._avg_session_var = tk.StringVar(value='Avg Session: $0')
        self._running_loss_var = tk.StringVar(value='Running Loss: $0')
        
        ttk.Label(row2, textvariable=self._sessions_var, font=('Arial', 9)).pack(side='left', padx=(0, 20))
        ttk.Label(row2, textvariable=self._avg_session_var, font=('Arial', 9)).pack(side='left', padx=(0, 20))
        ttk.Label(row2, textvariable=self._running_loss_var, font=('Arial', 9, 'bold')).pack(side='left')
        
        # Create main notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Create tab frames
        self.purchases_tab = ttk.Frame(self.notebook)
        self.redemptions_tab = ttk.Frame(self.notebook)
        self.game_sessions_tab = ttk.Frame(self.notebook)  # NEW
        self.daily_tax_tab = ttk.Frame(self.notebook)  # NEW
        self.unrealized_tab = ttk.Frame(self.notebook)  # RENAMED from open_sessions
        self.realized_tab = ttk.Frame(self.notebook)  # RENAMED from closed_sessions
        self.expenses_tab = ttk.Frame(self.notebook)
        self.reports_tab = ttk.Frame(self.notebook)
        self.setup_tab = ttk.Frame(self.notebook)
        
        # Add tabs to notebook
        self.notebook.add(self.purchases_tab, text="Purchases")
        self.notebook.add(self.redemptions_tab, text="Redemptions")
        self.notebook.add(self.game_sessions_tab, text="Game Sessions")  # NEW
        self.notebook.add(self.daily_tax_tab, text="Daily Sessions")  # RENAMED
        self.notebook.add(self.unrealized_tab, text="Unrealized")  # RENAMED
        self.notebook.add(self.realized_tab, text="Realized")  # RENAMED
        self.notebook.add(self.expenses_tab, text="Expenses")
        self.notebook.add(self.reports_tab, text="Reports")
        self.notebook.add(self.setup_tab, text="Setup")
        
        # Build tabs
        build_purchases_tab(self)
        build_redemptions_tab(self)
        build_game_sessions_tab(self)  # NEW
        build_daily_tax_tab(self)  # NEW
        build_unrealized_positions_tab(self)  # NEW (renamed)
        self.build_closed_sessions_tab()  # Keep existing (now "Realized")
        self.build_expenses_tab()
        self.build_reports_tab()
        build_setup_tab(self)  # From gui_tabs - includes Users/Sites/Cards/Methods/Tools
        
        # Set default stats filter to current year
        self._set_stats_filter_this_year()
        
        # Load initial data
        self.refresh_all()
    
    def refresh_all(self):
        """Refresh all data displays"""
        self.refresh_dropdowns()
        self.refresh_purchases()
        self.refresh_redemptions()
        self.refresh_game_sessions()  # NEW
        self.refresh_daily_tax_sessions()  # NEW
        self.refresh_unrealized_positions()  # RENAMED from refresh_open_sessions
        self.refresh_closed_sessions()
        self.refresh_expenses()
        self.refresh_reports()
        self.refresh_monthly_subtab()
        self.refresh_global_stats()
    
    # ========================================================================
    # AUDIT LOGGING
    # ========================================================================
    
    def log_audit(self, action, table_name, record_id=None, details=None, user_name=None):
        """Write to audit log"""
        try:
            conn = self.db.get_connection()
            c = conn.cursor()
            c.execute('''
                INSERT INTO audit_log (timestamp, action, table_name, record_id, details, user_name)
                VALUES (datetime('now', 'localtime'), ?, ?, ?, ?, ?)
            ''', (action, table_name, record_id, details, user_name))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Audit log error: {e}")
    
    # ========================================================================
    # PURCHASE METHODS
    # ========================================================================
    
    def on_purchase_user_selected(self, e=None):
        """Update card dropdown when user is selected"""
        user_name = self.p_user.get().strip()
        
        # Track previous user to detect actual changes
        previous_user = getattr(self, '_previous_purchase_user', None)
        
        if not user_name:
            self.p_card['values'] = []
            if hasattr(self.p_card, '_excel_master'):
                self.p_card._excel_master = []
            if previous_user:  # Only clear if there was a previous user
                self.p_card.set('')
            self._previous_purchase_user = None
            return
        
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE name = ?", (user_name,))
        result = c.fetchone()
        
        if not result:
            conn.close()
            self.p_card['values'] = []
            if hasattr(self.p_card, '_excel_master'):
                self.p_card._excel_master = []
            if previous_user:  # Only clear if there was a previous user
                self.p_card.set('')
            self._previous_purchase_user = None
            return
        
        user_id = result['id']
        c.execute("SELECT name FROM cards WHERE active = 1 AND user_id = ? ORDER BY name", (user_id,))
        cards = [r['name'] for r in c.fetchall()]
        conn.close()
        
        # Update dropdown values
        self.p_card['values'] = cards
        
        # Force refresh of autosuggest master list
        if hasattr(self.p_card, '_excel_master'):
            self.p_card._excel_master = cards
        
        # Clear card selection ONLY if the user actually changed
        if previous_user and previous_user != user_name:
            self.p_card.set('')
        
        # Remember this user for next time
        self._previous_purchase_user = user_name
    
    def clear_purchase_form(self):
        """Clear purchase form"""
        from datetime import datetime
        self.p_user.set('')
        self.p_date.delete(0, tk.END)
        self.p_date.insert(0, date.today().strftime("%Y-%m-%d"))
        self.p_time.delete(0, tk.END)
        self.p_time.insert(0, datetime.now().strftime("%H:%M:%S"))
        self.p_amount.delete(0, tk.END)
        self.p_sc.delete(0, tk.END)
        self.p_start_sc.delete(0, tk.END)
        self.p_start_sc.insert(0, "0")
        self.p_site.set('')
        self.p_card.set('')
        self.p_notes.delete('1.0', tk.END)
        self.p_edit_id = None
        self._previous_purchase_user = None  # Reset user tracking
    
    
    def smart_save_purchase(self):
        """Smart save - save_purchase already handles both add and update via p_edit_id"""
        self.save_purchase()
    
    def save_purchase(self):
        """Save purchase"""
        try:
            user_name = self.p_user.get().strip()
            site_name = self.p_site.get().strip()
            card_name = self.p_card.get().strip()
            
            # Validate required fields
            if not all([user_name, site_name, card_name]):
                messagebox.showwarning("Missing Fields", "Please select User, Site, and Card")
                return
            
            # Validate and parse date
            date_str = self.p_date.get().strip()
            if not date_str:
                messagebox.showwarning("Missing Date", "Please enter a purchase date")
                return
            
            try:
                pdate = parse_date(date_str)
            except:
                messagebox.showerror("Invalid Date", "Please enter a valid date (YYYY-MM-DD)")
                return
            
            # Validate and parse time
            time_str = self.p_time.get().strip()
            if not time_str:
                # Default to current time if blank
                from datetime import datetime
                ptime = datetime.now().strftime("%H:%M:%S")
            else:
                # Validate time format (HH:MM:SS or HH:MM)
                try:
                    from datetime import datetime
                    # Try parsing with seconds first
                    try:
                        datetime.strptime(time_str, "%H:%M:%S")
                        ptime = time_str
                    except:
                        # Try without seconds
                        datetime.strptime(time_str, "%H:%M")
                        ptime = time_str + ":00"  # Add seconds
                except:
                    messagebox.showerror("Invalid Time", "Please enter time as HH:MM:SS or HH:MM (24-hour format)")
                    return
            
            # Check for future date
            if pdate > date.today():
                messagebox.showerror("Future Date", "Purchase date cannot be in the future")
                return
            
            # Validate amount
            amount_str = self.p_amount.get().strip()
            if not amount_str:
                messagebox.showwarning("Missing Amount", "Please enter a purchase amount")
                return
            
            valid, result = validate_currency(amount_str)
            if not valid:
                messagebox.showerror("Invalid Amount", result)
                return
            amount = result
            
            # Validate SC received
            sc_str = self.p_sc.get().strip()
            if not sc_str:
                messagebox.showwarning("Missing SC", "Please enter SC received")
                return
            
            valid, result = validate_currency(sc_str)
            if not valid:
                messagebox.showerror("Invalid SC", result)
                return
            sc = result
            
            # Validate starting SC balance
            start_sc_str = self.p_start_sc.get().strip() or "0"
            valid, result = validate_currency(start_sc_str)
            if not valid:
                messagebox.showerror("Invalid Balance", result)
                return
            start_sc = result
            
            notes = self.p_notes.get('1.0', 'end-1c').strip()
            
            conn = self.db.get_connection()
            c = conn.cursor()
            
            # Get user ID
            c.execute("SELECT id FROM users WHERE name = ?", (user_name,))
            user_row = c.fetchone()
            if not user_row:
                conn.close()
                messagebox.showerror("Error", f"User '{user_name}' not found")
                return
            user_id = user_row['id']
            
            # Get site ID
            c.execute("SELECT id FROM sites WHERE name = ?", (site_name,))
            site_row = c.fetchone()
            if not site_row:
                conn.close()
                messagebox.showerror("Error", f"Site '{site_name}' not found")
                return
            site_id = site_row['id']
            
            # Get card ID and verify it belongs to user
            c.execute("SELECT id FROM cards WHERE name = ? AND user_id = ?", (card_name, user_id))
            card_row = c.fetchone()
            if not card_row:
                conn.close()
                messagebox.showerror("Error", 
                    f"Card '{card_name}' not found for user '{user_name}'.\n\n"
                    "Please select a card that belongs to this user.")
                return
            card_id = card_row['id']
            
            if self.p_edit_id:
                # Get old purchase data
                c.execute('SELECT amount, remaining_amount, site_id, user_id FROM purchases WHERE id = ?', (self.p_edit_id,))
                old_purchase = c.fetchone()
                old_amount = float(old_purchase['amount']) if old_purchase else 0.0
                old_remaining = float(old_purchase['remaining_amount']) if old_purchase else 0.0
                old_site_id = old_purchase['site_id'] if old_purchase else None
                old_user_id = old_purchase['user_id'] if old_purchase else None
                
                consumed = old_amount - old_remaining
                
                # CRITICAL FIX 1.1: Can't change amount, site, OR user if some was consumed
                if consumed > 0:
                    if old_amount != amount:
                        conn.close()
                        messagebox.showerror("Error", 
                            "Cannot change amount - purchase has been partially redeemed.\n"
                            f"${consumed:.2f} has been used for redemptions.")
                        return
                    
                    if old_site_id != site_id or old_user_id != user_id:
                        conn.close()
                        messagebox.showerror("Error", 
                            "Cannot change site or user - purchase has been partially redeemed.\n"
                            f"${consumed:.2f} has been used for redemptions.\n"
                            "Delete the redemptions first.")
                        return
                
                # New remaining = new amount (if nothing consumed yet)
                new_remaining = amount
                
                # Update existing purchase
                c.execute('''
                    UPDATE purchases 
                    SET purchase_date=?, purchase_time=?, site_id=?, amount=?, sc_received=?,
                        starting_sc_balance=?, card_id=?, user_id=?, remaining_amount=?, notes=? 
                    WHERE id=?
                ''', (pdate, ptime, site_id, amount, sc, start_sc, card_id, user_id, new_remaining, notes, self.p_edit_id))
                
                # CRITICAL FIX 1.2: Update session totals properly for all change types
                site_changed = old_site_id != site_id
                user_changed = old_user_id != user_id
                amount_changed = old_amount != amount
                
                if site_changed or user_changed:
                    # Site or user changed - move purchase between sessions
                    # Remove from old session
                    c.execute('''
                        SELECT id FROM site_sessions 
                        WHERE site_id = ? AND user_id = ? AND status IN ('Active', 'Redeeming')
                        ORDER BY start_date DESC LIMIT 1
                    ''', (old_site_id, old_user_id))
                    old_session = c.fetchone()
                    
                    if old_session:
                        c.execute('''
                            UPDATE site_sessions 
                            SET total_buyin = total_buyin - ? 
                            WHERE id = ?
                        ''', (old_amount, old_session['id']))
                        
                        # Check if old session now has 0 buyin and should be deleted
                        c.execute('SELECT total_buyin FROM site_sessions WHERE id = ?', (old_session['id'],))
                        updated_old = c.fetchone()
                        if updated_old and float(updated_old['total_buyin']) <= 0:
                            # Check for redemptions before deleting
                            c.execute('SELECT COUNT(*) as count FROM redemptions WHERE site_session_id = ?', 
                                     (old_session['id'],))
                            if c.fetchone()['count'] == 0:
                                c.execute('DELETE FROM site_sessions WHERE id = ?', (old_session['id'],))
                    
                    conn.commit()
                    conn.close()
                    
                    # Add to new session (or create it) - AFTER closing connection to avoid lock
                    new_session_id = self.session_mgr.get_or_create_site_session(site_id, user_id, pdate)
                    self.session_mgr.add_purchase_to_session(new_session_id, amount)
                    
                elif amount_changed:
                    # Same site/user, just amount changed
                    amount_diff = amount - old_amount
                    
                    c.execute('''
                        SELECT id FROM site_sessions 
                        WHERE site_id = ? AND user_id = ? AND status IN ('Active', 'Redeeming')
                        ORDER BY start_date DESC LIMIT 1
                    ''', (site_id, user_id))
                    session = c.fetchone()
                    
                    if session:
                        c.execute('''
                            UPDATE site_sessions 
                            SET total_buyin = total_buyin + ? 
                            WHERE id = ?
                        ''', (amount_diff, session['id']))
                
                conn.commit()
                conn.close()
                
                # Auto-recalculate affected sessions
                recalc_count = self.session_mgr.auto_recalculate_affected_sessions(site_id, user_id, pdate, ptime)
                
                success_msg = "Purchase updated"
                if recalc_count > 0:
                    success_msg += f" (recalculated {recalc_count} affected session{'s' if recalc_count != 1 else ''})"
                
                messagebox.showinfo("Success", success_msg)
            else:
                # Insert new purchase
                c.execute('''
                    INSERT INTO purchases 
                    (purchase_date, purchase_time, site_id, amount, sc_received, starting_sc_balance, card_id, user_id, remaining_amount, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (pdate, ptime, site_id, amount, sc, start_sc, card_id, user_id, amount, notes))
                purchase_id = c.lastrowid
                conn.commit()
                conn.close()
                
                # Log to audit trail
                self.log_audit('INSERT', 'purchases', purchase_id, 
                             f'{user_name} - {site_name} - ${amount:.2f}', user_name)
                
                # Add to session - AFTER closing connection to avoid lock
                session_id = self.session_mgr.get_or_create_site_session(site_id, user_id, pdate)
                self.session_mgr.add_purchase_to_session(session_id, amount)
                
                # Auto-recalculate affected sessions
                recalc_count = self.session_mgr.auto_recalculate_affected_sessions(site_id, user_id, pdate, ptime)
                
                success_msg = "Purchase added"
                if recalc_count > 0:
                    success_msg += f" (recalculated {recalc_count} affected session{'s' if recalc_count != 1 else ''})"
                
                messagebox.showinfo("Success", success_msg)
            
            self.clear_purchase_form()
            self.refresh_all_views()
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def update_purchase(self):
        """Update existing purchase"""
        if not self.p_edit_id:
            messagebox.showwarning("No Selection", "No purchase selected for update")
            return
        
        try:
            user_name = self.p_user.get().strip()
            pdate = parse_date(self.p_date.get().strip())
            amount = float(self.p_amount.get().strip())
            sc = float(self.p_sc.get().strip() or 0)
            start_sc = float(self.p_start_sc.get().strip() or 0)
            site_name = self.p_site.get().strip()
            card_name = self.p_card.get().strip()
            
            if not user_name or not site_name or not card_name:
                messagebox.showwarning("Missing", "Fill all fields")
                return
            
            conn = self.db.get_connection()
            c = conn.cursor()
            
            # Get user ID
            c.execute("SELECT id FROM users WHERE name = ?", (user_name,))
            user_row = c.fetchone()
            if not user_row:
                conn.close()
                messagebox.showerror("Error", f"User '{user_name}' not found")
                return
            user_id = user_row['id']
            
            # Get site ID
            c.execute("SELECT id FROM sites WHERE name = ?", (site_name,))
            site_row = c.fetchone()
            if not site_row:
                conn.close()
                messagebox.showerror("Error", f"Site '{site_name}' not found")
                return
            site_id = site_row['id']
            
            # Get card ID
            c.execute("SELECT id FROM cards WHERE name = ?", (card_name,))
            card_row = c.fetchone()
            if not card_row:
                conn.close()
                messagebox.showerror("Error", f"Card '{card_name}' not found")
                return
            card_id = card_row['id']
            
            # Verify card belongs to the selected user
            c.execute("SELECT user_id FROM cards WHERE id = ?", (card_id,))
            card_owner = c.fetchone()
            if card_owner and card_owner['user_id'] != user_id:
                conn.close()
                messagebox.showerror("Error", 
                    f"Card '{card_name}' does not belong to user '{user_name}'.\n\n"
                    "Please select a card that belongs to this user.")
                return
            
            # Check if amount consumed and calculate new remaining
            c.execute('SELECT amount, remaining_amount FROM purchases WHERE id = ?', (self.p_edit_id,))
            old_purchase = c.fetchone()
            if old_purchase:
                old_amount = float(old_purchase['amount'])
                old_remaining = float(old_purchase['remaining_amount'])
                consumed = old_amount - old_remaining
                
                # Can't change amount if some was consumed
                if old_amount != amount and consumed > 0:
                    conn.close()
                    messagebox.showerror("Error", "Cannot change amount - purchase has been partially redeemed")
                    return
                
                # New remaining = new amount (if nothing consumed yet)
                new_remaining = amount
            else:
                new_remaining = amount
            
            c.execute('''
                UPDATE purchases
                SET purchase_date=?, amount=?, sc_received=?, starting_sc_balance=?,
                    site_id=?, card_id=?, user_id=?, remaining_amount=?
                WHERE id=?
            ''', (pdate, amount, sc, start_sc, site_id, card_id, user_id, new_remaining, self.p_edit_id))
            
            conn.commit()
            conn.close()
            
            self.clear_purchase_form()
            self.refresh_all_views()
            messagebox.showinfo("Success", "Purchase updated")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def edit_purchase(self):
        """Load selected purchase for editing"""
        sel = self.p_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select a purchase")
            return
        
        # Check if multiple selected
        if len(sel) > 1:
            messagebox.showwarning("Multiple Selection", 
                "Please select only one purchase to edit.\n\n"
                "Tip: Use Ctrl+Click or Shift+Click to select multiple items for deletion.")
            return
        
        # Get ID from tags - tags are (color_tag, id)
        tags = self.p_tree.item(sel[0])['tags']
        pid = tags[1] if len(tags) > 1 else tags[0]  # ID is second tag now
        
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute('''
            SELECT p.*, s.name as site_name, ca.name as card_name, u.name as user_name
            FROM purchases p 
            JOIN sites s ON p.site_id = s.id
            JOIN cards ca ON p.card_id = ca.id 
            JOIN users u ON p.user_id = u.id
            WHERE p.id = ?
        ''', (pid,))
        p = c.fetchone()
        conn.close()
        
        if p:
            self.p_user.set(p['user_name'])
            self._previous_purchase_user = p['user_name']  # Set tracking before calling handler
            self.on_purchase_user_selected()
            self.p_date.delete(0, tk.END)
            self.p_date.insert(0, p['purchase_date'])
            self.p_time.delete(0, tk.END)
            self.p_time.insert(0, p['purchase_time'] or '00:00:00')
            self.p_amount.delete(0, tk.END)
            self.p_amount.insert(0, str(p['amount']))
            self.p_sc.delete(0, tk.END)
            self.p_sc.insert(0, str(p['sc_received']))
            self.p_start_sc.delete(0, tk.END)
            self.p_start_sc.insert(0, str(p['starting_sc_balance']))
            self.p_site.set(p['site_name'])
            self.p_card.set(p['card_name'])
            self.p_notes.delete('1.0', tk.END)
            if p['notes']:
                self.p_notes.insert('1.0', p['notes'])
            self.p_edit_id = pid
    
    def delete_purchase(self):
        """Delete selected purchase(s) - must update session totals"""
        sel = self.p_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select purchase(s) to delete")
            return
        
        # Check if multiple items selected
        if len(sel) > 1:
            if not messagebox.askyesno("Confirm", f"Delete {len(sel)} purchases?"):
                return
        else:
            if not messagebox.askyesno("Confirm", "Delete this purchase?"):
                return
        
        conn = self.db.get_connection()
        c = conn.cursor()
        
        deleted_count = 0
        error_messages = []
        affected_combinations = set()  # Track which site/user/dates need recalc
        
        for item in sel:
            tags = self.p_tree.item(item)['tags']
            pid = tags[1] if len(tags) > 1 else tags[0]  # ID is second tag now
            
            # Get purchase info before deleting
            c.execute('''
                SELECT amount, remaining_amount, site_id, user_id, purchase_date, purchase_time
                FROM purchases 
                WHERE id = ?
            ''', (pid,))
            purchase = c.fetchone()
            
            if not purchase:
                error_messages.append(f"Purchase ID {pid} not found")
                continue
            
            amount = float(purchase['amount'])
            remaining = float(purchase['remaining_amount'])
            consumed = amount - remaining
            site_id = purchase['site_id']
            user_id = purchase['user_id']
            pdate = purchase['purchase_date']
            ptime = purchase['purchase_time'] or '00:00:00'
            
            # Track for auto-recalc
            affected_combinations.add((site_id, user_id, pdate, ptime))
            
            # Check if any cost basis was consumed (used by redemptions)
            if consumed > 0:
                error_messages.append(f"Purchase of ${amount:.2f} cannot be deleted - ${consumed:.2f} has been used for redemptions")
                continue
            
            # Find the session for this purchase
            c.execute('''
                SELECT id FROM site_sessions 
                WHERE site_id = ? AND user_id = ? AND status IN ('Active', 'Redeeming')
                ORDER BY start_date DESC LIMIT 1
            ''', (site_id, user_id))
            session = c.fetchone()
            
            # Delete the purchase
            c.execute("DELETE FROM purchases WHERE id = ?", (pid,))
            deleted_count += 1
            
            # Log to audit trail
            self.log_audit('DELETE', 'purchases', pid, f'Deleted ${amount:.2f}', None)
            
            # Update session total_buyin
            if session:
                session_id = session['id']
                c.execute('''
                    UPDATE site_sessions 
                    SET total_buyin = total_buyin - ? 
                    WHERE id = ?
                ''', (amount, session_id))
                
                # CRITICAL FIX 1.5: Check if session should be deleted (only if safe)
                c.execute('SELECT total_buyin, total_redeemed FROM site_sessions WHERE id = ?', (session_id,))
                updated_session = c.fetchone()
                
                if updated_session:
                    total_buyin = float(updated_session['total_buyin'])
                    total_redeemed = float(updated_session['total_redeemed'])
                    
                    # Only delete if:
                    # 1. No buyin remaining, AND
                    # 2. No redemptions have been made, AND
                    # 3. No redemption records reference this session
                    if total_buyin <= 0 and total_redeemed == 0:
                        c.execute('SELECT COUNT(*) as count FROM redemptions WHERE site_session_id = ?', 
                                 (session_id,))
                        redemption_count = c.fetchone()['count']
                        
                        if redemption_count == 0:
                            # Safe to delete - session is truly empty
                            c.execute('DELETE FROM site_sessions WHERE id = ?', (session_id,))
        
        conn.commit()
        conn.close()
        
        # Auto-recalculate affected sessions for all site/user combinations
        total_recalc_count = 0
        for site_id, user_id, pdate, ptime in affected_combinations:
            recalc_count = self.session_mgr.auto_recalculate_affected_sessions(site_id, user_id, pdate, ptime)
            total_recalc_count += recalc_count
        
        # Show results
        self.refresh_all_views()
        
        if error_messages:
            error_text = "\n".join(error_messages)
            success_msg = f"Deleted {deleted_count} purchase(s)."
            if total_recalc_count > 0:
                success_msg += f" Recalculated {total_recalc_count} session{'s' if total_recalc_count != 1 else ''}."
            success_msg += f"\n\nErrors:\n{error_text}"
            messagebox.showwarning("Partial Success", success_msg)
        else:
            success_msg = f"Deleted {deleted_count} purchase{'s' if deleted_count != 1 else ''}"
            if total_recalc_count > 0:
                success_msg += f" (recalculated {total_recalc_count} affected session{'s' if total_recalc_count != 1 else ''})"
            messagebox.showinfo("Success", success_msg)
    
    # ========================================================================
    # REDEMPTION METHODS
    # ========================================================================
    
    def on_r_user_sel(self, e=None):
        """Update when redemption user selected - filter redemption methods"""
        user_name = self.r_user.get().strip()
        
        # Track previous user to detect actual changes
        previous_user = getattr(self, '_previous_redemption_user', None)
        
        if not user_name:
            self.r_method['values'] = []
            if hasattr(self.r_method, '_excel_master'):
                self.r_method._excel_master = []
            if previous_user:  # Only clear if there was a previous user
                self.r_method.set('')
            self._previous_redemption_user = None
            self.on_r_site_sel()
            return
        
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Get user_id
        c.execute("SELECT id FROM users WHERE name = ?", (user_name,))
        user_result = c.fetchone()
        
        if not user_result:
            conn.close()
            self.r_method['values'] = []
            if hasattr(self.r_method, '_excel_master'):
                self.r_method._excel_master = []
            if previous_user:  # Only clear if there was a previous user
                self.r_method.set('')
            self._previous_redemption_user = None
            self.on_r_site_sel()
            return
        
        user_id = user_result['id']
        
        # Get methods: global (no user_id) + user-specific methods
        c.execute('''
            SELECT name FROM redemption_methods 
            WHERE active = 1 AND (user_id IS NULL OR user_id = ?)
            ORDER BY name
        ''', (user_id,))
        methods = [r['name'] for r in c.fetchall()]
        conn.close()
        
        # Update dropdown values
        self.r_method['values'] = methods
        
        # Force refresh of autosuggest master list
        if hasattr(self.r_method, '_excel_master'):
            self.r_method._excel_master = methods
        
        # Check if currently selected method is valid for this user
        current_method = self.r_method.get().strip()
        if current_method and current_method not in methods:
            # Current method doesn't belong to this user - clear it
            self.r_method.set('')
        
        # Remember this user for next time
        self._previous_redemption_user = user_name
        
        self.on_r_site_sel()
    
    def on_r_site_sel(self, e=None):
        """Update session info when site selected"""
        site_name = self.r_site.get().strip()
        user_name = self.r_user.get().strip()
        
        if not site_name or not user_name:
            return
        
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM sites WHERE name = ?", (site_name,))
        site_result = c.fetchone()
        
        if not site_result:
            conn.close()
            return
        
        site_id = site_result['id']
        
        c.execute("SELECT id FROM users WHERE name = ?", (user_name,))
        user_result = c.fetchone()
        
        if not user_result:
            conn.close()
            return
        
        user_id = user_result['id']
        
        c.execute('''
            SELECT total_buyin, total_redeemed 
            FROM site_sessions
            WHERE site_id = ? AND user_id = ? AND status IN ('Active', 'Redeeming')
            ORDER BY start_date DESC LIMIT 1
        ''', (site_id, user_id))
        sess = c.fetchone()
        conn.close()
        
        if sess:
            buyin = sess['total_buyin']
            redeemed = sess['total_redeemed']
            bal = buyin - redeemed
            self.r_info.config(
                text=f"Buy-in: ${buyin:.2f} | Redeemed: ${redeemed:.2f} | Balance: ${bal:.2f}"
            )
        else:
            self.r_info.config(text="No active session")
    
    def clear_redemption_form(self):
        """Clear redemption form"""
        from datetime import datetime
        self.r_user.set('')
        self.r_date.delete(0, tk.END)
        self.r_date.insert(0, date.today().strftime("%Y-%m-%d"))
        self.r_time.delete(0, tk.END)
        self.r_time.insert(0, datetime.now().strftime("%H:%M:%S"))
        self.r_amount.delete(0, tk.END)
        self.r_receipt.delete(0, tk.END)
        self.r_site.set('')
        self.r_method.set('')
        self.r_more.set(False)
        self.r_free.set(False)
        self.r_processed.set(False)
        self.r_notes.delete('1.0', tk.END)
        self.r_info.config(text="")
        self.r_edit_id = None
    
    
    def smart_save_redemption(self):
        """Smart save - save_redemption already handles both add and update via r_edit_id"""
        self.save_redemption()
    
    def save_redemption(self):
        """Save redemption"""
        try:
            user_name = self.r_user.get().strip()
            site_name = self.r_site.get().strip()
            
            # Validate required fields
            if not user_name or not site_name:
                messagebox.showwarning("Missing Fields", "Please select User and Site")
                return
            
            # Validate and parse redemption date
            date_str = self.r_date.get().strip()
            if not date_str:
                messagebox.showwarning("Missing Date", "Please enter a redemption date")
                return
            
            try:
                rdate = parse_date(date_str)
            except:
                messagebox.showerror("Invalid Date", "Please enter a valid redemption date (YYYY-MM-DD)")
                return
            
            # Validate and parse time
            time_str = self.r_time.get().strip()
            if not time_str:
                # Default to current time if blank
                from datetime import datetime
                rtime = datetime.now().strftime("%H:%M:%S")
            else:
                # Validate time format (HH:MM:SS or HH:MM)
                try:
                    from datetime import datetime
                    # Try parsing with seconds first
                    try:
                        datetime.strptime(time_str, "%H:%M:%S")
                        rtime = time_str
                    except:
                        # Try without seconds
                        datetime.strptime(time_str, "%H:%M")
                        rtime = time_str + ":00"  # Add seconds
                except:
                    messagebox.showerror("Invalid Time", "Please enter time as HH:MM:SS or HH:MM (24-hour format)")
                    return
            
            # Validate receipt date (optional, but must be valid if provided)
            receipt_str = self.r_receipt.get().strip()
            receipt_date = None
            if receipt_str:
                try:
                    receipt_date = parse_date(receipt_str)
                    # Receipt date should not be before redemption date
                    if receipt_date < rdate:
                        messagebox.showerror("Invalid Receipt Date", 
                            "Receipt date cannot be before redemption date")
                        return
                except:
                    messagebox.showerror("Invalid Receipt Date", 
                        "Please enter a valid receipt date (YYYY-MM-DD)")
                    return
            
            # Validate amount
            amount_str = self.r_amount.get().strip()
            if not amount_str:
                messagebox.showwarning("Missing Amount", "Please enter a redemption amount")
                return
            
            valid, result = validate_currency(amount_str)
            if not valid:
                messagebox.showerror("Invalid Amount", result)
                return
            amount = result
            
            # Get checkboxes
            more = self.r_more.get()
            free = self.r_free.get()
            processed = 1 if self.r_processed.get() else 0
            
            # Validate redemption method (required if amount > 0)
            method_name = self.r_method.get().strip()
            if amount > 0 and not method_name:
                messagebox.showwarning("Missing Method", 
                    "Please select a redemption method (Venmo, PayPal, etc.)")
                return
            
            notes = self.r_notes.get('1.0', 'end-1c').strip()
            
            conn = self.db.get_connection()
            c = conn.cursor()
            c.execute("SELECT id FROM users WHERE name = ?", (user_name,))
            user_id = c.fetchone()['id']
            c.execute("SELECT id FROM sites WHERE name = ?", (site_name,))
            site_id = c.fetchone()['id']
            
            # CRITICAL CHECK: Prevent redemption of unsessioned promotional value
            # Check for active game sessions (existing check)
            c.execute('''
                SELECT id, starting_sc_balance 
                FROM game_sessions
                WHERE site_id = ? AND user_id = ? AND status = 'Active'
                ORDER BY session_date DESC, start_time DESC
                LIMIT 1
            ''', (site_id, user_id))
            
            active_session = c.fetchone()
            # Only block if: (1) Active session exists, (2) Not free SC, AND (3) Creating NEW redemption
            if active_session and not free and not self.r_edit_id:
                conn.close()
                messagebox.showerror("Active Session", 
                    f"Cannot create new redemption while session is active.\n\n"
                    f"Please end your current session first (started with {active_session['starting_sc_balance']:.2f} SC)\n\n"
                    f"Note: You CAN edit existing redemptions during active sessions.")
                return
            
            # NEW CHECK: Verify all current balance has been sessioned
            # This check applies to ALL redemptions, even free SC
            # (Free SC still needs to be sessioned to capture income, just doesn't consume basis)
            # SKIP this check when EDITING existing redemption (would double-count the redemption being edited)
            if not self.r_edit_id:
                expected_total, expected_redeemable = self.session_mgr.compute_expected_balances(
                    site_id, user_id, rdate, rtime
                )
                sc_rate = self.session_mgr.get_sc_rate(site_id)
                expected_balance = expected_redeemable * sc_rate

                # If trying to redeem more than expected (unsessioned promotional value)
                # Allow small tolerance for rounding (50 cents)
                unsessioned_amount = amount - expected_balance
                
                if unsessioned_amount > 0.50:
                        conn.close()
                        messagebox.showerror("Unsessioned Balance", 
                            f"Cannot redeem ${amount:,.2f} - you have unsessioned promotional value!\n\n"
                            f"Expected sessioned balance: ${expected_balance:,.2f}\n"
                            f"Attempting to redeem: ${amount:,.2f}\n"
                            f"Unsessioned amount: ${unsessioned_amount:,.2f}\n\n"
                            f"ACTION REQUIRED:\n"
                            f"Create a session first to capture this ${unsessioned_amount:,.2f} as taxable income.\n\n"
                            f"Go to Sessions tab → Start Session with current balance → End Session → Then redeem.")
                        return
                # End of unsessioned balance check (skipped when editing)
            
            method_id = None
            if method_name:
                c.execute("SELECT id FROM redemption_methods WHERE name = ?", (method_name,))
                result = c.fetchone()
                if result:
                    method_id = result['id']
            
            session_id = None
            if not free:
                c.execute('''
                    SELECT id FROM site_sessions
                    WHERE site_id = ? AND user_id = ? AND status IN ('Active', 'Redeeming')
                    ORDER BY start_date DESC LIMIT 1
                ''', (site_id, user_id))
                result = c.fetchone()
                if result:
                    session_id = result['id']
            
            if self.r_edit_id:
                # Get old redemption and tax_session info to reverse properly
                c.execute('''
                    SELECT r.amount, r.site_session_id, r.site_id, r.user_id,
                           ts.cost_basis
                    FROM redemptions r
                    LEFT JOIN tax_sessions ts ON ts.redemption_id = r.id
                    WHERE r.id = ?
                ''', (self.r_edit_id,))
                old_data = c.fetchone()
                
                old_amount = float(old_data['amount']) if old_data else 0.0
                old_session_id = old_data['site_session_id'] if old_data else None
                old_site_id = old_data['site_id'] if old_data else None
                old_user_id = old_data['user_id'] if old_data else None
                old_cost_basis = float(old_data['cost_basis']) if old_data and old_data['cost_basis'] else 0.0
                
                # CRITICAL FIX 1.3: Update redemption record INCLUDING site_session_id
                c.execute('''
                    UPDATE redemptions 
                    SET site_session_id=?, site_id=?, redemption_date=?, redemption_time=?, amount=?, receipt_date=?, 
                        redemption_method_id=?, is_free_sc=?, more_remaining=?, user_id=?, processed=?, notes=?
                    WHERE id=?
                ''', (session_id, site_id, rdate, rtime, amount, receipt_date, method_id, 
                      1 if free else 0, 1 if more else 0, user_id, processed, notes, self.r_edit_id))
                
                # Reverse old session totals
                if old_session_id:
                    c.execute('''
                        UPDATE site_sessions 
                        SET total_redeemed = total_redeemed - ? 
                        WHERE id = ?
                    ''', (old_amount, old_session_id))
                
                # CRITICAL FIX 1.4: Update NEW session totals (if session changed)
                if session_id and session_id != old_session_id:
                    c.execute('''
                        UPDATE site_sessions 
                        SET total_redeemed = total_redeemed + ? 
                        WHERE id = ?
                    ''', (amount, session_id))
                
                # Delete old tax_session
                c.execute('DELETE FROM tax_sessions WHERE redemption_id = ?', (self.r_edit_id,))
                
                conn.commit()
                conn.close()
                
                # Restore cost basis to purchases (reverse FIFO)
                if old_cost_basis > 0 and old_site_id and old_user_id:
                    self.session_mgr.fifo_calc.reverse_cost_basis(old_site_id, old_user_id, old_cost_basis)
                
                # Reprocess with updated values - is_edit=True prevents double-counting total_redeemed
                self.session_mgr.process_redemption(self.r_edit_id, site_id, amount, rdate, rtime, user_id, free, more, is_edit=True)
                
                # Recalculate subsequent redemptions if any exist
                if hasattr(self, 'r_has_subsequent') and self.r_has_subsequent and hasattr(self, 'r_subsequent_ids'):
                    self._recalculate_subsequent_redemptions(self.r_subsequent_ids, site_id, user_id)

                # Canonical recompute for affected pairs
                pairs_to_recalc = {(site_id, user_id)}
                if old_site_id and old_user_id:
                    pairs_to_recalc.add((old_site_id, old_user_id))
                total_recalc = 0
                for sid, uid in pairs_to_recalc:
                    total_recalc += self.session_mgr.auto_recalculate_affected_sessions(sid, uid, rdate, rtime)

                messagebox.showinfo(
                    "Success",
                    "Redemption updated" +
                    (f" (recalculated {len(self.r_subsequent_ids)} subsequent redemptions)"
                     if hasattr(self, 'r_has_subsequent') and self.r_has_subsequent else "") +
                    (f" (recalculated {total_recalc} sessions)" if total_recalc else "")
                )
            else:
                # Insert new redemption
                c.execute('''
                    INSERT INTO redemptions 
                    (site_session_id, site_id, redemption_date, redemption_time, amount, receipt_date,
                     redemption_method_id, is_free_sc, more_remaining, user_id, processed, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (session_id, site_id, rdate, rtime, amount, receipt_date, method_id,
                      1 if free else 0, 1 if more else 0, user_id, processed, notes))
                rid = c.lastrowid
                conn.commit()
                conn.close()
                
                # Every redemption is a taxable event - always create tax_session
                self.session_mgr.process_redemption(rid, site_id, amount, rdate, rtime, user_id, free, more)

                recalc_count = self.session_mgr.auto_recalculate_affected_sessions(site_id, user_id, rdate, rtime)
                messagebox.showinfo(
                    "Success",
                    "Redemption logged" + (f" (recalculated {recalc_count} sessions)" if recalc_count else "")
                )
            
            self.clear_redemption_form()
            self.refresh_all_views()
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def _recalculate_subsequent_redemptions(self, redemption_ids, site_id, user_id):
        """
        Recalculate FIFO cost basis for subsequent redemptions after editing an earlier one
        
        Args:
            redemption_ids: List of redemption IDs to recalculate (in chronological order)
            site_id: Site ID
            user_id: User ID
        """
        for rid in redemption_ids:
            conn = self.db.get_connection()
            c = conn.cursor()
            
            # Get redemption details
            c.execute('''
                SELECT amount, redemption_date, redemption_time, is_free_sc, site_session_id
                FROM redemptions
                WHERE id = ?
            ''', (rid,))
            redemption = c.fetchone()
            
            if not redemption:
                conn.close()
                continue
            
            amount = float(redemption['amount'])
            rdate = redemption['redemption_date']
            rtime = redemption['redemption_time'] or '00:00:00'
            is_free_sc = bool(redemption['is_free_sc'])
            
            # Get old cost basis from tax_sessions
            c.execute('SELECT cost_basis FROM tax_sessions WHERE redemption_id = ?', (rid,))
            old_tax = c.fetchone()
            old_cost_basis = float(old_tax['cost_basis']) if old_tax else 0.0
            
            # Delete old tax_session
            c.execute('DELETE FROM tax_sessions WHERE redemption_id = ?', (rid,))
            conn.commit()
            conn.close()
            
            # Reverse old FIFO allocation
            if old_cost_basis > 0:
                self.session_mgr.fifo_calc.reverse_cost_basis(site_id, user_id, old_cost_basis)
            
            # Recalculate FIFO and create new tax_session
            # Note: We use is_edit=True to prevent updating session totals (already correct)
            # We also assume more_remaining=True since we're recalculating middle redemptions
            self.session_mgr.process_redemption(rid, site_id, amount, rdate, rtime, user_id, is_free_sc, 
                                               more_remaining=True, is_edit=True)
    
    def update_redemption(self):
        """Update existing redemption - updates receipt date or other edits"""
        if not self.r_edit_id:
            messagebox.showwarning("No Selection", "No redemption selected for update")
            return
        
        try:
            # Get current redemption data
            conn = self.db.get_connection()
            c = conn.cursor()
            c.execute('SELECT * FROM redemptions WHERE id = ?', (self.r_edit_id,))
            existing = c.fetchone()
            
            if not existing:
                conn.close()
                messagebox.showerror("Error", "Redemption not found")
                return
            
            # Get form data
            receipt_date_str = self.r_receipt.get().strip()
            receipt_date = parse_date(receipt_date_str) if receipt_date_str else None
            
            # Update just the receipt date (main use case for editing redemptions)
            c.execute('''
                UPDATE redemptions
                SET receipt_date = ?
                WHERE id = ?
            ''', (receipt_date, self.r_edit_id))
            
            conn.commit()
            conn.close()
            
            self.clear_redemption_form()
            self.refresh_all_views()
            messagebox.showinfo("Success", "Redemption updated")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def edit_redemption(self):
        """Load selected redemption for editing"""
        sel = self.r_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select a redemption")
            return
        
        # Check if multiple selected
        if len(sel) > 1:
            messagebox.showwarning("Multiple Selection", 
                "Please select only one redemption to edit.\n\n"
                "Tip: Use Ctrl+Click or Shift+Click to select multiple items for deletion.")
            return
        
        # Get ID from tags - tags are (color_tag, id)
        tags = self.r_tree.item(sel[0])['tags']
        rid = tags[1] if len(tags) > 1 else tags[0]  # ID is second tag now
        
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Check if there are subsequent redemptions for same site/user
        c.execute('''
            SELECT r1.redemption_date, r1.site_id, r1.user_id
            FROM redemptions r1
            WHERE r1.id = ?
        ''', (rid,))
        this_redemption = c.fetchone()
        
        # Store info about subsequent redemptions for warning/recalculation
        self.r_has_subsequent = False
        self.r_subsequent_ids = []
        
        if this_redemption:
            c.execute('''
                SELECT r2.id, r2.redemption_date, r2.amount
                FROM redemptions r2
                WHERE r2.site_id = ? 
                  AND r2.user_id = ? 
                  AND r2.redemption_date >= ?
                  AND r2.id != ?
                ORDER BY r2.redemption_date ASC, r2.id ASC
            ''', (this_redemption['site_id'], 
                  this_redemption['user_id'],
                  this_redemption['redemption_date'],
                  rid))
            
            subsequent = c.fetchall()
            
            if subsequent:
                self.r_has_subsequent = True
                self.r_subsequent_ids = [row['id'] for row in subsequent]
                
                # Show warning dialog
                warning_msg = (
                    f"⚠️¸ WARNING: This redemption has {len(subsequent)} subsequent redemption(s).\n\n"
                    f"Editing this will automatically recalculate their FIFO cost basis.\n\n"
                    f"Affected redemptions:\n"
                )
                for row in subsequent[:5]:  # Show first 5
                    warning_msg += f"  • {row['redemption_date']}: ${row['amount']:.2f}\n"
                if len(subsequent) > 5:
                    warning_msg += f"  • ... and {len(subsequent) - 5} more\n"
                
                warning_msg += "\nContinue with edit?"
                
                if not messagebox.askyesno("Subsequent Redemptions", warning_msg, icon='warning'):
                    conn.close()
                    return
        
        c.execute('''
            SELECT r.*, s.name as site_name, rm.name as method_name, u.name as user_name
            FROM redemptions r 
            JOIN sites s ON r.site_id = s.id
            LEFT JOIN redemption_methods rm ON r.redemption_method_id = rm.id
            JOIN users u ON r.user_id = u.id
            WHERE r.id = ?
        ''', (rid,))
        r = c.fetchone()
        conn.close()
        
        if r:
            self.r_user.set(r['user_name'])
            self.on_r_user_sel()  # Update methods for this user
            self.r_date.delete(0, tk.END)
            self.r_date.insert(0, r['redemption_date'])
            self.r_time.delete(0, tk.END)
            self.r_time.insert(0, r['redemption_time'] or '00:00:00')
            self.r_amount.delete(0, tk.END)
            self.r_amount.insert(0, str(r['amount']))
            self.r_receipt.delete(0, tk.END)
            if r['receipt_date']:
                self.r_receipt.insert(0, r['receipt_date'])
            self.r_site.set(r['site_name'])
            # Set method AFTER on_r_user_sel has populated the methods list
            if r['method_name']:
                self.r_method.set(r['method_name'])
            else:
                self.r_method.set('')
            self.r_free.set(bool(r['is_free_sc']))
            self.r_processed.set(bool(r['processed']))
            self.r_notes.delete('1.0', tk.END)
            if r['notes']:
                self.r_notes.insert('1.0', r['notes'])
            
            # Check if this redemption's session is still in 'Redeeming' status
            # If so, that means "more balance remaining" was checked
            if r['site_session_id']:
                conn = self.db.get_connection()
                c = conn.cursor()
                c.execute('SELECT status FROM site_sessions WHERE id = ?', (r['site_session_id'],))
                sess = c.fetchone()
                conn.close()
                if sess and sess['status'] == 'Redeeming':
                    self.r_more.set(True)
                else:
                    self.r_more.set(False)
            else:
                self.r_more.set(False)
            
            self.r_edit_id = rid
    
    def delete_redemption(self):
        """Delete selected redemption(s)"""
        sel = self.r_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select redemption(s) to delete")
            return
        
        # Check if multiple items selected
        if len(sel) > 1:
            if not messagebox.askyesno("Confirm", f"Delete {len(sel)} redemptions?"):
                return
        else:
            if not messagebox.askyesno("Confirm", "Delete this redemption?"):
                return
        
        deleted_count = 0
        error_messages = []
        pairs_to_recalc = set()
        
        for item in sel:
            tags = self.r_tree.item(item)['tags']
            rid = tags[1] if len(tags) > 1 else tags[0]  # ID is second tag now

            conn = self.db.get_connection()
            c = conn.cursor()
            c.execute('SELECT site_id, user_id, redemption_date, redemption_time FROM redemptions WHERE id = ?', (rid,))
            row = c.fetchone()
            conn.close()
            
            # Use business logic to properly reverse all accounting
            success = self.session_mgr.delete_redemption(int(rid))
            
            if success:
                deleted_count += 1
                if row:
                    pairs_to_recalc.add((row['site_id'], row['user_id'], row['redemption_date'], row['redemption_time'] or '00:00:00'))
            else:
                error_messages.append(f"Redemption ID {rid} not found")

        total_recalc = 0
        for site_id, user_id, rdate, rtime in pairs_to_recalc:
            total_recalc += self.session_mgr.auto_recalculate_affected_sessions(site_id, user_id, rdate, rtime)
        
        self.refresh_all_views()
        
        if error_messages:
            error_text = "\n".join(error_messages)
            messagebox.showwarning("Partial Success", 
                f"Deleted {deleted_count} redemption(s).\n\nErrors:\n{error_text}")
        else:
            if deleted_count > 1:
                messagebox.showinfo(
                    "Success",
                    f"Deleted {deleted_count} redemptions" + (f" (recalculated {total_recalc} sessions)" if total_recalc else "")
                )
            else:
                messagebox.showinfo(
                    "Success",
                    "Redemption deleted" + (f" (recalculated {total_recalc} sessions)" if total_recalc else "")
                )
    
    # ========================================================================
    # REFRESH METHODS
    # ========================================================================
    
    def refresh_dropdowns(self):
        """Refresh all dropdown menus and update their displayed values"""
        if not hasattr(self, 'p_user'):
            return
        
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Users
        c.execute("SELECT name FROM users WHERE active = 1 ORDER BY name")
        users = [r['name'] for r in c.fetchall()]
        
        # Update all user dropdowns
        for dropdown in [self.p_user, self.r_user]:
            current = dropdown.get()
            dropdown['values'] = users
            # If current selection is no longer valid, clear it
            if current and current not in users:
                dropdown.set('')
            if hasattr(dropdown, '_excel_master'):
                dropdown._excel_master = users
        
        # Game sessions user dropdown
        if hasattr(self, 'gs_user'):
            current = self.gs_user.get()
            self.gs_user['values'] = users
            if current and current not in users:
                self.gs_user.set('')
            if hasattr(self.gs_user, '_excel_master'):
                self.gs_user._excel_master = users
        
        # Expenses user dropdown (optional)
        if hasattr(self, 'e_user'):
            current = self.e_user.get()
            self.e_user['values'] = users
            if current and current not in users:
                self.e_user.set('')
        
        # Sites
        c.execute("SELECT name FROM sites WHERE active = 1 ORDER BY name")
        sites = [r['name'] for r in c.fetchall()]
        
        for dropdown in [self.p_site, self.r_site]:
            current = dropdown.get()
            dropdown['values'] = sites
            if current and current not in sites:
                dropdown.set('')
            if hasattr(dropdown, '_excel_master'):
                dropdown._excel_master = sites
        
        # Game sessions site dropdown
        if hasattr(self, 'gs_site'):
            current = self.gs_site.get()
            self.gs_site['values'] = sites
            if current and current not in sites:
                self.gs_site.set('')
            if hasattr(self.gs_site, '_excel_master'):
                self.gs_site._excel_master = sites
        
        # Redemption methods - show ALL active methods initially
        # Filtering by user happens in on_r_user_sel()
        c.execute("SELECT name FROM redemption_methods WHERE active = 1 ORDER BY name")
        methods = [r['name'] for r in c.fetchall()]
        current = self.r_method.get()
        self.r_method['values'] = methods
        if current and current not in methods:
            self.r_method.set('')
        if hasattr(self.r_method, '_excel_master'):
            self.r_method._excel_master = methods
        
        # Cards - refresh if user is selected
        if hasattr(self, 'p_card'):
            current_user = self.p_user.get().strip()
            if current_user:
                # Refresh cards for this user
                self.on_purchase_user_selected()
            else:
                self.p_card['values'] = []
                if hasattr(self.p_card, '_excel_master'):
                    self.p_card._excel_master = []
        
        conn.close()
    
    def refresh_purchases(self):
        """Refresh purchases list with color coding and date filter"""
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Build query with optional date filter
        query = '''
            SELECT p.id, u.name as user_name, p.purchase_date, s.name as site, 
                   p.amount, p.sc_received, p.starting_sc_balance, ca.name as card, p.remaining_amount, p.notes
            FROM purchases p 
            JOIN sites s ON p.site_id = s.id
            JOIN cards ca ON p.card_id = ca.id
            JOIN users u ON p.user_id = u.id
        '''
        
        params = []
        
        # Apply date filter if set, otherwise default to current year
        if hasattr(self, 'p_filter_start') and hasattr(self, 'p_filter_end'):
            start = self.p_filter_start.get().strip()
            end = self.p_filter_end.get().strip()
            
            if start and end:
                query += ' WHERE p.purchase_date BETWEEN ? AND ?'
                params.extend([start, end])
            elif start:
                query += ' WHERE p.purchase_date >= ?'
                params.append(start)
            elif end:
                query += ' WHERE p.purchase_date <= ?'
                params.append(end)
            else:
                # Default to current year if no filter set
                current_year_start = f"{date.today().year}-01-01"
                current_year_end = str(date.today())
                query += ' WHERE p.purchase_date BETWEEN ? AND ?'
                params.extend([current_year_start, current_year_end])
        else:
            # Default to current year if filter fields don't exist yet
            current_year_start = f"{date.today().year}-01-01"
            current_year_end = str(date.today())
            query += ' WHERE p.purchase_date BETWEEN ? AND ?'
            params.extend([current_year_start, current_year_end])
        
        # Don't add ORDER BY - let SearchableTreeview handle sorting
        
        c.execute(query, params)
        
        data = []
        for row in c.fetchall():
            # Color code based on availability
            # Use epsilon comparison to avoid floating point precision issues
            tag = 'available' if row['remaining_amount'] > 0.001 else 'consumed'
            
            # Truncate notes for display (first 50 chars)
            notes_display = (row['notes'] or '')[:50]
            if row['notes'] and len(row['notes']) > 50:
                notes_display += '...'
            
            values = (
                row['user_name'], row['purchase_date'], row['site'], f"${row['amount']:.2f}",
                f"{row['sc_received']:.2f}", f"{row['starting_sc_balance']:.2f}",
                row['card'], f"${row['remaining_amount']:.2f}", notes_display
            )
            
            tags = (tag, str(row['id']))  # Color tag first, then ID
            data.append((values, tags))  # Store with tags for search/sort
        
        conn.close()
        
        # Configure color tags BEFORE populating tree
        self.p_tree.tag_configure('available', foreground='green')
        self.p_tree.tag_configure('consumed', foreground='gray')
        
        # Use SearchableTreeview to populate (this preserves sort)
        if hasattr(self, 'p_searchable'):
            self.p_searchable.set_data(data)
        else:
            # Fallback if SearchableTreeview not available
            for item in self.p_tree.get_children():
                self.p_tree.delete(item)
            for values, tags in data:
                self.p_tree.insert('', 'end', values=values, tags=tags)
    
    def refresh_redemptions(self):
        """Refresh redemptions list with date filter"""
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Build query with optional date filter
        query = '''
            SELECT r.id, u.name as user_name, r.redemption_date, s.name as site, 
                   r.amount, r.receipt_date, rm.name as method, r.is_free_sc, r.processed, r.notes
            FROM redemptions r 
            JOIN sites s ON r.site_id = s.id
            LEFT JOIN redemption_methods rm ON r.redemption_method_id = rm.id
            JOIN users u ON r.user_id = u.id
        '''
        
        params = []
        
        # Apply date filter if set, otherwise default to current year
        if hasattr(self, 'r_filter_start') and hasattr(self, 'r_filter_end'):
            start = self.r_filter_start.get().strip()
            end = self.r_filter_end.get().strip()
            
            if start and end:
                query += ' WHERE r.redemption_date BETWEEN ? AND ?'
                params.extend([start, end])
            elif start:
                query += ' WHERE r.redemption_date >= ?'
                params.append(start)
            elif end:
                query += ' WHERE r.redemption_date <= ?'
                params.append(end)
            else:
                # Default to current year if no filter set
                current_year_start = f"{date.today().year}-01-01"
                current_year_end = str(date.today())
                query += ' WHERE r.redemption_date BETWEEN ? AND ?'
                params.extend([current_year_start, current_year_end])
        else:
            # Default to current year if filter fields don't exist yet
            current_year_start = f"{date.today().year}-01-01"
            current_year_end = str(date.today())
            query += ' WHERE r.redemption_date BETWEEN ? AND ?'
            params.extend([current_year_start, current_year_end])
        
        # Don't add ORDER BY - let SearchableTreeview handle sorting
        
        c.execute(query, params)
        
        data = []
        for row in c.fetchall():
            # Determine status and tags
            is_total_loss = (row['amount'] == 0.0 and not row['is_free_sc'])
            is_pending = (row['receipt_date'] is None or row['receipt_date'] == '')
            is_free_sc = row['is_free_sc']
            
            # Prioritize tags: total_loss > pending > free_sc > normal
            if is_total_loss:
                tag = 'total_loss'
            elif is_pending:
                tag = 'pending'
            elif is_free_sc:
                tag = 'free_sc'
            else:
                tag = 'normal'
            
            # For total losses, show the redemption date as receipt date (no actual payout to receive)
            if is_total_loss:
                receipt_display = row['redemption_date']
            elif is_pending:
                receipt_display = '⏳ PENDING'
            else:
                receipt_display = row['receipt_date'] or ''
            
            # Truncate notes for display
            notes_display = (row['notes'] or '')[:50]
            if row['notes'] and len(row['notes']) > 50:
                notes_display += '...'
            
            values = (
                row['user_name'], 
                row['redemption_date'], 
                row['site'], 
                f"${row['amount']:.2f}" + (" (LOSS)" if is_total_loss else ""),
                receipt_display, 
                row['method'] or '',
                'Yes' if row['is_free_sc'] else 'No',
                '✓' if row['processed'] else '',
                notes_display
            )
            
            tags = (tag, str(row['id']))  # Color tag first, then ID
            data.append((values, tags))  # Store with tags for search/sort
        
        # Configure tag colors
        self.r_tree.tag_configure('normal', font=('Arial', 10))
        self.r_tree.tag_configure('total_loss', font=('Arial', 10, 'bold'), foreground='red')
        self.r_tree.tag_configure('pending', font=('Arial', 10), foreground='orange')
        self.r_tree.tag_configure('free_sc', font=('Arial', 10), foreground='green')
        
        conn.close()
        
        # Use SearchableTreeview to populate (this preserves sort)
        if hasattr(self, 'r_searchable'):
            self.r_searchable.set_data(data)
        else:
            # Fallback if SearchableTreeview not available
            for item in self.r_tree.get_children():
                self.r_tree.delete(item)
            for values, tags in data:
                self.r_tree.insert('', 'end', values=values, tags=tags)
    
    # ========================================================================
    # ADDITIONAL TAB BUILDERS
    # ========================================================================
    
    def build_open_sessions_tab(self):
        """Build open sessions view with double-click to edit"""
        main_frame = ttk.Frame(self.open_sessions_tab, padding=10)
        main_frame.pack(fill='both', expand=True)
        
        # Info label
        info_label = ttk.Label(main_frame, 
                              text="Double-click a session to view details, edit notes, or close as loss", 
                              font=('Arial', 10, 'italic'),
                              foreground='gray')
        info_label.pack(pady=(0, 5))
        
        # Date Range Filter
        filter_section = ttk.LabelFrame(main_frame, text="🎯 Filter", padding=5)
        filter_section.pack(fill='x', pady=(0, 5))
        
        filter_frame = ttk.Frame(filter_section)
        filter_frame.pack(fill='x')
        
        ttk.Label(filter_frame, text="From:").pack(side='left', padx=5)
        
        start_frame = ttk.Frame(filter_frame)
        start_frame.pack(side='left')
        self.os_filter_start = ttk.Entry(start_frame, width=12)
        self.os_filter_start.pack(side='left')
        
        def pick_os_filter_start():
            try:
                from tkcalendar import Calendar
                top = tk.Toplevel(self.root)
                top.title("Select Start Date")
                top.geometry("300x300")
                cal = Calendar(top, selectmode='day', date_pattern='y-mm-dd')
                cal.pack(pady=20)
                def select():
                    self.os_filter_start.delete(0, tk.END)
                    self.os_filter_start.insert(0, cal.get_date())
                    top.destroy()
                ttk.Button(top, text="Select", command=select).pack(pady=10)
                ttk.Button(top, text="Cancel", command=top.destroy).pack()
            except ImportError:
                pass
        
        ttk.Button(start_frame, text="📅", width=3, command=pick_os_filter_start).pack(side='left', padx=2)
        
        ttk.Label(filter_frame, text="To:").pack(side='left', padx=5)
        
        end_frame = ttk.Frame(filter_frame)
        end_frame.pack(side='left')
        self.os_filter_end = ttk.Entry(end_frame, width=12)
        self.os_filter_end.pack(side='left')
        
        def pick_os_filter_end():
            try:
                from tkcalendar import Calendar
                top = tk.Toplevel(self.root)
                top.title("Select End Date")
                top.geometry("300x300")
                cal = Calendar(top, selectmode='day', date_pattern='y-mm-dd')
                cal.pack(pady=20)
                def select():
                    self.os_filter_end.delete(0, tk.END)
                    self.os_filter_end.insert(0, cal.get_date())
                    top.destroy()
                ttk.Button(top, text="Select", command=select).pack(pady=10)
                ttk.Button(top, text="Cancel", command=top.destroy).pack()
            except ImportError:
                pass
        
        ttk.Button(end_frame, text="📅", width=3, command=pick_os_filter_end).pack(side='left', padx=2)
        
        ttk.Button(filter_frame, text="Apply Filter", 
                  command=lambda: self.refresh_open_sessions()).pack(side='left', padx=5)
        ttk.Button(filter_frame, text="Clear", 
                  command=lambda: (
                      self.os_filter_start.delete(0, tk.END),
                      self.os_filter_end.delete(0, tk.END),
                      self.refresh_open_sessions()
                  )).pack(side='left', padx=5)
        
        from datetime import timedelta
        ttk.Button(filter_frame, text="Last 30 Days", 
                  command=lambda: (
                      self.os_filter_start.delete(0, tk.END),
                      self.os_filter_start.insert(0, (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")),
                      self.os_filter_end.delete(0, tk.END),
                      self.os_filter_end.insert(0, date.today().strftime("%Y-%m-%d")),
                      self.refresh_open_sessions()
                  )).pack(side='left', padx=5)
        ttk.Button(filter_frame, text="This Month", 
                  command=lambda: (
                      self.os_filter_start.delete(0, tk.END),
                      self.os_filter_start.insert(0, date.today().replace(day=1).strftime("%Y-%m-%d")),
                      self.os_filter_end.delete(0, tk.END),
                      self.os_filter_end.insert(0, date.today().strftime("%Y-%m-%d")),
                      self.refresh_open_sessions()
                  )).pack(side='left', padx=5)
        ttk.Button(filter_frame, text="This Year", 
                  command=lambda: (
                      self.os_filter_start.delete(0, tk.END),
                      self.os_filter_start.insert(0, date.today().replace(month=1, day=1).strftime("%Y-%m-%d")),
                      self.os_filter_end.delete(0, tk.END),
                      self.os_filter_end.insert(0, date.today().strftime("%Y-%m-%d")),
                      self.refresh_open_sessions()
                  )).pack(side='left', padx=5)
        
        # Treeview frame
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill='both', expand=True)
        
        # Add search frame
        from table_helpers import SearchableTreeview, export_tree_to_csv
        search_frame = ttk.Frame(tree_frame)
        search_frame.pack(fill='x', padx=5, pady=(0, 5))
        
        # Add export button
        ttk.Button(search_frame, text="📤 Export CSV", 
                  command=lambda: export_tree_to_csv(self.os_tree, "open_sessions", self.root),
                  width=15).pack(side='right', padx=5)
        
        cols = ('Site', 'User', 'Start', 'Status', 'Buy-in', 'Redeemed', 'Balance', 'Notes')
        self.os_tree = ttk.Treeview(tree_frame, columns=cols, show='headings', height=20)
        
        for col in cols:
            self.os_tree.heading(col, text=col)
            if col == 'Notes':
                self.os_tree.column(col, width=200)
            else:
                self.os_tree.column(col, width=120)
        
        scroll = ttk.Scrollbar(tree_frame, orient='vertical', command=self.os_tree.yview)
        self.os_tree.configure(yscrollcommand=scroll.set)
        self.os_tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        
        # Bind double-click to open session details popup
        self.os_tree.bind('<Double-1>', self.open_session_details_popup)
        
        # Initialize search/sort
        self.os_searchable = SearchableTreeview(self.os_tree, cols, search_frame)
    
    def build_closed_sessions_tab(self):
        """Build closed/tax sessions view - click arrows to expand/collapse details"""
        main_frame = ttk.Frame(self.realized_tab, padding=10)
        main_frame.pack(fill='both', expand=True)
        
        
        # Date Range Filter
        filter_section = ttk.LabelFrame(main_frame, text="🎯 Filters", padding=5)
        filter_section.pack(fill='x', pady=(0, 5))
        
        filter_frame = ttk.Frame(filter_section)
        filter_frame.pack(fill='x')
        
        # First row: Date filters and quick buttons
        date_row = ttk.Frame(filter_frame)
        date_row.pack(fill='x', pady=(0, 5))
        
        # Start Date
        start_frame = ttk.Frame(date_row)
        start_frame.pack(side='left', padx=5)
        ttk.Label(start_frame, text="From:").pack(side='left', padx=(0, 5))
        self.cs_filter_start = ttk.Entry(start_frame, width=12)
        self.cs_filter_start.pack(side='left')
        
        def pick_cs_filter_start():
            try:
                from tkcalendar import Calendar
                top = tk.Toplevel(self.root)
                top.title("Select Start Date")
                top.geometry("300x300")
                cal = Calendar(top, selectmode='day', date_pattern='y-mm-dd')
                cal.pack(pady=20)
                def select():
                    self.cs_filter_start.delete(0, tk.END)
                    self.cs_filter_start.insert(0, cal.get_date())
                    top.destroy()
                ttk.Button(top, text="Select", command=select).pack(pady=10)
                ttk.Button(top, text="Cancel", command=top.destroy).pack()
            except ImportError:
                pass
        
        ttk.Button(start_frame, text="📅", width=3, command=pick_cs_filter_start).pack(side='left', padx=2)
        
        # End Date
        end_frame = ttk.Frame(date_row)
        end_frame.pack(side='left', padx=5)
        ttk.Label(end_frame, text="To:").pack(side='left', padx=(0, 5))
        self.cs_filter_end = ttk.Entry(end_frame, width=12)
        self.cs_filter_end.pack(side='left')
        
        def pick_cs_filter_end():
            try:
                from tkcalendar import Calendar
                top = tk.Toplevel(self.root)
                top.title("Select End Date")
                top.geometry("300x300")
                cal = Calendar(top, selectmode='day', date_pattern='y-mm-dd')
                cal.pack(pady=20)
                def select():
                    self.cs_filter_end.delete(0, tk.END)
                    self.cs_filter_end.insert(0, cal.get_date())
                    top.destroy()
                ttk.Button(top, text="Select", command=select).pack(pady=10)
                ttk.Button(top, text="Cancel", command=top.destroy).pack()
            except ImportError:
                pass
        
        ttk.Button(end_frame, text="📅", width=3, command=pick_cs_filter_end).pack(side='left', padx=2)
        
        # Quick date buttons
        from datetime import timedelta
        ttk.Button(date_row, text="Today", 
                  command=lambda: (
                      self.cs_filter_start.delete(0, tk.END),
                      self.cs_filter_start.insert(0, date.today().strftime("%Y-%m-%d")),
                      self.cs_filter_end.delete(0, tk.END),
                      self.cs_filter_end.insert(0, date.today().strftime("%Y-%m-%d")),
                      self.refresh_closed_sessions()
                  )).pack(side='left', padx=5)
        ttk.Button(date_row, text="Last 30 Days", 
                  command=lambda: (
                      self.cs_filter_start.delete(0, tk.END),
                      self.cs_filter_start.insert(0, (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")),
                      self.cs_filter_end.delete(0, tk.END),
                      self.cs_filter_end.insert(0, date.today().strftime("%Y-%m-%d")),
                      self.refresh_closed_sessions()
                  )).pack(side='left', padx=5)
        ttk.Button(date_row, text="This Month", 
                  command=lambda: (
                      self.cs_filter_start.delete(0, tk.END),
                      self.cs_filter_start.insert(0, date.today().replace(day=1).strftime("%Y-%m-%d")),
                      self.cs_filter_end.delete(0, tk.END),
                      self.cs_filter_end.insert(0, date.today().strftime("%Y-%m-%d")),
                      self.refresh_closed_sessions()
                  )).pack(side='left', padx=5)
        ttk.Button(date_row, text="This Year", 
                  command=lambda: (
                      self.cs_filter_start.delete(0, tk.END),
                      self.cs_filter_start.insert(0, date.today().replace(month=1, day=1).strftime("%Y-%m-%d")),
                      self.cs_filter_end.delete(0, tk.END),
                      self.cs_filter_end.insert(0, date.today().strftime("%Y-%m-%d")),
                      self.refresh_closed_sessions()
                  )).pack(side='left', padx=5)
        
        # Second row: Site/User Filters and Apply/Clear buttons
        filter_frame2 = ttk.Frame(filter_section)
        filter_frame2.pack(fill='x', pady=(5, 0))
        
        ttk.Label(filter_frame2, text="Sites:").pack(side='left', padx=(5, 5))
        ttk.Button(filter_frame2, text="Filter Sites...", 
                  command=self.show_cs_site_filter, width=15).pack(side='left', padx=(0, 10))
        self.cs_site_filter_label = ttk.Label(filter_frame2, text="All", foreground='gray')
        self.cs_site_filter_label.pack(side='left', padx=(0, 15))
        
        ttk.Label(filter_frame2, text="Users:").pack(side='left', padx=(5, 5))
        ttk.Button(filter_frame2, text="Filter Users...", 
                  command=self.show_cs_user_filter, width=15).pack(side='left', padx=(0, 10))
        self.cs_user_filter_label = ttk.Label(filter_frame2, text="All", foreground='gray')
        self.cs_user_filter_label.pack(side='left', padx=(0, 10))
        
        # Apply and Clear buttons on second row
        ttk.Button(filter_frame2, text="Apply", 
                  command=lambda: self.refresh_closed_sessions(), width=10).pack(side='left', padx=5)
        ttk.Button(filter_frame2, text="Clear", 
                  command=self.clear_cs_filters, width=10).pack(side='left', padx=5)
        
        # Initialize filter sets (empty = all)
        self.cs_selected_sites = set()  # Empty = all sites
        self.cs_selected_users = set()  # Empty = all users
        
        # Search frame for closed sessions
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill='x', pady=(5, 5))
        
        ttk.Label(search_frame, text="Search:").pack(side='left', padx=(0, 5))
        self.cs_search_var = tk.StringVar()
        self.cs_search_entry = ttk.Entry(search_frame, textvariable=self.cs_search_var, width=30)
        self.cs_search_entry.pack(side='left', padx=(0, 10))
        
        ttk.Button(search_frame, text="Clear Search", 
                  command=lambda: (self.cs_search_var.set(''), self.refresh_closed_sessions()), 
                  width=12).pack(side='left')
        
        # Add export button
        from table_helpers import export_tree_to_csv
        ttk.Button(search_frame, text="📤 Export CSV", 
                  command=lambda: export_tree_to_csv(self.cs_tree, "closed_sessions", self.root),
                  width=15).pack(side='right', padx=5)
        
        # Add Expand/Collapse All buttons
        ttk.Button(search_frame, text="⬇️ Expand All", 
                  command=self.expand_all_closed_sessions,
                  width=15).pack(side='right', padx=5)
        
        ttk.Button(search_frame, text="⬆️ Collapse All", 
                  command=self.collapse_all_closed_sessions,
                  width=15).pack(side='right', padx=5)
        
        # Add Notes button
        ttk.Button(search_frame, text="📝 Add/Edit Notes", 
                  command=self.edit_closed_session_notes,
                  width=18).pack(side='right', padx=5)
        
        # Bind search to refresh (using trace_add for Tcl 9 compatibility)
        self.cs_search_var.trace_add('write', lambda *args: self.refresh_closed_sessions())
        
        # Sessions list frame
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill='both', expand=True)
        
        cols = ('Date', 'Site', 'User', 'Cost Basis', 'Payout', 'Net P/L', 'Notes')
        self.cs_tree = ttk.Treeview(list_frame, columns=cols, show='tree headings', height=20)
        
        # Track sort state for closed sessions
        self.cs_sort_column = None
        self.cs_sort_reverse = False
        
        # Make ALL columns sortable
        for col in cols:
            self.cs_tree.heading(col, text=col, 
                                command=lambda c=col: self._sort_closed_sessions(c))
            
            # Set column width - Notes column narrower for icon
            if col == 'Notes':
                self.cs_tree.column(col, width=50)
            else:
                self.cs_tree.column(col, width=130)
        
        # Make the tree column narrower since it's just for expand/collapse
        self.cs_tree.column('#0', width=30)
        
        scroll = ttk.Scrollbar(list_frame, orient='vertical', command=self.cs_tree.yview)
        self.cs_tree.configure(yscrollcommand=scroll.set)
        self.cs_tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        
        # Bind double-click to edit notes
        self.cs_tree.bind('<Double-Button-1>', lambda e: self.edit_closed_session_notes())
        
        # Initialize SearchableTreeview for filtering
        from table_helpers import SearchableTreeview
        self.cs_searchable = SearchableTreeview(self.cs_tree, cols, search_frame, enable_filters=True)
    
    def build_expenses_tab(self):
        """Build expenses tab with Schedule C categories"""
        
        # Date Range Filter
        filter_frame = ttk.LabelFrame(self.expenses_tab, text="🎯 Filter", padding=5)
        filter_frame.pack(fill='x', padx=10, pady=(10, 0))
        
        ttk.Label(filter_frame, text="From:").pack(side='left', padx=5)
        
        start_frame = ttk.Frame(filter_frame)
        start_frame.pack(side='left')
        self.e_filter_start = ttk.Entry(start_frame, width=12)
        self.e_filter_start.pack(side='left')
        
        def pick_e_filter_start():
            try:
                from tkcalendar import Calendar
                top = tk.Toplevel(self.root)
                top.title("Select Start Date")
                top.geometry("300x300")
                cal = Calendar(top, selectmode='day', date_pattern='y-mm-dd')
                cal.pack(pady=20)
                def select():
                    self.e_filter_start.delete(0, tk.END)
                    self.e_filter_start.insert(0, cal.get_date())
                    top.destroy()
                ttk.Button(top, text="Select", command=select).pack(pady=10)
                ttk.Button(top, text="Cancel", command=top.destroy).pack()
            except ImportError:
                pass
        
        ttk.Button(start_frame, text="📅", width=3, command=pick_e_filter_start).pack(side='left', padx=2)
        
        ttk.Label(filter_frame, text="To:").pack(side='left', padx=5)
        
        end_frame = ttk.Frame(filter_frame)
        end_frame.pack(side='left')
        self.e_filter_end = ttk.Entry(end_frame, width=12)
        self.e_filter_end.pack(side='left')
        
        def pick_e_filter_end():
            try:
                from tkcalendar import Calendar
                top = tk.Toplevel(self.root)
                top.title("Select End Date")
                top.geometry("300x300")
                cal = Calendar(top, selectmode='day', date_pattern='y-mm-dd')
                cal.pack(pady=20)
                def select():
                    self.e_filter_end.delete(0, tk.END)
                    self.e_filter_end.insert(0, cal.get_date())
                    top.destroy()
                ttk.Button(top, text="Select", command=select).pack(pady=10)
                ttk.Button(top, text="Cancel", command=top.destroy).pack()
            except ImportError:
                pass
        
        ttk.Button(end_frame, text="📅", width=3, command=pick_e_filter_end).pack(side='left', padx=2)
        
        ttk.Button(filter_frame, text="Apply", 
                  command=lambda: self.refresh_expenses()).pack(side='left', padx=5)
        ttk.Button(filter_frame, text="Clear", 
                  command=lambda: (
                      self.e_filter_start.delete(0, tk.END),
                      self.e_filter_end.delete(0, tk.END),
                      self.refresh_expenses()
                  )).pack(side='left', padx=5)
        
        from datetime import timedelta
        ttk.Button(filter_frame, text="Today", 
                  command=lambda: (
                      self.e_filter_start.delete(0, tk.END),
                      self.e_filter_start.insert(0, date.today().strftime("%Y-%m-%d")),
                      self.e_filter_end.delete(0, tk.END),
                      self.e_filter_end.insert(0, date.today().strftime("%Y-%m-%d")),
                      self.refresh_expenses()
                  )).pack(side='left', padx=5)
        ttk.Button(filter_frame, text="Last 30 Days", 
                  command=lambda: (
                      self.e_filter_start.delete(0, tk.END),
                      self.e_filter_start.insert(0, (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")),
                      self.e_filter_end.delete(0, tk.END),
                      self.e_filter_end.insert(0, date.today().strftime("%Y-%m-%d")),
                      self.refresh_expenses()
                  )).pack(side='left', padx=5)
        ttk.Button(filter_frame, text="This Month", 
                  command=lambda: (
                      self.e_filter_start.delete(0, tk.END),
                      self.e_filter_start.insert(0, date.today().replace(day=1).strftime("%Y-%m-%d")),
                      self.e_filter_end.delete(0, tk.END),
                      self.e_filter_end.insert(0, date.today().strftime("%Y-%m-%d")),
                      self.refresh_expenses()
                  )).pack(side='left', padx=5)
        ttk.Button(filter_frame, text="This Year", 
                  command=lambda: (
                      self.e_filter_start.delete(0, tk.END),
                      self.e_filter_start.insert(0, date.today().replace(month=1, day=1).strftime("%Y-%m-%d")),
                      self.e_filter_end.delete(0, tk.END),
                      self.e_filter_end.insert(0, date.today().strftime("%Y-%m-%d")),
                      self.refresh_expenses()
                  )).pack(side='left', padx=5)
        
        form = ttk.LabelFrame(self.expenses_tab, text="Add Expense", padding=10)
        form.pack(fill='x', padx=10, pady=10)
        
        # Row 0
        ttk.Label(form, text="Date:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        
        date_frame = ttk.Frame(form)
        date_frame.grid(row=0, column=1, sticky='w', padx=5, pady=5)
        
        self.e_date = ttk.Entry(date_frame, width=12)
        self.e_date.insert(0, date.today().strftime("%Y-%m-%d"))
        self.e_date.pack(side='left')
        
        def pick_expense_date():
            try:
                from tkcalendar import Calendar
                top = tk.Toplevel(self.root)
                top.title("Select Expense Date")
                top.geometry("300x300")
                
                cal = Calendar(top, selectmode='day', date_pattern='y-mm-dd')
                cal.pack(pady=20)
                
                def select_date():
                    self.e_date.delete(0, tk.END)
                    self.e_date.insert(0, cal.get_date())
                    top.destroy()
                
                ttk.Button(top, text="Select", command=select_date).pack(pady=10)
                ttk.Button(top, text="Cancel", command=top.destroy).pack()
            except ImportError:
                self.e_date.delete(0, tk.END)
                self.e_date.insert(0, date.today().strftime("%Y-%m-%d"))
        
        ttk.Button(date_frame, text="📅", width=3, command=pick_expense_date).pack(side='left', padx=2)
        
        ttk.Label(form, text="Amount:").grid(row=0, column=2, sticky='w', padx=5, pady=5)
        self.e_amount = ttk.Entry(form, width=15)
        self.e_amount.grid(row=0, column=3, sticky='w', padx=5, pady=5)
        
        # Row 1
        ttk.Label(form, text="Vendor:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.e_vendor = ttk.Entry(form, width=20)
        self.e_vendor.grid(row=1, column=1, sticky='w', padx=5, pady=5)
        
        ttk.Label(form, text="User (optional):").grid(row=1, column=2, sticky='w', padx=5, pady=5)
        self.e_user = ttk.Combobox(form, width=20, state='readonly')
        self.e_user.grid(row=1, column=3, sticky='w', padx=5, pady=5)
        
        # Row 2 - Category
        ttk.Label(form, text="Category:").grid(row=2, column=0, sticky='w', padx=5, pady=5)
        self.e_category = ttk.Combobox(form, width=30, state='readonly')
        self.e_category['values'] = [
            'Advertising',
            'Car and Truck Expenses',
            'Commissions and Fees',
            'Contract Labor',
            'Depreciation',
            'Insurance (Business)',
            'Interest (Mortgage/Other)',
            'Legal and Professional Services',
            'Office Expense',
            'Rent or Lease (Vehicles/Equipment)',
            'Rent or Lease (Other Business Property)',
            'Repairs and Maintenance',
            'Supplies',
            'Taxes and Licenses',
            'Travel',
            'Meals (Deductible)',
            'Utilities',
            'Wages (Not Contract Labor)',
            'Other Expenses'
        ]
        self.e_category.current(18)  # Default to "Other Expenses"
        self.e_category.grid(row=2, column=1, columnspan=3, sticky='w', padx=5, pady=5)
        
        # Row 3 - Description
        ttk.Label(form, text="Description:").grid(row=3, column=0, sticky='w', padx=5, pady=5)
        self.e_desc = ttk.Entry(form, width=50)
        self.e_desc.grid(row=3, column=1, columnspan=3, sticky='w', padx=5, pady=5)
        
        # Row 4 - Buttons (smart Save button)
        btn_frame = ttk.Frame(form)
        btn_frame.grid(row=4, column=0, columnspan=4, pady=10)
        
        ttk.Button(btn_frame, text="Save", command=self.smart_save_expense, width=12).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Delete", command=self.delete_expense, width=12).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Clear", command=self.clear_expense_form, width=12).pack(side='left', padx=5)
        
        # Escape key clears current field
        def clear_current_field(e):
            widget = self.root.focus_get()
            if isinstance(widget, (ttk.Entry, tk.Entry, ttk.Combobox)):
                if isinstance(widget, ttk.Combobox):
                    widget.set('')
                else:
                    widget.delete(0, tk.END)
        
        form.bind('<Escape>', clear_current_field)
        
        # List frame
        list_frame = ttk.LabelFrame(self.expenses_tab, text="Expenses", padding=10)
        list_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Add search frame
        from table_helpers import SearchableTreeview, export_tree_to_csv
        search_frame = ttk.Frame(list_frame)
        search_frame.pack(fill='x', padx=5, pady=(0, 5))
        
        # Add export button
        ttk.Button(search_frame, text="📤 Export CSV", 
                  command=lambda: export_tree_to_csv(self.e_tree, "expenses", self.root),
                  width=15).pack(side='right', padx=5)
        
        cols = ('Date', 'Category', 'Vendor', 'User', 'Amount', 'Description')
        self.e_tree = ttk.Treeview(list_frame, columns=cols, show='headings', height=15)
        
        self.e_tree.heading('Date', text='Date')
        self.e_tree.heading('Category', text='Schedule C Category')
        self.e_tree.heading('Vendor', text='Vendor')
        self.e_tree.heading('User', text='User')
        self.e_tree.heading('Amount', text='Amount')
        self.e_tree.heading('Description', text='Description')
        
        self.e_tree.column('Date', width=100)
        self.e_tree.column('Category', width=180)
        self.e_tree.column('Vendor', width=130)
        self.e_tree.column('User', width=100)
        self.e_tree.column('Amount', width=100)
        self.e_tree.column('Description', width=200)
        
        scroll = ttk.Scrollbar(list_frame, orient='vertical', command=self.e_tree.yview)
        self.e_tree.configure(yscrollcommand=scroll.set)
        self.e_tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        
        # Initialize search/sort
        self.e_searchable = SearchableTreeview(self.e_tree, cols, search_frame)
        
        # Enable multi-select
        from table_helpers import enable_multi_select
        enable_multi_select(self.e_tree)
        
        # Bind double-click to edit
        self.e_tree.bind('<Double-Button-1>', self.edit_expense)
    
    def clear_expense_form(self):
        """Clear expense form"""
        self.e_date.delete(0, tk.END)
        self.e_date.insert(0, date.today().strftime("%Y-%m-%d"))
        self.e_amount.delete(0, tk.END)
        self.e_vendor.delete(0, tk.END)
        self.e_user.set('')  # Clear user selection
        self.e_desc.delete(0, tk.END)
        self.e_category.current(18)  # Reset to "Other Expenses"
        # Clear any tree selection
        for item in self.e_tree.selection():
            self.e_tree.selection_remove(item)
    
    def edit_expense(self, event=None):
        """Load expense into form for editing (double-click)"""
        sel = self.e_tree.selection()
        if not sel:
            return
        
        # Check if multiple selected
        if len(sel) > 1:
            messagebox.showwarning("Multiple Selection", 
                "Please select only one expense to edit.\n\n"
                "Tip: Use Ctrl+Click or Shift+Click to select multiple items for deletion.")
            return
        
        eid = self.e_tree.item(sel[0])['tags'][0]
        
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute('''
            SELECT e.*, u.name as user_name
            FROM expenses e
            LEFT JOIN users u ON e.user_id = u.id
            WHERE e.id = ?
        ''', (eid,))
        exp = c.fetchone()
        conn.close()
        
        if exp:
            self.e_date.delete(0, tk.END)
            self.e_date.insert(0, exp['expense_date'])
            self.e_amount.delete(0, tk.END)
            self.e_amount.insert(0, str(exp['amount']))
            self.e_vendor.delete(0, tk.END)
            self.e_vendor.insert(0, exp['vendor'])
            self.e_user.set(exp['user_name'] or '')  # Set user
            self.e_desc.delete(0, tk.END)
            if exp['description']:
                self.e_desc.insert(0, exp['description'])
            
            # Set category (handle None/null values)
            category = exp['category'] if exp['category'] else 'Other Expenses'
            try:
                idx = list(self.e_category['values']).index(category)
                self.e_category.current(idx)
            except ValueError:
                self.e_category.current(18)  # Default to Other Expenses
    
    def build_reports_tab(self):
        """Build comprehensive reports dashboard with sub-tabs"""
        # Create notebook for sub-tabs (like Setup tab)
        nb = ttk.Notebook(self.reports_tab)
        nb.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create sub-tab frames
        overview_frame = ttk.Frame(nb)
        monthly_frame = ttk.Frame(nb)
        schedc_frame = ttk.Frame(nb)
        export_frame = ttk.Frame(nb)
        
        nb.add(overview_frame, text="Overview")
        nb.add(monthly_frame, text="Monthly & Financial")
        nb.add(schedc_frame, text="Tax Planning")
        nb.add(export_frame, text="Export CSVs")
        
        # Build each sub-tab
        self.build_overview_subtab(overview_frame)
        self.build_monthly_subtab(monthly_frame)
        self.build_schedc_subtab(schedc_frame)
        self.build_export_subtab(export_frame)
    
    def build_overview_subtab(self, parent):
        """Overview: Performance Dashboard with Charts and Metrics"""
        # Create scrollable canvas
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        def configure_canvas_width(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind('<Configure>', configure_canvas_width)
        
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        frame = ttk.Frame(scrollable_frame, padding=20)
        frame.pack(fill='x')
        
        # Title
        ttk.Label(frame, text="Performance Overview", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 10))
        
        # Filters Section
        filter_section = ttk.LabelFrame(frame, text="🎯 Filters", padding=10)
        filter_section.pack(fill='x', pady=(0, 15))
        
        # Row 1: Date filters
        date_row = ttk.Frame(filter_section)
        date_row.pack(fill='x', pady=(0, 5))
        
        ttk.Label(date_row, text="From:").pack(side='left', padx=5)
        self.rep_filter_start = ttk.Entry(date_row, width=12)
        self.rep_filter_start.pack(side='left')
        
        def pick_rep_filter_start():
            try:
                from tkcalendar import Calendar
                top = tk.Toplevel(self.root)
                top.title("Select Start Date")
                top.geometry("300x300")
                cal = Calendar(top, selectmode='day', date_pattern='y-mm-dd')
                cal.pack(pady=20)
                def select():
                    self.rep_filter_start.delete(0, tk.END)
                    self.rep_filter_start.insert(0, cal.get_date())
                    top.destroy()
                ttk.Button(top, text="Select", command=select).pack(pady=10)
                ttk.Button(top, text="Cancel", command=top.destroy).pack()
            except ImportError:
                pass
        
        ttk.Button(date_row, text="📅", width=3, command=pick_rep_filter_start).pack(side='left', padx=2)
        
        ttk.Label(date_row, text="To:").pack(side='left', padx=(10, 5))
        self.rep_filter_end = ttk.Entry(date_row, width=12)
        self.rep_filter_end.pack(side='left')
        
        def pick_rep_filter_end():
            try:
                from tkcalendar import Calendar
                top = tk.Toplevel(self.root)
                top.title("Select End Date")
                top.geometry("300x300")
                cal = Calendar(top, selectmode='day', date_pattern='y-mm-dd')
                cal.pack(pady=20)
                def select():
                    self.rep_filter_end.delete(0, tk.END)
                    self.rep_filter_end.insert(0, cal.get_date())
                    top.destroy()
                ttk.Button(top, text="Select", command=select).pack(pady=10)
                ttk.Button(top, text="Cancel", command=top.destroy).pack()
            except ImportError:
                pass
        
        ttk.Button(date_row, text="📅", width=3, command=pick_rep_filter_end).pack(side='left', padx=(2, 15))
        
        # Quick date buttons
        ttk.Button(date_row, text="Today", 
                  command=lambda: (
                      self.rep_filter_start.delete(0, tk.END),
                      self.rep_filter_start.insert(0, date.today().strftime("%Y-%m-%d")),
                      self.rep_filter_end.delete(0, tk.END),
                      self.rep_filter_end.insert(0, date.today().strftime("%Y-%m-%d")),
                      self.refresh_reports()
                  ), width=12).pack(side='left', padx=2)
        ttk.Button(date_row, text="Last 30 Days", 
                  command=lambda: (
                      self.rep_filter_start.delete(0, tk.END),
                      self.rep_filter_start.insert(0, (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")),
                      self.rep_filter_end.delete(0, tk.END),
                      self.rep_filter_end.insert(0, date.today().strftime("%Y-%m-%d")),
                      self.refresh_reports()
                  ), width=12).pack(side='left', padx=2)
        ttk.Button(date_row, text="This Month", 
                  command=lambda: (
                      self.rep_filter_start.delete(0, tk.END),
                      self.rep_filter_start.insert(0, date.today().replace(day=1).strftime("%Y-%m-%d")),
                      self.rep_filter_end.delete(0, tk.END),
                      self.rep_filter_end.insert(0, date.today().strftime("%Y-%m-%d")),
                      self.refresh_reports()
                  ), width=12).pack(side='left', padx=2)
        ttk.Button(date_row, text="This Year", 
                  command=lambda: (
                      self.rep_filter_start.delete(0, tk.END),
                      self.rep_filter_start.insert(0, date.today().replace(month=1, day=1).strftime("%Y-%m-%d")),
                      self.rep_filter_end.delete(0, tk.END),
                      self.rep_filter_end.insert(0, date.today().strftime("%Y-%m-%d")),
                      self.refresh_reports()
                  ), width=12).pack(side='left', padx=2)
        
        # Row 2: Site and User filters with checkbox style
        filter_row = ttk.Frame(filter_section)
        filter_row.pack(fill='x', pady=(5, 5))
        
        ttk.Label(filter_row, text="Sites:").pack(side='left', padx=(0, 5))
        ttk.Button(filter_row, text="Filter Sites...", 
                  command=self.show_rep_site_filter, width=15).pack(side='left', padx=(0, 10))
        self.rep_site_filter_label = ttk.Label(filter_row, text="All", foreground='gray')
        self.rep_site_filter_label.pack(side='left', padx=(0, 15))
        
        ttk.Label(filter_row, text="Users:").pack(side='left', padx=(0, 5))
        ttk.Button(filter_row, text="Filter Users...", 
                  command=self.show_rep_user_filter, width=15).pack(side='left', padx=(0, 10))
        self.rep_user_filter_label = ttk.Label(filter_row, text="All", foreground='gray')
        self.rep_user_filter_label.pack(side='left', padx=(0, 15))
        
        # Initialize filter sets
        self.rep_selected_sites = set()
        self.rep_selected_users = set()
        
        # Apply/Clear buttons
        ttk.Button(filter_row, text="Apply", 
                  command=lambda: self.refresh_reports(), 
                  width=12).pack(side='left', padx=5)
        ttk.Button(filter_row, text="Clear", 
                  command=lambda: (
                      self.rep_filter_start.delete(0, tk.END),
                      self.rep_filter_end.delete(0, tk.END),
                      setattr(self, 'rep_selected_sites', set()),
                      setattr(self, 'rep_selected_users', set()),
                      self.rep_site_filter_label.config(text="All", foreground='gray'),
                      self.rep_user_filter_label.config(text="All", foreground='gray'),
                      self.refresh_reports()
                  ), width=12).pack(side='left', padx=5)
        
        # Set default dates to current year
        self.rep_filter_start.insert(0, date.today().replace(month=1, day=1).strftime("%Y-%m-%d"))
        self.rep_filter_end.insert(0, date.today().strftime("%Y-%m-%d"))
        
        # === SECTION 1: SESSION METRICS ===
        session_frame = ttk.LabelFrame(frame, text="🎰 Session Performance", padding=15)
        session_frame.pack(fill='x', pady=(0, 15))
        
        # Create 2 columns for metrics
        left_col = ttk.Frame(session_frame)
        left_col.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        right_col = ttk.Frame(session_frame)
        right_col.pack(side='left', fill='both', expand=True)
        
        self.rep_session_labels = {}
        
        # Left column metrics
        for metric in ['Total Sessions', 'Win Rate', 'Average Session P/L']:
            metric_frame = ttk.Frame(left_col)
            metric_frame.pack(fill='x', pady=5)
            ttk.Label(metric_frame, text=metric + ":", font=('Arial', 10)).pack(side='left')
            label = ttk.Label(metric_frame, text="--", font=('Arial', 10, 'bold'))
            label.pack(side='right')
            self.rep_session_labels[metric] = label
        
        # Right column metrics
        for metric in ['Best Session', 'Worst Session', 'Current Streak']:
            metric_frame = ttk.Frame(right_col)
            metric_frame.pack(fill='x', pady=5)
            ttk.Label(metric_frame, text=metric + ":", font=('Arial', 10)).pack(side='left')
            label = ttk.Label(metric_frame, text="--", font=('Arial', 10, 'bold'))
            label.pack(side='right')
            self.rep_session_labels[metric] = label
        
        # === SECTION 2: TAX METRICS ===
        tax_frame = ttk.LabelFrame(frame, text="💰 Tax Metrics", padding=15)
        tax_frame.pack(fill='x', pady=(0, 15))
        
        tax_left = ttk.Frame(tax_frame)
        tax_left.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        tax_right = ttk.Frame(tax_frame)
        tax_right.pack(side='left', fill='both', expand=True)
        
        self.rep_tax_labels = {}
        
        # Left column
        for metric in ['Total Net Taxable', 'Total Delta Total (SC)', 'Total Delta Redeemable (SC)']:
            metric_frame = ttk.Frame(tax_left)
            metric_frame.pack(fill='x', pady=5)
            ttk.Label(metric_frame, text=metric + ":", font=('Arial', 10)).pack(side='left')
            label = ttk.Label(metric_frame, text="$0.00", font=('Arial', 10, 'bold'))
            label.pack(side='right')
            self.rep_tax_labels[metric] = label
        
        # Right column
        for metric in ['Unrealized Value', 'Avg Profit Per Day']:
            metric_frame = ttk.Frame(tax_right)
            metric_frame.pack(fill='x', pady=5)
            ttk.Label(metric_frame, text=metric + ":", font=('Arial', 10)).pack(side='left')
            label = ttk.Label(metric_frame, text="$0.00", font=('Arial', 10, 'bold'))
            label.pack(side='right')
            self.rep_tax_labels[metric] = label
        
        # === SECTION 3: ROI & EFFICIENCY ===
        roi_frame = ttk.LabelFrame(frame, text="📊 ROI & Efficiency", padding=15)
        roi_frame.pack(fill='x', pady=(0, 15))
        
        roi_left = ttk.Frame(roi_frame)
        roi_left.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        roi_right = ttk.Frame(roi_frame)
        roi_right.pack(side='left', fill='both', expand=True)
        
        self.rep_roi_labels = {}
        
        # Left column
        for metric in ['Overall ROI %', 'Average Session Duration']:
            metric_frame = ttk.Frame(roi_left)
            metric_frame.pack(fill='x', pady=5)
            ttk.Label(metric_frame, text=metric + ":", font=('Arial', 10)).pack(side='left')
            label = ttk.Label(metric_frame, text="--", font=('Arial', 10, 'bold'))
            label.pack(side='right')
            self.rep_roi_labels[metric] = label
        
        # Right column
        for metric in ['Hourly Win Rate', 'Win Rate by Game Type']:
            metric_frame = ttk.Frame(roi_right)
            metric_frame.pack(fill='x', pady=5)
            ttk.Label(metric_frame, text=metric + ":", font=('Arial', 10)).pack(side='left')
            label = ttk.Label(metric_frame, text="--", font=('Arial', 10, 'bold'))
            label.pack(side='right')
            self.rep_roi_labels[metric] = label
        
        # === SECTION 4: CHARTS ===
        charts_frame = ttk.LabelFrame(frame, text="📈 Performance Charts", padding=15)
        charts_frame.pack(fill='x', pady=(0, 15))
        
        # Chart container - will hold matplotlib figures
        self.rep_chart_frame = ttk.Frame(charts_frame)
        self.rep_chart_frame.pack(fill='both', expand=True)
        
        # === SECTION 5: PERFORMANCE BY SITE TABLE ===
        site_frame = ttk.LabelFrame(frame, text="🎯 Performance by Site (Filtered by User selection above)", padding=15)
        site_frame.pack(fill='both', expand=True, pady=(0, 15))
        
        # Search frame for site table
        site_search_frame = ttk.Frame(site_frame)
        site_search_frame.pack(fill='x', pady=(0, 5))
        
        # Tree for site performance
        tree_frame = ttk.Frame(site_frame)
        tree_frame.pack(fill='both', expand=True)
        
        cols = ('Site', 'Sessions', 'Win Rate', 'Total P/L', 'Avg P/L', 'ROI %')
        self.rep_site_tree = ttk.Treeview(tree_frame, columns=cols, show='headings', height=10)
        
        for col in cols:
            self.rep_site_tree.heading(col, text=col, command=lambda c=col: self.sort_rep_site_column(c))
            if col in ('Total P/L', 'Avg P/L'):
                self.rep_site_tree.column(col, width=120)
            elif col in ('Win Rate', 'ROI %'):
                self.rep_site_tree.column(col, width=80)
            elif col == 'Sessions':
                self.rep_site_tree.column(col, width=70)
            else:
                self.rep_site_tree.column(col, width=100)
        
        scroll = ttk.Scrollbar(tree_frame, orient='vertical', command=self.rep_site_tree.yview)
        self.rep_site_tree.configure(yscrollcommand=scroll.set)
        self.rep_site_tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        
        # Color tags
        self.rep_site_tree.tag_configure('profit', foreground='green')
        self.rep_site_tree.tag_configure('loss', foreground='red')
        
        # Initialize searchable
        from table_helpers import SearchableTreeview
        self.rep_site_searchable = SearchableTreeview(self.rep_site_tree, cols, site_search_frame)
        
        # Initialize sort tracking
        self.rep_site_sort_column = None
        self.rep_site_sort_reverse = False
    def build_monthly_subtab(self, parent):
        """Monthly Performance and Financial Summary"""
        # Create scrollable canvas
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        # Create window with width constraint
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        # Bind canvas width to constrain the window width
        def configure_canvas_width(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind('<Configure>', configure_canvas_width)
        
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Now use scrollable_frame - don't expand, just fill horizontally
        frame = ttk.Frame(scrollable_frame, padding=20)
        frame.pack(fill='x')
        
        ttk.Label(frame, text="Monthly & Financial Summary", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 10))
        
        # Filters Section
        filter_section = ttk.LabelFrame(frame, text="🎯 Filters", padding=10)
        filter_section.pack(fill='x', pady=(0, 15))
        
        # Row 1: Date filters
        date_row = ttk.Frame(filter_section)
        date_row.pack(fill='x', pady=(0, 5))
        
        ttk.Label(date_row, text="From:").pack(side='left', padx=5)
        self.monthly_filter_start = ttk.Entry(date_row, width=12)
        self.monthly_filter_start.pack(side='left')
        
        def pick_monthly_filter_start():
            try:
                from tkcalendar import Calendar
                top = tk.Toplevel(self.root)
                top.title("Select Start Date")
                top.geometry("300x300")
                cal = Calendar(top, selectmode='day', date_pattern='y-mm-dd')
                cal.pack(pady=20)
                def select():
                    self.monthly_filter_start.delete(0, tk.END)
                    self.monthly_filter_start.insert(0, cal.get_date())
                    top.destroy()
                ttk.Button(top, text="Select", command=select).pack(pady=10)
                ttk.Button(top, text="Cancel", command=top.destroy).pack()
            except ImportError:
                pass
        
        ttk.Button(date_row, text="📅", width=3, command=pick_monthly_filter_start).pack(side='left', padx=2)
        
        ttk.Label(date_row, text="To:").pack(side='left', padx=(10, 5))
        self.monthly_filter_end = ttk.Entry(date_row, width=12)
        self.monthly_filter_end.pack(side='left', padx=(0, 15))
        
        def pick_monthly_filter_end():
            try:
                from tkcalendar import Calendar
                top = tk.Toplevel(self.root)
                top.title("Select End Date")
                top.geometry("300x300")
                cal = Calendar(top, selectmode='day', date_pattern='y-mm-dd')
                cal.pack(pady=20)
                def select():
                    self.monthly_filter_end.delete(0, tk.END)
                    self.monthly_filter_end.insert(0, cal.get_date())
                    top.destroy()
                ttk.Button(top, text="Select", command=select).pack(pady=10)
                ttk.Button(top, text="Cancel", command=top.destroy).pack()
            except ImportError:
                pass
        
        ttk.Button(date_row, text="📅", width=3, command=pick_monthly_filter_end).pack(side='left', padx=2)
        
        # Quick date buttons
        from datetime import timedelta
        ttk.Button(date_row, text="Today", 
                  command=lambda: (
                      self.monthly_filter_start.delete(0, tk.END),
                      self.monthly_filter_start.insert(0, date.today().strftime("%Y-%m-%d")),
                      self.monthly_filter_end.delete(0, tk.END),
                      self.monthly_filter_end.insert(0, date.today().strftime("%Y-%m-%d")),
                      self.refresh_monthly_subtab()
                  ), width=12).pack(side='left', padx=2)
        ttk.Button(date_row, text="Last 30 Days", 
                  command=lambda: (
                      self.monthly_filter_start.delete(0, tk.END),
                      self.monthly_filter_start.insert(0, (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")),
                      self.monthly_filter_end.delete(0, tk.END),
                      self.monthly_filter_end.insert(0, date.today().strftime("%Y-%m-%d")),
                      self.refresh_monthly_subtab()
                  ), width=12).pack(side='left', padx=2)
        ttk.Button(date_row, text="This Month", 
                  command=lambda: (
                      self.monthly_filter_start.delete(0, tk.END),
                      self.monthly_filter_start.insert(0, date.today().replace(day=1).strftime("%Y-%m-%d")),
                      self.monthly_filter_end.delete(0, tk.END),
                      self.monthly_filter_end.insert(0, date.today().strftime("%Y-%m-%d")),
                      self.refresh_monthly_subtab()
                  ), width=12).pack(side='left', padx=2)
        ttk.Button(date_row, text="This Year", 
                  command=lambda: (
                      self.monthly_filter_start.delete(0, tk.END),
                      self.monthly_filter_start.insert(0, date.today().replace(month=1, day=1).strftime("%Y-%m-%d")),
                      self.monthly_filter_end.delete(0, tk.END),
                      self.monthly_filter_end.insert(0, date.today().strftime("%Y-%m-%d")),
                      self.refresh_monthly_subtab()
                  ), width=12).pack(side='left', padx=2)
        
        # Row 2: Site and User filters with checkbox style
        filter_row = ttk.Frame(filter_section)
        filter_row.pack(fill='x', pady=(5, 5))
        
        ttk.Label(filter_row, text="Sites:").pack(side='left', padx=(0, 5))
        ttk.Button(filter_row, text="Filter Sites...", 
                  command=self.show_monthly_site_filter, width=15).pack(side='left', padx=(0, 10))
        self.monthly_site_filter_label = ttk.Label(filter_row, text="All", foreground='gray')
        self.monthly_site_filter_label.pack(side='left', padx=(0, 15))
        
        ttk.Label(filter_row, text="Users:").pack(side='left', padx=(0, 5))
        ttk.Button(filter_row, text="Filter Users...", 
                  command=self.show_monthly_user_filter, width=15).pack(side='left', padx=(0, 10))
        self.monthly_user_filter_label = ttk.Label(filter_row, text="All", foreground='gray')
        self.monthly_user_filter_label.pack(side='left', padx=(0, 15))
        
        # Initialize filter sets
        self.monthly_selected_sites = set()
        self.monthly_selected_users = set()
        
        # Apply/Clear buttons
        ttk.Button(filter_row, text="Apply", 
                  command=lambda: self.refresh_monthly_subtab(), 
                  width=12).pack(side='left', padx=5)
        ttk.Button(filter_row, text="Clear", 
                  command=lambda: (
                      self.monthly_filter_start.delete(0, tk.END),
                      self.monthly_filter_end.delete(0, tk.END),
                      setattr(self, 'monthly_selected_sites', set()),
                      setattr(self, 'monthly_selected_users', set()),
                      self.monthly_site_filter_label.config(text="All", foreground='gray'),
                      self.monthly_user_filter_label.config(text="All", foreground='gray'),
                      self.refresh_monthly_subtab()
                  ), width=12).pack(side='left', padx=5)
        
        # === SECTION 4: MONTHLY TRENDS ===
        monthly_frame = ttk.LabelFrame(frame, text="📅 Monthly Performance", padding=15)
        monthly_frame.pack(fill='x', pady=(0, 15))
        
        # Search frame for monthly table
        monthly_search_frame = ttk.Frame(monthly_frame)
        monthly_search_frame.pack(fill='x', pady=(0, 5))
        
        # Add export button
        from table_helpers import export_tree_to_csv
        ttk.Button(monthly_search_frame, text="📤 Export CSV", 
                  command=lambda: export_tree_to_csv(self.rep_monthly_tree, "monthly_performance", self.root),
                  width=15).pack(side='right', padx=5)
        
        cols = ('Month', 'Sessions', 'Days Played', 'Win Rate', 'Basis Consumed', 'Net Taxable', 'Avg Per Day')
        self.rep_monthly_tree = ttk.Treeview(monthly_frame, columns=cols, show='headings', height=12)
        
        for col in cols:
            self.rep_monthly_tree.heading(col, text=col)
            if col in ('Basis Consumed', 'Net Taxable', 'Avg Per Day'):
                self.rep_monthly_tree.column(col, width=120)
            elif col == 'Win Rate':
                self.rep_monthly_tree.column(col, width=80)
            elif col in ('Sessions', 'Days Played'):
                self.rep_monthly_tree.column(col, width=90)
            else:
                self.rep_monthly_tree.column(col, width=130)
        
        self.rep_monthly_tree.pack(fill='x')
        
        # Add SearchableTreeview
        from table_helpers import SearchableTreeview
        self.rep_monthly_searchable = SearchableTreeview(self.rep_monthly_tree, cols, monthly_search_frame)
        
        # === SECTION 5: FINANCIAL SUMMARY ===
        summary_frame = ttk.LabelFrame(frame, text="💵 Cash Flow Summary", padding=15)
        summary_frame.pack(fill='x', pady=(0, 15))
        
        self.rep_summary_labels = {}
        summary_metrics = [
            'Total Invested',
            'Total Redeemed', 
            'Net Cash Flow',
            'Unrealized Value',
            'Overall P/L'
        ]
        
        for i, metric in enumerate(summary_metrics):
            row = i // 2
            col = (i % 2) * 2
            ttk.Label(summary_frame, text=f"{metric}:", 
                     font=('Arial', 11, 'bold')).grid(
                row=row, column=col, sticky='w', padx=20, pady=8)
            val_label = ttk.Label(summary_frame, text="$0.00", font=('Arial', 11))
            val_label.grid(row=row, column=col+1, sticky='w', padx=20, pady=8)
            self.rep_summary_labels[metric] = val_label
    
    def build_schedc_subtab(self, parent):
        """Schedule C Tax Reporting"""
        # Add scrollable canvas
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        # Create window with width constraint
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        # Bind canvas width to constrain the window width
        def configure_canvas_width(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind('<Configure>', configure_canvas_width)
        
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        frame = ttk.Frame(scrollable_frame, padding=20)
        frame.pack(fill='x')
        
        ttk.Label(frame, text="Schedule C - Business Tax Reporting", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # === SECTION 6: SCHEDULE C BUSINESS REPORTING ===
        schedc_frame = ttk.LabelFrame(frame, text="📋 Schedule C - Business Income & Expenses", padding=15)
        schedc_frame.pack(fill='x', pady=(0, 15))
        
        ttk.Label(schedc_frame, text="Tax Year:", font=('Arial', 11, 'bold')).pack(anchor='w', pady=(0, 10))
        
        year_frame = ttk.Frame(schedc_frame)
        year_frame.pack(fill='x', pady=(0, 15))
        
        self.tax_year_var = tk.StringVar(value=str(date.today().year))
        ttk.Label(year_frame, text="Select Year:").pack(side='left', padx=(0, 10))
        year_spinner = ttk.Spinbox(year_frame, from_=2020, to=2030, textvariable=self.tax_year_var, 
                                   width=10, command=self.refresh_schedc)
        year_spinner.pack(side='left')
        ttk.Button(year_frame, text="Refresh", command=self.refresh_schedc).pack(side='left', padx=10)
        
        # Cashback treatment option
        cashback_frame = ttk.Frame(schedc_frame)
        cashback_frame.pack(fill='x', pady=(0, 15))
        
        ttk.Label(cashback_frame, text="Credit Card Cashback Treatment:", 
                 font=('Arial', 10, 'bold')).pack(side='left', padx=(0, 10))
        
        self.cashback_treatment_var = tk.StringVar(value="gross_receipts")
        
        ttk.Radiobutton(cashback_frame, text="Include with Gross Receipts", 
                       variable=self.cashback_treatment_var, value="gross_receipts",
                       command=self.refresh_schedc).pack(side='left', padx=5)
        ttk.Radiobutton(cashback_frame, text="Not Reported", 
                       variable=self.cashback_treatment_var, value="unreported",
                       command=self.refresh_schedc).pack(side='left', padx=5)
        
        # 90% Loss Limitation (2026+ new tax treatment)
        loss_cap_frame = ttk.Frame(schedc_frame)
        loss_cap_frame.pack(fill='x', pady=(0, 15))
        
        self.loss_cap_var = tk.BooleanVar(value=False)
        
        loss_cap_checkbox = ttk.Checkbutton(
            loss_cap_frame, 
            text="☑️ Apply 90% Loss Limitation (2026+ Tax Rule)",
            variable=self.loss_cap_var,
            command=self.refresh_schedc
        )
        loss_cap_checkbox.pack(side='left')
        
        ttk.Label(loss_cap_frame, 
                 text="⚠️ Limits deductible losses to 90% of losing session amounts (10% non-deductible)",
                 font=('Arial', 8), foreground='red').pack(side='left', padx=(10, 0))
        
        # Part I: Income
        income_section = ttk.LabelFrame(schedc_frame, text="Part I - Income", padding=10)
        income_section.pack(fill='x', pady=(0, 10))
        
        self.schedc_income_labels = {}
        income_items = [
            ('Gross Receipts (Redemptions)', 'Line 1'),
            ('Returns & Allowances', 'Line 2'),
            ('Subtract line 2 from line 1', 'Line 3'),
            ('Other Income (e.g., Cashback)', 'Line 6'),
        ]
        
        for item, line in income_items:
            item_frame = ttk.Frame(income_section)
            item_frame.pack(fill='x', pady=3)
            ttk.Label(item_frame, text=f"{line}: {item}", width=40, anchor='w').pack(side='left')
            val = ttk.Label(item_frame, text="$0.00", font=('Arial', 10))
            val.pack(side='left', padx=20)
            self.schedc_income_labels[line] = val
            
            # Add composition note under Line 1
            if line == 'Line 1':
                breakdown_frame = ttk.Frame(income_section)
                breakdown_frame.pack(fill='x', padx=(45, 0), pady=(0, 5))
                self.schedc_gross_receipts_breakdown = ttk.Label(
                    breakdown_frame, 
                    text="", 
                    font=('Arial', 8), 
                    foreground='gray'
                )
                self.schedc_gross_receipts_breakdown.pack(anchor='w')
        
        # Gross Profit (no COGS in session-based method)
        gross_profit_frame = ttk.Frame(schedc_frame, relief='solid', borderwidth=1, padding=5)
        gross_profit_frame.pack(fill='x', pady=10)
        ttk.Label(gross_profit_frame, text="Gross Profit (Line 3):", 
                 font=('Arial', 11, 'bold')).pack(side='left')
        self.schedc_gross_profit = ttk.Label(gross_profit_frame, text="$0.00", 
                                            font=('Arial', 11, 'bold'))
        self.schedc_gross_profit.pack(side='left', padx=20)
        
        # Part III: Expenses
        expenses_section = ttk.LabelFrame(schedc_frame, text="Part III - Expenses", padding=10)
        expenses_section.pack(fill='x', pady=(0, 10))
        
        self.schedc_expense_labels = {}
        expense_items = [
            'Gambling Losses (Losing Sessions)',
            'Advertising',
            'Car and Truck',
            'Commissions and Fees',
            'Contract Labor',
            'Depreciation',
            'Insurance',
            'Interest',
            'Legal & Professional',
            'Office Expense',
            'Rent or Lease',
            'Repairs & Maintenance',
            'Supplies',
            'Taxes and Licenses',
            'Travel',
            'Meals',
            'Utilities',
            'Wages',
            'Other Expenses (from line 48)',
            'Total Expenses (Line 28)',
        ]
        
        for item in expense_items:
            item_frame = ttk.Frame(expenses_section)
            item_frame.pack(fill='x', pady=2)
            ttk.Label(item_frame, text=f"{item}:", width=35, anchor='w').pack(side='left')
            val = ttk.Label(item_frame, text="$0.00", font=('Arial', 9))
            val.pack(side='left', padx=20)
            self.schedc_expense_labels[item] = val
        
        # Net Profit/Loss
        net_frame = ttk.Frame(schedc_frame, relief='solid', borderwidth=2, padding=10)
        net_frame.pack(fill='x', pady=10)
        ttk.Label(net_frame, text="Net Profit or (Loss) (Line 31):", 
                 font=('Arial', 12, 'bold')).pack(side='left')
        self.schedc_net_profit = ttk.Label(net_frame, text="$0.00", 
                                          font=('Arial', 12, 'bold'))
        self.schedc_net_profit.pack(side='left', padx=20)
        
        # === TAX PLANNING SUMMARY ===
        tax_planning_section = ttk.LabelFrame(schedc_frame, text="📊 Tax Planning Summary", padding=15)
        tax_planning_section.pack(fill='x', pady=(20, 10))
        
        self.tax_planning_labels = {}
        
        planning_items = [
            ('Schedule C Net Profit/Loss', 'schedc_net', 'What flows to Schedule 1 & SE'),
            ('Self-Employment Tax (15.3%)', 'se_tax', 'Social Security + Medicare on net profit'),
            ('Federal Income Tax Estimate', 'fed_tax', 'Based on your tax bracket'),
            ('Non-Deductible Expenses (90% cap)', 'cap_impact', '10% of all gambling expenses that cannot be deducted if 2026+ rule applies'),
            ('Total Tax Liability', 'total_tax', 'SE Tax + Income Tax'),
        ]
        
        for label, key, desc in planning_items:
            item_frame = ttk.Frame(tax_planning_section)
            item_frame.pack(fill='x', pady=5)
            
            label_frame = ttk.Frame(item_frame)
            label_frame.pack(fill='x')
            ttk.Label(label_frame, text=f"{label}:", width=35, anchor='w', 
                     font=('Arial', 10, 'bold')).pack(side='left')
            val = ttk.Label(label_frame, text="$0.00", font=('Arial', 10, 'bold'))
            val.pack(side='left', padx=20)
            self.tax_planning_labels[key] = val
            
            ttk.Label(item_frame, text=desc, font=('Arial', 8), 
                     foreground='gray').pack(anchor='w', padx=(5, 0))
        
        # === 1099 RECONCILIATION ===
        reconciliation_section = ttk.LabelFrame(schedc_frame, text="📋 Form 1099 vs Schedule C Explanation", padding=15)
        reconciliation_section.pack(fill='x', pady=(10, 10))
        
        ttk.Label(reconciliation_section, 
                 text="Why Form 1099s don't match Schedule C (Session-Based Reporting):",
                 font=('Arial', 10, 'bold')).pack(anchor='w', pady=(0, 10))
        
        self.reconciliation_labels = {}
        recon_items = [
            ('Form 1099-MISC Total (Redemptions)', 'total_1099', 'Cash received from gambling sites'),
            ('', 'blank1', ''),
            ('Schedule C Method (Session-Based)', 'header1', ''),
            ('  Winning Daily Sessions (Income)', 'winning_sessions', 'Days with net gains'),
            ('  Losing Daily Sessions (Expense)', 'losing_sessions', 'Days with net losses'),
            ('  Schedule C Net Profit/(Loss)', 'schedc_result', 'Actual taxable amount'),
            ('', 'blank2', ''),
            ('Cash Flow Analysis', 'header2', ''),
            ('  Total Invested (Purchases)', 'purchase_basis', 'Money spent buying sweeps coins'),
            ('  Total Redeemed (1099 Amount)', 'total_redeemed', 'Money received back'),
            ('  Net Cash Flow', 'cash_flow', 'Actual dollars won/lost'),
        ]
        
        for label, key, desc in recon_items:
            item_frame = ttk.Frame(reconciliation_section)
            item_frame.pack(fill='x', pady=2)
            
            if key.startswith('header'):
                # Header row
                ttk.Label(item_frame, text=label, font=('Arial', 9, 'bold', 'underline')).pack(anchor='w')
            elif key.startswith('blank'):
                # Blank spacer
                pass
            else:
                # Data row
                ttk.Label(item_frame, text=f"{label}:", width=40, anchor='w').pack(side='left')
                val = ttk.Label(item_frame, text="$0.00", font=('Arial', 9))
                val.pack(side='left', padx=20)
                self.reconciliation_labels[key] = val
                
                if desc:
                    ttk.Label(item_frame, text=desc, font=('Arial', 8), 
                             foreground='gray').pack(side='left', padx=(10, 0))
        
        ttk.Label(schedc_frame, text="Note: This is a simplified Schedule C calculation. Consult a tax professional for filing.",
                 font=('Arial', 9), foreground='red').pack(pady=(10, 0))
    
    def build_export_subtab(self, parent):
        """CSV Exports for CPA - Comprehensive Export Options"""
        # Add scrollable canvas
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        # Create window with width constraint
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        # Bind canvas width to constrain the window width
        def configure_canvas_width(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind('<Configure>', configure_canvas_width)
        
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        frame = ttk.Frame(scrollable_frame, padding=20)
        frame.pack(fill='x')
        
        ttk.Label(frame, text="Export Tax Reports & Data", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Year selector (global for all exports)
        year_frame = ttk.Frame(frame)
        year_frame.pack(fill='x', pady=(0, 15))
        
        ttk.Label(year_frame, text="Tax Year:", font=('Arial', 11, 'bold')).pack(side='left', padx=(0, 10))
        self.export_year_var = tk.StringVar(value=str(date.today().year))
        ttk.Spinbox(year_frame, from_=2020, to=2030, textvariable=self.export_year_var, 
                   width=10).pack(side='left')
        ttk.Label(year_frame, text="(Applies to all tax-year based exports below)",
                 font=('Arial', 9), foreground='gray').pack(side='left', padx=(15, 0))
        
        # === TAX REPORTING EXPORTS ===
        tax_export_frame = ttk.LabelFrame(frame, text="📋 Tax Reporting Exports", padding=15)
        tax_export_frame.pack(fill='x', pady=(0, 15))
        
        ttk.Label(tax_export_frame, text="Session-based tax reports for filing:",
                 font=('Arial', 10)).pack(anchor='w', pady=(0, 10))
        
        tax_btn_row1 = ttk.Frame(tax_export_frame)
        tax_btn_row1.pack(fill='x', pady=5)
        
        ttk.Button(tax_btn_row1, text="📊 Game Sessions Summary", 
                  command=self.export_game_sessions_summary,
                  width=25).pack(side='left', padx=5)
        ttk.Label(tax_btn_row1, text="All game sessions with deltas and net taxable",
                 font=('Arial', 9), foreground='gray').pack(side='left', padx=5)
        
        tax_btn_row2 = ttk.Frame(tax_export_frame)
        tax_btn_row2.pack(fill='x', pady=5)
        
        ttk.Button(tax_btn_row2, text="📅 Daily Tax Sessions", 
                  command=self.export_daily_tax_sessions,
                  width=25).pack(side='left', padx=5)
        ttk.Label(tax_btn_row2, text="Daily rollup by site/user for tax filing",
                 font=('Arial', 9), foreground='gray').pack(side='left', padx=5)
        
        tax_btn_row3 = ttk.Frame(tax_export_frame)
        tax_btn_row3.pack(fill='x', pady=5)
        
        ttk.Button(tax_btn_row3, text="💰 Income Summary", 
                  command=self.export_income_summary,
                  width=25).pack(side='left', padx=5)
        ttk.Label(tax_btn_row3, text="Net taxable totals and cashback",
                 font=('Arial', 9), foreground='gray').pack(side='left', padx=5)
        
        tax_btn_row4 = ttk.Frame(tax_export_frame)
        tax_btn_row4.pack(fill='x', pady=5)
        
        ttk.Button(tax_btn_row4, text="📝 Expenses by Category", 
                  command=self.export_expenses_by_category,
                  width=25).pack(side='left', padx=5)
        ttk.Label(tax_btn_row4, text="Schedule C expense categories",
                 font=('Arial', 9), foreground='gray').pack(side='left', padx=5)
        
        # === TRANSACTION EXPORTS ===
        txn_export_frame = ttk.LabelFrame(frame, text="💳 Transaction Exports", padding=15)
        txn_export_frame.pack(fill='x', pady=(0, 15))
        
        ttk.Label(txn_export_frame, text="Detailed transaction logs:",
                 font=('Arial', 10)).pack(anchor='w', pady=(0, 10))
        
        txn_btn_row1 = ttk.Frame(txn_export_frame)
        txn_btn_row1.pack(fill='x', pady=5)
        
        ttk.Button(txn_btn_row1, text="💵 All Purchases", 
                  command=self.export_purchases_detail,
                  width=25).pack(side='left', padx=5)
        ttk.Label(txn_btn_row1, text="Complete purchase history with FIFO basis",
                 font=('Arial', 9), foreground='gray').pack(side='left', padx=5)
        
        txn_btn_row2 = ttk.Frame(txn_export_frame)
        txn_btn_row2.pack(fill='x', pady=5)
        
        ttk.Button(txn_btn_row2, text="💸 All Redemptions", 
                  command=self.export_redemptions_detail,
                  width=25).pack(side='left', padx=5)
        ttk.Label(txn_btn_row2, text="Complete redemption history",
                 font=('Arial', 9), foreground='gray').pack(side='left', padx=5)
        
        txn_btn_row3 = ttk.Frame(txn_export_frame)
        txn_btn_row3.pack(fill='x', pady=5)
        
        ttk.Button(txn_btn_row3, text="🎰 Sessions by Site", 
                  command=self.export_sessions_by_site,
                  width=25).pack(side='left', padx=5)
        ttk.Label(txn_btn_row3, text="Performance breakdown per casino site",
                 font=('Arial', 9), foreground='gray').pack(side='left', padx=5)
        
        # === COMPLETE DATABASE EXPORT ===
        db_export_frame = ttk.LabelFrame(frame, text="🗄️ Complete Database Export", padding=15)
        db_export_frame.pack(fill='x', pady=(0, 15))
        
        ttk.Label(db_export_frame, text="Export entire database to CSV files:",
                 font=('Arial', 10)).pack(anchor='w', pady=(0, 10))
        
        db_btn_row = ttk.Frame(db_export_frame)
        db_btn_row.pack(fill='x', pady=5)
        
        ttk.Button(db_btn_row, text="📦 Export All Data (ZIP)", 
                  command=self.export_all_tax_data,
                  width=25).pack(side='left', padx=5)
        ttk.Label(db_btn_row, text="Creates ZIP with all tables as CSVs (migration/backup)",
                 font=('Arial', 9), foreground='gray').pack(side='left', padx=5)
        
        # Save location info
        ttk.Separator(frame, orient='horizontal').pack(fill='x', pady=15)
        ttk.Label(frame, text="💾 Files will be saved to your Desktop (or current directory if Desktop unavailable)",
                 font=('Arial', 9), foreground='blue').pack(pady=(0, 5))
        ttk.Label(frame, text="📌 Tip: All exports respect the Tax Year selected above (except 'All Purchases/Redemptions')",
                 font=('Arial', 9), foreground='gray').pack()
    
    def download_template(self, data_type):
        """Generate and download CSV template"""
        import csv
        from tkinter import filedialog
        
        templates = {
            'purchases': ['Date', 'Time', 'User', 'Site', 'Amount', 'SC Received', 'Starting SC', 'Card', 'Notes'],
            'redemptions': ['Date', 'Time', 'User', 'Site', 'Amount', 'Receipt Date', 'Method', 'Free SC', 'More Remaining', 'Notes'],
            'expenses': ['Date', 'Amount', 'Vendor', 'Category', 'Description'],
            'sessions': ['Date', 'Start Time', 'End Time', 'User', 'Site', 'Starting SC', 'Ending SC', 'Game Type', 'Notes']
        }
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"{data_type}_template.csv"
        )
        
        if filename:
            try:
                with open(filename, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(templates[data_type])
                    
                    # Add example rows
                    if data_type == 'redemptions':
                        writer.writerow(['2025-04-01', '15:30:00', 'Elliot', 'Stake', '5000', '2025-04-02', 'Venmo', '0', '0', 'Full cashout - closes site session'])
                        writer.writerow(['2025-04-02', '10:00:00', 'Elliot', 'Pulsz', '50', '', 'PayPal', '0', '1', 'Partial cashout - more balance remains'])
                    elif data_type == 'sessions':
                        writer.writerow(['2025-04-01', '14:00:00', '16:30:00', 'Elliot', 'Stake', '1250.50', '1580.75', 'Slots', 'Good session'])
                        writer.writerow(['2025-04-01', '20:00:00', '22:15:00', 'Elliot', 'Pulsz', '500.00', '425.50', 'Blackjack', 'Small loss'])
                        
                messagebox.showinfo("Success", f"Template saved to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save template: {e}")
    
    def import_csv(self, data_type):
        """Import CSV file for the specified data type"""
        from tkinter import filedialog
        import csv
        
        filename = filedialog.askopenfilename(
            title=f"Select {data_type.title()} CSV File",
            filetypes=[("CSV files", "*.csv"), ("Excel files", "*.xlsx"), ("All files", "*.*")]
        )
        
        if not filename:
            return
        
        try:
            # Handle both CSV and Excel
            if filename.endswith('.xlsx'):
                import openpyxl
                wb = openpyxl.load_workbook(filename)
                ws = wb.active
                rows = list(ws.iter_rows(values_only=True))
                headers = [str(h).strip() for h in rows[0]]
                data_rows = rows[1:]
            else:
                with open(filename, 'r', encoding='utf-8-sig') as f:
                    reader = csv.reader(f)
                    headers = [h.strip() for h in next(reader)]
                    data_rows = list(reader)
            
            # Process based on type
            if data_type == 'purchases':
                self.import_purchases_data(headers, data_rows)
            elif data_type == 'redemptions':
                self.import_redemptions_data(headers, data_rows)
            elif data_type == 'expenses':
                self.import_expenses_data(headers, data_rows)
            elif data_type == 'sessions':
                self.import_sessions_data(headers, data_rows)
            
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to import: {str(e)}")
    
    def import_purchases_data(self, headers, rows):
        """Import purchases from parsed CSV data"""
        # Map column names (case-insensitive)
        col_map = {h.lower(): i for i, h in enumerate(headers)}
        
        required = ['date', 'user', 'site', 'amount', 'sc received', 'starting sc', 'card']
        missing = [r for r in required if r not in col_map]
        
        if missing:
            messagebox.showerror("Missing Columns", f"Required columns missing: {', '.join(missing)}")
            return
        
        # Create progress dialog
        progress_window = tk.Toplevel(self.root)
        progress_window.title("Importing Purchases")
        progress_window.geometry("500x150")
        progress_window.transient(self.root)
        progress_window.grab_set()
        
        frame = ttk.Frame(progress_window, padding=20)
        frame.pack(fill='both', expand=True)
        
        status_label = ttk.Label(frame, text=f"Importing {len(rows)} purchases...", font=('Arial', 10))
        status_label.pack(pady=(0, 10))
        
        progress_bar = ttk.Progressbar(frame, length=400, mode='determinate', maximum=len(rows))
        progress_bar.pack(pady=(0, 10))
        
        detail_label = ttk.Label(frame, text="Starting import...", font=('Arial', 9), foreground='gray')
        detail_label.pack()
        
        progress_window.update()
        
        # CRITICAL: Sort rows by date AND TIME chronologically BEFORE processing
        # This ensures proper FIFO accounting and session management
        detail_label.config(text="Sorting by date and time...")
        progress_window.update()
        
        sorted_rows = []
        for row in rows:
            try:
                pdate = parse_date(row[col_map['date']])
                # Get time if present, default to 00:00:00
                ptime = row[col_map.get('time', -1)].strip() if 'time' in col_map and col_map.get('time', -1) < len(row) else '00:00:00'
                # Validate time format
                from datetime import datetime
                try:
                    datetime.strptime(ptime, '%H:%M:%S')
                except:
                    try:
                        datetime.strptime(ptime, '%H:%M')
                        ptime = ptime + ':00'
                    except:
                        ptime = '00:00:00'
                sorted_rows.append((pdate, ptime, row))
            except:
                # If date parsing fails, put at end
                sorted_rows.append((date(9999, 12, 31), '23:59:59', row))
        
        sorted_rows.sort(key=lambda x: (x[0], x[1]))  # Sort by date, then time
        rows = [row for _, _, row in sorted_rows]  # Extract just the rows
        
        detail_label.config(text="Starting import...")
        progress_window.update()
        
        conn = self.db.get_connection()
        c = conn.cursor()
        
        imported = 0
        errors = []
        auto_created = {'users': set(), 'sites': set(), 'cards': set()}
        
        # Cache for users, sites, cards to avoid repeated lookups
        user_cache = {}
        site_cache = {}
        card_cache = {}
        session_cache = {}  # Cache sessions by (site_id, user_id, date)
        
        # Batch purchases for session updates
        session_purchases = {}  # {session_key: total_amount}
        
        for i, row in enumerate(rows, start=2):
            try:
                # Update progress every 50 rows or on first/last
                if i % 50 == 0 or i == 2 or i == len(rows) + 1:
                    progress_bar['value'] = i - 2
                    detail_label.config(text=f"Processing row {i - 1} of {len(rows)}... ({imported} imported)")
                    progress_window.update()
                
                # Extract values
                pdate = parse_date(row[col_map['date']])
                
                # Extract time if present, default to 00:00:00
                ptime = row[col_map.get('time', -1)].strip() if 'time' in col_map and col_map.get('time', -1) < len(row) else '00:00:00'
                # Validate time format
                from datetime import datetime
                try:
                    datetime.strptime(ptime, '%H:%M:%S')
                except:
                    try:
                        datetime.strptime(ptime, '%H:%M')
                        ptime = ptime + ':00'
                    except:
                        ptime = '00:00:00'
                
                user_name = row[col_map['user']].strip()
                site_name = row[col_map['site']].strip()
                amount = float(row[col_map['amount']])
                sc_received = float(row[col_map['sc received']])
                starting_sc = float(row[col_map['starting sc']])
                card_name = row[col_map['card']].strip()
                notes = row[col_map.get('notes', -1)].strip() if 'notes' in col_map and col_map['notes'] < len(row) else None
                
                # Get or create User (with caching)
                if user_name not in user_cache:
                    c.execute("SELECT id FROM users WHERE name = ?", (user_name,))
                    user_row = c.fetchone()
                    if not user_row:
                        c.execute("INSERT INTO users (name, active) VALUES (?, 1)", (user_name,))
                        user_id = c.lastrowid
                        auto_created['users'].add(user_name)
                    else:
                        user_id = user_row['id']
                    user_cache[user_name] = user_id
                else:
                    user_id = user_cache[user_name]
                
                # Get or create Site (with caching)
                if site_name not in site_cache:
                    c.execute("SELECT id FROM sites WHERE name = ?", (site_name,))
                    site_row = c.fetchone()
                    if not site_row:
                        c.execute("INSERT INTO sites (name, sc_rate, active) VALUES (?, 1.0, 1)", (site_name,))
                        site_id = c.lastrowid
                        auto_created['sites'].add(site_name)
                    else:
                        site_id = site_row['id']
                    site_cache[site_name] = site_id
                else:
                    site_id = site_cache[site_name]
                
                # Get or create Card (with caching)
                card_key = (card_name, user_id)
                if card_key not in card_cache:
                    c.execute("SELECT id FROM cards WHERE name = ? AND user_id = ?", (card_name, user_id))
                    card_row = c.fetchone()
                    if not card_row:
                        c.execute("INSERT INTO cards (name, user_id, cashback_rate) VALUES (?, ?, 0.0)", (card_name, user_id))
                        card_id = c.lastrowid
                        auto_created['cards'].add(f"{card_name} ({user_name})")
                    else:
                        card_id = card_row['id']
                    card_cache[card_key] = card_id
                else:
                    card_id = card_cache[card_key]
                
                # Insert purchase with processed=0 (will be processed later)
                c.execute('''
                    INSERT INTO purchases 
                    (purchase_date, purchase_time, site_id, amount, sc_received, starting_sc_balance, card_id, user_id, remaining_amount, notes, processed)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                ''', (pdate, ptime, site_id, amount, sc_received, starting_sc, card_id, user_id, amount, notes))
                
                imported += 1
                
                # Commit every 100 rows to avoid memory issues
                if i % 100 == 0:
                    conn.commit()
                
            except Exception as e:
                errors.append(f"Row {i}: {str(e)}")
        
        # Final commit
        conn.commit()
        conn.close()
        
        progress_window.destroy()
        
        # Show results
        msg = f"Imported {imported} purchases successfully\n\n"
        msg += "⚠️¸ IMPORTANT: Click 'Process Imported Purchases & Redemptions'\n"
        msg += "to calculate cost basis and create sessions."
        
        if auto_created['users'] or auto_created['sites'] or auto_created['cards']:
            msg += "\n\nAuto-created:"
            if auto_created['users']:
                msg += f"\n  Users: {', '.join(sorted(auto_created['users']))}"
            if auto_created['sites']:
                msg += f"\n  Sites: {', '.join(sorted(auto_created['sites']))}"
            if auto_created['cards']:
                msg += f"\n  Cards: {', '.join(sorted(auto_created['cards']))}"
            msg += "\n\n(You can edit these in the Setup tab)"
        
        if errors:
            msg += f"\n\n{len(errors)} errors:\n" + "\n".join(errors[:10])
            if len(errors) > 10:
                msg += f"\n... and {len(errors) - 10} more"
        
        messagebox.showinfo("Import Complete", msg)
        self.refresh_all_views()
    
    def import_redemptions_data(self, headers, rows):
        """Import redemptions from parsed CSV data"""
        col_map = {h.lower(): i for i, h in enumerate(headers)}
        
        required = ['date', 'user', 'site', 'amount']
        missing = [r for r in required if r not in col_map]
        
        if missing:
            messagebox.showerror("Missing Columns", f"Required columns missing: {', '.join(missing)}")
            return
        
        # CRITICAL: Sort rows by date AND TIME chronologically BEFORE processing
        # This ensures proper FIFO accounting and session management
        sorted_rows = []
        for row in rows:
            try:
                rdate = parse_date(row[col_map['date']])
                # Get time if present, default to 00:00:00
                rtime = row[col_map.get('time', -1)].strip() if 'time' in col_map and col_map.get('time', -1) < len(row) else '00:00:00'
                # Validate time format
                from datetime import datetime
                try:
                    datetime.strptime(rtime, '%H:%M:%S')
                except:
                    try:
                        datetime.strptime(rtime, '%H:%M')
                        rtime = rtime + ':00'
                    except:
                        rtime = '00:00:00'
                sorted_rows.append((rdate, rtime, row))
            except:
                # If date parsing fails, put at end
                sorted_rows.append((date(9999, 12, 31), '23:59:59', row))
        
        sorted_rows.sort(key=lambda x: (x[0], x[1]))  # Sort by date, then time
        rows = [row for _, _, row in sorted_rows]  # Extract just the rows
        
        conn = self.db.get_connection()
        c = conn.cursor()
        
        imported = 0
        errors = []
        auto_created = {'users': set(), 'sites': set(), 'methods': set()}
        
        for i, row in enumerate(rows, start=2):
            try:
                rdate = parse_date(row[col_map['date']])
                
                # Extract time if present, default to 00:00:00
                rtime = row[col_map.get('time', -1)].strip() if 'time' in col_map and col_map.get('time', -1) < len(row) else '00:00:00'
                # Validate time format
                from datetime import datetime
                try:
                    datetime.strptime(rtime, '%H:%M:%S')
                except:
                    try:
                        datetime.strptime(rtime, '%H:%M')
                        rtime = rtime + ':00'
                    except:
                        rtime = '00:00:00'
                
                user_name = row[col_map['user']].strip()
                site_name = row[col_map['site']].strip()
                amount = float(row[col_map['amount']])
                
                receipt_date = None
                if 'receipt date' in col_map and col_map['receipt date'] < len(row) and row[col_map['receipt date']].strip():
                    receipt_date = parse_date(row[col_map['receipt date']])
                
                method_name = row[col_map.get('method', -1)].strip() if 'method' in col_map and col_map['method'] < len(row) else None
                free_sc = row[col_map.get('free sc', -1)].strip().lower() in ['yes', 'true', '1'] if 'free sc' in col_map and col_map['free sc'] < len(row) else False
                processed = row[col_map.get('processed', -1)].strip().lower() in ['yes', 'true', '1'] if 'processed' in col_map and col_map['processed'] < len(row) else False
                
                # Parse More Remaining flag (defaults to 0/False - assume closing out site)
                more_remaining_str = row[col_map.get('more remaining', -1)].strip() if 'more remaining' in col_map and col_map['more remaining'] < len(row) else '0'
                more_remaining = 1 if more_remaining_str.lower() in ['1', 'true', 'yes'] else 0
                
                notes = row[col_map.get('notes', -1)].strip() if 'notes' in col_map and col_map['notes'] < len(row) else None
                
                # Get or create User
                c.execute("SELECT id FROM users WHERE name = ?", (user_name,))
                user_row = c.fetchone()
                if not user_row:
                    c.execute("INSERT INTO users (name, active) VALUES (?, 1)", (user_name,))
                    user_id = c.lastrowid
                    auto_created['users'].add(user_name)
                    conn.commit()
                else:
                    user_id = user_row['id']
                
                # Get or create Site
                c.execute("SELECT id FROM sites WHERE name = ?", (site_name,))
                site_row = c.fetchone()
                if not site_row:
                    c.execute("INSERT INTO sites (name, sc_rate, active) VALUES (?, 1.0, 1)", (site_name,))
                    site_id = c.lastrowid
                    auto_created['sites'].add(site_name)
                    conn.commit()
                else:
                    site_id = site_row['id']
                
                # Get or create Method
                method_id = None
                if method_name:
                    c.execute("SELECT id FROM redemption_methods WHERE name = ?", (method_name,))
                    method_row = c.fetchone()
                    if not method_row:
                        c.execute("INSERT INTO redemption_methods (name) VALUES (?)", (method_name,))
                        method_id = c.lastrowid
                        auto_created['methods'].add(method_name)
                        conn.commit()
                    else:
                        method_id = method_row['id']
                
                # Insert redemption with processed=0 (will be processed later)
                c.execute('''
                    INSERT INTO redemptions 
                    (site_session_id, site_id, redemption_date, redemption_time, amount, receipt_date, redemption_method_id, is_free_sc, more_remaining, user_id, processed, notes)
                    VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                ''', (site_id, rdate, rtime, amount, receipt_date, method_id, 1 if free_sc else 0, more_remaining, user_id, notes))
                
                imported += 1
                
            except Exception as e:
                errors.append(f"Row {i}: {str(e)}")
        
        conn.close()
        
        msg = f"Imported {imported} redemptions successfully\n\n"
        msg += "⚠️¸ IMPORTANT: Click 'Process Imported Purchases & Redemptions'\n"
        msg += "to calculate cost basis and create tax sessions."
        
        if auto_created['users'] or auto_created['sites'] or auto_created['methods']:
            msg += "\n\nAuto-created:"
            if auto_created['users']:
                msg += f"\n  Users: {', '.join(sorted(auto_created['users']))}"
            if auto_created['sites']:
                msg += f"\n  Sites: {', '.join(sorted(auto_created['sites']))}"
            if auto_created['methods']:
                msg += f"\n  Methods: {', '.join(sorted(auto_created['methods']))}"
            msg += "\n\n(You can edit these in the Setup tab)"
        
        if errors:
            msg += f"\n\n{len(errors)} errors:\n" + "\n".join(errors[:10])
            if len(errors) > 10:
                msg += f"\n... and {len(errors) - 10} more"
        
        messagebox.showinfo("Import Complete", msg)
        self.refresh_all_views()
    
    def import_expenses_data(self, headers, rows):
        """Import expenses from parsed CSV data"""
        col_map = {h.lower(): i for i, h in enumerate(headers)}
        
        required = ['date', 'amount', 'vendor']
        missing = [r for r in required if r not in col_map]
        
        if missing:
            messagebox.showerror("Missing Columns", f"Required columns missing: {', '.join(missing)}")
            return
        
        conn = self.db.get_connection()
        c = conn.cursor()
        
        imported = 0
        errors = []
        
        for i, row in enumerate(rows, start=2):
            try:
                edate = parse_date(row[col_map['date']])
                amount = float(row[col_map['amount']])
                vendor = row[col_map['vendor']].strip()
                category = row[col_map.get('category', -1)].strip() if 'category' in col_map and col_map['category'] < len(row) else 'Other Expenses'
                description = row[col_map.get('description', -1)].strip() if 'description' in col_map and col_map['description'] < len(row) else None
                
                c.execute('''
                    INSERT INTO expenses (expense_date, amount, vendor, category, description)
                    VALUES (?, ?, ?, ?, ?)
                ''', (edate, amount, vendor, category, description))
                
                imported += 1
                
            except Exception as e:
                errors.append(f"Row {i}: {str(e)}")
        
        conn.commit()
        conn.close()
        
        msg = f"Imported {imported} expenses successfully"
        if errors:
            msg += f"\n\n{len(errors)} errors:\n" + "\n".join(errors[:10])
            if len(errors) > 10:
                msg += f"\n... and {len(errors) - 10} more"
        
        messagebox.showinfo("Import Complete", msg)
        self.refresh_all_views()
    
    def import_sessions_data(self, headers, rows):
        """Import game sessions from parsed CSV data (marks as unprocessed)"""
        col_map = {h.lower(): i for i, h in enumerate(headers)}
        
        required = ['date', 'user', 'site', 'starting sc', 'ending sc']
        missing = [r for r in required if r not in col_map]
        
        if missing:
            messagebox.showerror("Missing Columns", 
                f"Required columns missing: {', '.join(missing)}\n\n"
                "Required: Date, User, Site, Starting SC, Ending SC\n"
                "Optional: Start Time, End Time, Game Type, Notes")
            return
        
        conn = self.db.get_connection()
        c = conn.cursor()
        
        imported = 0
        errors = []
        auto_created = {'users': set(), 'sites': set()}
        
        for i, row in enumerate(rows, start=2):
            try:
                session_date = parse_date(row[col_map['date']])
                
                # Extract times if present
                start_time = row[col_map.get('start time', -1)].strip() if 'start time' in col_map and col_map.get('start time', -1) < len(row) else '00:00:00'
                end_time = row[col_map.get('end time', -1)].strip() if 'end time' in col_map and col_map.get('end time', -1) < len(row) else None
                
                # Validate and normalize time formats
                from datetime import datetime
                try:
                    datetime.strptime(start_time, '%H:%M:%S')
                except:
                    try:
                        datetime.strptime(start_time, '%H:%M')
                        start_time = start_time + ':00'
                    except:
                        start_time = '00:00:00'
                
                if end_time:
                    try:
                        datetime.strptime(end_time, '%H:%M:%S')
                    except:
                        try:
                            datetime.strptime(end_time, '%H:%M')
                            end_time = end_time + ':00'
                        except:
                            end_time = None
                
                user_name = row[col_map['user']].strip()
                site_name = row[col_map['site']].strip()
                starting_sc = float(row[col_map['starting sc']])
                ending_sc = float(row[col_map['ending sc']])
                
                game_type = row[col_map.get('game type', -1)].strip() if 'game type' in col_map and col_map.get('game type', -1) < len(row) else None
                notes = row[col_map.get('notes', -1)].strip() if 'notes' in col_map and col_map.get('notes', -1) < len(row) else None
                
                # Get or create User
                c.execute("SELECT id FROM users WHERE name = ?", (user_name,))
                user_row = c.fetchone()
                if not user_row:
                    c.execute("INSERT INTO users (name, active) VALUES (?, 1)", (user_name,))
                    user_id = c.lastrowid
                    auto_created['users'].add(user_name)
                else:
                    user_id = user_row['id']
                
                # Get or create Site
                c.execute("SELECT id FROM sites WHERE name = ?", (site_name,))
                site_row = c.fetchone()
                if not site_row:
                    c.execute("INSERT INTO sites (name, sc_rate, active) VALUES (?, 1.0, 1)", (site_name,))
                    site_id = c.lastrowid
                    auto_created['sites'].add(site_name)
                else:
                    site_id = site_row['id']
                
                # Insert session (marked as Closed but processed=0 for reconciliation)
                c.execute('''
                    INSERT INTO game_sessions (
                        session_date, start_time, end_time, site_id, user_id,
                        starting_sc_balance, ending_sc_balance, game_type,
                        status, notes, processed
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Closed', ?, 0)
                ''', (session_date, start_time, end_time, site_id, user_id,
                      starting_sc, ending_sc, game_type, notes))
                
                imported += 1
                
            except Exception as e:
                errors.append(f"Row {i}: {str(e)}")
        
        conn.commit()
        conn.close()
        
        msg = f"Imported {imported} sessions successfully (marked as unprocessed)\n\n"
        msg += "⚠️ Important: Run 'Reconcile Imported Data' to recompute session metrics and finalize sessions."
        
        if auto_created['users'] or auto_created['sites']:
            msg += "\n\nAuto-created:"
            if auto_created['users']:
                msg += f"\n• Users: {', '.join(sorted(auto_created['users']))}"
            if auto_created['sites']:
                msg += f"\n• Sites: {', '.join(sorted(auto_created['sites']))}"
        
        if errors:
            msg += f"\n\n{len(errors)} errors:\n" + "\n".join(errors[:10])
            if len(errors) > 10:
                msg += f"\n... and {len(errors) - 10} more"
        
        messagebox.showinfo("Import Complete", msg)
        # Don't refresh yet - wait for reconciliation
    
    def restore_database(self):
        from tkinter import filedialog, messagebox
        import shutil
        
        response = messagebox.askyesno(
            "Restore Database",
            "⚠️¸ WARNING: This will replace your current database!\n\n"
            "Your current data will be lost unless you have a backup.\n\n"
            "Continue?"
        )
        
        if not response:
            return
        
        filepath = filedialog.askopenfilename(
            title="Select Backup Database",
            filetypes=[("Database files", "*.db"), ("All files", "*.*")]
        )
        
        if filepath:
            try:
                # Create emergency backup first
                emergency_backup = "casino_accounting_pre_restore.db"
                shutil.copy2('casino_accounting.db', emergency_backup)
                
                # Restore from selected backup
                shutil.copy2(filepath, 'casino_accounting.db')
                
                messagebox.showinfo("Success", 
                    f"Database restored from:\n{filepath}\n\n"
                    f"Emergency backup saved as:\n{emergency_backup}\n\n"
                    "Please restart the application.")
                
                # Close and reopen to refresh
                self.root.destroy()
                
            except Exception as e:
                messagebox.showerror("Restore Error", f"Failed to restore database:\n{str(e)}")

    
    def close_as_loss(self):
        """Close selected session as loss"""
        sel = self.os_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select a session")
            return
        
        sid = self.os_tree.item(sel[0])['tags'][0]
        
        if not messagebox.askyesno("Confirm", "Close as total loss?"):
            return
        
        try:
            # Get and parse the loss date
            loss_date = parse_date(self.os_loss_date.get().strip())
        except Exception as e:
            messagebox.showerror("Invalid Date", f"Please enter a valid date: {e}")
            return
        
        self.session_mgr.close_session_as_loss(int(sid), loss_date)
        self.refresh_open_sessions()
        self.refresh_closed_sessions()
        self.refresh_global_stats()
        messagebox.showinfo("Success", "Closed as loss")
    
    
    def close_as_loss_prompt_with_session(self, session_id):
        """Prompt for date and notes, then close specified session as loss"""
        # Create popup for date entry
        popup = tk.Toplevel(self.root)
        popup.title("Close Session as Loss")
        popup.geometry("400x250")
        popup.transient(self.root)
        popup.grab_set()
        
        frame = ttk.Frame(popup, padding=20)
        frame.pack(fill='both', expand=True)
        
        # Date field
        ttk.Label(frame, text="Enter Loss Date:", font=('Arial', 11)).pack(pady=(0, 5))
        
        date_frame = ttk.Frame(frame)
        date_frame.pack(pady=(0, 15))
        
        date_entry = ttk.Entry(date_frame, width=20, font=('Arial', 11))
        date_entry.insert(0, date.today().strftime("%Y-%m-%d"))
        date_entry.pack(side='left')
        date_entry.focus()
        date_entry.select_range(0, tk.END)
        
        # Notes field
        ttk.Label(frame, text="Notes (optional):", font=('Arial', 11)).pack(pady=(0, 5))
        
        notes_text = tk.Text(frame, height=4, width=40, font=('Arial', 10))
        notes_text.pack(pady=10, fill='both', expand=True)
        
        def confirm():
            try:
                loss_date_str = date_entry.get().strip()
                if not loss_date_str:
                    messagebox.showwarning("Missing Date", "Please enter a loss date")
                    return
                
                try:
                    loss_date = parse_date(loss_date_str)
                except:
                    messagebox.showerror("Invalid Date", "Please enter a valid date (YYYY-MM-DD)")
                    return
            except Exception as e:
                messagebox.showerror("Invalid Date", f"Please enter a valid date: {e}")
                return
            
            notes = notes_text.get('1.0', 'end-1c').strip()
            
            popup.destroy()
            
            if messagebox.askyesno("Confirm", "Close this session as a total loss?"):
                try:
                    self.session_mgr.close_session_as_loss(int(session_id), loss_date, notes)
                    self.refresh_all_views()
                    messagebox.showinfo("Success", "Session closed as loss")
                except ValueError as e:
                    messagebox.showerror("Error", str(e))
        
        def cancel():
            popup.destroy()
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="Confirm", command=confirm).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=cancel).pack(side='left', padx=5)
        
        date_entry.bind('<Return>', lambda e: confirm())
        popup.bind('<Escape>', lambda e: cancel())
    
    def close_as_loss_prompt(self, event=None):
        """Prompt for date and notes, then close selected session as loss"""
        sel = self.os_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select a session to close")
            return
        
        sid = self.os_tree.item(sel[0])['tags'][0]
        
        # Create popup for date and notes entry
        popup = tk.Toplevel(self.root)
        popup.title("Close Session as Loss")
        popup.geometry("400x300")
        popup.transient(self.root)
        popup.grab_set()
        
        # Center the popup
        popup.update_idletasks()
        x = (popup.winfo_screenwidth() // 2) - (popup.winfo_width() // 2)
        y = (popup.winfo_screenheight() // 2) - (popup.winfo_height() // 2)
        popup.geometry(f"+{x}+{y}")
        
        frame = ttk.Frame(popup, padding=20)
        frame.pack(fill='both', expand=True)
        
        # Date field
        ttk.Label(frame, text="Enter Loss Date:", font=('Arial', 11)).pack(pady=(0, 5))
        
        date_frame = ttk.Frame(frame)
        date_frame.pack(pady=(0, 15))
        
        date_entry = ttk.Entry(date_frame, width=20, font=('Arial', 11))
        date_entry.insert(0, date.today().strftime("%Y-%m-%d"))
        date_entry.pack(side='left')
        date_entry.focus()
        date_entry.select_range(0, tk.END)
        
        def pick_loss_date():
            try:
                from tkcalendar import Calendar
                top = tk.Toplevel(popup)
                top.title("Select Loss Date")
                top.geometry("300x300")
                top.transient(popup)
                top.grab_set()
                
                cal = Calendar(top, selectmode='day', date_pattern='y-mm-dd')
                cal.pack(pady=20)
                
                def select():
                    date_entry.delete(0, tk.END)
                    date_entry.insert(0, cal.get_date())
                    top.destroy()
                
                ttk.Button(top, text="Select", command=select).pack(pady=10)
                ttk.Button(top, text="Cancel", command=top.destroy).pack()
            except ImportError:
                date_entry.delete(0, tk.END)
                date_entry.insert(0, date.today().strftime("%Y-%m-%d"))
        
        ttk.Button(date_frame, text="📅", width=3, command=pick_loss_date).pack(side='left', padx=2)
        
        # Notes field
        ttk.Label(frame, text="Notes (optional):", font=('Arial', 11)).pack(pady=(0, 5))
        ttk.Label(frame, text="Document why this session closed as a loss", 
                 font=('Arial', 9, 'italic'), foreground='gray').pack()
        
        notes_text = tk.Text(frame, height=5, width=40, font=('Arial', 10))
        notes_text.pack(pady=10, fill='both', expand=True)
        
        def confirm():
            try:
                loss_date = parse_date(date_entry.get().strip())
            except Exception as e:
                messagebox.showerror("Invalid Date", f"Please enter a valid date: {e}")
                return
            
            notes = notes_text.get('1.0', 'end-1c').strip()
            
            popup.destroy()
            
            if messagebox.askyesno("Confirm", "Close this session as a total loss?"):
                try:
                    self.session_mgr.close_session_as_loss(int(sid), loss_date, notes)
                    self.refresh_all_views()
                    messagebox.showinfo("Success", "Session closed as loss")
                except ValueError as e:
                    messagebox.showerror("Error", str(e))
        
        def cancel():
            popup.destroy()
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="Confirm", command=confirm).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=cancel).pack(side='left', padx=5)
        
        # Bind Enter key in date field to confirm
        date_entry.bind('<Return>', lambda e: confirm())
        popup.bind('<Escape>', lambda e: cancel())
    
    def refresh_all_views(self):
        """Refresh all data views after any change"""
        self.refresh_purchases()
        self.refresh_redemptions()
        self.refresh_game_sessions()  # NEW
        self.refresh_daily_tax_sessions()  # NEW
        self.refresh_unrealized_positions()  # NEW (renamed from open_sessions)
        self.refresh_closed_sessions()  # Keep for historical reference
        self.refresh_expenses()
        self.refresh_reports()
        self.refresh_global_stats()
    
    # ========================================================================
    # GAME SESSION METHODS
    # ========================================================================
    
    def save_game_session_start(self):
        """Save/start a game session from inline form"""
        try:
            # Get values from form
            session_date = self.gs_date.get().strip()
            start_time = self.gs_start_time.get().strip()
            site_name = self.gs_site.get().strip()
            user_name = self.gs_user.get().strip()
            game_type = self.gs_game_type.get().strip()
            starting_sc_str = self.gs_starting_sc.get().strip()
            starting_redeemable_str = self.gs_starting_redeemable.get().strip() if hasattr(self, 'gs_starting_redeemable') else ''
            notes = self.gs_notes.get('1.0', 'end-1c').strip()
            
            # Validate required fields
            if not all([session_date, site_name, user_name, game_type, starting_sc_str]):
                messagebox.showwarning("Missing Fields", 
                    "Please fill in Date, Site, User, Game Type, and Starting SC")
                return
            
            # Validate date
            try:
                from gui_tabs import parse_date
                parsed_date = parse_date(session_date)
            except:
                messagebox.showerror("Invalid Date", "Please enter a valid date (YYYY-MM-DD)")
                return
            
            # Validate starting total SC
            valid, result = validate_currency(starting_sc_str)
            if not valid:
                messagebox.showerror("Invalid Total SC", result)
                return
            starting_sc = result
            
            # Validate starting redeemable SC
            # If editing and field is empty, get from database
            if self.gs_edit_id and not starting_redeemable_str:
                # Get current value from database
                conn_temp = self.db.get_connection()
                c_temp = conn_temp.cursor()
                c_temp.execute('SELECT starting_redeemable_sc FROM game_sessions WHERE id = ?', 
                              (self.gs_edit_id,))
                db_row = c_temp.fetchone()
                conn_temp.close()
                
                if db_row and db_row['starting_redeemable_sc'] is not None:
                    starting_redeemable = db_row['starting_redeemable_sc']
                else:
                    # Old sessions might not have this field, default to total
                    starting_redeemable = starting_sc
            elif not starting_redeemable_str:
                # New session with no redeemable specified - default to 0
                # Most purchases are locked SC (not redeemable until played through)
                starting_redeemable = 0
            else:
                # Field has a value - validate it
                valid, result = validate_currency(starting_redeemable_str)
                if not valid:
                    messagebox.showerror("Invalid Redeemable SC", result)
                    return
                starting_redeemable = result
            
            # Validate redeemable <= total
            if starting_redeemable > starting_sc:
                messagebox.showerror("Invalid", "Starting Redeemable SC cannot exceed Starting Total SC")
                return
            
            # Get IDs
            conn = self.db.get_connection()
            c = conn.cursor()
            
            c.execute("SELECT id FROM sites WHERE name = ?", (site_name,))
            site_row = c.fetchone()
            if not site_row:
                conn.close()
                messagebox.showerror("Error", f"Site '{site_name}' not found")
                return
            site_id = site_row['id']
            
            c.execute("SELECT id FROM users WHERE name = ?", (user_name,))
            user_row = c.fetchone()
            if not user_row:
                conn.close()
                messagebox.showerror("Error", f"User '{user_name}' not found")
                return
            user_id = user_row['id']
            
            # NEW VALIDATION: Check for existing active session on same site/user
            if not self.gs_edit_id:  # Only check when starting new session, not editing
                c.execute('''
                    SELECT id, session_date, start_time, starting_sc_balance
                    FROM game_sessions
                    WHERE site_id = ? AND user_id = ? AND status = 'Active'
                    LIMIT 1
                ''', (site_id, user_id))
                
                existing_session = c.fetchone()
                if existing_session:
                    conn.close()
                    messagebox.showerror("Active Session Exists", 
                        f"You already have an active session on {site_name}!\n\n"
                        f"Started: {existing_session['session_date']} at {existing_session['start_time']}\n"
                        f"Starting SC: {existing_session['starting_sc_balance']:.2f}\n\n"
                        f"Please end that session first before starting a new one.\n\n"
                        f"Go to Sessions tab → Game Sessions → Click the active session → End Session")
                    return
            
            conn.close()
            
            if self.gs_edit_id:
                # Editing existing session
                conn = self.db.get_connection()
                c = conn.cursor()
                
                # Get current session status and data
                c.execute('''
                    SELECT status, starting_sc_balance, starting_redeemable_sc, ending_sc_balance 
                    FROM game_sessions WHERE id = ?
                ''', (self.gs_edit_id,))
                status_row = c.fetchone()
                
                if not status_row:
                    conn.close()
                    messagebox.showerror("Error", "Session not found")
                    return
                
                is_closed = (status_row['status'] == 'Closed')
                old_starting_sc = status_row['starting_sc_balance']
                old_starting_redeemable = status_row['starting_redeemable_sc'] if status_row['starting_redeemable_sc'] is not None else old_starting_sc
                ending_sc = status_row['ending_sc_balance']
                
                # Update session
                c.execute('''
                    UPDATE game_sessions
                    SET session_date = ?, start_time = ?, site_id = ?, user_id = ?,
                        game_type = ?, starting_sc_balance = ?, starting_redeemable_sc = ?, notes = ?
                    WHERE id = ?
                ''', (parsed_date, start_time, site_id, user_id, game_type, 
                      starting_sc, starting_redeemable, notes, self.gs_edit_id))
                
                # If closed session and key values changed, recalculate tax fields
                if is_closed and ending_sc is not None:
                    # Check if values that affect tax calculation changed
                    if old_starting_sc != starting_sc or old_starting_redeemable != starting_redeemable:
                        # Trigger canonical recompute for this session
                        conn.commit()
                        conn.close()
                        
                        # Auto-recalculate this session and any affected sessions
                        recalc_count = self.session_mgr.auto_recalculate_affected_sessions(
                            site_id, user_id, parsed_date, start_time
                        )
                        
                        messagebox.showinfo(
                            "Success",
                            "Session updated" + (f" (recalculated {recalc_count} sessions)" if recalc_count else "")
                        )
                        self.clear_game_session_form()
                        self.refresh_all_views()
                        return
                
                conn.commit()
                conn.close()
                
                messagebox.showinfo("Success", "Session updated")
                self.clear_game_session_form()
                self.refresh_all_views()
                
            else:
                # Starting new session
                # First, check if starting SC is significantly less than expected
                # This usually means forgotten redemption or untracked loss
                conn = self.db.get_connection()
                c = conn.cursor()
                
                expected_total, expected_redeemable = self.session_mgr.compute_expected_balances(
                    site_id, user_id, parsed_date, start_time
                )
                expected_sc = expected_total
                
                conn.close()
                
                # Warn if starting SC is less than expected (ANY amount)
                if starting_sc < expected_sc:
                    deficit = expected_sc - starting_sc
                    response = messagebox.askyesno(
                        "Starting Balance Warning",
                        f"Starting SC ({starting_sc:.2f}) is {deficit:.2f} LESS than expected ({expected_sc:.2f})\n\n"
                        f"This usually means:\n"
                        f"- You redeemed {deficit:.2f} SC without recording it\n"
                        f"- You lost {deficit:.2f} SC playing without tracking\n"
                        f"- Data entry error\n\n"
                        f"This will create a NEGATIVE starting delta of -{deficit:.2f} SC\n\n"
                        f"Continue anyway?",
                        icon='warning'
                    )
                    
                    if not response:
                        return
                
                session_id, freebies_amount, reactivated_count, reactivated_basis = self.session_mgr.start_game_session(
                    site_id, user_id, game_type, starting_sc, starting_redeemable, 
                    parsed_date, notes, start_time
                )
                
                # Show confirmation with informative messages
                message_parts = ["Session started!"]
                
                if reactivated_basis > 0:
                    message_parts.append(f"\n\n✓ Recovered ${reactivated_basis:.2f} from previously closed balance")
                
                if freebies_amount > 0:
                    message_parts.append(f"\n✓ Detected ${freebies_amount:.2f} in freebies")
                
                message = "".join(message_parts)
                messagebox.showinfo("Success", message)
                
                self.clear_game_session_form()
                self.refresh_all_views()
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start session: {str(e)}")
    
    def save_game_session_end(self):
        """End a game session from inline form"""
        
        # Check if we have a session selected
        if not self.gs_edit_id:
            # Try to get from selection
            sel = self.gs_tree.selection()
            if not sel:
                messagebox.showwarning("No Session", 
                    "Please select an active session from the table or load it in the form")
                return
            
            tags = self.gs_tree.item(sel[0])['tags']
            session_id = int(tags[0])
        else:
            session_id = self.gs_edit_id
        
        # Check if session is active
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT status, starting_sc_balance, starting_redeemable_sc FROM game_sessions WHERE id = ?", (session_id,))
        session = c.fetchone()
        conn.close()
        
        if not session:
            messagebox.showerror("Error", "Session not found")
            return
        
        if session['status'] != 'Active':
            messagebox.showwarning("Not Active", "This session is already closed")
            return
        
        # Show popup for ending SC
        dialog = tk.Toplevel(self.root)
        dialog.title("End Game Session")
        dialog.geometry("450x350")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="End Game Session", 
                 font=('Arial', 12, 'bold')).pack(pady=10)
        
        form_frame = ttk.Frame(dialog, padding=20)
        form_frame.pack(fill='both', expand=True)
        
        # Show starting balance
        start_redeemable = session['starting_redeemable_sc']
        if start_redeemable is None:
            start_redeemable = session['starting_sc_balance']

        ttk.Label(form_frame, text=f"Starting SC: {session['starting_sc_balance']:.2f}",
                 font=('Arial', 10)).pack(pady=5)
        
        # End Date
        date_frame = ttk.Frame(form_frame)
        date_frame.pack(pady=5, fill='x')
        ttk.Label(date_frame, text="End Date:").pack(side='left', padx=5)
        end_date_var = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
        end_date_entry = ttk.Entry(date_frame, textvariable=end_date_var, width=12)
        end_date_entry.pack(side='left', padx=5)
        
        def pick_end_date():
            try:
                from tkcalendar import Calendar
                top = tk.Toplevel(dialog)
                top.title("Select End Date")
                top.geometry("300x300")
                
                cal = Calendar(top, selectmode='day', date_pattern='y-mm-dd')
                cal.pack(pady=20)
                
                def select_date():
                    end_date_var.set(cal.get_date())
                    top.destroy()
                
                ttk.Button(top, text="Select", command=select_date).pack(pady=10)
                ttk.Button(top, text="Cancel", command=top.destroy).pack()
            except ImportError:
                end_date_var.set(date.today().strftime("%Y-%m-%d"))
        
        ttk.Button(date_frame, text="📅", width=3, command=pick_end_date).pack(side='left', padx=2)
        
        # End Time
        time_frame = ttk.Frame(form_frame)
        time_frame.pack(pady=5, fill='x')
        ttk.Label(time_frame, text="End Time:").pack(side='left', padx=5)
        from datetime import datetime
        end_time_var = tk.StringVar(value=datetime.now().strftime("%H:%M:%S"))
        end_time_entry = ttk.Entry(time_frame, textvariable=end_time_var, width=10)
        end_time_entry.pack(side='left', padx=5)
        ttk.Button(time_frame, text="Now", width=5, 
                  command=lambda: end_time_var.set(datetime.now().strftime("%H:%M:%S"))).pack(side='left', padx=5)
        
        # Total Ending SC
        ttk.Label(form_frame, text="Total Ending SC Balance:").pack(pady=(10, 2))
        ending_sc_var = tk.StringVar()
        ending_sc_entry = ttk.Entry(form_frame, textvariable=ending_sc_var, width=20)
        ending_sc_entry.pack(pady=2)
        
        # Redeemable Ending SC
        ttk.Label(form_frame, text="Redeemable SC (Playthrough Complete):").pack(pady=(5, 2))
        redeemable_sc_var = tk.StringVar()
        redeemable_sc_entry = ttk.Entry(form_frame, textvariable=redeemable_sc_var, width=20)
        redeemable_sc_entry.pack(pady=2)
        redeemable_sc_entry.focus()
        
        # Locked SC (auto-calculated)
        locked_label = ttk.Label(form_frame, text="Locked/Bonus SC: --", 
                                font=('Arial', 9, 'italic'), foreground='gray')
        locked_label.pack(pady=2)
        
        def update_locked(*args):
            try:
                total = float(ending_sc_var.get() or 0)
                redeemable = float(redeemable_sc_var.get() or 0)
                locked = total - redeemable
                if locked >= 0:
                    locked_label.config(text=f"Locked/Bonus SC: {locked:.2f}")
                else:
                    locked_label.config(text=f"Locked/Bonus SC: -- (redeemable > total?)", foreground='red')
            except:
                locked_label.config(text="Locked/Bonus SC: --", foreground='gray')
        
        ending_sc_var.trace_add('write', update_locked)
        redeemable_sc_var.trace_add('write', update_locked)
        
        # P/L preview (based on redeemable SC only)
        pnl_label = ttk.Label(form_frame, text="", font=('Arial', 10, 'bold'))
        pnl_label.pack(pady=10)
        
        def update_pnl(*args):
            try:
                redeemable = float(redeemable_sc_var.get() or 0)
                change = redeemable - float(start_redeemable or 0)
                if change >= 0:
                    pnl_label.config(text=f"Redeemable Change: +{change:.2f} SC", foreground='green')
                else:
                    pnl_label.config(text=f"Redeemable Change: {change:.2f} SC", foreground='red')
            except:
                pnl_label.config(text="")
        
        redeemable_sc_var.trace_add('write', update_pnl)
        
        def save_end():
            try:
                ending_sc_str = ending_sc_var.get().strip()
                redeemable_sc_str = redeemable_sc_var.get().strip()
                end_date = end_date_var.get().strip()
                end_time = end_time_var.get().strip()
                
                # Validate total SC
                valid, result = validate_currency(ending_sc_str)
                if not valid:
                    messagebox.showerror("Invalid Total SC", result)
                    return
                ending_sc = result
                
                # Validate redeemable SC
                valid, result = validate_currency(redeemable_sc_str)
                if not valid:
                    messagebox.showerror("Invalid Redeemable SC", result)
                    return
                redeemable_sc = result
                
                # Validate redeemable <= total
                if redeemable_sc > ending_sc:
                    messagebox.showerror("Invalid", "Redeemable SC cannot exceed Total SC")
                    return
                
                # End session with both values
                pnl = self.session_mgr.end_game_session(
                    session_id, ending_sc, redeemable_sc, 
                    end_date=end_date, end_time=end_time
                )
                
                dialog.destroy()
                
                # Show result
                if pnl >= 0:
                    message = f"Session ended!\n\nProfit: +${pnl:.2f}"
                else:
                    message = f"Session ended!\n\nLoss: ${pnl:.2f}"
                
                messagebox.showinfo("Success", message)
                
                self.clear_game_session_form()
                self.refresh_all_views()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to end session: {str(e)}")
        
        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="End Session", command=save_end).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)
    
    def edit_game_session(self):
        """Load selected game session into form for editing"""
        sel = self.gs_tree.selection()
        if not sel:
            return
        
        tags = self.gs_tree.item(sel[0])['tags']
        session_id = int(tags[0])
        
        # Get session data
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute('''
            SELECT gs.*, s.name as site_name, u.name as user_name
            FROM game_sessions gs
            JOIN sites s ON gs.site_id = s.id
            JOIN users u ON gs.user_id = u.id
            WHERE gs.id = ?
        ''', (session_id,))
        
        session = c.fetchone()
        conn.close()
        
        if not session:
            return
        
        # If closed, use the full edit dialog
        if session['status'] != 'Active':
            self.edit_closed_session_full()
            return
        
        # OLD WARNING REMOVED - now using full edit dialog for closed sessions
                # Load into form
        self.gs_edit_id = session_id
        
        self.gs_date.delete(0, tk.END)
        self.gs_date.insert(0, session['session_date'])
        
        self.gs_start_time.delete(0, tk.END)
        self.gs_start_time.insert(0, session['start_time'] or '')
        
        self.gs_site.set(session['site_name'])
        self.gs_user.set(session['user_name'])
        self.gs_game_type.set(session['game_type'])
        
        self.gs_starting_sc.delete(0, tk.END)
        self.gs_starting_sc.insert(0, str(session['starting_sc_balance']))
        
        # Load starting redeemable field if it exists
        if hasattr(self, 'gs_starting_redeemable'):
            self.gs_starting_redeemable.delete(0, tk.END)
            starting_redeemable = session['starting_redeemable_sc'] if session['starting_redeemable_sc'] is not None else 0
            self.gs_starting_redeemable.insert(0, str(starting_redeemable))
        
        self.gs_notes.delete('1.0', tk.END)
        if session['notes']:
            self.gs_notes.insert('1.0', session['notes'])
        
        # Change button text to indicate edit mode
        if hasattr(self, 'gs_save_btn'):
            self.gs_save_btn.config(text="Edit Session")
    
    def clear_game_session_form(self):
        """Clear the game session form"""
        self.gs_edit_id = None
        
        from datetime import date, datetime
        self.gs_date.delete(0, tk.END)
        self.gs_date.insert(0, date.today().strftime("%Y-%m-%d"))
        
        self.gs_start_time.delete(0, tk.END)
        self.gs_start_time.insert(0, datetime.now().strftime("%H:%M:%S"))
        
        self.gs_site.set('')
        self.gs_user.set('')
        self.gs_game_type.set('')  # Blank
        
        self.gs_starting_sc.delete(0, tk.END)
        
        # Clear starting redeemable field if it exists
        if hasattr(self, 'gs_starting_redeemable'):
            self.gs_starting_redeemable.delete(0, tk.END)
        
        self.gs_notes.delete('1.0', tk.END)
        
        self.gs_freebie_label.config(text='')
        
        # Reset button text to "Start Session"
        if hasattr(self, 'gs_save_btn'):
            self.gs_save_btn.config(text="Start Session")
    
    def edit_closed_session_full(self):
        """Edit all fields of a closed session including ending SC"""
        sel = self.gs_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select a closed session to edit")
            return
        
        tags = self.gs_tree.item(sel[0])['tags']
        session_id = int(tags[0])
        
        # Get session data
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute('''
            SELECT gs.*, s.name as site_name, u.name as user_name
            FROM game_sessions gs
            JOIN sites s ON gs.site_id = s.id
            JOIN users u ON gs.user_id = u.id
            WHERE gs.id = ?
        ''', (session_id,))
        
        session = c.fetchone()
        conn.close()
        
        if not session:
            return
        
        if session['status'] != 'Closed':
            messagebox.showinfo("Not Closed", "This session is still active. End it first, then you can edit it.")
            return
        
        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Closed Session")
        dialog.geometry("550x750")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Edit Closed Session", 
                 font=('Arial', 12, 'bold')).pack(pady=10)
        
        form_frame = ttk.Frame(dialog, padding=20)
        form_frame.pack(fill='both', expand=True)
        
        # Start Date
        start_date_row = ttk.Frame(form_frame)
        start_date_row.grid(row=0, column=0, columnspan=2, sticky='w', pady=5)
        ttk.Label(start_date_row, text="Start Date:").pack(side='left', padx=(0,5))
        start_date_var = tk.StringVar(value=session['session_date'])
        start_date_entry = ttk.Entry(start_date_row, textvariable=start_date_var, width=12)
        start_date_entry.pack(side='left', padx=(0,2))
        
        def pick_start_date():
            try:
                from tkcalendar import Calendar
                top = tk.Toplevel(dialog)
                top.grab_set()
                cal = Calendar(top, selectmode='day', date_pattern='yyyy-mm-dd')
                cal.pack(padx=10, pady=10)
                def select_date():
                    start_date_var.set(cal.get_date())
                    top.destroy()
                ttk.Button(top, text="Select", command=select_date).pack(pady=5)
                ttk.Button(top, text="Cancel", command=top.destroy).pack()
            except ImportError:
                from datetime import date
                start_date_var.set(date.today().strftime("%Y-%m-%d"))
        
        ttk.Button(start_date_row, text="📅", width=3, command=pick_start_date).pack(side='left', padx=2)
        
        # Start Time
        start_time_row = ttk.Frame(form_frame)
        start_time_row.grid(row=1, column=0, columnspan=2, sticky='w', pady=5)
        ttk.Label(start_time_row, text="Start Time:").pack(side='left', padx=(0,5))
        start_time_var = tk.StringVar(value=session['start_time'] or '00:00:00')
        start_time_entry = ttk.Entry(start_time_row, textvariable=start_time_var, width=12)
        start_time_entry.pack(side='left', padx=(0,2))
        
        def set_start_now():
            from datetime import datetime
            start_time_var.set(datetime.now().strftime("%H:%M:%S"))
        
        ttk.Button(start_time_row, text="Now", width=5, command=set_start_now).pack(side='left', padx=2)
        
        # End Date  
        end_date_row = ttk.Frame(form_frame)
        end_date_row.grid(row=2, column=0, columnspan=2, sticky='w', pady=5)
        ttk.Label(end_date_row, text="End Date:").pack(side='left', padx=(0,5))
        end_date_var = tk.StringVar(value=session['end_date'] if session['end_date'] else session['session_date'])
        end_date_entry = ttk.Entry(end_date_row, textvariable=end_date_var, width=12)
        end_date_entry.pack(side='left', padx=(0,2))
        
        def pick_end_date():
            try:
                from tkcalendar import Calendar
                top = tk.Toplevel(dialog)
                top.grab_set()
                cal = Calendar(top, selectmode='day', date_pattern='yyyy-mm-dd')
                cal.pack(padx=10, pady=10)
                def select_date():
                    end_date_var.set(cal.get_date())
                    top.destroy()
                ttk.Button(top, text="Select", command=select_date).pack(pady=5)
                ttk.Button(top, text="Cancel", command=top.destroy).pack()
            except ImportError:
                from datetime import date
                end_date_var.set(date.today().strftime("%Y-%m-%d"))
        
        ttk.Button(end_date_row, text="📅", width=3, command=pick_end_date).pack(side='left', padx=2)
        
        # End Time
        end_time_row = ttk.Frame(form_frame)
        end_time_row.grid(row=3, column=0, columnspan=2, sticky='w', pady=5)
        ttk.Label(end_time_row, text="End Time:").pack(side='left', padx=(0,5))
        end_time_var = tk.StringVar(value=session['end_time'] or '00:00:00')
        end_time_entry = ttk.Entry(end_time_row, textvariable=end_time_var, width=12)
        end_time_entry.pack(side='left', padx=(0,2))
        
        def set_end_now():
            from datetime import datetime
            end_time_var.set(datetime.now().strftime("%H:%M:%S"))
        
        ttk.Button(end_time_row, text="Now", width=5, command=set_end_now).pack(side='left', padx=2)
        
        # Site (now editable)
        ttk.Label(form_frame, text="Site:").grid(row=4, column=0, sticky='w', pady=5)
        site_var = tk.StringVar(value=session['site_name'])
        site_combo = ttk.Combobox(form_frame, textvariable=site_var, width=20, state='normal')
        # Populate with sites
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT name FROM sites ORDER BY name")
        sites = [row['name'] for row in c.fetchall()]
        conn.close()
        site_combo['values'] = sites
        from gui_tabs import enable_excel_autosuggest
        enable_excel_autosuggest(site_combo)
        site_combo.grid(row=4, column=1, sticky='w', pady=5)
        
        # User (now editable)
        ttk.Label(form_frame, text="User:").grid(row=5, column=0, sticky='w', pady=5)
        user_var = tk.StringVar(value=session['user_name'])
        user_combo = ttk.Combobox(form_frame, textvariable=user_var, width=20, state='normal')
        # Populate with users
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT name FROM users ORDER BY name")
        users = [row['name'] for row in c.fetchall()]
        conn.close()
        user_combo['values'] = users
        enable_excel_autosuggest(user_combo)
        user_combo.grid(row=5, column=1, sticky='w', pady=5)
        
        # Game Type (now editable)
        ttk.Label(form_frame, text="Game Type:").grid(row=6, column=0, sticky='w', pady=5)
        game_type_var = tk.StringVar(value=session['game_type'])
        game_type_combo = ttk.Combobox(form_frame, textvariable=game_type_var, width=20, state='normal')
        game_type_combo['values'] = ['Slots', 'Blackjack', 'Other']
        enable_excel_autosuggest(game_type_combo)
        game_type_combo.grid(row=6, column=1, sticky='w', pady=5)
        
        # Starting SC
        ttk.Label(form_frame, text="Starting Total SC:").grid(row=7, column=0, sticky='w', pady=5)
        start_sc_var = tk.StringVar(value=str(session['starting_sc_balance']))
        start_sc_entry = ttk.Entry(form_frame, textvariable=start_sc_var, width=15)
        start_sc_entry.grid(row=7, column=1, sticky='w', pady=5)
        
        # Starting Redeemable SC
        ttk.Label(form_frame, text="Starting Redeemable SC:").grid(row=8, column=0, sticky='w', pady=5)
        start_redeemable_value = session['starting_redeemable_sc'] if session['starting_redeemable_sc'] is not None else session['starting_sc_balance']
        start_redeemable_var = tk.StringVar(value=str(start_redeemable_value))
        start_redeemable_entry = ttk.Entry(form_frame, textvariable=start_redeemable_var, width=15)
        start_redeemable_entry.grid(row=8, column=1, sticky='w', pady=5)
        
        # Ending SC
        ttk.Label(form_frame, text="Ending Total SC:").grid(row=9, column=0, sticky='w', pady=5)
        end_sc_var = tk.StringVar(value=str(session['ending_sc_balance'] or ''))
        end_sc_entry = ttk.Entry(form_frame, textvariable=end_sc_var, width=15)
        end_sc_entry.grid(row=9, column=1, sticky='w', pady=5)
        
        # Ending Redeemable SC
        ttk.Label(form_frame, text="Ending Redeemable SC:").grid(row=10, column=0, sticky='w', pady=5)
        end_redeemable_value = session['ending_redeemable_sc'] if session['ending_redeemable_sc'] is not None else session['ending_sc_balance']
        end_redeemable_var = tk.StringVar(value=str(end_redeemable_value if end_redeemable_value is not None else ''))
        end_redeemable_entry = ttk.Entry(form_frame, textvariable=end_redeemable_var, width=15)
        end_redeemable_entry.grid(row=10, column=1, sticky='w', pady=5)
        
        # P/L Preview
        pnl_label = ttk.Label(form_frame, text="", font=('Arial', 10, 'bold'))
        pnl_label.grid(row=11, column=0, columnspan=2, pady=10)
        
        def update_pnl(*args):
            try:
                start_red = float(start_redeemable_var.get())
                end_red = float(end_redeemable_var.get())
                change = end_red - start_red
                if change >= 0:
                    pnl_label.config(text=f"Redeemable Change: +{change:.2f} SC", foreground='green')
                else:
                    pnl_label.config(text=f"Redeemable Change: {change:.2f} SC", foreground='red')
            except:
                pnl_label.config(text="")
        
        start_redeemable_var.trace_add('write', update_pnl)
        end_redeemable_var.trace_add('write', update_pnl)
        update_pnl()  # Initial calculation
        
        # Notes
        ttk.Label(form_frame, text="Notes:").grid(row=12, column=0, sticky='nw', pady=5)
        notes_text = tk.Text(form_frame, height=6, width=40, wrap='word')
        notes_text.grid(row=12, column=1, pady=5)
        if session['notes']:
            notes_text.insert('1.0', session['notes'])
        
        def save_changes():
            try:
                # Validate fields
                new_start_date = start_date_var.get().strip()
                new_end_date = end_date_var.get().strip()
                new_start_time = start_time_var.get().strip()
                new_end_time = end_time_var.get().strip()
                new_start_sc = start_sc_var.get().strip()
                new_start_redeemable = start_redeemable_var.get().strip()
                new_end_sc = end_sc_var.get().strip()
                new_end_redeemable = end_redeemable_var.get().strip()
                new_notes = notes_text.get('1.0', 'end-1c').strip()
                new_site = site_var.get().strip()
                new_user = user_var.get().strip()
                new_game_type = game_type_var.get().strip()
                
                if not all([new_start_date, new_end_date, new_start_sc, new_start_redeemable, 
                           new_end_sc, new_end_redeemable, new_site, new_user, new_game_type]):
                    messagebox.showwarning("Missing Fields", "Please fill in all required fields")
                    return
                
                # Validate numbers
                valid_start, start_val = validate_currency(new_start_sc)
                if not valid_start:
                    messagebox.showerror("Invalid Starting Total SC", start_val)
                    return
                
                valid_start_red, start_red_val = validate_currency(new_start_redeemable)
                if not valid_start_red:
                    messagebox.showerror("Invalid Starting Redeemable SC", start_red_val)
                    return
                
                valid_end, end_val = validate_currency(new_end_sc)
                if not valid_end:
                    messagebox.showerror("Invalid Ending Total SC", end_val)
                    return
                
                valid_end_red, end_red_val = validate_currency(new_end_redeemable)
                if not valid_end_red:
                    messagebox.showerror("Invalid Ending Redeemable SC", end_red_val)
                    return
                
                # Validate dates
                try:
                    from gui_tabs import parse_date
                    parsed_start_date = parse_date(new_start_date)
                    parsed_end_date = parse_date(new_end_date)
                except:
                    messagebox.showerror("Invalid Date", "Please enter valid dates (YYYY-MM-DD)")
                    return
                
                # Get site and user IDs
                conn = self.db.get_connection()
                c = conn.cursor()
                
                c.execute("SELECT id FROM sites WHERE name = ?", (new_site,))
                site_row = c.fetchone()
                if not site_row:
                    conn.close()
                    messagebox.showerror("Error", f"Site '{new_site}' not found")
                    return
                new_site_id = site_row['id']
                
                c.execute("SELECT id FROM users WHERE name = ?", (new_user,))
                user_row = c.fetchone()
                if not user_row:
                    conn.close()
                    messagebox.showerror("Error", f"User '{new_user}' not found")
                    return
                new_user_id = user_row['id']
                
                # Update session with new values
                c.execute('''
                    UPDATE game_sessions
                    SET session_date = ?,
                        end_date = ?,
                        start_time = ?,
                        end_time = ?,
                        site_id = ?,
                        user_id = ?,
                        game_type = ?,
                        starting_sc_balance = ?,
                        starting_redeemable_sc = ?,
                        ending_sc_balance = ?,
                        ending_redeemable_sc = ?,
                        notes = ?
                    WHERE id = ?
                ''', (parsed_start_date, parsed_end_date, new_start_time, new_end_time, 
                      new_site_id, new_user_id, new_game_type,
                      start_val, start_red_val, end_val, end_red_val, 
                      new_notes, session_id))
                
                conn.commit()
                conn.close()
                
                # Recalculate tax fields using the canonical engine
                recalc_count = self.session_mgr.auto_recalculate_affected_sessions(
                    new_site_id, new_user_id, parsed_start_date, new_start_time
                )
                
                dialog.destroy()
                messagebox.showinfo(
                    "Success",
                    "Session updated successfully" + (f" (recalculated {recalc_count} sessions)" if recalc_count else "")
                )
                self.refresh_all_views()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update session: {str(e)}")
        
        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="Save Changes", command=save_changes).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)
    
    def delete_game_session(self):
        """Delete selected game session"""
        # Check if editing a session in the form
        if self.gs_edit_id:
            session_id = self.gs_edit_id
        else:
            # Try to get from tree selection
            sel = self.gs_tree.selection()
            if not sel:
                messagebox.showwarning("No Selection", 
                    "Please select a session to delete or load one in the form")
                return
            
            tags = self.gs_tree.item(sel[0])['tags']
            session_id = int(tags[0])
        
        # Get session details for confirmation
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute('''
            SELECT gs.*, s.name as site_name, u.name as user_name
            FROM game_sessions gs
            JOIN sites s ON gs.site_id = s.id
            JOIN users u ON gs.user_id = u.id
            WHERE gs.id = ?
        ''', (session_id,))
        
        session = c.fetchone()
        
        if not session:
            conn.close()
            messagebox.showerror("Error", "Session not found")
            return
        
        # Confirm deletion
        session_desc = f"{session['site_name']} - {session['user_name']} on {session['session_date']}"
        
        if session['status'] == 'Closed':
            # Warn about deleting closed sessions
            total_taxable = session['total_taxable'] if session['total_taxable'] is not None else 0
            ending_sc = session['ending_sc_balance'] if session['ending_sc_balance'] is not None else 0
            
            response = messagebox.askyesno(
                "Delete Closed Session?",
                f"⚠️¸ WARNING: This session is CLOSED.\n\n"
                f"{session_desc}\n"
                f"Starting: {session['starting_sc_balance']:.2f} SC\n"
                f"Ending: {ending_sc:.2f} SC\n"
                f"Total Taxable: ${total_taxable:.2f}\n\n"
                f"Deleting this will affect your tax calculations!\n\n"
                f"Are you sure you want to delete it?"
            )
        else:
            # Active session - simpler confirmation
            response = messagebox.askyesno(
                "Delete Session?",
                f"Delete this active session?\n\n{session_desc}\n\n"
                f"This cannot be undone."
            )
        
        if not response:
            conn.close()
            return
        
        try:
            session_date = session['session_date']
            user_id = session['user_id']
            
            # Delete any other_income records linked to this session
            c.execute("DELETE FROM other_income WHERE game_session_id = ?", (session_id,))
            
            # Delete the session
            c.execute("DELETE FROM game_sessions WHERE id = ?", (session_id,))
            
            conn.commit()
            conn.close()
            
            # Canonical recompute for this site/user pair
            recalc_count = self.session_mgr.auto_recalculate_affected_sessions(
                session['site_id'], session['user_id'], session_date, session['start_time'] or '00:00:00'
            )
            
            # Clear form if it was loaded
            if self.gs_edit_id == session_id:
                self.clear_game_session_form()
            
            # Refresh views
            self.refresh_all_views()
            
            messagebox.showinfo(
                "Deleted",
                "Session deleted successfully" + (f" (recalculated {recalc_count} sessions)" if recalc_count else "")
            )
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete session:\n{str(e)}")
    
    def refresh_game_sessions(self):
        """Refresh game sessions list"""
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Build query with optional date filter
        query = '''
            SELECT 
                
                gs.id,
                gs.session_date,
                COALESCE(gs.start_time,'00:00:00') as start_time,
                COALESCE(gs.end_date, gs.session_date) as end_date,
                COALESCE(gs.end_time,'00:00:00') as end_time,
                s.name as site_name,
                u.name as user_name,
                gs.game_type,
                COALESCE(gs.starting_sc_balance,0) as starting_total,
                COALESCE(gs.ending_sc_balance,0) as ending_total,
                COALESCE(gs.starting_redeemable_sc, COALESCE(gs.starting_sc_balance,0)) as starting_redeem,
                COALESCE(gs.ending_redeemable_sc, COALESCE(gs.ending_sc_balance,0)) as ending_redeem,
                COALESCE(gs.delta_total, gs.ending_sc_balance - gs.starting_sc_balance) as delta_total,
                COALESCE(gs.delta_redeem, gs.ending_redeemable_sc - gs.starting_redeemable_sc) as delta_redeem,
                COALESCE(gs.basis_consumed, gs.session_basis) as basis_consumed,
                COALESCE(gs.net_taxable_pl, gs.total_taxable, 0) as net_pl,
                gs.status,
                gs.notes

            FROM game_sessions gs
            JOIN sites s ON gs.site_id = s.id
            JOIN users u ON gs.user_id = u.id
            WHERE 1=1
        '''
        
        params = []
        
        # Apply date filter if available
        if hasattr(self, 'gs_filter_start') and hasattr(self, 'gs_filter_end'):
            start = self.gs_filter_start.get().strip()
            end = self.gs_filter_end.get().strip()
            
            if start and end:
                query += ' AND gs.session_date BETWEEN ? AND ?'
                params.extend([start, end])
            elif start:
                query += ' AND gs.session_date >= ?'
                params.append(start)
            elif end:
                query += ' AND gs.session_date <= ?'
                params.append(end)
        
        query += ' ORDER BY gs.session_date DESC, gs.start_time DESC'
        
        c.execute(query, params)
        
        active_count = 0
        data_with_tags = []  # Collect data for SearchableTreeview
        
        for row in c.fetchall():
            if row['status'] != 'Closed':
                active_count += 1

            # Format date/time with multi-day indicator
            time_str = row['start_time'][:5] if row['start_time'] else ""
            raw_date = row['session_date'] or ""
            display_date = raw_date
            if raw_date:
                try:
                    from datetime import datetime
                    display_date = datetime.strptime(raw_date, '%Y-%m-%d').strftime('%m/%d/%y')
                except Exception:
                    display_date = raw_date
            date_time_str = display_date
            if time_str:
                date_time_str = f"{display_date} {time_str}"

            if row['status'] == 'Closed' and row['end_date'] and row['session_date']:
                try:
                    from datetime import datetime
                    start_date = datetime.strptime(row['session_date'], '%Y-%m-%d').date()
                    end_date = datetime.strptime(row['end_date'], '%Y-%m-%d').date()
                    day_span = (end_date - start_date).days
                    if day_span > 0:
                        date_time_str = f"{date_time_str} (+{day_span}d)"
                except Exception:
                    pass
            
            # Format values
            start_total = f"{float(row['starting_total'] or 0):.2f}"
            end_total = f"{float(row['ending_total'] or 0):.2f}" if row['status'] == 'Closed' else "-"
            start_redeem = f"{float(row['starting_redeem'] or 0):.2f}"
            end_redeem = f"{float(row['ending_redeem'] or 0):.2f}" if row['status'] == 'Closed' else "-"

            delta_total = float(row['delta_total'] or 0)
            delta_redeem = float(row['delta_redeem'] or 0)
            delta_total_str = f"{delta_total:+.2f}"
            delta_redeem_str = f"{delta_redeem:+.2f}"

            # Session basis
            basis_val = row['basis_consumed']
            basis_consumed_str = f"${float(basis_val):.2f}" if basis_val is not None else "-"

            # Net P/L (net taxable P/L per spec)
            net_val = row['net_pl']
            if net_val is not None:
                net_val = float(net_val)
                if net_val >= 0:
                    net_pnl = f"+${net_val:.2f}"
                    tag = 'win'
                else:
                    net_pnl = f"${net_val:.2f}"
                    tag = 'loss'
            else:
                net_pnl = "-"
                tag = 'active'

            # Notes indicator
            notes_display = '📝' if row['notes'] else ''

            values = (
                date_time_str,
                row['site_name'],
                row['user_name'],
                row['game_type'],
                start_total,
                end_total,
                start_redeem,
                end_redeem,
                delta_total_str,
                delta_redeem_str,
                basis_consumed_str,
                net_pnl,
                row['status'],
                notes_display
            )

            data_with_tags.append((values, (str(row['id']), tag)))
        
        conn.close()
        
        # Use SearchableTreeview to populate (enables filtering)
        if hasattr(self, 'gs_searchable'):
            self.gs_searchable.set_data(data_with_tags)
        
        # Update active sessions label
        if hasattr(self, 'active_sessions_label'):
            if active_count > 0:
                self.active_sessions_label.config(
                    text=f"Active Sessions: {active_count}",
                    foreground='green'
                )
            else:
                self.active_sessions_label.config(
                    text="Active Sessions: 0",
                    foreground='gray'
                )
    
    # ========================================================================
    # DAILY TAX SESSION METHODS
    # ========================================================================
    
    def refresh_daily_tax_sessions(self):
        """
        Refresh daily tax sessions with new hierarchy:
        Date → User → Game Sessions
        
        This gives household view: one row per date showing combined totals
        """
        # Get search term if available
        search_term = ''
        if hasattr(self, 'dt_search_var'):
            search_term = self.dt_search_var.get().lower().strip()
        
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Get all CLOSED game sessions with filters
        query = '''
            SELECT 
                gs.session_date,
                gs.user_id,
                u.name as user_name,
                gs.site_id,
                s.name as site_name,
                gs.id,
                gs.game_type,
                gs.start_time,
                gs.end_time,
                COALESCE(gs.delta_total, gs.ending_sc_balance - gs.starting_sc_balance) as delta_total,
                COALESCE(gs.net_taxable_pl, gs.total_taxable, 0) as total_taxable,
                gs.notes
            FROM game_sessions gs
            JOIN users u ON gs.user_id = u.id
            JOIN sites s ON gs.site_id = s.id
            WHERE gs.status = 'Closed'
        '''
        
        params = []
        
        # Apply user filter (checkbox style)
        if hasattr(self, 'dt_selected_users') and self.dt_selected_users:
            placeholders = ','.join('?' * len(self.dt_selected_users))
            query += f' AND u.name IN ({placeholders})'
            params.extend(list(self.dt_selected_users))
        
        # Apply site filter (checkbox style)
        if hasattr(self, 'dt_selected_sites') and self.dt_selected_sites:
            placeholders = ','.join('?' * len(self.dt_selected_sites))
            query += f' AND s.name IN ({placeholders})'
            params.extend(list(self.dt_selected_sites))
        
        # Apply date filter
        if hasattr(self, 'dt_filter_start') and hasattr(self, 'dt_filter_end'):
            start = self.dt_filter_start.get().strip()
            end = self.dt_filter_end.get().strip()
            
            if start and end:
                query += ' AND gs.session_date BETWEEN ? AND ?'
                params.extend([start, end])
            elif start:
                query += ' AND gs.session_date >= ?'
                params.append(start)
            elif end:
                query += ' AND gs.session_date <= ?'
                params.append(end)
            else:
                # Default to current year
                from datetime import date
                current_year_start = f"{date.today().year}-01-01"
                current_year_end = str(date.today())
                query += ' AND gs.session_date BETWEEN ? AND ?'
                params.extend([current_year_start, current_year_end])
        else:
            # Default to current year
            from datetime import date
            current_year_start = f"{date.today().year}-01-01"
            current_year_end = str(date.today())
            query += ' AND gs.session_date BETWEEN ? AND ?'
            params.extend([current_year_start, current_year_end])
        
        query += ' ORDER BY gs.session_date DESC, u.name, s.name, gs.start_time'
        
        c.execute(query, params)
        all_sessions = c.fetchall()
        
        # Apply search filter
        if search_term:
            filtered_sessions = []
            for sess in all_sessions:
                search_fields = [
                    str(sess['session_date']),
                    sess['user_name'],
                    sess['site_name'],
                    sess['game_type'],
                    f"{_rowv(sess, 'delta_total', 0):.2f}",
                    f"{sess['total_taxable']:.2f}",
                    sess['notes'] or ''
                ]
                if any(search_term in str(field).lower() for field in search_fields):
                    filtered_sessions.append(sess)
            all_sessions = filtered_sessions
        
        # Group by date, then user, then site
        from collections import defaultdict
        dates = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        
        for sess in all_sessions:
            dates[sess['session_date']][sess['user_id']][sess['site_id']].append(sess)
        
        # Collect parent rows for SearchableTreeview
        parent_data = []
        date_children = {}  # Store children data for each date
        
        # Build tree: Date → User → Sessions
        for session_date in sorted(dates.keys(), reverse=True):
            users_data = dates[session_date]
            
            # Calculate date totals (all users combined)
            date_gameplay = sum(
                _rowv(sess, 'delta_total', 0)
                for user_sessions in users_data.values()
                for site_sessions in user_sessions.values()
                for sess in site_sessions
            )
            date_total = sum(
                sess['total_taxable']
                for user_sessions in users_data.values()
                for site_sessions in user_sessions.values()
                for sess in site_sessions
            )
            date_status = 'Win' if date_total >= 0 else 'Loss'
            date_tag = 'win' if date_total >= 0 else 'loss'
            
            total_sessions = sum(
                len(site_sessions)
                for user_sessions in users_data.values()
                for site_sessions in user_sessions.values()
            )
            
            # Parent row values with text for arrow
            parent_values = (
                session_date,
                f"{date_gameplay:+.2f}",
                f"${date_total:+.2f}" + (" ✓" if date_total >= 0 else " ✗"),
                date_status,
                f"{len(users_data)} users, {total_sessions} sessions",
                ''
            )
            parent_data.append((parent_values, (date_tag,), '▶'))  # Include arrow text
            
            # Store children for this date
            date_children[session_date] = (users_data, date_tag)
        
        # Define callback to add children
        def add_daily_children(parent_id, parent_values):
            session_date = parent_values[0]
            if session_date not in date_children:
                return
            
            users_data, date_tag = date_children[session_date]
            
            # Users under date
            for user_id in sorted(users_data.keys()):
                sites_data = users_data[user_id]
                user_name = list(sites_data.values())[0][0]['user_name']
                
                # Calculate user totals
                user_gameplay = sum(
                    _rowv(sess, 'delta_total', 0)
                    for site_sessions in sites_data.values()
                    for sess in site_sessions
                )
                user_total = sum(
                    sess['total_taxable']
                    for site_sessions in sites_data.values()
                    for sess in site_sessions
                )
                user_status = 'Win' if user_total >= 0 else 'Loss'
                user_tag = 'win' if user_total >= 0 else 'loss'
                
                user_sessions_count = sum(len(sessions) for sessions in sites_data.values())
                
                # User header
                user_item = self.dt_tree.insert(parent_id, 'end', text='  ▶', values=(
                    user_name,
                    f"{user_gameplay:+.2f}",
                    f"${user_total:+.2f}" + (" ✓" if user_total >= 0 else " ✗"),
                    user_status,
                    f"{user_sessions_count} sessions",
                    ''
                ), tags=(user_tag,))
                
                # Sessions under user
                all_user_sessions = [
                    sess
                    for site_sessions in sites_data.values()
                    for sess in site_sessions
                ]
                all_user_sessions.sort(key=lambda x: x['start_time'])
                
                for sess in all_user_sessions:
                    time_range = f"{sess['start_time'][:5]}-{sess['end_time'][:5]}" if sess['end_time'] else f"{sess['start_time'][:5]}-Active"
                    sess_tag = 'win' if sess['total_taxable'] >= 0 else 'loss'
                    sess_status = "Win" if sess['total_taxable'] >= 0 else "Loss"
                    sess_notes_display = '📝' if sess['notes'] else ''
                    
                    self.dt_tree.insert(user_item, 'end', text='    └─', values=(
                        f"{sess['site_name']} {sess['game_type']}",
                        f"{_rowv(sess, 'delta_total', 0):+.2f}",
                        f"${sess['total_taxable']:+.2f}" + (" ✓" if sess['total_taxable'] >= 0 else " ✗"),
                        sess_status,
                        time_range,
                        sess_notes_display
                    ), tags=(str(sess['id']), sess_tag))
        
        # Use SearchableTreeview with text and children callback
        if hasattr(self, 'dt_searchable'):
            self.dt_searchable.set_data(parent_data, children_callback=add_daily_children)
        
        conn.close()
    
    def expand_all_daily_tax(self):
        """Expand all items in daily tax tree"""
        def expand_recursive(item):
            self.dt_tree.item(item, open=True)
            for child in self.dt_tree.get_children(item):
                expand_recursive(child)
        
        for item in self.dt_tree.get_children():
            expand_recursive(item)

    def collapse_all_daily_tax(self):
        """Collapse all items in daily tax tree"""
        def collapse_recursive(item):
            self.dt_tree.item(item, open=False)
            for child in self.dt_tree.get_children(item):
                collapse_recursive(child)
        
        for item in self.dt_tree.get_children():
            collapse_recursive(item)
    
    def show_dt_site_filter(self):
        """Show site filter dialog for Daily Sessions"""
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT name FROM sites WHERE active = 1 ORDER BY name")
        all_sites = [row['name'] for row in c.fetchall()]
        conn.close()
        
        if not all_sites:
            messagebox.showinfo("No Sites", "No sites found")
            return
        
        from table_helpers import FilterDialog
        FilterDialog(self.root, "Sites", all_sites, self.dt_selected_sites, 
                    self.on_dt_site_filter_changed)
    
    def show_dt_user_filter(self):
        """Show user filter dialog for Daily Sessions"""
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT name FROM users WHERE active = 1 ORDER BY name")
        all_users = [row['name'] for row in c.fetchall()]
        conn.close()
        
        if not all_users:
            messagebox.showinfo("No Users", "No users found")
            return
        
        from table_helpers import FilterDialog
        FilterDialog(self.root, "Users", all_users, self.dt_selected_users, 
                    self.on_dt_user_filter_changed)
    
    def on_dt_site_filter_changed(self, column_name, selected_values):
        """Callback when site filter changes"""
        self.dt_selected_sites = selected_values
        
        if not selected_values:
            self.dt_site_filter_label.config(text="All", foreground='gray')
        else:
            count = len(selected_values)
            self.dt_site_filter_label.config(text=f"{count} selected", foreground='blue')
    
    def on_dt_user_filter_changed(self, column_name, selected_values):
        """Callback when user filter changes"""
        self.dt_selected_users = selected_values
        
        if not selected_values:
            self.dt_user_filter_label.config(text="All", foreground='gray')
        else:
            count = len(selected_values)
            self.dt_user_filter_label.config(text=f"{count} selected", foreground='blue')
    
    def add_daily_session_notes(self):
        """Add or edit notes for a daily session, or view game session details"""
        sel = self.dt_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection", "Please select a day or game session")
            return
        
        # Get the selected item's tags and values
        tags = self.dt_tree.item(sel[0])['tags']
        values = self.dt_tree.item(sel[0])['values']
        
        # Determine if this is a day row or a game session row
        # Game session rows have their site/game in first column like "Stake Table Games"
        # Day rows have dates in first column like "2025-12-27"
        first_col = str(values[0]) if values else ''
        
        # Check if this is a game session (has site name in first column)
        is_game_session = first_col and not (len(first_col) == 10 and first_col[4] == '-' and first_col[7] == '-')
        
        if is_game_session:
            # This is a game session - show details popup
            self.view_game_session_from_daily(values)
        else:
            # This is a day row - edit daily session notes
            self.edit_daily_session_notes(tags)
    
    def edit_daily_session_notes(self, tags):
        """Edit notes for a daily tax session"""
        # Find the date from tags
        session_date = None
        for tag in tags:
            if len(tag) == 10 and tag[4] == '-' and tag[7] == '-':
                session_date = tag
                break
        
        if not session_date:
            messagebox.showinfo("Invalid Selection", "Please select a specific day (not a month header)")
            return
        
        # Get current notes
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute('SELECT notes FROM daily_tax_sessions WHERE session_date = ?', (session_date,))
        row = c.fetchone()
        current_notes = row['notes'] if row and row['notes'] else ''
        conn.close()
        
        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Daily Session Notes - {session_date}")
        dialog.geometry("500x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text=f"Notes for {session_date}:", 
                 font=('Arial', 11, 'bold')).pack(pady=10)
        
        notes_text = tk.Text(dialog, height=10, width=60, wrap='word')
        notes_text.pack(padx=10, pady=10, fill='both', expand=True)
        notes_text.insert('1.0', current_notes)
        notes_text.focus()
        
        def save_notes():
            new_notes = notes_text.get('1.0', 'end-1c').strip()
            
            conn = self.db.get_connection()
            c = conn.cursor()
            c.execute('UPDATE daily_tax_sessions SET notes = ? WHERE session_date = ?',
                     (new_notes if new_notes else None, session_date))
            conn.commit()
            conn.close()
            
            dialog.destroy()
            self.refresh_daily_tax_sessions()
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="Save", command=save_notes).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)
    
    def view_game_session_from_daily(self, values):
        """Show game session details popup from Daily Sessions tab"""
        # Get the session ID from the tree item tags
        sel = self.dt_tree.selection()
        if not sel:
            messagebox.showinfo("Error", "No selection found")
            return
        
        # Check if this is a game session (has numeric tag = session ID)
        tags = self.dt_tree.item(sel[0])['tags']
        if not tags:
            messagebox.showinfo("Info", "Please select a game session")
            return
        
        # Try to get session ID from first tag
        try:
            session_id = int(tags[0])
        except (ValueError, IndexError):
            messagebox.showinfo("Info", "Please select a game session, not a date or month header")
            return
        
        # Get session details from database
        conn = self.db.get_connection()
        c = conn.cursor()
        
        c.execute('''
            SELECT gs.id, gs.session_date, gs.start_time, gs.end_time,
                   s.name as site, u.name as user, gs.game_type,
                   gs.starting_sc_balance, gs.ending_sc_balance,
                   gs.sc_change, gs.delta_total, gs.delta_redeem,
                   COALESCE(gs.net_taxable_pl, gs.total_taxable, 0) as total_taxable,
                   gs.notes, gs.status
            FROM game_sessions gs
            JOIN sites s ON gs.site_id = s.id
            JOIN users u ON gs.user_id = u.id
            WHERE gs.id = ?
        ''', (session_id,))
        
        target_session = c.fetchone()
        
        if not target_session:
            conn.close()
            messagebox.showinfo("Not Found", "Could not locate this game session")
            return
        
        # Create details dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Game Session Details - {target_session['session_date']}")
        dialog.geometry("500x600")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Header
        header_frame = ttk.Frame(dialog)
        header_frame.pack(fill='x', padx=20, pady=10)
        
        ttk.Label(header_frame, text=f"{target_session['site']} - {target_session['game_type']}", 
                 font=('Arial', 14, 'bold')).pack()
        ttk.Label(header_frame, text=f"{target_session['user']}", 
                 font=('Arial', 10)).pack()
        
        # Details
        details_frame = ttk.Frame(dialog)
        details_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        def add_row(label, value, row):
            ttk.Label(details_frame, text=label + ":", 
                     font=('Arial', 10, 'bold')).grid(row=row, column=0, sticky='w', pady=5)
            ttk.Label(details_frame, text=str(value), 
                     font=('Arial', 10)).grid(row=row, column=1, sticky='w', padx=20, pady=5)
        
        row = 0
        add_row("Date", target_session['session_date'], row); row += 1
        
        time_str = f"{target_session['start_time']}"
        if target_session['end_time']:
            time_str += f" → {target_session['end_time']}"
        add_row("Time", time_str, row); row += 1
        
        add_row("Starting SC", f"${target_session['starting_sc_balance']:.2f}", row); row += 1
        add_row("Ending SC", f"${target_session['ending_sc_balance']:.2f}", row); row += 1
        add_row("SC Change", f"{target_session['sc_change']:+.2f}", row); row += 1
        
        ttk.Separator(details_frame, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky='ew', pady=10)
        row += 1
        
        add_row("Delta Total (SC)", f"{(target_session['delta_total'] or 0):+.2f}", row); row += 1
        add_row("Delta Redeemable (SC)", f"{(target_session['delta_redeem'] or 0):+.2f}", row); row += 1
        add_row("Net Taxable", f"${target_session['total_taxable']:+.2f}", row); row += 1
        
        if target_session['notes']:
            ttk.Separator(details_frame, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky='ew', pady=10)
            row += 1
            
            ttk.Label(details_frame, text="Notes:", 
                     font=('Arial', 10, 'bold')).grid(row=row, column=0, sticky='nw', pady=5)
            notes_label = ttk.Label(details_frame, text=target_session['notes'], 
                                   font=('Arial', 10), wraplength=300, justify='left')
            notes_label.grid(row=row, column=1, sticky='w', padx=20, pady=5)
        
        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=20)
        
        def view_in_game_sessions():
            # Switch to Game Sessions tab and select this session
            self.notebook.select(self.game_sessions_tab)
            
            # Find and select the session in the tree
            for item in self.gs_tree.get_children():
                item_tags = self.gs_tree.item(item)['tags']
                if item_tags and int(item_tags[0]) == target_session['id']:
                    self.gs_tree.selection_set(item)
                    self.gs_tree.see(item)
                    break
            
            dialog.destroy()
        
        ttk.Button(btn_frame, text="View in Game Sessions", 
                  command=view_in_game_sessions, width=20).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Close", command=dialog.destroy, width=12).pack(side='left', padx=5)
        
        conn.close()
    
    # ========================================================================
    # UNREALIZED POSITIONS METHODS
    # ========================================================================
    
    def refresh_unrealized_positions(self):
        """Refresh unrealized positions (sites with remaining basis)"""
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Collect all data first
        all_data = []
        
        # Get date filter if available
        filter_start = None
        filter_end = None
        if hasattr(self, 'unreal_filter_start') and hasattr(self, 'unreal_filter_end'):
            filter_start = self.unreal_filter_start.get().strip()
            filter_end = self.unreal_filter_end.get().strip()
        
        # Get all site/user combinations with purchases (exclude dormant)
        c.execute('''
            SELECT DISTINCT
                p.site_id,
                p.user_id,
                s.name as site_name,
                u.name as user_name
            FROM purchases p
            JOIN sites s ON p.site_id = s.id
            JOIN users u ON p.user_id = u.id
            WHERE p.remaining_amount > 0.001
              AND (p.status IS NULL OR p.status = 'active')
        ''')
        
        positions = c.fetchall()
        
        for pos in positions:
            site_id = pos['site_id']
            user_id = pos['user_id']
            
            # Get REMAINING purchase basis (after FIFO consumption from redemptions, exclude dormant)
            # Start date = oldest purchase with remaining basis (not all purchases)
            c.execute('''
                SELECT 
                    MIN(purchase_date) as start_date,
                    SUM(remaining_amount) as remaining_basis,
                    SUM(sc_received) as total_sc_purchased
                FROM purchases
                WHERE site_id = ? AND user_id = ?
                  AND (status IS NULL OR status = 'active')
                  AND remaining_amount > 0.001
            ''', (site_id, user_id))
            
            purchase_data = c.fetchone()
            remaining_basis = purchase_data['remaining_basis'] or 0
            total_sc_purchased = purchase_data['total_sc_purchased'] or 0
            
            # Skip if no remaining basis (fully redeemed)
            # Use epsilon comparison for floating point
            if remaining_basis < 0.01:  # Less than 1 cent
                continue
            
            # Get current SC balance from last game session
            c.execute('''
                SELECT ending_sc_balance, ending_redeemable_sc, session_date, end_time
                FROM game_sessions
                WHERE site_id = ? AND user_id = ? AND ending_sc_balance IS NOT NULL
                ORDER BY session_date DESC, end_time DESC
                LIMIT 1
            ''', (site_id, user_id))
            
            last_session = c.fetchone()
            
            if last_session:
                # Use redeemable SC for unrealized P/L (what you can cash out NOW)
                # Fallback to total SC if redeemable not set (old sessions)
                current_sc = last_session['ending_redeemable_sc'] if last_session['ending_redeemable_sc'] is not None else last_session['ending_sc_balance']
                last_activity = last_session['session_date']
                last_time = last_session['end_time']
                
                # Check for redemptions AFTER last session
                c.execute('''
                    SELECT COALESCE(SUM(amount), 0) as total_redeemed
                    FROM redemptions
                    WHERE site_id = ? AND user_id = ?
                    AND (redemption_date > ? OR (redemption_date = ? AND redemption_time > ?))
                ''', (site_id, user_id, last_activity, last_activity, last_time or '00:00:00'))
                
                redemptions_since = c.fetchone()['total_redeemed']
                
                # Reduce balance by redemptions
                if redemptions_since >= current_sc:
                    # Fully redeemed - check for new purchases
                    c.execute('''
                        SELECT COALESCE(SUM(sc_received), 0) as new_sc
                        FROM purchases
                        WHERE site_id = ? AND user_id = ?
                        AND (purchase_date > ? OR (purchase_date = ? AND purchase_time > ?))
                    ''', (site_id, user_id, last_activity, last_activity, last_time or '00:00:00'))
                    
                    new_purchases = c.fetchone()['new_sc']
                    
                    if new_purchases > 0:
                        # New purchases after redemption - calculate total SC
                        # Get the starting balance from most recent purchase + all SC received
                        c.execute('''
                            SELECT starting_sc_balance, SUM(sc_received) as total_sc_received
                            FROM purchases
                            WHERE site_id = ? AND user_id = ?
                            AND (purchase_date > ? OR (purchase_date = ? AND purchase_time > ?))
                            ORDER BY purchase_date DESC, purchase_time DESC
                            LIMIT 1
                        ''', (site_id, user_id, last_activity, last_activity, last_time or '00:00:00'))
                        
                        recent_purchase = c.fetchone()
                        if recent_purchase and recent_purchase['starting_sc_balance'] is not None:
                            current_sc = recent_purchase['starting_sc_balance'] + recent_purchase['total_sc_received']
                        else:
                            current_sc = new_purchases
                        last_activity = purchase_data['start_date']  # Show most recent purchase date
                    else:
                        # Fully redeemed, no new purchases
                        current_sc = 0
                else:
                    # Partial redemption
                    current_sc -= redemptions_since
            else:
                # No game sessions yet - calculate from purchases
                # Get most recent purchase's starting balance + all SC received
                c.execute('''
                    SELECT starting_sc_balance
                    FROM purchases
                    WHERE site_id = ? AND user_id = ?
                      AND (status IS NULL OR status = 'active')
                    ORDER BY purchase_date DESC, purchase_time DESC
                    LIMIT 1
                ''', (site_id, user_id))
                
                recent_purchase = c.fetchone()
                if recent_purchase and recent_purchase['starting_sc_balance'] is not None:
                    # Starting balance from most recent purchase + all SC received
                    current_sc = recent_purchase['starting_sc_balance'] + total_sc_purchased
                else:
                    # No starting balance recorded - use total SC purchased
                    current_sc = total_sc_purchased
                
                # Get last activity date from most recent purchase
                c.execute('''
                    SELECT MAX(purchase_date) as last_date
                    FROM purchases
                    WHERE site_id = ? AND user_id = ?
                ''', (site_id, user_id))
                last_activity = c.fetchone()['last_date'] or purchase_data['start_date']
            
            # Calculate current value and unrealized P/L
            # Unrealized P/L = Current Redeemable SC value - Remaining Basis
            # This shows what you could cash out NOW vs. what you've invested
            sc_rate = self.session_mgr.get_sc_rate(site_id)
            
            if current_sc is not None:
                current_value = current_sc * sc_rate
                unrealized_pnl = current_value - remaining_basis
            else:
                # No session data - can't calculate current value
                current_value = None
                unrealized_pnl = None
            
            # Get notes from site_sessions if exists
            c.execute('''
                SELECT notes FROM site_sessions
                WHERE site_id = ? AND user_id = ? AND status IN ('Active', 'Redeeming')
                ORDER BY start_date DESC
                LIMIT 1
            ''', (site_id, user_id))
            
            notes_row = c.fetchone()
            has_notes = bool(notes_row and notes_row['notes'])
            notes_icon = '📝' if has_notes else ''
            
            # Determine tag
            if unrealized_pnl is not None:
                if unrealized_pnl > 0:
                    tag = 'profit'
                elif unrealized_pnl < 0:
                    tag = 'loss'
                else:
                    tag = ''
            else:
                tag = 'unknown'
            
            values = (
                pos['site_name'],
                pos['user_name'],
                purchase_data['start_date'],
                f"${remaining_basis:.2f}",
                f"{current_sc:.2f}" if current_sc is not None else "Unknown",
                f"${current_value:.2f}" if current_value is not None else "Unknown",
                f"${unrealized_pnl:+.2f}" if unrealized_pnl is not None else "Unknown",
                last_activity,
                notes_icon
            )
            
            # Apply date filter if set
            if filter_start or filter_end:
                # Filter by last activity date
                if filter_start and last_activity < filter_start:
                    continue
                if filter_end and last_activity > filter_end:
                    continue
            
            # Store with tags for searchable
            all_data.append((values, (str(site_id), str(user_id), tag)))
        
        conn.close()
        
        # Update searchable treeview with all data
        if hasattr(self, 'unreal_searchable'):
            self.unreal_searchable.set_data(all_data)
        else:
            # Fallback to manual insert if searchable not initialized
            for item in self.unreal_tree.get_children():
                self.unreal_tree.delete(item)
            for values, tags in all_data:
                self.unreal_tree.insert('', 'end', values=values, tags=tags)
    
    def add_unrealized_notes(self):
        """Add/edit notes for unrealized position"""
        # This can reuse the existing open_session_details_popup logic
        # Or create a simple notes dialog similar to closed session notes
        sel = self.unreal_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select a position to add notes")
            return
        
        # Get site and user IDs from tags
        tags = self.unreal_tree.item(sel[0])['tags']
        if len(tags) < 2:
            return
        
        site_id = int(tags[0])
        user_id = int(tags[1])
        
        # Get or create site_session
        conn = self.db.get_connection()
        c = conn.cursor()
        
        c.execute('''
            SELECT id, notes FROM site_sessions
            WHERE site_id = ? AND user_id = ? AND status IN ('Active', 'Redeeming')
            ORDER BY start_date DESC
            LIMIT 1
        ''', (site_id, user_id))
        
        session = c.fetchone()
        
        if session:
            session_id = session['id']
            current_notes = session['notes'] or ''
        else:
            # Create a site_session if it doesn't exist
            c.execute('''
                INSERT INTO site_sessions (site_id, user_id, start_date, status, total_buyin)
                VALUES (?, ?, date('now'), 'Active', 0)
            ''', (site_id, user_id))
            session_id = c.lastrowid
            current_notes = ''
        
        conn.close()
        
        # Show notes dialog (similar to open session details)
        popup = tk.Toplevel(self.root)
        popup.title("Position Notes")
        popup.geometry("500x300")
        popup.transient(self.root)
        popup.grab_set()
        
        ttk.Label(popup, text="Position Notes:", font=('Arial', 11, 'bold')).pack(pady=10)
        
        text_frame = ttk.Frame(popup)
        text_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        text = tk.Text(text_frame, wrap='word', height=10, width=50)
        text.pack(side='left', fill='both', expand=True)
        
        scroll = ttk.Scrollbar(text_frame, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        
        text.insert('1.0', current_notes)
        
        def save_notes():
            new_notes = text.get('1.0', 'end-1c').strip()
            conn = self.db.get_connection()
            c = conn.cursor()
            c.execute("UPDATE site_sessions SET notes = ? WHERE id = ?", (new_notes, session_id))
            conn.commit()
            conn.close()
            
            popup.destroy()
            messagebox.showinfo("Success", "Notes saved")
            self.refresh_unrealized_positions()
        
        btn_frame = ttk.Frame(popup)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="Save", command=save_notes).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=popup.destroy).pack(side='left', padx=5)
    
    def close_unrealized_balance(self):
        """Close/dormant an unrealized balance - removes from view, no tax impact"""
        sel = self.unreal_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select a position to close")
            return
        
        # Get site and user info
        tags = self.unreal_tree.item(sel[0])['tags']
        if len(tags) < 2:
            return
        
        site_id = int(tags[0])
        user_id = int(tags[1])
        
        # Get site and user names for display
        values = self.unreal_tree.item(sel[0])['values']
        site_name = values[0]
        user_name = values[1]
        basis_str = values[3]  # Purchase Basis column
        
        # Check for active session
        conn = self.db.get_connection()
        c = conn.cursor()
        
        c.execute('''
            SELECT id FROM game_sessions
            WHERE site_id = ? AND user_id = ? AND status = 'Active'
        ''', (site_id, user_id))
        
        if c.fetchone():
            conn.close()
            messagebox.showerror("Active Session", 
                "Cannot close balance - you have an active session on this site.\n\n"
                "Please end the session first.")
            return
        
        # Get current SC balance from last game session
        c.execute('''
            SELECT ending_sc_balance
            FROM game_sessions
            WHERE site_id = ? AND user_id = ? AND ending_sc_balance IS NOT NULL
            ORDER BY session_date DESC, end_time DESC
            LIMIT 1
        ''', (site_id, user_id))
        
        last_session = c.fetchone()
        current_sc_balance = last_session['ending_sc_balance'] if last_session else 0
        
        # Get total cost basis (for calculating net loss)
        c.execute('''
            SELECT SUM(remaining_amount) as total_basis
            FROM purchases
            WHERE site_id = ? AND user_id = ? AND remaining_amount > 0 AND status = 'active'
        ''', (site_id, user_id))
        
        result = c.fetchone()
        total_cost_basis = result['total_basis'] if result and result['total_basis'] else 0
        
        if total_cost_basis == 0:
            conn.close()
            messagebox.showinfo("No Balance", "No active basis to close for this site/user")
            return
        
        conn.close()
        
        # Confirmation dialog
        response = messagebox.askyesno(
            "Close Balance",
            f"Close balance for {site_name} ({user_name})?\n\n"
            f"Current SC balance: {current_sc_balance:.2f} SC (${current_sc_balance:.2f})\n"
            f"Cost basis: ${total_cost_basis:.2f}\n"
            f"Net loss if closed: ${total_cost_basis - current_sc_balance:.2f}\n\n"
            f"This will:\n"
            f"• Mark ${current_sc_balance:.2f} SC as dormant\n"
            f"• Remove from Unrealized tab\n"
            f"• Show -${total_cost_basis - current_sc_balance:.2f} cash flow loss in Realized tab\n"
            f"• NO tax impact (not a deduction)\n"
            f"• Dormant balance will reactivate if you play this site again\n\n"
            f"Continue?",
            icon='warning'
        )
        
        if not response:
            return
        
        conn = self.db.get_connection()
        c = conn.cursor()
        
        from datetime import date, datetime
        today = date.today().strftime('%Y-%m-%d')
        now = datetime.now().strftime('%H:%M:%S')
        
        # Get current SC balance from last session
        c.execute('''
            SELECT ending_sc_balance
            FROM game_sessions
            WHERE site_id = ? AND user_id = ? AND ending_sc_balance IS NOT NULL
            ORDER BY session_date DESC, end_time DESC
            LIMIT 1
        ''', (site_id, user_id))
        
        last_session = c.fetchone()
        current_sc_balance = last_session['ending_sc_balance'] if last_session else 0
        
        # Calculate net cash flow loss for this batch
        # Total cost basis - current SC balance = net loss
        c.execute('''
            SELECT COALESCE(SUM(remaining_amount), 0) as total_basis
            FROM purchases
            WHERE site_id = ? AND user_id = ? AND remaining_amount > 0 AND status = 'active'
        ''', (site_id, user_id))
        
        total_cost_basis = c.fetchone()['total_basis']
        net_loss = total_cost_basis - current_sc_balance
        
        # Create a special "balance closed" redemption showing the net loss
        # Amount = $0 (nothing redeemed), but notes show what happened
        c.execute('''
            INSERT INTO redemptions 
            (redemption_date, redemption_time, site_id, user_id, amount, redemption_method_id, notes, processed)
            VALUES (?, ?, ?, ?, 0, NULL, ?, 1)
        ''', (today, now, site_id, user_id, 
              f"Balance Closed - Net Loss: ${net_loss:.2f} (${current_sc_balance:.2f} SC marked dormant)"))
        
        redemption_id = c.lastrowid
        
        # Create tax_session showing net cash flow (NOT a tax deduction)
        # This represents: Put in $13.49, keeping $0.48 dormant = -$13.01 cash flow for this batch
        c.execute('''
            INSERT INTO tax_sessions
            (session_date, site_id, redemption_id, cost_basis, payout, net_pl, user_id)
            VALUES (?, ?, ?, ?, 0, ?, ?)
        ''', (today, site_id, redemption_id, net_loss, -net_loss, user_id))
        
        # Mark all active purchases as dormant
        c.execute('''
            UPDATE purchases
            SET status = 'dormant'
            WHERE site_id = ? AND user_id = ? AND remaining_amount > 0 AND status = 'active'
        ''', (site_id, user_id))
        
        conn.commit()
        conn.close()
        
        # Refresh views
        self.refresh_unrealized_positions()
        self.refresh_closed_sessions()  # Realized tab
        
        messagebox.showinfo("Success", 
            f"Balance closed for {site_name} ({user_name})\n\n"
            f"Net cash flow loss: -${net_loss:.2f}\n"
            f"Dormant SC balance: {current_sc_balance:.2f} SC (${current_sc_balance:.2f})\n\n"
            f"The -${net_loss:.2f} will show in Realized tab\n"
            f"Dormant ${current_sc_balance:.2f} will reactivate on next session")
    
    def sort_unrealized_column(self, col):
        """Sort unrealized positions by column"""
        # Toggle sort direction if same column, otherwise default to ascending
        if hasattr(self, 'unreal_sort_column') and self.unreal_sort_column == col:
            self.unreal_sort_reverse = not self.unreal_sort_reverse
        else:
            self.unreal_sort_column = col
            self.unreal_sort_reverse = False
        
        # Get all items
        items = [(self.unreal_tree.set(item, col), item) for item in self.unreal_tree.get_children('')]
        
        # Determine column index
        cols = ('Site', 'User', 'Start', 'Purchase Basis', 'Current SC', 'Current Value', 
                'Unrealized P/L', 'Bonuses', 'Last Activity', 'Notes')
        col_index = cols.index(col)
        
        # Sort - handle currency values
        def sort_key(item):
            val = item[0]
            # Remove $ and + signs for numeric columns
            if col in ('Purchase Basis', 'Current Value', 'Unrealized P/L', 'Bonuses', 'Current SC'):
                if val in ('Unknown', '-', ''):
                    return -999999 if self.unreal_sort_reverse else 999999
                val = val.replace('$', '').replace('+', '').replace(',', '')
                try:
                    return float(val)
                except:
                    return 0
            return val.lower() if isinstance(val, str) else val
        
        items.sort(key=sort_key, reverse=self.unreal_sort_reverse)
        
        # Rearrange items in sorted order
        for index, (val, item) in enumerate(items):
            self.unreal_tree.move(item, '', index)
        
        # Update column heading to show sort direction
        for c in cols:
            if c == col:
                direction = ' ▼' if self.unreal_sort_reverse else ' ▲'
                self.unreal_tree.heading(c, text=c + direction)
            else:
                self.unreal_tree.heading(c, text=c)
    
    
    def smart_save_expense(self):
        """Smart save - detects if adding new or updating existing"""
        if self.e_tree.selection():
            # Updating existing (row is selected)
            self.update_expense()
        else:
            # Adding new
            self.save_expense()
    
    def save_expense(self):
        """Add new expense (business expenses don't need user)"""
        try:
            # Validate and parse date
            date_str = self.e_date.get().strip()
            if not date_str:
                messagebox.showwarning("Missing Date", "Please enter an expense date")
                return
            
            try:
                edate = parse_date(date_str)
            except:
                messagebox.showerror("Invalid Date", "Please enter a valid date (YYYY-MM-DD)")
                return
            
            # Validate amount
            amount_str = self.e_amount.get().strip()
            if not amount_str:
                messagebox.showwarning("Missing Amount", "Please enter an amount")
                return
            
            valid, result = validate_currency(amount_str)
            if not valid:
                messagebox.showerror("Invalid Amount", result)
                return
            amount = result
            
            # Validate vendor (description)
            vendor = self.e_vendor.get().strip()
            if not vendor:
                messagebox.showwarning("Missing Vendor", "Please enter vendor name")
                return
            
            # Validate category
            category = self.e_category.get().strip()
            if not category:
                messagebox.showwarning("Missing Category", "Please select a category")
                return
            
            desc = self.e_desc.get().strip()
            
            conn = self.db.get_connection()
            c = conn.cursor()
            
            # Get user_id if selected (optional)
            user_id = None
            user_name = self.e_user.get().strip()
            if user_name:
                c.execute("SELECT id FROM users WHERE name = ?", (user_name,))
                user_row = c.fetchone()
                if user_row:
                    user_id = user_row['id']
            
            # Insert new expense
            c.execute('''
                INSERT INTO expenses (expense_date, amount, vendor, description, category, user_id) 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (edate, amount, vendor, desc, category, user_id))
            
            conn.commit()
            conn.close()
            
            self.clear_expense_form()
            self.refresh_all_views()
            messagebox.showinfo("Success", "Expense added")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def update_expense(self):
        """Update selected expense"""
        sel = self.e_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select an expense to update")
            return
        
        eid = self.e_tree.item(sel[0])['tags'][0]
        
        try:
            # Validate and parse date
            date_str = self.e_date.get().strip()
            if not date_str:
                messagebox.showwarning("Missing Date", "Please enter an expense date")
                return
            
            try:
                edate = parse_date(date_str)
            except:
                messagebox.showerror("Invalid Date", "Please enter a valid date (YYYY-MM-DD)")
                return
            
            # Validate amount
            amount_str = self.e_amount.get().strip()
            if not amount_str:
                messagebox.showwarning("Missing Amount", "Please enter an amount")
                return
            
            valid, result = validate_currency(amount_str)
            if not valid:
                messagebox.showerror("Invalid Amount", result)
                return
            amount = result
            
            # Validate vendor
            vendor = self.e_vendor.get().strip()
            if not vendor:
                messagebox.showwarning("Missing Vendor", "Please enter vendor name")
                return
            
            # Validate category
            category = self.e_category.get().strip()
            if not category:
                messagebox.showwarning("Missing Category", "Please select a category")
                return
            
            desc = self.e_desc.get().strip()
            
            conn = self.db.get_connection()
            c = conn.cursor()
            
            # Get user_id if selected (optional)
            user_id = None
            user_name = self.e_user.get().strip()
            if user_name:
                c.execute("SELECT id FROM users WHERE name = ?", (user_name,))
                user_row = c.fetchone()
                if user_row:
                    user_id = user_row['id']
            
            c.execute('''
                UPDATE expenses 
                SET expense_date=?, amount=?, vendor=?, description=?, category=?, user_id=?
                WHERE id=?
            ''', (edate, amount, vendor, desc, category, user_id, eid))
            
            conn.commit()
            conn.close()
            
            self.clear_expense_form()
            self.refresh_all_views()
            messagebox.showinfo("Success", "Expense updated")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def delete_expense(self):
        """Delete selected expense(s)"""
        sel = self.e_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select expense(s) to delete")
            return
        
        # Check if multiple items selected
        if len(sel) > 1:
            if not messagebox.askyesno("Confirm", f"Delete {len(sel)} expenses?"):
                return
        else:
            if not messagebox.askyesno("Confirm", "Delete this expense?"):
                return
        
        try:
            conn = self.db.get_connection()
            c = conn.cursor()
            
            deleted_count = 0
            for item in sel:
                eid = self.e_tree.item(item)['tags'][0]
                c.execute("DELETE FROM expenses WHERE id = ?", (eid,))
                deleted_count += 1
            
            conn.commit()
            conn.close()
            
            self.clear_expense_form()
            self.refresh_all_views()
            
            if deleted_count > 1:
                messagebox.showinfo("Success", f"Deleted {deleted_count} expenses")
            else:
                messagebox.showinfo("Success", "Expense deleted")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def refresh_open_sessions(self):
        """Refresh open sessions list with actual FIFO remaining balances"""
        # If using new unrealized positions tab, call that instead
        if not hasattr(self, 'os_tree'):
            return self.refresh_unrealized_positions()
        
        for item in self.os_tree.get_children():
            self.os_tree.delete(item)
        
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Build query with optional date filter
        query = '''
            SELECT ss.id, s.name as site, u.name as user_name, ss.start_date, ss.status,
                   ss.total_buyin, ss.total_redeemed, ss.site_id, ss.user_id, ss.notes
            FROM site_sessions ss 
            JOIN sites s ON ss.site_id = s.id
            JOIN users u ON ss.user_id = u.id
            WHERE ss.status IN ('Active', 'Redeeming', 'Below Minimum')
        '''
        
        params = []
        
        # Apply date filter if set
        if hasattr(self, 'os_filter_start') and hasattr(self, 'os_filter_end'):
            start = self.os_filter_start.get().strip()
            end = self.os_filter_end.get().strip()
            
            if start and end:
                query += ' AND ss.start_date BETWEEN ? AND ?'
                params.extend([start, end])
            elif start:
                query += ' AND ss.start_date >= ?'
                params.append(start)
            elif end:
                query += ' AND ss.start_date <= ?'
                params.append(end)
        
        query += ' ORDER BY ss.start_date DESC'
        
        c.execute(query, params)
        
        data = []
        for row in c.fetchall():
            # Calculate actual unredeemed balance from purchases (FIFO remaining)
            c.execute('''
                SELECT COALESCE(SUM(remaining_amount), 0) as remaining
                FROM purchases
                WHERE site_id = ? AND user_id = ? AND remaining_amount > 0
            ''', (row['site_id'], row['user_id']))
            
            actual_balance = float(c.fetchone()['remaining'])
            
            # Truncate notes for display (first 50 chars)
            notes_display = row['notes'] if row['notes'] else ''
            if len(notes_display) > 50:
                notes_display = notes_display[:47] + '...'
            
            values = (
                row['site'], row['user_name'], row['start_date'], row['status'],
                f"${row['total_buyin']:.2f}", 
                f"${row['total_redeemed']:.2f}", 
                f"${actual_balance:.2f}",  # Use actual FIFO balance
                notes_display
            )
            tags = (str(row['id']),)
            
            self.os_tree.insert('', 'end', values=values, tags=tags)
            data.append((values, tags))
        
        conn.close()
        
        # Sync with search/sort if available
        if hasattr(self, 'os_searchable'):
            self.os_searchable.set_data(data)
    
    def open_session_details_popup(self, event=None):
        """Open popup to view/edit session details when double-clicked"""
        sel = self.os_tree.selection()
        if not sel:
            return
        
        session_id = self.os_tree.item(sel[0])['tags'][0]
        
        # Get session details
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute('''
            SELECT ss.*, s.name as site_name, u.name as user_name
            FROM site_sessions ss
            JOIN sites s ON ss.site_id = s.id
            JOIN users u ON ss.user_id = u.id
            WHERE ss.id = ?
        ''', (session_id,))
        session = c.fetchone()
        conn.close()
        
        if not session:
            return
        
        # Create popup
        popup = tk.Toplevel(self.root)
        popup.title(f"Session Details - {session['site_name']} / {session['user_name']}")
        popup.geometry("600x500")
        popup.transient(self.root)
        popup.grab_set()
        
        # Main frame
        frame = ttk.Frame(popup, padding=20)
        frame.pack(fill='both', expand=True)
        
        # Session info
        info_frame = ttk.LabelFrame(frame, text="Session Information", padding=10)
        info_frame.pack(fill='x', pady=(0, 10))
        
        info_text = (
            f"Site: {session['site_name']}\n"
            f"User: {session['user_name']}\n"
            f"Start Date: {session['start_date']}\n"
            f"Status: {session['status']}\n"
            f"Total Buy-in: ${float(session['total_buyin']):,.2f}\n"
            f"Total Redeemed: ${float(session['total_redeemed']):,.2f}\n"
            f"Balance: ${float(session['total_buyin']) - float(session['total_redeemed']):,.2f}"
        )
        
        ttk.Label(info_frame, text=info_text, font=('Arial', 10)).pack(anchor='w')
        
        # Notes section
        notes_frame = ttk.LabelFrame(frame, text="Session Notes", padding=10)
        notes_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        ttk.Label(notes_frame, text="Notes (e.g., 'Pending redemption', 'Below minimum', etc.):", 
                 font=('Arial', 9)).pack(anchor='w', pady=(0, 5))
        
        notes_text = tk.Text(notes_frame, height=8, width=60, font=('Arial', 10), wrap='word')
        notes_text.pack(fill='both', expand=True, pady=(0, 5))
        
        # Load existing notes
        if session['notes']:
            notes_text.insert('1.0', session['notes'])
        
        # Action buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x')
        
        def save_notes():
            notes = notes_text.get('1.0', 'end-1c').strip()
            conn = self.db.get_connection()
            c = conn.cursor()
            c.execute('UPDATE site_sessions SET notes = ? WHERE id = ?', (notes, session_id))
            conn.commit()
            conn.close()
            
            self.db.log_audit('UPDATE', 'site_sessions', session_id, "Updated session notes")
            self.refresh_open_sessions()
            messagebox.showinfo("Success", "Notes saved")
        
        def close_as_loss():
            # Close popup first
            popup.destroy()
            # Call existing close as loss method
            self.close_as_loss_prompt_with_session(session_id)
        
        ttk.Button(btn_frame, text="Save Notes", command=save_notes).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Close as Loss", command=close_as_loss).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=popup.destroy).pack(side='right', padx=5)
        
        popup.bind('<Escape>', lambda e: popup.destroy())
    
    def expand_all_closed_sessions(self):
        """Expand all items in closed sessions tree"""
        def expand_recursive(item):
            self.cs_tree.item(item, open=True)
            for child in self.cs_tree.get_children(item):
                expand_recursive(child)
        
        for item in self.cs_tree.get_children():
            expand_recursive(item)
    
    def collapse_all_closed_sessions(self):
        """Collapse all items in closed sessions tree"""
        def collapse_recursive(item):
            self.cs_tree.item(item, open=False)
            for child in self.cs_tree.get_children(item):
                collapse_recursive(child)
        
        for item in self.cs_tree.get_children():
            collapse_recursive(item)
    
    def edit_closed_session_notes(self):
        """Edit notes for selected closed session (tax session)"""
        sel = self.cs_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select a transaction to add notes")
            return
        
        # Get the selected item
        item = sel[0]
        tags = self.cs_tree.item(item, 'tags')
        
        # Check if it's a transaction (not a daily or site aggregate)
        if 'transaction' not in tags:
            messagebox.showwarning("Invalid Selection", 
                                 "Please select an individual transaction (not a date or site total)")
            return
        
        # Get tax_session ID from tags (should be the 3rd tag after trans_profit/loss and 'transaction')
        session_id = None
        for tag in tags:
            if tag.isdigit():
                session_id = int(tag)
                break
        
        if not session_id:
            messagebox.showerror("Error", "Could not find transaction ID")
            return
        
        # Get current notes
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT notes FROM tax_sessions WHERE id = ?", (session_id,))
        row = c.fetchone()
        current_notes = row['notes'] if row and row['notes'] else ''
        conn.close()
        
        # Show popup
        popup = tk.Toplevel(self.root)
        popup.title("Transaction Notes")
        popup.geometry("500x300")
        popup.transient(self.root)
        popup.grab_set()
        
        ttk.Label(popup, text="Transaction Notes:", font=('Arial', 11, 'bold')).pack(pady=10)
        
        text_frame = ttk.Frame(popup)
        text_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        text = tk.Text(text_frame, wrap='word', height=10, width=50)
        text.pack(side='left', fill='both', expand=True)
        
        scroll = ttk.Scrollbar(text_frame, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        
        text.insert('1.0', current_notes)
        
        def save_notes():
            new_notes = text.get('1.0', 'end-1c').strip()
            conn = self.db.get_connection()
            c = conn.cursor()
            c.execute("UPDATE tax_sessions SET notes = ? WHERE id = ?", (new_notes, session_id))
            conn.commit()
            conn.close()
            
            # Log audit
            self.log_audit('UPDATE', 'tax_sessions', session_id, 'Updated notes', None)
            
            # Refresh view
            self.refresh_closed_sessions()
            popup.destroy()
            messagebox.showinfo("Success", "Notes saved")
        
        btn_frame = ttk.Frame(popup)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="Save", command=save_notes).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=popup.destroy).pack(side='left', padx=5)
    
    def _sort_closed_sessions(self, col):
        """Sort closed sessions by the specified column (only sorts top-level date rows)"""
        # Get all top-level items (dates)
        items = []
        for item_id in self.cs_tree.get_children(''):
            val = self.cs_tree.set(item_id, col)
            items.append((val, item_id))
        
        # Toggle sort direction
        if self.cs_sort_column == col:
            self.cs_sort_reverse = not self.cs_sort_reverse
        else:
            self.cs_sort_column = col
            self.cs_sort_reverse = False
        
        # Sort items
        try:
            # Try numeric sort for dollar amounts
            if col in ('Cost Basis', 'Payout', 'Net P/L'):
                items.sort(
                    key=lambda x: float(x[0].replace('$', '').replace(',', '').replace('(', '-').replace(')', '')),
                    reverse=self.cs_sort_reverse
                )
            else:
                # String sort for dates
                items.sort(key=lambda x: x[0], reverse=self.cs_sort_reverse)
        except:
            # Fallback to string sort
            items.sort(key=lambda x: x[0], reverse=self.cs_sort_reverse)
        
        # Reorder items
        for idx, (val, item_id) in enumerate(items):
            self.cs_tree.move(item_id, '', idx)
        
        # Update heading to show sort direction
        for c in ('Date', 'Site', 'User', 'Game Type', 'Cost Basis', 'Payout', 'Net P/L', 'Notes'):
            heading_text = c
            if c == col:
                heading_text = f"{c} {'▼' if self.cs_sort_reverse else '▲'}"
            self.cs_tree.heading(c, text=heading_text)
    
    
    def clear_cs_filters(self):
        """Clear all filters for Closed Sessions"""
        self.cs_selected_sites = set()
        self.cs_selected_users = set()
        self.cs_site_filter_label.config(text="All", foreground='gray')
        self.cs_user_filter_label.config(text="All", foreground='gray')
        self.cs_filter_start.delete(0, tk.END)
        self.cs_filter_end.delete(0, tk.END)
        self.refresh_closed_sessions()
    
    def show_cs_site_filter(self):
        """Show site filter dialog for Closed Sessions"""
        # Get all sites
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT name FROM sites WHERE active = 1 ORDER BY name")
        all_sites = [row['name'] for row in c.fetchall()]
        conn.close()
        
        if not all_sites:
            messagebox.showinfo("No Sites", "No sites found")
            return
        
        # Show filter dialog
        from table_helpers import FilterDialog
        FilterDialog(self.root, "Sites", all_sites, self.cs_selected_sites, 
                    self.on_cs_site_filter_changed)
    
    def show_cs_user_filter(self):
        """Show user filter dialog for Closed Sessions"""
        # Get all users
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT name FROM users WHERE active = 1 ORDER BY name")
        all_users = [row['name'] for row in c.fetchall()]
        conn.close()
        
        if not all_users:
            messagebox.showinfo("No Users", "No users found")
            return
        
        # Show filter dialog
        from table_helpers import FilterDialog
        FilterDialog(self.root, "Users", all_users, self.cs_selected_users, 
                    self.on_cs_user_filter_changed)
    
    def on_cs_site_filter_changed(self, column_name, selected_values):
        """Callback when site filter changes"""
        self.cs_selected_sites = selected_values
        
        # Update label
        if not selected_values:
            self.cs_site_filter_label.config(text="All", foreground='gray')
        else:
            self.cs_site_filter_label.config(
                text=f"{len(selected_values)} selected", 
                foreground='blue'
            )
        
        # Refresh display
        self.refresh_closed_sessions()
    
    def on_cs_user_filter_changed(self, column_name, selected_values):
        """Callback when user filter changes"""
        self.cs_selected_users = selected_values
        
        # Update label
        if not selected_values:
            self.cs_user_filter_label.config(text="All", foreground='gray')
        else:
            self.cs_user_filter_label.config(
                text=f"{len(selected_values)} selected", 
                foreground='blue'
            )
        
        # Refresh display
        self.refresh_closed_sessions()
    
    def refresh_closed_sessions(self):
        """Refresh closed sessions list - 3-level hierarchy: Date → Site → Transactions"""
        # Get search term if available
        search_term = ''
        if hasattr(self, 'cs_search_var'):
            search_term = self.cs_search_var.get().lower().strip()
        
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Build query with optional date filter
        query = '''
            SELECT 
                ts.session_date,
                SUM(ts.cost_basis) as daily_cost_basis,
                SUM(ts.payout) as daily_payout,
                SUM(ts.net_pl) as daily_net_pl,
                COUNT(DISTINCT ts.site_id) as site_count,
                COUNT(*) as transaction_count
            FROM tax_sessions ts
        '''
        
        params = []
        where_clauses = []
        
        # Apply site filter if set
        if hasattr(self, 'cs_selected_sites') and self.cs_selected_sites:
            # Filter by selected sites
            site_placeholders = ','.join('?' * len(self.cs_selected_sites))
            where_clauses.append(f'ts.site_id IN (SELECT id FROM sites WHERE name IN ({site_placeholders}))')
            params.extend(list(self.cs_selected_sites))
        
        # Apply user filter if set
        if hasattr(self, 'cs_selected_users') and self.cs_selected_users:
            # Filter by selected users
            user_placeholders = ','.join('?' * len(self.cs_selected_users))
            where_clauses.append(f'ts.user_id IN (SELECT id FROM users WHERE name IN ({user_placeholders}))')
            params.extend(list(self.cs_selected_users))
        
        # Apply date filter if set, otherwise default to current year
        if hasattr(self, 'cs_filter_start') and hasattr(self, 'cs_filter_end'):
            start = self.cs_filter_start.get().strip()
            end = self.cs_filter_end.get().strip()
            
            if start and end:
                where_clauses.append('ts.session_date BETWEEN ? AND ?')
                params.extend([start, end])
            elif start:
                where_clauses.append('ts.session_date >= ?')
                params.append(start)
            elif end:
                where_clauses.append('ts.session_date <= ?')
                params.append(end)
            else:
                # Default to current year if no filter set
                current_year_start = f"{date.today().year}-01-01"
                current_year_end = str(date.today())
                where_clauses.append('ts.session_date BETWEEN ? AND ?')
                params.extend([current_year_start, current_year_end])
        else:
            # Default to current year if filter fields don't exist yet
            current_year_start = f"{date.today().year}-01-01"
            current_year_end = str(date.today())
            where_clauses.append('ts.session_date BETWEEN ? AND ?')
            params.extend([current_year_start, current_year_end])
        
        if where_clauses:
            query += ' WHERE ' + ' AND '.join(where_clauses)
        
        query += '''
            GROUP BY ts.session_date
            ORDER BY ts.session_date DESC
        '''
        
        c.execute(query, params)
        
        dates = c.fetchall()
        
        # Collect parent (date) rows for SearchableTreeview
        parent_data = []
        date_children_map = {}  # Map date -> (date_row, search_term, params)
        
        for date_row in dates:
            session_date = date_row['session_date']
            
            # If searching, check if this date has any matching sites/transactions
            skip_date = False
            if search_term:
                # First check aggregated site totals
                c.execute('''
                    SELECT COUNT(*) as match_count
                    FROM (
                        SELECT 
                            ts.site_id,
                            ts.user_id,
                            s.name as site_name,
                            u.name as user_name,
                            SUM(ts.cost_basis) as total_cost_basis,
                            SUM(ts.payout) as total_payout,
                            SUM(ts.net_pl) as total_net_pl
                        FROM tax_sessions ts
                        JOIN sites s ON ts.site_id = s.id
                        JOIN users u ON ts.user_id = u.id
                        WHERE ts.session_date = ?
                        GROUP BY ts.site_id, ts.user_id
                    ) aggregated
                    WHERE 
                        LOWER(aggregated.site_name) LIKE ? 
                        OR LOWER(aggregated.user_name) LIKE ?
                        OR printf('%.2f', aggregated.total_cost_basis) LIKE ?
                        OR printf('%.2f', aggregated.total_payout) LIKE ?
                        OR printf('%.2f', aggregated.total_net_pl) LIKE ?
                        OR CAST(CAST(aggregated.total_cost_basis AS INTEGER) AS TEXT) LIKE ?
                        OR CAST(CAST(aggregated.total_payout AS INTEGER) AS TEXT) LIKE ?
                        OR CAST(CAST(aggregated.total_net_pl AS INTEGER) AS TEXT) LIKE ?
                ''', (session_date, f'%{search_term}%', f'%{search_term}%',
                     f'%{search_term}%', f'%{search_term}%', f'%{search_term}%',
                     f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
                
                agg_count = c.fetchone()['match_count']
                
                # Also check individual transactions
                c.execute('''
                    SELECT COUNT(DISTINCT ts.site_id || '-' || ts.user_id) as match_count
                    FROM tax_sessions ts
                    WHERE ts.session_date = ?
                    AND (
                        printf('%.2f', ts.cost_basis) LIKE ?
                        OR printf('%.2f', ts.payout) LIKE ?
                        OR printf('%.2f', ts.net_pl) LIKE ?
                        OR CAST(CAST(ts.cost_basis AS INTEGER) AS TEXT) LIKE ?
                        OR CAST(CAST(ts.payout AS INTEGER) AS TEXT) LIKE ?
                        OR CAST(CAST(ts.net_pl AS INTEGER) AS TEXT) LIKE ?
                    )
                ''', (session_date, f'%{search_term}%', f'%{search_term}%', f'%{search_term}%',
                     f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
                
                ind_count = c.fetchone()['match_count']
                
                # If neither matched, skip this date
                if agg_count == 0 and ind_count == 0:
                    skip_date = True
            
            if not skip_date:
                daily_net_pl = date_row['daily_net_pl']
                
                # Format daily totals
                if daily_net_pl >= 0:
                    daily_pl_str = f"${daily_net_pl:.2f} ✓"
                    daily_tag = 'daily_profit'
                else:
                    daily_pl_str = f"${daily_net_pl:.2f} ✓—"
                    daily_tag = 'daily_loss'
                
                site_info = f"{date_row['site_count']} site(s), {date_row['transaction_count']} transaction(s)"
                
                # Collect parent row data with arrow text
                parent_values = (
                    session_date,
                    site_info,
                    '',  # User column blank for daily totals
                    f"${date_row['daily_cost_basis']:.2f}",
                    f"${date_row['daily_payout']:.2f}",
                    daily_pl_str,
                    ''  # Notes column blank for daily totals
                )
                parent_data.append((parent_values, (daily_tag, 'daily'), ''))  # No text needed, children provide structure
                
                # Store children data for later
                date_children_map[session_date] = (date_row, search_term, params)
        
        # Define callback to add children
        def add_realized_children(parent_id, parent_values):
            session_date = parent_values[0]
            if session_date not in date_children_map:
                return
            
            # Get site/user groups for this date
            site_user_query = '''
                SELECT ts.site_id, ts.user_id, s.name as site, u.name as user_name,
                       SUM(ts.cost_basis) as total_cost_basis, SUM(ts.payout) as total_payout,
                       SUM(ts.net_pl) as total_net_pl, COUNT(*) as redemption_count
                FROM tax_sessions ts
                JOIN sites s ON ts.site_id = s.id
                JOIN users u ON ts.user_id = u.id
                WHERE ts.session_date = ?
            '''
            site_user_params = [session_date]
            
            if hasattr(self, 'cs_selected_sites') and self.cs_selected_sites:
                site_placeholders = ','.join('?' * len(self.cs_selected_sites))
                site_user_query += f' AND s.name IN ({site_placeholders})'
                site_user_params.extend(list(self.cs_selected_sites))
            
            if hasattr(self, 'cs_selected_users') and self.cs_selected_users:
                user_placeholders = ','.join('?' * len(self.cs_selected_users))
                site_user_query += f' AND u.name IN ({user_placeholders})'
                site_user_params.extend(list(self.cs_selected_users))
            
            site_user_query += ' GROUP BY ts.site_id, ts.user_id ORDER BY s.name ASC'
            c.execute(site_user_query, site_user_params)
            
            for site_row in c.fetchall():
                site_net_pl = site_row['total_net_pl']
                site_pl_str = f"${site_net_pl:.2f} ✓" if site_net_pl >= 0 else f"${site_net_pl:.2f} ✓—"
                site_tag = 'site_profit' if site_net_pl >= 0 else 'site_loss'
                transaction_info = f" ({site_row['redemption_count']} transactions)" if site_row['redemption_count'] > 1 else ""
                
                site_parent = self.cs_tree.insert(parent_id, 'end', values=(
                    '', f"  {site_row['site']}{transaction_info}", site_row['user_name'],
                    f"${site_row['total_cost_basis']:.2f}", f"${site_row['total_payout']:.2f}",
                    site_pl_str, ''
                ), tags=(site_tag, 'site'))
                
                c.execute('''SELECT ts.id, r.amount as redemption_amount, ts.cost_basis, ts.payout,
                             ts.net_pl, r.is_free_sc, ts.notes FROM tax_sessions ts
                             JOIN redemptions r ON ts.redemption_id = r.id
                             WHERE ts.session_date = ? AND ts.site_id = ? AND ts.user_id = ?
                             ORDER BY ts.id ASC''',
                          (session_date, site_row['site_id'], site_row['user_id']))
                
                for t in c.fetchall():
                    trans_type = ("    └─ Free SC Redemption" if t['is_free_sc'] else
                                  "    └─ Total Loss" if t['redemption_amount'] == 0 else
                                  f"    └─ Redemption (${t['redemption_amount']:.2f})")
                    t_net_pl_str = f"${t['net_pl']:.2f} ✓" if t['net_pl'] >= 0 else f"${t['net_pl']:.2f} ✓—"
                    t_tag = 'trans_profit' if t['net_pl'] >= 0 else 'trans_loss'
                    notes_display = '📝' if t['notes'] else ''
                    
                    self.cs_tree.insert(site_parent, 'end', values=(
                        '', trans_type, '', f"${t['cost_basis']:.2f}",
                        f"${t['payout']:.2f}", t_net_pl_str, notes_display
                    ), tags=(t_tag, 'transaction', str(t['id'])))
        
        # Use SearchableTreeview with children callback
        if hasattr(self, 'cs_searchable'):
            self.cs_searchable.set_data(parent_data, children_callback=add_realized_children)
        
        # Configure colors for all levels
        self.cs_tree.tag_configure('daily_profit', foreground='green', font=('TkDefaultFont', 10, 'bold'))
        self.cs_tree.tag_configure('daily_loss', foreground='red', font=('TkDefaultFont', 10, 'bold'))
        self.cs_tree.tag_configure('site_profit', foreground='green', font=('TkDefaultFont', 10))
        self.cs_tree.tag_configure('site_loss', foreground='red', font=('TkDefaultFont', 10))
        self.cs_tree.tag_configure('trans_profit', foreground='green', font=('TkDefaultFont', 10))
        self.cs_tree.tag_configure('trans_loss', foreground='red', font=('TkDefaultFont', 10))
        
        conn.close()
        # Configure colors for all levels - consistent font sizes
        # Daily totals are bold to stand out
        self.cs_tree.tag_configure('daily_profit', foreground='green', font=('TkDefaultFont', 10, 'bold'))
        self.cs_tree.tag_configure('daily_loss', foreground='red', font=('TkDefaultFont', 10, 'bold'))
        # Site and transaction levels use normal font with just color
        self.cs_tree.tag_configure('site_profit', foreground='green', font=('TkDefaultFont', 10))
        self.cs_tree.tag_configure('site_loss', foreground='red', font=('TkDefaultFont', 10))
        self.cs_tree.tag_configure('trans_profit', foreground='green', font=('TkDefaultFont', 10))
        self.cs_tree.tag_configure('trans_loss', foreground='red', font=('TkDefaultFont', 10))
        
        conn.close()
    
    def refresh_expenses(self):
        """Refresh expenses list with date filter"""
        for item in self.e_tree.get_children():
            self.e_tree.delete(item)
        
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Build query with optional date filter and include user
        query = '''
            SELECT e.id, e.expense_date, e.category, e.vendor, e.amount, e.description, u.name as user_name
            FROM expenses e
            LEFT JOIN users u ON e.user_id = u.id
        '''
        
        params = []
        
        # Apply date filter if set, otherwise default to current year
        if hasattr(self, 'e_filter_start') and hasattr(self, 'e_filter_end'):
            start = self.e_filter_start.get().strip()
            end = self.e_filter_end.get().strip()
            
            if start and end:
                query += ' WHERE e.expense_date BETWEEN ? AND ?'
                params.extend([start, end])
            elif start:
                query += ' WHERE e.expense_date >= ?'
                params.append(start)
            elif end:
                query += ' WHERE e.expense_date <= ?'
                params.append(end)
            else:
                # Default to current year if no filter set
                current_year_start = f"{date.today().year}-01-01"
                current_year_end = str(date.today())
                query += ' WHERE e.expense_date BETWEEN ? AND ?'
                params.extend([current_year_start, current_year_end])
        else:
            # Default to current year if filter fields don't exist yet
            current_year_start = f"{date.today().year}-01-01"
            current_year_end = str(date.today())
            query += ' WHERE e.expense_date BETWEEN ? AND ?'
            params.extend([current_year_start, current_year_end])
        
        query += ' ORDER BY e.expense_date DESC'
        
        c.execute(query, params)
        
        data = []
        for row in c.fetchall():
            values = (
                row['expense_date'],
                row['category'] or 'Other Expenses',
                row['vendor'],
                row['user_name'] or '',  # User column
                f"${row['amount']:.2f}", 
                row['description'] or ''
            )
            tags = (str(row['id']),)
            data.append((values, tags))
        
        conn.close()
        
        # Sync with search/sort if available
        if hasattr(self, 'e_searchable'):
            self.e_searchable.set_data(data)
    
    
    def refresh_monthly_subtab(self):
        """Refresh Monthly & Financial Summary - SESSION-BASED MODEL"""
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Get filters
        start_date = self.monthly_filter_start.get().strip() if hasattr(self, 'monthly_filter_start') else ''
        end_date = self.monthly_filter_end.get().strip() if hasattr(self, 'monthly_filter_end') else ''
        
        # Build WHERE clause with all filters
        where_clauses = ["gs.status = 'Closed'"]
        filter_params = []
        
        # Date filter
        if start_date and end_date:
            where_clauses.append("gs.session_date BETWEEN ? AND ?")
            filter_params.extend([start_date, end_date])
        elif start_date:
            where_clauses.append("gs.session_date >= ?")
            filter_params.append(start_date)
        elif end_date:
            where_clauses.append("gs.session_date <= ?")
            filter_params.append(end_date)
        
        # Site filter (checkbox style)
        if hasattr(self, 'monthly_selected_sites') and self.monthly_selected_sites:
            placeholders = ','.join('?' * len(self.monthly_selected_sites))
            where_clauses.append(f"gs.site_id IN (SELECT id FROM sites WHERE name IN ({placeholders}))")
            filter_params.extend(list(self.monthly_selected_sites))
        
        # User filter (checkbox style)
        if hasattr(self, 'monthly_selected_users') and self.monthly_selected_users:
            placeholders = ','.join('?' * len(self.monthly_selected_users))
            where_clauses.append(f"gs.user_id IN (SELECT id FROM users WHERE name IN ({placeholders}))")
            filter_params.extend(list(self.monthly_selected_users))
        
        full_where = " AND ".join(where_clauses)
        
        # === MONTHLY TRENDS ===
        query = f'''
            SELECT 
                strftime('%Y-%m', gs.session_date) as month,
                COUNT(DISTINCT gs.session_date) as days_played,
                COUNT(*) as sessions,
                SUM(COALESCE(gs.basis_consumed, gs.session_basis, 0)) as total_basis_consumed,
                SUM(COALESCE(gs.net_taxable_pl, gs.total_taxable, 0)) as total_net_taxable,
                SUM(CASE WHEN COALESCE(gs.net_taxable_pl, gs.total_taxable, 0) >= 0 THEN 1 ELSE 0 END) as winning_sessions,
                COUNT(*) as total_sessions
            FROM game_sessions gs
            WHERE {full_where}
            GROUP BY strftime('%Y-%m', gs.session_date)
            ORDER BY month DESC
            LIMIT 24
        '''
        c.execute(query, filter_params)
        
        monthly_data = []
        for row in c.fetchall():
            win_rate = (row['winning_sessions'] / row['total_sessions'] * 100) if row['total_sessions'] > 0 else 0
            avg_per_day = (row['total_net_taxable'] / row['days_played']) if row['days_played'] > 0 else 0
            tag = 'profit' if row['total_net_taxable'] >= 0 else 'loss'
            
            # Format month nicely
            from datetime import datetime
            month_display = datetime.strptime(row['month'], '%Y-%m').strftime('%B %Y')
            
            values = (
                month_display,
                str(row['sessions']),
                str(row['days_played']),
                f"{win_rate:.1f}%",
                f"${row['total_basis_consumed']:,.2f}",
                f"${row['total_net_taxable']:+,.2f}",
                f"${avg_per_day:+,.2f}"
            )
            monthly_data.append((values, (tag,)))
        
        if hasattr(self, 'rep_monthly_searchable'):
            self.rep_monthly_searchable.set_data(monthly_data)
        
        self.rep_monthly_tree.tag_configure('profit', foreground='green')
        self.rep_monthly_tree.tag_configure('loss', foreground='red')
        
        # === FINANCIAL SUMMARY ===
        # Build purchase/redemption filters
        purchase_where_clauses = []
        purchase_params = []
        
        if start_date and end_date:
            purchase_where_clauses.append("purchase_date BETWEEN ? AND ?")
            purchase_params.extend([start_date, end_date])
        elif start_date:
            purchase_where_clauses.append("purchase_date >= ?")
            purchase_params.append(start_date)
        elif end_date:
            purchase_where_clauses.append("purchase_date <= ?")
            purchase_params.append(end_date)
        
        # Site filter (checkbox style)
        if hasattr(self, 'rep_selected_sites') and self.rep_selected_sites:
            placeholders = ','.join('?' * len(self.rep_selected_sites))
            purchase_where_clauses.append(f"site_id IN (SELECT id FROM sites WHERE name IN ({placeholders}))")
            purchase_params.extend(list(self.rep_selected_sites))
        
        # User filter (checkbox style)
        if hasattr(self, 'rep_selected_users') and self.rep_selected_users:
            placeholders = ','.join('?' * len(self.rep_selected_users))
            purchase_where_clauses.append(f"user_id IN (SELECT id FROM users WHERE name IN ({placeholders}))")
            purchase_params.extend(list(self.rep_selected_users))
        
        purchase_where = " AND ".join(purchase_where_clauses) if purchase_where_clauses else "1=1"
        
        # Total invested
        c.execute(f'SELECT COALESCE(SUM(amount), 0) as total FROM purchases WHERE {purchase_where}', purchase_params)
        total_invested = float(c.fetchone()['total'])
        
        # Total redeemed (use same filters but for redemptions table)
        redemption_where = purchase_where.replace('purchase_date', 'redemption_date')
        c.execute(f'SELECT COALESCE(SUM(amount), 0) as total FROM redemptions WHERE {redemption_where}', purchase_params)
        total_redeemed = float(c.fetchone()['total'])
        
        # Unrealized value (money still in play)
        c.execute(f'SELECT COALESCE(SUM(remaining_amount), 0) as total FROM purchases WHERE {purchase_where}', purchase_params)
        unrealized_value = float(c.fetchone()['total'])
        
        # Net cash flow
        net_cash_flow = total_redeemed - total_invested
        
        # Overall P/L from sessions (query directly instead of summing formatted values)
        c.execute(f'''
            SELECT COALESCE(SUM(gs.total_taxable), 0) as overall_pl
            FROM game_sessions gs
            WHERE {full_where}
        ''', filter_params)
        overall_pl = float(c.fetchone()['overall_pl'])
        
        # Update financial summary labels with session-based data
        overall_roi = (overall_pl / total_invested * 100) if total_invested > 0 else 0
        
        if hasattr(self, 'rep_summary_labels'):
            self.rep_summary_labels['Total Invested'].config(text=f"${total_invested:,.2f}")
            self.rep_summary_labels['Total Redeemed'].config(text=f"${total_redeemed:,.2f}")
            self.rep_summary_labels['Net Cash Flow'].config(
                text=f"${net_cash_flow:,.2f}",
                foreground='green' if net_cash_flow >= 0 else 'red'
            )
            self.rep_summary_labels['Unrealized Value'].config(
                text=f"${unrealized_value:,.2f}",
                foreground='orange'
            )
            self.rep_summary_labels['Overall P/L'].config(
                text=f"${overall_pl:,.2f}",
                foreground='green' if overall_pl >= 0 else 'red'
            )
        
        conn.close()
    
    def refresh_reports(self):
        """Refresh comprehensive reports dashboard - SESSION-BASED MODEL"""
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Get filters
        start_date = self.rep_filter_start.get().strip() if hasattr(self, 'rep_filter_start') else ''
        end_date = self.rep_filter_end.get().strip() if hasattr(self, 'rep_filter_end') else ''
        
        # Build WHERE clause with all filters
        where_clauses = ["status = 'Closed'"]
        filter_params = []
        
        # Date filter
        if start_date and end_date:
            where_clauses.append("session_date BETWEEN ? AND ?")
            filter_params.extend([start_date, end_date])
        elif start_date:
            where_clauses.append("session_date >= ?")
            filter_params.append(start_date)
        elif end_date:
            where_clauses.append("session_date <= ?")
            filter_params.append(end_date)
        
        # Site filter (checkbox style)
        if hasattr(self, 'rep_selected_sites') and self.rep_selected_sites:
            placeholders = ','.join('?' * len(self.rep_selected_sites))
            where_clauses.append(f"site_id IN (SELECT id FROM sites WHERE name IN ({placeholders}))")
            filter_params.extend(list(self.rep_selected_sites))
        
        # User filter (checkbox style)
        if hasattr(self, 'rep_selected_users') and self.rep_selected_users:
            placeholders = ','.join('?' * len(self.rep_selected_users))
            where_clauses.append(f"user_id IN (SELECT id FROM users WHERE name IN ({placeholders}))")
            filter_params.extend(list(self.rep_selected_users))
        
        full_where = " AND ".join(where_clauses)
        
        # For backward compatibility with queries that used date_where
        date_where = full_where
        date_params = filter_params
        
        # === SECTION 1: SESSION METRICS ===
        
        # Total sessions (closed only)
        c.execute(f'''
            SELECT COUNT(*) as total
            FROM game_sessions
            WHERE status = 'Closed' AND {date_where}
        ''', date_params)
        total_sessions = c.fetchone()['total'] or 0
        
        # Win rate
        c.execute(f'''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN total_taxable >= 0 THEN 1 ELSE 0 END) as wins
            FROM game_sessions
            WHERE status = 'Closed' AND {date_where}
        ''', date_params)
        row = c.fetchone()
        wins = row['wins'] or 0
        win_rate = (wins / total_sessions * 100) if total_sessions > 0 else 0
        
        # Average session P/L
        c.execute(f'''
            SELECT AVG(total_taxable) as avg_pl
            FROM game_sessions
            WHERE status = 'Closed' AND {date_where}
        ''', date_params)
        avg_session_pl = c.fetchone()['avg_pl'] or 0
        
        # Best and worst sessions
        c.execute(f'''
            SELECT 
                MAX(total_taxable) as best,
                MIN(total_taxable) as worst
            FROM game_sessions
            WHERE status = 'Closed' AND {date_where}
        ''', date_params)
        row = c.fetchone()
        best_session = row['best'] or 0
        worst_session = row['worst'] or 0
        
        # Current streak
        c.execute('''
            SELECT total_taxable, session_date, end_time
            FROM game_sessions
            WHERE status = 'Closed'
            ORDER BY session_date DESC, end_time DESC
            LIMIT 20
        ''')
        recent = c.fetchall()
        
        streak_count = 0
        streak_type = None
        if recent:
            # Determine if first session was win or loss
            streak_type = 'Win' if recent[0]['total_taxable'] >= 0 else 'Loss'
            for sess in recent:
                sess_type = 'Win' if sess['total_taxable'] >= 0 else 'Loss'
                if sess_type == streak_type:
                    streak_count += 1
                else:
                    break
        
        # Update labels
        self.rep_session_labels['Total Sessions'].config(text=str(total_sessions))
        self.rep_session_labels['Win Rate'].config(
            text=f"{win_rate:.1f}% ({wins}/{total_sessions})",
            foreground='green' if win_rate >= 50 else 'red'
        )
        self.rep_session_labels['Average Session P/L'].config(
            text=f"${avg_session_pl:,.2f}",
            foreground='green' if avg_session_pl >= 0 else 'red'
        )
        self.rep_session_labels['Best Session'].config(
            text=f"${best_session:,.2f}",
            foreground='green'
        )
        self.rep_session_labels['Worst Session'].config(
            text=f"${worst_session:,.2f}",
            foreground='red' if worst_session < 0 else 'black'
        )
        if streak_count > 0:
            self.rep_session_labels['Current Streak'].config(
                text=f"{streak_count} {streak_type}{'s' if streak_count > 1 else ''}",
                foreground='green' if streak_type == 'Win' else 'red'
            )
        else:
            self.rep_session_labels['Current Streak'].config(text="--", foreground='black')
        
        # === SECTION 2: TAX METRICS ===
        
        # Total net taxable
        c.execute(f'''
            SELECT COALESCE(SUM(total_taxable), 0) as total
            FROM game_sessions
            WHERE status = 'Closed' AND {date_where}
        ''', date_params)
        total_taxable = c.fetchone()['total']

        # Total delta totals (SC) and redeemable delta (SC)
        c.execute(f'''
            SELECT
                COALESCE(SUM(delta_total), 0) as total_delta,
                COALESCE(SUM(delta_redeem), 0) as total_delta_redeem
            FROM game_sessions
            WHERE status = 'Closed' AND {date_where}
        ''', date_params)
        delta_row = c.fetchone()
        total_delta_total = delta_row['total_delta']
        total_delta_redeem = delta_row['total_delta_redeem']
        
        # Unrealized value (current positions)
        c.execute('SELECT COALESCE(SUM(remaining_amount), 0) as total FROM purchases')
        unrealized_value = c.fetchone()['total']
        
        # Average profit per day played
        c.execute(f'''
            SELECT COUNT(DISTINCT session_date) as days_played
            FROM game_sessions
            WHERE status = 'Closed' AND {date_where}
        ''', date_params)
        days_played = c.fetchone()['days_played'] or 0
        avg_per_day = (total_taxable / days_played) if days_played > 0 else 0
        
        # Update labels
        self.rep_tax_labels['Total Net Taxable'].config(
            text=f"${total_taxable:+,.2f}",
            foreground='green' if total_taxable >= 0 else 'red'
        )
        self.rep_tax_labels['Total Delta Total (SC)'].config(
            text=f"{total_delta_total:+,.2f}",
            foreground='green' if total_delta_total >= 0 else 'red'
        )
        self.rep_tax_labels['Total Delta Redeemable (SC)'].config(
            text=f"{total_delta_redeem:+,.2f}",
            foreground='green' if total_delta_redeem >= 0 else 'red'
        )
        self.rep_tax_labels['Unrealized Value'].config(
            text=f"${unrealized_value:,.2f}",
            foreground='orange'
        )
        self.rep_tax_labels['Avg Profit Per Day'].config(
            text=f"${avg_per_day:,.2f}",
            foreground='green' if avg_per_day >= 0 else 'red'
        )
        
        # === SECTION 3: ROI & EFFICIENCY ===
        
        # Overall ROI % (total taxable / total invested * 100)
        c.execute('SELECT COALESCE(SUM(amount), 0) as total FROM purchases')
        total_invested = c.fetchone()['total']
        overall_roi = (total_taxable / total_invested * 100) if total_invested > 0 else 0
        
        # Average session duration
        c.execute(f'''
            SELECT AVG(
                CASE 
                    WHEN end_time IS NOT NULL AND start_time IS NOT NULL THEN
                        (julianday(session_date || ' ' || end_time) - julianday(session_date || ' ' || start_time)) * 24
                    ELSE NULL
                END
            ) as avg_hours
            FROM game_sessions
            WHERE status = 'Closed' AND {date_where}
        ''', date_params)
        avg_hours = c.fetchone()['avg_hours'] or 0
        avg_duration_str = f"{int(avg_hours)}h {int((avg_hours % 1) * 60)}m" if avg_hours > 0 else "--"
        
        # Hourly win rate
        c.execute(f'''
            SELECT SUM(
                CASE 
                    WHEN end_time IS NOT NULL AND start_time IS NOT NULL THEN
                        (julianday(session_date || ' ' || end_time) - julianday(session_date || ' ' || start_time)) * 24
                    ELSE 0
                END
            ) as total_hours
            FROM game_sessions
            WHERE status = 'Closed' AND {date_where}
        ''', date_params)
        total_hours = c.fetchone()['total_hours'] or 0
        hourly_rate = (total_taxable / total_hours) if total_hours > 0 else 0
        
        # Win rate by game type
        c.execute(f'''
            SELECT 
                game_type,
                COUNT(*) as total,
                SUM(CASE WHEN total_taxable >= 0 THEN 1 ELSE 0 END) as wins
            FROM game_sessions
            WHERE status = 'Closed' AND {date_where}
            GROUP BY game_type
            ORDER BY total DESC
        ''', date_params)
        game_type_stats = c.fetchall()
        
        game_type_str = " | ".join([
            f"{row['game_type']}: {(row['wins']/row['total']*100):.0f}%"
            for row in game_type_stats[:3]  # Top 3 game types
        ]) if game_type_stats else "--"
        
        # Update labels
        self.rep_roi_labels['Overall ROI %'].config(
            text=f"{overall_roi:+.1f}%",
            foreground='green' if overall_roi >= 0 else 'red'
        )
        self.rep_roi_labels['Average Session Duration'].config(
            text=avg_duration_str
        )
        self.rep_roi_labels['Hourly Win Rate'].config(
            text=f"${hourly_rate:,.2f}/hr",
            foreground='green' if hourly_rate >= 0 else 'red'
        )
        self.rep_roi_labels['Win Rate by Game Type'].config(
            text=game_type_str,
            foreground='blue'
        )
        
        # === SECTION 4: CHARTS ===
        self.draw_report_charts(c, date_where, date_params)
        
        # === SECTION 5: PERFORMANCE BY SITE TABLE ===
        # This table respects global Site/User filters and groups by site only
        
        c.execute(f'''
            SELECT 
                s.name as site,
                COUNT(*) as sessions,
                SUM(CASE WHEN gs.total_taxable >= 0 THEN 1 ELSE 0 END) as wins,
                SUM(gs.total_taxable) as total_pl,
                AVG(gs.total_taxable) as avg_pl
            FROM game_sessions gs
            JOIN sites s ON gs.site_id = s.id
            WHERE {date_where}
            GROUP BY s.name
            ORDER BY total_pl DESC
        ''', date_params)
        
        site_data = []
        for row in c.fetchall():
            win_rate = (row['wins'] / row['sessions'] * 100) if row['sessions'] > 0 else 0
            
            # Calculate ROI for this site (respecting user filter if set)
            c2 = conn.cursor()
            
            # Build WHERE for purchases to match the filters
            purchase_where_clauses = ["s.name = ?"]
            purchase_params = [row['site']]
            
            # User filter (checkbox style)
            if hasattr(self, 'rep_selected_users') and self.rep_selected_users:
                placeholders = ','.join('?' * len(self.rep_selected_users))
                purchase_where_clauses.append(f"p.user_id IN (SELECT id FROM users WHERE name IN ({placeholders}))")
                purchase_params.extend(list(self.rep_selected_users))
            
            purchase_where = " AND ".join(purchase_where_clauses)
            
            c2.execute(f'''
                SELECT COALESCE(SUM(p.amount), 0) as invested
                FROM purchases p
                JOIN sites s ON p.site_id = s.id
                WHERE {purchase_where}
            ''', purchase_params)
            invested = c2.fetchone()['invested']
            roi = (row['total_pl'] / invested * 100) if invested > 0 else 0
            
            tag = 'profit' if row['total_pl'] >= 0 else 'loss'
            
            values = (
                row['site'],
                str(row['sessions']),
                f"{win_rate:.1f}%",
                f"${row['total_pl']:+,.2f}",
                f"${row['avg_pl']:+,.2f}",
                f"{roi:+.1f}%"
            )
            site_data.append((values, (tag,)))
        
        if hasattr(self, 'rep_site_searchable'):
            self.rep_site_searchable.set_data(site_data)
        
        conn.close()
    
    def show_rep_site_filter(self):
        """Show site filter dialog for Overview"""
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT name FROM sites WHERE active = 1 ORDER BY name")
        all_sites = [row['name'] for row in c.fetchall()]
        conn.close()
        
        if not all_sites:
            messagebox.showinfo("No Sites", "No sites found")
            return
        
        from table_helpers import FilterDialog
        FilterDialog(self.root, "Sites", all_sites, self.rep_selected_sites, 
                    self.on_rep_site_filter_changed)
    
    def show_rep_user_filter(self):
        """Show user filter dialog for Overview"""
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT name FROM users WHERE active = 1 ORDER BY name")
        all_users = [row['name'] for row in c.fetchall()]
        conn.close()
        
        if not all_users:
            messagebox.showinfo("No Users", "No users found")
            return
        
        from table_helpers import FilterDialog
        FilterDialog(self.root, "Users", all_users, self.rep_selected_users, 
                    self.on_rep_user_filter_changed)
    
    def on_rep_site_filter_changed(self, column_name, selected_values):
        """Callback when site filter changes"""
        self.rep_selected_sites = selected_values
        
        if not selected_values:
            self.rep_site_filter_label.config(text="All", foreground='gray')
        else:
            count = len(selected_values)
            self.rep_site_filter_label.config(text=f"{count} selected", foreground='blue')
    
    def on_rep_user_filter_changed(self, column_name, selected_values):
        """Callback when user filter changes"""
        self.rep_selected_users = selected_values
        
        if not selected_values:
            self.rep_user_filter_label.config(text="All", foreground='gray')
        else:
            count = len(selected_values)
            self.rep_user_filter_label.config(text=f"{count} selected", foreground='blue')
    
    def show_monthly_site_filter(self):
        """Show site filter dialog for Monthly"""
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT name FROM sites WHERE active = 1 ORDER BY name")
        all_sites = [row['name'] for row in c.fetchall()]
        conn.close()
        
        if not all_sites:
            messagebox.showinfo("No Sites", "No sites found")
            return
        
        from table_helpers import FilterDialog
        FilterDialog(self.root, "Sites", all_sites, self.monthly_selected_sites, 
                    self.on_monthly_site_filter_changed)
    
    def show_monthly_user_filter(self):
        """Show user filter dialog for Monthly"""
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT name FROM users WHERE active = 1 ORDER BY name")
        all_users = [row['name'] for row in c.fetchall()]
        conn.close()
        
        if not all_users:
            messagebox.showinfo("No Users", "No users found")
            return
        
        from table_helpers import FilterDialog
        FilterDialog(self.root, "Users", all_users, self.monthly_selected_users, 
                    self.on_monthly_user_filter_changed)
    
    def on_monthly_site_filter_changed(self, column_name, selected_values):
        """Callback when site filter changes"""
        self.monthly_selected_sites = selected_values
        
        if not selected_values:
            self.monthly_site_filter_label.config(text="All", foreground='gray')
        else:
            count = len(selected_values)
            self.monthly_site_filter_label.config(text=f"{count} selected", foreground='blue')
    
    def on_monthly_user_filter_changed(self, column_name, selected_values):
        """Callback when user filter changes"""
        self.monthly_selected_users = selected_values
        
        if not selected_values:
            self.monthly_user_filter_label.config(text="All", foreground='gray')
        else:
            count = len(selected_values)
            self.monthly_user_filter_label.config(text=f"{count} selected", foreground='blue')
    
    def draw_report_charts(self, cursor, date_where, date_params):
        """Draw performance charts using matplotlib"""
        try:
            import matplotlib
            matplotlib.use('TkAgg')
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        except ImportError:
            # Try to install matplotlib automatically
            try:
                import subprocess
                import sys
                
                ttk.Label(self.rep_chart_frame, 
                         text="Installing matplotlib... please wait",
                         foreground='blue').pack(pady=20)
                self.rep_chart_frame.update()
                
                subprocess.check_call([sys.executable, "-m", "pip", "install", "matplotlib"])
                
                # Try importing again after install
                import matplotlib
                matplotlib.use('TkAgg')
                from matplotlib.figure import Figure
                from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
                
                # Clear the "installing" message
                for widget in self.rep_chart_frame.winfo_children():
                    widget.destroy()
            except Exception as install_error:
                ttk.Label(self.rep_chart_frame, 
                         text=f"Charts require matplotlib. Install with: pip install matplotlib\n\nError: {str(install_error)}",
                         foreground='red', wraplength=600).pack(pady=20)
                return
        
        try:
            
            # Clear existing charts
            for widget in self.rep_chart_frame.winfo_children():
                widget.destroy()
            
            # Create figure with 2 subplots side by side
            fig = Figure(figsize=(12, 4), dpi=80)
            
            # === CHART 1: Monthly P/L Trend ===
            ax1 = fig.add_subplot(121)
            
            cursor.execute(f'''
                SELECT 
                    strftime('%Y-%m', session_date) as month,
                    SUM(total_taxable) as monthly_pl
                FROM game_sessions
                WHERE status = 'Closed' AND {date_where}
                GROUP BY strftime('%Y-%m', session_date)
                ORDER BY month
            ''', date_params)
            
            monthly_data = cursor.fetchall()
            
            if monthly_data:
                months = [row['month'] for row in monthly_data]
                pls = [row['monthly_pl'] for row in monthly_data]
                
                colors = ['green' if pl >= 0 else 'red' for pl in pls]
                
                ax1.bar(range(len(months)), pls, color=colors, alpha=0.7)
                ax1.set_xlabel('Month')
                ax1.set_ylabel('P/L ($)')
                ax1.set_title('Monthly P/L Trend')
                ax1.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
                ax1.set_xticks(range(len(months)))
                ax1.set_xticklabels(months, rotation=45, ha='right')
                ax1.grid(True, alpha=0.3)
            else:
                ax1.text(0.5, 0.5, 'No data', ha='center', va='center', transform=ax1.transAxes)
            
            # === CHART 2: Win Rate by Site ===
            ax2 = fig.add_subplot(122)
            
            cursor.execute(f'''
                SELECT 
                    s.name as site,
                    COUNT(*) as sessions,
                    SUM(CASE WHEN gs.total_taxable >= 0 THEN 1 ELSE 0 END) as wins
                FROM game_sessions gs
                JOIN sites s ON gs.site_id = s.id
                WHERE gs.status = 'Closed' AND {date_where}
                GROUP BY s.name
                HAVING COUNT(*) >= 3
                ORDER BY (wins * 1.0 / sessions) DESC
                LIMIT 10
            ''', date_params)
            
            site_data = cursor.fetchall()
            
            if site_data:
                sites = [row['site'][:15] for row in site_data]  # Truncate long names
                win_rates = [(row['wins'] / row['sessions'] * 100) for row in site_data]
                
                colors = ['green' if wr >= 50 else 'red' for wr in win_rates]
                
                ax2.barh(range(len(sites)), win_rates, color=colors, alpha=0.7)
                ax2.set_xlabel('Win Rate (%)')
                ax2.set_ylabel('Site')
                ax2.set_title('Win Rate by Site (3+ sessions)')
                ax2.axvline(x=50, color='black', linestyle='--', linewidth=0.5)
                ax2.set_yticks(range(len(sites)))
                ax2.set_yticklabels(sites)
                ax2.grid(True, alpha=0.3, axis='x')
            else:
                ax2.text(0.5, 0.5, 'No data', ha='center', va='center', transform=ax2.transAxes)
            
            fig.tight_layout()
            
            # Embed in tkinter
            canvas = FigureCanvasTkAgg(fig, master=self.rep_chart_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill='both', expand=True)
            
        except ImportError:
            # Matplotlib not available
            ttk.Label(self.rep_chart_frame, 
                     text="Charts require matplotlib (pip install matplotlib)",
                     foreground='red').pack(pady=20)
        except Exception as e:
            ttk.Label(self.rep_chart_frame, 
                     text=f"Error drawing charts: {str(e)}",
                     foreground='red').pack(pady=20)
    
    def sort_rep_site_column(self, col):
        """Sort site performance table by column"""
        if hasattr(self, 'rep_site_sort_column') and self.rep_site_sort_column == col:
            self.rep_site_sort_reverse = not self.rep_site_sort_reverse
        else:
            self.rep_site_sort_column = col
            self.rep_site_sort_reverse = False
        
        items = [(self.rep_site_tree.set(item, col), item) for item in self.rep_site_tree.get_children('')]
        
        cols = ('Site', 'Sessions', 'Win Rate', 'Total P/L', 'Avg P/L', 'ROI %')
        
        def sort_key(item):
            val = item[0]
            if col in ('Total P/L', 'Avg P/L'):
                val = val.replace('$', '').replace('+', '').replace(',', '')
                try:
                    return float(val)
                except:
                    return 0
            elif col in ('Win Rate', 'ROI %'):
                val = val.replace('%', '')
                try:
                    return float(val)
                except:
                    return 0
            elif col == 'Sessions':
                try:
                    return int(val)
                except:
                    return 0
            return val.lower() if isinstance(val, str) else val
        
        items.sort(key=sort_key, reverse=self.rep_site_sort_reverse)
        
        for index, (val, item) in enumerate(items):
            self.rep_site_tree.move(item, '', index)
        
        # Update column heading
        for c in cols:
            if c == col:
                direction = ' ▼' if self.rep_site_sort_reverse else ' ▲'
                self.rep_site_tree.heading(c, text=c + direction)
            else:
                self.rep_site_tree.heading(c, text=c)
    def refresh_schedc(self):
        """Refresh Schedule C business tax calculations (SESSION-BASED REPORTING - Rev. Proc. 77-29)"""
        try:
            tax_year = int(self.tax_year_var.get())
        except:
            tax_year = date.today().year
        
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # === PART I: INCOME ===
        
        # Line 1: Gross receipts = WINNING DAILY SESSIONS (positive net_daily_pnl)
        # daily_tax_sessions aggregates ALL sites per day per user
        c.execute('''
            SELECT COALESCE(SUM(net_daily_pnl), 0) as total
            FROM daily_tax_sessions
            WHERE strftime('%Y', session_date) = ?
            AND net_daily_pnl > 0
        ''', (str(tax_year),))
        winning_sessions = float(c.fetchone()['total'])
        
        # Line 2: Returns & allowances (assumed 0)
        returns = 0.0
        
        # Line 3: Net receipts
        net_receipts = winning_sessions - returns
        
        # Get cashback amount
        c.execute('''
            SELECT COALESCE(SUM(p.amount * c.cashback_rate / 100), 0) as total
            FROM purchases p 
            JOIN cards c ON p.card_id = c.id
            WHERE strftime('%Y', p.purchase_date) = ?
        ''', (str(tax_year),))
        cashback_amount = float(c.fetchone()['total'])
        
        cashback_treatment = self.cashback_treatment_var.get()
        
        # Line 1: Gross receipts = Winning sessions + cashback (if included)
        if cashback_treatment == "gross_receipts":
            gross_receipts = winning_sessions + cashback_amount
            # Show breakdown
            breakdown_text = f"(Winnings: ${winning_sessions:,.2f} | Cashback: ${cashback_amount:,.2f})"
        else:
            gross_receipts = winning_sessions
            breakdown_text = ""
        
        # Line 2: Returns & allowances (assumed 0)
        returns = 0.0
        
        # Line 3: Net receipts (gross receipts - returns)
        net_receipts = gross_receipts - returns
        
        # Line 6: Other income (not used for cashback anymore)
        other_income = 0.0
        
        self.schedc_income_labels['Line 1'].config(text=f"${gross_receipts:,.2f}")
        self.schedc_gross_receipts_breakdown.config(text=breakdown_text)
        self.schedc_income_labels['Line 2'].config(text=f"${returns:,.2f}")
        self.schedc_income_labels['Line 3'].config(text=f"${net_receipts:,.2f}")
        self.schedc_income_labels['Line 6'].config(text=f"${other_income:,.2f}")
        
        
        # Gross Profit = Net Receipts (no COGS in session-based method)
        gross_profit = net_receipts + other_income
        self.schedc_gross_profit.config(
            text=f"${gross_profit:,.2f}",
            foreground='green' if gross_profit >= 0 else 'red'
        )
        
        # === PART III: EXPENSES ===
        
        # GAMBLING LOSSES (losing DAILY sessions)
        # daily_tax_sessions aggregates ALL sites per day per user
        c.execute('''
            SELECT COALESCE(SUM(ABS(net_daily_pnl)), 0) as total
            FROM daily_tax_sessions
            WHERE strftime('%Y', session_date) = ?
            AND net_daily_pnl < 0
        ''', (str(tax_year),))
        total_losing_sessions = float(c.fetchone()['total'])
        
        # Get business expenses by category
        c.execute('''
            SELECT category, COALESCE(SUM(amount), 0) as total
            FROM expenses
            WHERE strftime('%Y', expense_date) = ?
            GROUP BY category
        ''', (str(tax_year),))
        
        expenses_by_category = {row['category']: float(row['total']) for row in c.fetchall()}
        business_expenses_total = sum(expenses_by_category.values())
        
        # Apply 90% limitation if enabled (2026+ rule)
        # CRITICAL: Cap losses at GAMBLING WINNINGS ONLY (winning_sessions)
        # Do NOT include cashback in the loss limitation - cashback is not gambling winnings
        use_90_cap = self.loss_cap_var.get()
        
        if use_90_cap:
            # 2026+: Can only deduct 90% of all gambling expenses
            total_gambling_expenses = total_losing_sessions + business_expenses_total
            deductible_expenses = total_gambling_expenses * 0.90
            # Cap at GAMBLING WINNINGS ONLY (winning_sessions, NOT net_receipts which may include cashback)
            capped_expenses = min(deductible_expenses, winning_sessions)
            
            # Split the deduction proportionally between losses and business expenses
            if total_gambling_expenses > 0:
                loss_portion = total_losing_sessions / total_gambling_expenses
                business_portion = business_expenses_total / total_gambling_expenses
                gambling_losses = capped_expenses * loss_portion
                business_expenses_deductible = capped_expenses * business_portion
            else:
                gambling_losses = 0
                business_expenses_deductible = 0
        else:
            # Current: Can deduct 100% up to GAMBLING WINNINGS (not including cashback)
            total_gambling_expenses = total_losing_sessions + business_expenses_total
            # Cap at winning_sessions (gambling winnings only), NOT net_receipts
            capped_expenses = min(total_gambling_expenses, winning_sessions)
            
            # Split proportionally
            if total_gambling_expenses > 0:
                loss_portion = total_losing_sessions / total_gambling_expenses
                business_portion = business_expenses_total / total_gambling_expenses
                gambling_losses = capped_expenses * loss_portion
                business_expenses_deductible = capped_expenses * business_portion
            else:
                gambling_losses = 0
                business_expenses_deductible = 0
        
        # Total expenses = gambling losses + business expenses (both after cap)
        total_expenses = gambling_losses + business_expenses_deductible
        
        # Map database categories to Schedule C labels
        category_mapping = {
            'Advertising': 'Advertising',
            'Car and Truck Expenses': 'Car and Truck',
            'Commissions and Fees': 'Commissions and Fees',
            'Contract Labor': 'Contract Labor',
            'Depreciation': 'Depreciation',
            'Insurance (Business)': 'Insurance',
            'Interest (Mortgage/Other)': 'Interest',
            'Legal and Professional Services': 'Legal & Professional',
            'Office Expense': 'Office Expense',
            'Rent or Lease (Vehicles/Equipment)': 'Rent or Lease',
            'Rent or Lease (Other Business Property)': 'Rent or Lease',
            'Repairs and Maintenance': 'Repairs & Maintenance',
            'Supplies': 'Supplies',
            'Taxes and Licenses': 'Taxes and Licenses',
            'Travel': 'Travel',
            'Meals (Deductible)': 'Meals',
            'Utilities': 'Utilities',
            'Wages (Not Contract Labor)': 'Wages',
            'Other Expenses': 'Other Expenses (from line 48)'
        }
        
        # Calculate the reduction factor for business expenses if capped
        if business_expenses_total > 0:
            business_expense_reduction_factor = business_expenses_deductible / business_expenses_total
        else:
            business_expense_reduction_factor = 1.0
        
        # Update each expense line
        for expense_type in self.schedc_expense_labels.keys():
            if expense_type == 'Total Expenses (Line 28)':
                self.schedc_expense_labels[expense_type].config(
                    text=f"${total_expenses:,.2f}",
                    font=('Arial', 9, 'bold')
                )
            elif expense_type == 'Gambling Losses (Losing Sessions)':
                # Show gambling losses (after 90% cap if applicable)
                self.schedc_expense_labels[expense_type].config(
                    text=f"${gambling_losses:,.2f}",
                    font=('Arial', 9, 'bold'),
                    foreground='red' if gambling_losses > 0 else 'black'
                )
            else:
                # Find matching category amount from business expenses
                amount = 0.0
                for db_cat, label in category_mapping.items():
                    if label == expense_type:
                        amount += expenses_by_category.get(db_cat, 0.0)
                
                # Apply the reduction factor if 90% cap is in effect
                amount_after_cap = amount * business_expense_reduction_factor
                
                self.schedc_expense_labels[expense_type].config(text=f"${amount_after_cap:,.2f}")
        
        # Net Profit/Loss (Line 31)
        net_profit = gross_profit - total_expenses
        self.schedc_net_profit.config(
            text=f"${net_profit:,.2f}" if net_profit >= 0 else f"(${abs(net_profit):,.2f})",
            foreground='green' if net_profit >= 0 else 'red'
        )
        
        # === TAX PLANNING CALCULATIONS ===
        
        # Schedule C Net (same as net_profit)
        self.tax_planning_labels['schedc_net'].config(
            text=f"${net_profit:,.2f}" if net_profit >= 0 else f"(${abs(net_profit):,.2f})",
            foreground='green' if net_profit >= 0 else 'red'
        )
        
        # Self-Employment Tax (15.3% on net profit if positive)
        if net_profit > 0:
            se_tax = net_profit * 0.153
        else:
            se_tax = 0.0
        
        self.tax_planning_labels['se_tax'].config(
            text=f"${se_tax:,.2f}",
            foreground='red' if se_tax > 0 else 'black'
        )
        
        # Federal Income Tax Estimate (use a default 22% bracket - user can adjust)
        # Only on positive net profit
        if net_profit > 0:
            fed_tax = net_profit * 0.22
        else:
            fed_tax = 0.0
        
        self.tax_planning_labels['fed_tax'].config(
            text=f"${fed_tax:,.2f}",
            foreground='red' if fed_tax > 0 else 'black'
        )
        
        # 90% Cap Impact (if checkbox enabled) - includes ALL gambling expenses
        use_90_cap = self.loss_cap_var.get()
        if use_90_cap:
            # Total non-deductible = (Total losses + Total business expenses) - (Deductible losses + Deductible business expenses)
            c.execute('''
                SELECT COALESCE(SUM(ABS(net_daily_pnl)), 0) as total
                FROM daily_tax_sessions
                WHERE strftime('%Y', session_date) = ?
                AND net_daily_pnl < 0
            ''', (str(tax_year),))
            total_losses_full = float(c.fetchone()['total'])
            
            c.execute('''
                SELECT COALESCE(SUM(amount), 0) as total
                FROM expenses
                WHERE strftime('%Y', expense_date) = ?
            ''', (str(tax_year),))
            business_expenses_full = float(c.fetchone()['total'])
            
            total_expenses_full = total_losses_full + business_expenses_full
            total_expenses_deductible = gambling_losses + business_expenses_deductible
            
            non_deductible_amount = total_expenses_full - total_expenses_deductible
            cap_impact = non_deductible_amount
        else:
            cap_impact = 0.0
        
        self.tax_planning_labels['cap_impact'].config(
            text=f"${cap_impact:,.2f}" if cap_impact > 0 else "$0.00",
            foreground='red' if cap_impact > 0 else 'black'
        )
        
        # Total Tax Liability (SE + Fed, not including non-deductible losses which just reduce the loss)
        total_tax = se_tax + fed_tax
        self.tax_planning_labels['total_tax'].config(
            text=f"${total_tax:,.2f}",
            foreground='red' if total_tax > 0 else 'green'
        )
        
        # === 1099 RECONCILIATION ===
        
        # Total 1099s (redemptions)
        c.execute('''
            SELECT COALESCE(SUM(amount), 0) as total
            FROM redemptions
            WHERE strftime('%Y', redemption_date) = ?
        ''', (str(tax_year),))
        total_1099 = float(c.fetchone()['total'])
        
        # Purchase basis
        c.execute('''
            SELECT COALESCE(SUM(amount), 0) as total
            FROM purchases
            WHERE strftime('%Y', purchase_date) = ?
        ''', (str(tax_year),))
        purchase_basis = float(c.fetchone()['total'])
        
        # Get winning and losing daily sessions
        c.execute('''
            SELECT COALESCE(SUM(net_daily_pnl), 0) as total
            FROM daily_tax_sessions
            WHERE strftime('%Y', session_date) = ?
            AND net_daily_pnl > 0
        ''', (str(tax_year),))
        winning_days = float(c.fetchone()['total'])
        
        c.execute('''
            SELECT COALESCE(SUM(ABS(net_daily_pnl)), 0) as total
            FROM daily_tax_sessions
            WHERE strftime('%Y', session_date) = ?
            AND net_daily_pnl < 0
        ''', (str(tax_year),))
        losing_days = float(c.fetchone()['total'])
        
        # Cash flow
        cash_flow = total_1099 - purchase_basis
        
        # Update reconciliation labels
        self.reconciliation_labels['total_1099'].config(text=f"${total_1099:,.2f}")
        self.reconciliation_labels['winning_sessions'].config(
            text=f"${winning_days:,.2f}",
            foreground='green' if winning_days > 0 else 'black'
        )
        self.reconciliation_labels['losing_sessions'].config(
            text=f"${losing_days:,.2f}",
            foreground='red' if losing_days > 0 else 'black'
        )
        self.reconciliation_labels['schedc_result'].config(
            text=f"${net_profit:,.2f}" if net_profit >= 0 else f"(${abs(net_profit):,.2f})",
            foreground='green' if net_profit >= 0 else 'red'
        )
        self.reconciliation_labels['purchase_basis'].config(text=f"${purchase_basis:,.2f}")
        self.reconciliation_labels['total_redeemed'].config(text=f"${total_1099:,.2f}")
        self.reconciliation_labels['cash_flow'].config(
            text=f"${cash_flow:,.2f}" if cash_flow >= 0 else f"(${abs(cash_flow):,.2f})",
            foreground='green' if cash_flow >= 0 else 'red'
        )
        
        conn.close()
    
    
    def _set_stats_filter_last_n_days(self, n):
        """Set stats filter to last N days"""
        from datetime import timedelta
        end_date = date.today()
        start_date = end_date - timedelta(days=n)
        self.stats_filter_start.delete(0, tk.END)
        self.stats_filter_start.insert(0, start_date.strftime("%Y-%m-%d"))
        self.stats_filter_end.delete(0, tk.END)
        self.stats_filter_end.insert(0, end_date.strftime("%Y-%m-%d"))
        self.refresh_global_stats()
    
    def _set_stats_filter_this_month(self):
        """Set stats filter to current month"""
        today = date.today()
        start_date = today.replace(day=1)
        self.stats_filter_start.delete(0, tk.END)
        self.stats_filter_start.insert(0, start_date.strftime("%Y-%m-%d"))
        self.stats_filter_end.delete(0, tk.END)
        self.stats_filter_end.insert(0, today.strftime("%Y-%m-%d"))
        self.refresh_global_stats()
    
    def _set_stats_filter_this_year(self):
        """Set stats filter to current year"""
        today = date.today()
        start_date = today.replace(month=1, day=1)
        self.stats_filter_start.delete(0, tk.END)
        self.stats_filter_start.insert(0, start_date.strftime("%Y-%m-%d"))
        self.stats_filter_end.delete(0, tk.END)
        self.stats_filter_end.insert(0, today.strftime("%Y-%m-%d"))
        self.refresh_global_stats()
    
    def _set_stats_filter_all_time(self):
        """Set stats filter to all time"""
        self.stats_filter_start.delete(0, tk.END)
        self.stats_filter_end.delete(0, tk.END)
        self.refresh_global_stats()
    
    def refresh_global_stats(self):
        """
        Refresh the global P/L bar with comprehensive metrics
        
        OPTION B: Show BOTH cash flow and session-based P/L, emphasize session P/L
        - Cash flow = bankroll management (money in/out)
        - Session P/L = tax reality (what IRS sees)
        """
        from datetime import date as dt
        
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Get filters
        start_date = self.stats_filter_start.get().strip()
        end_date = self.stats_filter_end.get().strip()
        filter_site = self.stats_filter_site.get() if hasattr(self, 'stats_filter_site') else 'All Sites'
        filter_user = self.stats_filter_user.get() if hasattr(self, 'stats_filter_user') else 'All Users'
        
        # Build WHERE clauses with all filters
        # For purchases table
        purchase_where_clauses = []
        purchase_params = []
        
        if start_date and end_date:
            purchase_where_clauses.append("purchase_date BETWEEN ? AND ?")
            purchase_params.extend([start_date, end_date])
            period_text = f"({start_date} to {end_date})"
        elif start_date:
            purchase_where_clauses.append("purchase_date >= ?")
            purchase_params.append(start_date)
            period_text = f"(from {start_date})"
        elif end_date:
            purchase_where_clauses.append("purchase_date <= ?")
            purchase_params.append(end_date)
            period_text = f"(up to {end_date})"
        else:
            period_text = "(All Time)"
        
        if filter_site and filter_site != 'All Sites':
            purchase_where_clauses.append("site_id = (SELECT id FROM sites WHERE name = ?)")
            purchase_params.append(filter_site)
        
        if filter_user and filter_user != 'All Users':
            purchase_where_clauses.append("user_id = (SELECT id FROM users WHERE name = ?)")
            purchase_params.append(filter_user)
        
        # WHERE clause for purchases table (no alias)
        date_where = " WHERE " + " AND ".join(purchase_where_clauses) if purchase_where_clauses else ""
        date_params = purchase_params
        
        # WHERE clause for cashback query (uses 'p' alias for purchases)
        cashback_where_clauses = []
        if start_date and end_date:
            cashback_where_clauses.append("p.purchase_date BETWEEN ? AND ?")
        elif start_date:
            cashback_where_clauses.append("p.purchase_date >= ?")
        elif end_date:
            cashback_where_clauses.append("p.purchase_date <= ?")
        
        if filter_site and filter_site != 'All Sites':
            cashback_where_clauses.append("p.site_id = (SELECT id FROM sites WHERE name = ?)")
        
        if filter_user and filter_user != 'All Users':
            cashback_where_clauses.append("p.user_id = (SELECT id FROM users WHERE name = ?)")
        
        cashback_where = " WHERE " + " AND ".join(cashback_where_clauses) if cashback_where_clauses else ""
        
        # Update period label
        filter_text_parts = [period_text]
        if filter_site and filter_site != 'All Sites':
            filter_text_parts.append(f"Site: {filter_site}")
        if filter_user and filter_user != 'All Users':
            filter_text_parts.append(f"User: {filter_user}")
        self.stats_period_label.config(text=" | ".join(filter_text_parts))
        
        # ========================================================================
        # CASH FLOW METRICS (Bankroll Management)
        # ========================================================================
        
        # Total invested (filtered by purchase_date)
        c.execute(f'SELECT COALESCE(SUM(amount), 0) as total FROM purchases{date_where}', date_params)
        total_invested = float(c.fetchone()['total'])
        
        # Build WHERE clause for redemptions with same filters
        redemption_where_clauses = []
        redemption_params = []
        
        if start_date and end_date:
            redemption_where_clauses.append("redemption_date BETWEEN ? AND ?")
            redemption_params.extend([start_date, end_date])
        elif start_date:
            redemption_where_clauses.append("redemption_date >= ?")
            redemption_params.append(start_date)
        elif end_date:
            redemption_where_clauses.append("redemption_date <= ?")
            redemption_params.append(end_date)
        
        if filter_site and filter_site != 'All Sites':
            redemption_where_clauses.append("site_id = (SELECT id FROM sites WHERE name = ?)")
            redemption_params.append(filter_site)
        
        if filter_user and filter_user != 'All Users':
            redemption_where_clauses.append("user_id = (SELECT id FROM users WHERE name = ?)")
            redemption_params.append(filter_user)
        
        redemption_where = " WHERE " + " AND ".join(redemption_where_clauses) if redemption_where_clauses else ""
        
        # Total redeemed (filtered)
        c.execute(f'SELECT COALESCE(SUM(amount), 0) as total FROM redemptions{redemption_where}', redemption_params)
        total_redeemed = float(c.fetchone()['total'])
        
        # Net cash (simple delta)
        net_cash = total_redeemed - total_invested
        
        # Unrealized cost basis (still at risk) - filtered
        c.execute(f'SELECT COALESCE(SUM(remaining_amount), 0) as unrealized FROM purchases{date_where}', date_params)
        unrealized_cost = float(c.fetchone()['unrealized'])
        
        # ========================================================================
        # SESSION-BASED P/L (Tax Reality - uses game_sessions table)
        # ========================================================================
        
        # Build WHERE clause for sessions
        session_where_clauses = ["status = 'Closed'"]
        session_params = []
        
        if start_date and end_date:
            session_where_clauses.append("session_date BETWEEN ? AND ?")
            session_params.extend([start_date, end_date])
        elif start_date:
            session_where_clauses.append("session_date >= ?")
            session_params.append(start_date)
        elif end_date:
            session_where_clauses.append("session_date <= ?")
            session_params.append(end_date)
        
        if filter_site and filter_site != 'All Sites':
            session_where_clauses.append("site_id = (SELECT id FROM sites WHERE name = ?)")
            session_params.append(filter_site)
        
        if filter_user and filter_user != 'All Users':
            session_where_clauses.append("user_id = (SELECT id FROM users WHERE name = ?)")
            session_params.append(filter_user)
        
        session_where = " WHERE " + " AND ".join(session_where_clauses)
        
        # Session P/L from game_sessions (net taxable)
        c.execute(f'''
            SELECT COALESCE(SUM(total_taxable), 0) as total 
            FROM game_sessions 
            {session_where}
        ''', session_params)
        session_pl = float(c.fetchone()['total'])
        
        # Number of closed game sessions
        c.execute(f'''
            SELECT COUNT(*) as count 
            FROM game_sessions 
            {session_where}
        ''', session_params)
        num_sessions = int(c.fetchone()['count'])
        
        # Number of ACTIVE game sessions (currently playing) - filtered by site/user
        active_where_clauses = ["status = 'Active'"]
        active_params = []
        
        if filter_site and filter_site != 'All Sites':
            active_where_clauses.append("site_id = (SELECT id FROM sites WHERE name = ?)")
            active_params.append(filter_site)
        
        if filter_user and filter_user != 'All Users':
            active_where_clauses.append("user_id = (SELECT id FROM users WHERE name = ?)")
            active_params.append(filter_user)
        
        active_where = " WHERE " + " AND ".join(active_where_clauses)
        
        c.execute(f'''
            SELECT COUNT(*) as count 
            FROM game_sessions 
            {active_where}
        ''', active_params)
        active_sessions = int(c.fetchone()['count'])
        
        # Today's P/L (current date only)
        today_str = dt.today().strftime('%Y-%m-%d')
        c.execute('''
            SELECT COALESCE(SUM(total_taxable), 0) as total 
            FROM game_sessions 
            WHERE status = 'Closed' AND session_date = ?
        ''', (today_str,))
        today_pl = float(c.fetchone()['total'])
        
        # Cashback earned - filtered
        c.execute(f'''
            SELECT COALESCE(SUM(p.amount * c.cashback_rate / 100), 0) as total
            FROM purchases p JOIN cards c ON p.card_id = c.id
            {cashback_where}
        ''', date_params)
        total_cashback = float(c.fetchone()['total'])
        
        # Expenses - build WHERE clause properly
        expense_where_clauses = []
        expense_params = []
        
        if start_date and end_date:
            expense_where_clauses.append("expense_date BETWEEN ? AND ?")
            expense_params.extend([start_date, end_date])
        elif start_date:
            expense_where_clauses.append("expense_date >= ?")
            expense_params.append(start_date)
        elif end_date:
            expense_where_clauses.append("expense_date <= ?")
            expense_params.append(end_date)
        
        # Note: Expenses don't have site_id/user_id filters in this context
        # They're business expenses, not tied to specific sites
        
        expense_where = " WHERE " + " AND ".join(expense_where_clauses) if expense_where_clauses else ""
        c.execute(f'SELECT COALESCE(SUM(amount), 0) as total FROM expenses{expense_where}', expense_params)
        total_expenses = float(c.fetchone()['total'])
        
        # ========================================================================
        # RUNNING LOSS CALCULATION (Anti-Tilt Mechanism)
        # ========================================================================
        
        # Get chronological session P/L history - filtered
        c.execute(f'''
            SELECT session_date, SUM(total_taxable) as daily_pl
            FROM game_sessions
            {session_where}
            GROUP BY session_date
            ORDER BY session_date ASC
        ''', session_params)
        play_results = c.fetchall()
        play_history = [(row['session_date'], float(row['daily_pl'])) for row in play_results]
        
        # Get cumulative cashback by date - filtered
        c.execute(f'''
            SELECT p.purchase_date as date, SUM(p.amount * c.cashback_rate / 100) as cashback
            FROM purchases p
            JOIN cards c ON p.card_id = c.id
            {cashback_where}
            GROUP BY p.purchase_date
            ORDER BY p.purchase_date ASC
        ''', date_params)
        cashback_results = c.fetchall()
        cashback_history = {row['date']: float(row['cashback']) for row in cashback_results}
        
        # Calculate peak by tracking GAMBLING P/L chronologically (session P/L + cashback only, NO expenses)
        all_dates = set()
        for date_str, _ in play_history:
            all_dates.add(date_str)
        all_dates.update(cashback_history.keys())
        
        cumulative_gambling_pl = 0.0
        peak_gambling_pl = 0.0  # Starting peak is $0
        
        for date_str in sorted(all_dates):
            # Add session P/L for this date
            for play_date, play_pl in play_history:
                if play_date == date_str:
                    cumulative_gambling_pl += play_pl
            
            # Add cashback for this date
            cumulative_gambling_pl += cashback_history.get(date_str, 0.0)
            
            # Update peak (no expenses included)
            if cumulative_gambling_pl > peak_gambling_pl:
                peak_gambling_pl = cumulative_gambling_pl
        
        # Calculate running loss (current GAMBLING P/L vs peak GAMBLING P/L)
        # Only tracks session P/L + cashback, NOT expenses
        current_gambling_pl = session_pl + total_cashback
        running_loss = current_gambling_pl - peak_gambling_pl
        
        conn.close()
        
        # ========================================================================
        # CALCULATE DISPLAY METRICS
        # ========================================================================
        
        # ROI calculations
        session_roi = (session_pl / total_invested * 100) if total_invested > 0 else 0
        net_taxable = session_pl + total_cashback - total_expenses
        net_roi = (net_taxable / total_invested * 100) if total_invested > 0 else 0
        
        # Average session
        avg_session_pl = session_pl / num_sessions if num_sessions > 0 else 0
        
        # ========================================================================
        # UPDATE DISPLAY
        # ========================================================================
        
        try:
            # Row 1: Primary Financial Metrics
            self._invested_var.set(f"Invested: ${total_invested:,.2f}")
            self._redeemed_var.set(f"Redeemed: ${total_redeemed:,.2f} (Net: ${net_cash:+,.2f})")
            self._cashback_var.set(f"Cashback: ${total_cashback:,.2f}")
            self._expenses_var.set(f"Expenses: ${total_expenses:,.2f}")
            
            # Session P/L is THE primary metric (tax reality)
            session_color = 'green' if session_pl >= 0 else 'red'
            self._play_pl_var.set(f"Play P/L: ${session_pl:+,.2f} ({session_roi:+.1f}%)")
            
            # Unrealized cost
            unrealized_color = 'orange' if unrealized_cost > 0 else 'gray'
            self._unrealized_var.set(f"Unrealized: ${unrealized_cost:,.2f}")
            
            # Net after expenses
            net_color = 'green' if net_taxable >= 0 else 'red'
            self._net_pl_var.set(f"Net Taxable: ${net_taxable:+,.2f} ({net_roi:+.1f}%)")
            
            # Row 2: Session Info
            session_text = f"Sessions: {num_sessions}"
            if active_sessions > 0:
                session_text += f" (▶ {active_sessions} ACTIVE)"
            self._sessions_var.set(session_text)
            
            # Avg session
            avg_color = 'green' if avg_session_pl >= 0 else 'red'
            self._avg_session_var.set(f"Avg/Session: ${avg_session_pl:+,.2f}")
            
            # Running loss (anti-tilt)
            running_loss_color = 'red' if running_loss < 0 else 'gray'
            self._running_loss_var.set(f"Running Loss: ${running_loss:,.2f}")
            
            # Update colors by finding the labels by their textvariable
            def update_label_color(parent, textvariable, color):
                """Recursively find and update label color"""
                for widget in parent.winfo_children():
                    try:
                        if isinstance(widget, ttk.Label) and widget.cget('textvariable') == str(textvariable):
                            widget.config(foreground=color)
                            return True
                    except:
                        pass
                    # Check children recursively
                    if update_label_color(widget, textvariable, color):
                        return True
                return False
            
            update_label_color(self.root, self._play_pl_var, session_color)
            update_label_color(self.root, self._net_pl_var, net_color)
            update_label_color(self.root, self._cashback_var, 'green')  # Cashback is always green
            update_label_color(self.root, self._expenses_var, 'red')  # Expenses are always red
            update_label_color(self.root, self._avg_session_var, avg_color)
            update_label_color(self.root, self._running_loss_var, running_loss_color)
            update_label_color(self.root, self._unrealized_var, unrealized_color)
            
        except Exception as e:
            print(f"Error updating stats: {e}")
            import traceback
            traceback.print_exc()
            pass
    
    # ========================================================================
    # BACKUP/RESTORE METHODS
    # ========================================================================
    
    def auto_backup(self):
        """Auto-backup database on startup, keep last 7 days"""
        import shutil
        from pathlib import Path
        from datetime import datetime, timedelta
        
        try:
            backup_dir = Path.home() / "Desktop" / "CasinoTrackerBackups"
            if not backup_dir.exists():
                backup_dir.mkdir(parents=True)
            
            # Create timestamped backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = backup_dir / f"casino_backup_{timestamp}.db"
            
            shutil.copy2("casino_accounting.db", backup_file)
            
            # Clean up old backups (keep last 7 days)
            cutoff_date = datetime.now() - timedelta(days=7)
            for old_backup in backup_dir.glob("casino_backup_*.db"):
                try:
                    # Extract date from filename
                    date_str = old_backup.stem.split('_')[2]
                    backup_date = datetime.strptime(date_str, "%Y%m%d")
                    if backup_date < cutoff_date:
                        old_backup.unlink()
                except:
                    pass  # Skip if can't parse
        except Exception as e:
            print(f"Auto-backup failed: {e}")
    
    def backup_database(self):
        """Manual backup of database"""
        import shutil
        from pathlib import Path
        from datetime import datetime
        from tkinter import filedialog
        
        try:
            # Default to Desktop/CasinoTrackerBackups
            default_dir = Path.home() / "Desktop" / "CasinoTrackerBackups"
            if not default_dir.exists():
                default_dir.mkdir(parents=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_name = f"casino_backup_{timestamp}.db"
            
            filepath = filedialog.asksaveasfilename(
                initialdir=default_dir,
                initialfile=default_name,
                defaultextension=".db",
                filetypes=[("Database files", "*.db"), ("All files", "*.*")]
            )
            
            if filepath:
                shutil.copy2("casino_accounting.db", filepath)
                messagebox.showinfo("Success", f"Database backed up to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Backup failed: {e}")
    
    def restore_database(self):
        """Restore database from backup"""
        import shutil
        from tkinter import filedialog
        
        if not messagebox.askyesno("Confirm Restore", 
            "This will replace your current database with a backup.\n\n"
            "Current database will be backed up first.\n\n"
            "Continue?"):
            return
        
        try:
            # Backup current database first
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            shutil.copy2("casino_accounting.db", f"casino_backup_before_restore_{timestamp}.db")
            
            # Select backup file
            filepath = filedialog.askopenfilename(
                title="Select Backup File",
                filetypes=[("Database files", "*.db"), ("All files", "*.*")]
            )
            
            if filepath:
                # Close current connection
                self.db.close()
                
                # Restore
                shutil.copy2(filepath, "casino_accounting.db")
                
                # Reinitialize database connection
                self.db = Database()
                self.fifo_calc = FIFOCalculator(self.db)
                self.session_mgr = SessionManager(self.db, self.fifo_calc)
                
                # Refresh all views
                self.refresh_all_views()
                
                messagebox.showinfo("Success", 
                    f"Database restored from:\n{filepath}\n\n"
                    f"Previous database saved as:\ncasino_backup_before_restore_{timestamp}.db")
        except Exception as e:
            messagebox.showerror("Error", f"Restore failed: {e}")
    
    def view_audit_log(self):
        """View audit log in popup window"""
        popup = tk.Toplevel(self.root)
        popup.title("Audit Log")
        popup.geometry("1000x600")
        
        # Filter controls
        filter_frame = ttk.Frame(popup, padding=10)
        filter_frame.pack(fill='x')
        
        ttk.Label(filter_frame, text="Show last:").pack(side='left', padx=5)
        limit_var = tk.StringVar(value="100")
        limit_combo = ttk.Combobox(filter_frame, textvariable=limit_var, 
                                   values=['50', '100', '500', '1000', 'All'], width=10)
        limit_combo.pack(side='left', padx=5)
        
        def refresh_log():
            for item in log_tree.get_children():
                log_tree.delete(item)
            
            conn = self.db.get_connection()
            c = conn.cursor()
            
            limit = limit_var.get()
            if limit == 'All':
                query = 'SELECT * FROM audit_log ORDER BY timestamp DESC'
                c.execute(query)
            else:
                query = 'SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?'
                c.execute(query, (int(limit),))
            
            for row in c.fetchall():
                log_tree.insert('', 'end', values=(
                    row['timestamp'],
                    row['action'],
                    row['table_name'],
                    row['record_id'] or '',
                    row['details'] or '',
                    row['user_name'] or ''
                ))
            
            conn.close()
        
        ttk.Button(filter_frame, text="Refresh", command=refresh_log).pack(side='left', padx=5)
        ttk.Button(filter_frame, text="Close", command=popup.destroy).pack(side='right', padx=5)
        
        # Log tree
        log_frame = ttk.Frame(popup)
        log_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        cols = ('Timestamp', 'Action', 'Table', 'Record ID', 'Details', 'User')
        log_tree = ttk.Treeview(log_frame, columns=cols, show='headings', height=20)
        
        log_tree.heading('Timestamp', text='Timestamp')
        log_tree.heading('Action', text='Action')
        log_tree.heading('Table', text='Table')
        log_tree.heading('Record ID', text='Record ID')
        log_tree.heading('Details', text='Details')
        log_tree.heading('User', text='User')
        
        log_tree.column('Timestamp', width=150)
        log_tree.column('Action', width=80)
        log_tree.column('Table', width=100)
        log_tree.column('Record ID', width=80)
        log_tree.column('Details', width=400)
        log_tree.column('User', width=100)
        
        scroll = ttk.Scrollbar(log_frame, orient='vertical', command=log_tree.yview)
        log_tree.configure(yscrollcommand=scroll.set)
        log_tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        
        refresh_log()
    
    # ========================================================================
    # TAX CALCULATOR METHODS
    # ========================================================================
    
    def refresh_tax_calculators(self):
        """Refresh estimated tax calculator"""
        try:
            tax_year = int(self.tax_calc_year_var.get())
        except:
            tax_year = date.today().year
        
        # Get net profit from Schedule C calculation
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Get total redemptions (income)
        c.execute('''
            SELECT COALESCE(SUM(amount), 0) as total
            FROM redemptions
            WHERE strftime('%Y', redemption_date) = ?
        ''', (str(tax_year),))
        gross_receipts = float(c.fetchone()['total'])
        
        # Get COGS (cost basis consumed)
        c.execute('''
            SELECT COALESCE(SUM(cost_basis), 0) as total
            FROM tax_sessions
            WHERE strftime('%Y', session_date) = ?
        ''', (str(tax_year),))
        cogs = float(c.fetchone()['total'])
        
        # Get expenses
        c.execute('''
            SELECT COALESCE(SUM(amount), 0) as total
            FROM expenses
            WHERE strftime('%Y', expense_date) = ?
        ''', (str(tax_year),))
        total_expenses = float(c.fetchone()['total'])
        
        conn.close()
        
        # Calculate net profit
        gross_profit = gross_receipts - cogs
        net_profit = gross_profit - total_expenses
        
        # Calculate taxes
        # Self-employment tax: 15.3% on 92.35% of net profit
        se_tax_base = net_profit * 0.9235
        se_tax = max(0, se_tax_base * 0.153)
        
        # Federal income tax (estimated at 22% marginal rate)
        # Deduct 50% of SE tax from taxable income
        taxable_income = net_profit - (se_tax * 0.5)
        
        # Federal income tax using user's bracket
        try:
            tax_bracket = float(self.tax_bracket_var.get()) / 100
        except:
            tax_bracket = 0.22  # Default to 22% if invalid
        
        income_tax = max(0, taxable_income * tax_bracket)
        
        # Total tax
        total_tax = se_tax + income_tax
        
        # Already paid
        try:
            already_paid = float(self.tax_paid_entry.get() or 0)
        except:
            already_paid = 0
        
        # Still owe
        still_owe = total_tax - already_paid
        
        # Update labels
        self.tax_calc_labels['Business Net Profit (Schedule C)'].config(
            text=f"${net_profit:,.2f}",
            foreground='green' if net_profit >= 0 else 'red'
        )
        
        self.tax_calc_labels['Self-Employment Tax (15.3%)'].config(
            text=f"${se_tax:,.2f}"
        )
        
        self.tax_calc_labels['Federal Income Tax'].config(
            text=f"${income_tax:,.2f}"
        )
        
        self.tax_calc_labels['Total Estimated Tax'].config(
            text=f"${total_tax:,.2f}",
            font=('Arial', 10, 'bold')
        )
        
        self.tax_calc_labels['Still Owe / (Refund)'].config(
            text=f"${still_owe:,.2f}" if still_owe >= 0 else f"(${abs(still_owe):,.2f})",
            foreground='red' if still_owe > 0 else 'green',
            font=('Arial', 10, 'bold')
        )
    
    def calculate_home_office(self):
        """Calculate home office deduction"""
        try:
            home_sqft = float(self.home_sqft.get() or 0)
            office_sqft = float(self.office_sqft.get() or 0)
            rent = float(self.home_rent.get() or 0)
            utilities = float(self.home_utilities.get() or 0)
            internet = float(self.home_internet.get() or 0)
            insurance = float(self.home_insurance.get() or 0)
            
            if home_sqft == 0 or office_sqft == 0:
                percentage = 0
            else:
                percentage = (office_sqft / home_sqft) * 100
            
            # Calculate deductible amounts
            deduct_rent = rent * (percentage / 100)
            deduct_utilities = utilities * (percentage / 100)
            deduct_internet = internet * (percentage / 100)
            deduct_insurance = insurance * (percentage / 100)
            
            total_deduction = deduct_rent + deduct_utilities + deduct_internet + deduct_insurance
            
            # Update labels
            self.home_office_labels['Business Use Percentage'].config(
                text=f"{percentage:.1f}%"
            )
            self.home_office_labels['Deductible Rent/Mortgage'].config(
                text=f"${deduct_rent:,.2f}"
            )
            self.home_office_labels['Deductible Utilities'].config(
                text=f"${deduct_utilities:,.2f}"
            )
            self.home_office_labels['Deductible Internet'].config(
                text=f"${deduct_internet:,.2f}"
            )
            self.home_office_labels['Deductible Insurance'].config(
                text=f"${deduct_insurance:,.2f}"
            )
            self.home_office_labels['Total Home Office Deduction'].config(
                text=f"${total_deduction:,.2f}",
                foreground='green' if total_deduction > 0 else 'black'
            )
        except ValueError:
            pass
    
    def refresh_yoy(self):
        """Refresh year-over-year comparison"""
        # Clear existing
        for item in self.yoy_tree.get_children():
            self.yoy_tree.delete(item)
        
        try:
            year1 = int(self.yoy_year1.get())
            year2 = int(self.yoy_year2.get())
        except:
            return
        
        conn = self.db.get_connection()
        c = conn.cursor()
        
        def get_year_stats(year):
            """Get stats for a single year"""
            # Sessions count
            c.execute('''
                SELECT COUNT(DISTINCT session_date || '-' || site_id) as sessions
                FROM tax_sessions
                WHERE strftime('%Y', session_date) = ?
            ''', (str(year),))
            sessions = c.fetchone()['sessions'] or 0
            
            # Net P/L
            c.execute('''
                SELECT SUM(net_pl) as net_pl
                FROM tax_sessions
                WHERE strftime('%Y', session_date) = ?
            ''', (str(year),))
            net_pl = float(c.fetchone()['net_pl'] or 0)
            
            # Win rate (sessions with positive P/L)
            c.execute('''
                SELECT 
                    COUNT(DISTINCT CASE WHEN net_pl > 0 THEN session_date || '-' || site_id END) as wins,
                    COUNT(DISTINCT session_date || '-' || site_id) as total
                FROM tax_sessions
                WHERE strftime('%Y', session_date) = ?
            ''', (str(year),))
            row = c.fetchone()
            wins = row['wins'] or 0
            total = row['total'] or 1
            win_rate = (wins / total * 100) if total > 0 else 0
            
            # ROI
            c.execute('''
                SELECT SUM(cost_basis) as cost, SUM(net_pl) as profit
                FROM tax_sessions
                WHERE strftime('%Y', session_date) = ?
            ''', (str(year),))
            row = c.fetchone()
            cost = float(row['cost'] or 0)
            profit = float(row['profit'] or 0)
            roi = (profit / cost * 100) if cost > 0 else 0
            
            # Total invested
            c.execute('''
                SELECT SUM(amount) as invested
                FROM purchases
                WHERE strftime('%Y', purchase_date) = ?
            ''', (str(year),))
            invested = float(c.fetchone()['invested'] or 0)
            
            # Total redeemed
            c.execute('''
                SELECT SUM(amount) as redeemed
                FROM redemptions
                WHERE strftime('%Y', redemption_date) = ?
            ''', (str(year),))
            redeemed = float(c.fetchone()['redeemed'] or 0)
            
            return {
                'sessions': sessions,
                'net_pl': net_pl,
                'win_rate': win_rate,
                'roi': roi,
                'invested': invested,
                'redeemed': redeemed
            }
        
        stats1 = get_year_stats(year1)
        stats2 = get_year_stats(year2)
        
        conn.close()
        
        # Calculate changes
        metrics = [
            ('Total Sessions', stats1['sessions'], stats2['sessions'], 'count'),
            ('Net P/L', stats1['net_pl'], stats2['net_pl'], 'money'),
            ('Win Rate', stats1['win_rate'], stats2['win_rate'], 'percent'),
            ('ROI', stats1['roi'], stats2['roi'], 'percent'),
            ('Total Invested', stats1['invested'], stats2['invested'], 'money'),
            ('Total Redeemed', stats1['redeemed'], stats2['redeemed'], 'money')
        ]
        
        for metric_name, val1, val2, fmt in metrics:
            if fmt == 'money':
                v1_str = f"${val1:,.2f}"
                v2_str = f"${val2:,.2f}"
                change = val2 - val1
                if val1 != 0:
                    pct_change = (change / abs(val1)) * 100
                    change_str = f"${change:+,.2f} ({pct_change:+.1f}%)"
                else:
                    change_str = f"${change:+,.2f}"
            elif fmt == 'percent':
                v1_str = f"{val1:.1f}%"
                v2_str = f"{val2:.1f}%"
                change = val2 - val1
                change_str = f"{change:+.1f}%"
            else:  # count
                v1_str = f"{int(val1)}"
                v2_str = f"{int(val2)}"
                change = val2 - val1
                if val1 != 0:
                    pct_change = (change / val1) * 100
                    change_str = f"{change:+,.0f} ({pct_change:+.1f}%)"
                else:
                    change_str = f"{change:+,.0f}"
            
            self.yoy_tree.insert('', 'end', values=(metric_name, v1_str, v2_str, change_str))
    
    # ========================================================================
    # CSV EXPORT METHODS FOR CPA
    # ========================================================================
    
    def export_tax_sessions(self):
        """Export tax sessions as two files: Summary (by day) and Detail (by day/site)"""
        import csv
        from pathlib import Path
        
        try:
            tax_year = int(self.export_year_var.get())
        except:
            tax_year = date.today().year
        
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # === FILE 1: SUMMARY (One row per day - for tax filing) ===
        c.execute('''
            SELECT 
                ts.session_date as Date,
                COUNT(DISTINCT s.name) as "Sites Played",
                SUM(ts.cost_basis) as "Cost Basis",
                SUM(ts.payout) as Payout,
                SUM(ts.net_pl) as "Net P/L",
                COUNT(*) as "Transactions"
            FROM tax_sessions ts
            JOIN sites s ON ts.site_id = s.id
            WHERE strftime('%Y', ts.session_date) = ?
            GROUP BY ts.session_date
            ORDER BY ts.session_date ASC
        ''', (str(tax_year),))
        
        summary_rows = c.fetchall()
        
        if not summary_rows:
            conn.close()
            messagebox.showinfo("No Data", f"No tax sessions found for {tax_year}")
            return
        
        # === FILE 2: DETAIL (One row per day per site - for backup/reference) ===
        c.execute('''
            SELECT 
                ts.session_date as Date,
                s.name as Site,
                SUM(ts.cost_basis) as "Cost Basis",
                SUM(ts.payout) as Payout,
                SUM(ts.net_pl) as "Net P/L",
                COUNT(*) as "Transactions"
            FROM tax_sessions ts
            JOIN sites s ON ts.site_id = s.id
            WHERE strftime('%Y', ts.session_date) = ?
            GROUP BY ts.session_date, s.name
            ORDER BY ts.session_date ASC, s.name
        ''', (str(tax_year),))
        
        detail_rows = c.fetchall()
        conn.close()
        
        # Write Summary File
        summary_filename = f"Tax_Sessions_Summary_{tax_year}.csv"
        summary_filepath = Path.home() / "Desktop" / summary_filename
        
        if not summary_filepath.parent.exists():
            summary_filepath = Path(summary_filename)
        
        with open(summary_filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Date', 'Sites Played', 'Cost Basis', 'Payout', 'Net P/L', 'Transactions'])
            for row in summary_rows:
                writer.writerow([
                    row[0], 
                    row[1],
                    f"${row[2]:.2f}", 
                    f"${row[3]:.2f}", 
                    f"${row[4]:.2f}",
                    row[5]
                ])
        
        # Write Detail File
        detail_filename = f"Tax_Sessions_Detail_{tax_year}.csv"
        detail_filepath = Path.home() / "Desktop" / detail_filename
        
        if not detail_filepath.parent.exists():
            detail_filepath = Path(detail_filename)
        
        with open(detail_filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Date', 'Site', 'Cost Basis', 'Payout', 'Net P/L', 'Transactions'])
            for row in detail_rows:
                writer.writerow([
                    row[0],
                    row[1],
                    f"${row[2]:.2f}", 
                    f"${row[3]:.2f}", 
                    f"${row[4]:.2f}",
                    row[5]
                ])
        
        messagebox.showinfo("Success", 
            f"Exported 2 files:\n\n"
            f"Summary (for tax filing):\n{summary_filepath}\n\n"
            f"Detail (by site):\n{detail_filepath}")
    
    def export_income_summary(self):
        """Export monthly income summary (session-based)"""
        import csv
        from pathlib import Path
        
        try:
            tax_year = int(self.export_year_var.get())
        except:
            tax_year = date.today().year
        
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Monthly summary from game_sessions
        c.execute('''
            SELECT 
                strftime('%Y-%m', gs.session_date) as Month,
                COUNT(*) as "Game Sessions",
                SUM(gs.delta_total) as "Total Delta Total",
                SUM(gs.delta_redeem) as "Total Delta Redeemable",
                SUM(gs.total_taxable) as "Total Net Taxable"
            FROM game_sessions gs
            WHERE gs.status = 'Closed' AND strftime('%Y', gs.session_date) = ?
            GROUP BY strftime('%Y-%m', gs.session_date)
            ORDER BY Month
        ''', (str(tax_year),))
        
        game_rows = c.fetchall()
        
        # Also get redemptions and cashback for complete picture
        c.execute('''
            SELECT 
                strftime('%Y-%m', redemption_date) as Month,
                SUM(amount) as "Total Redeemed"
            FROM redemptions
            WHERE strftime('%Y', redemption_date) = ?
            GROUP BY strftime('%Y-%m', redemption_date)
        ''', (str(tax_year),))
        
        redemptions = {row['Month']: float(row['Total Redeemed']) for row in c.fetchall()}
        
        # Get cashback by month
        c.execute('''
            SELECT 
                strftime('%Y-%m', p.purchase_date) as Month,
                SUM(p.amount * c.cashback_rate / 100) as Cashback
            FROM purchases p
            JOIN cards c ON p.card_id = c.id
            WHERE strftime('%Y', p.purchase_date) = ?
            GROUP BY strftime('%Y-%m', p.purchase_date)
        ''', (str(tax_year),))
        
        cashback = {row['Month']: float(row['Cashback']) for row in c.fetchall()}
        
        conn.close()
        
        if not game_rows:
            messagebox.showinfo("No Data", f"No income data for {tax_year}")
            return
        
        filename = f"Income_Summary_{tax_year}.csv"
        filepath = Path.home() / "Desktop" / filename
        
        if not filepath.parent.exists():
            filepath = Path(filename)
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Month', 'Game Sessions', 'Delta Total (SC)', 'Delta Redeemable (SC)',
                           'Net Taxable', 'Cashback Earned', 'Redemptions'])
            for row in game_rows:
                month = row['Month']
                writer.writerow([
                    month,
                    row['Game Sessions'],
                    f"{(row['Total Delta Total'] or 0):+.2f}",
                    f"{(row['Total Delta Redeemable'] or 0):+.2f}",
                    f"${(row['Total Net Taxable'] or 0):+.2f}",
                    f"${cashback.get(month, 0):.2f}",
                    f"${redemptions.get(month, 0):.2f}"
                ])
        
        messagebox.showinfo("Success", f"Income summary exported to:\n{filepath}")
    
    def export_expenses_by_category(self):
        """Export expenses by Schedule C category"""
        import csv
        from pathlib import Path
        
        try:
            tax_year = int(self.export_year_var.get())
        except:
            tax_year = date.today().year
        
        conn = self.db.get_connection()
        c = conn.cursor()
        
        c.execute('''
            SELECT 
                e.expense_date as Date,
                e.category as "Schedule C Category",
                e.vendor as Vendor,
                e.description as Description,
                e.amount as Amount
            FROM expenses e
            WHERE strftime('%Y', e.expense_date) = ?
            ORDER BY e.category, e.expense_date
        ''', (str(tax_year),))
        
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            messagebox.showinfo("No Data", f"No expenses for {tax_year}")
            return
        
        filename = f"Expenses_By_Category_{tax_year}.csv"
        filepath = Path.home() / "Desktop" / filename
        
        if not filepath.parent.exists():
            filepath = Path(filename)
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Date', 'Category', 'Vendor', 'Description', 'Amount'])
            for row in rows:
                writer.writerow([row[0], row[1], row[2], row[3], f"${row[4]:.2f}"])
        
        messagebox.showinfo("Success", f"Exported to:\n{filepath}")
    
    def export_sessions_by_site(self):
        """Export performance by site (session-based)"""
        import csv
        from pathlib import Path
        
        try:
            tax_year = int(self.export_year_var.get())
        except:
            tax_year = date.today().year
        
        conn = self.db.get_connection()
        c = conn.cursor()
        
        c.execute('''
            SELECT 
                s.name as Site,
                COUNT(*) as "Game Sessions",
                SUM(CASE WHEN gs.total_taxable >= 0 THEN 1 ELSE 0 END) as Wins,
                ROUND(CAST(SUM(CASE WHEN gs.total_taxable >= 0 THEN 1 ELSE 0 END) AS REAL) / COUNT(*) * 100, 1) as "Win Rate %",
                SUM(gs.delta_total) as "Total Delta Total",
                SUM(gs.delta_redeem) as "Total Delta Redeemable",
                SUM(gs.total_taxable) as "Total Net Taxable",
                AVG(gs.total_taxable) as "Avg Per Session"
            FROM game_sessions gs
            JOIN sites s ON gs.site_id = s.id
            WHERE gs.status = 'Closed' AND strftime('%Y', gs.session_date) = ?
            GROUP BY s.name
            ORDER BY SUM(gs.total_taxable) DESC
        ''', (str(tax_year),))
        
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            messagebox.showinfo("No Data", f"No site data for {tax_year}")
            return
        
        filename = f"Performance_By_Site_{tax_year}.csv"
        filepath = Path.home() / "Desktop" / filename
        
        if not filepath.parent.exists():
            filepath = Path(filename)
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Site', 'Sessions', 'Wins', 'Win Rate %', 'Delta Total (SC)',
                           'Delta Redeemable (SC)', 'Net Taxable', 'Avg Per Session'])
            for row in rows:
                writer.writerow([
                    row[0], row[1], row[2], f"{row[3]:.1f}%",
                    f"{(row[4] or 0):+.2f}", f"{(row[5] or 0):+.2f}",
                    f"${(row[6] or 0):+.2f}", f"${(row[7] or 0):+.2f}"
                ])
        
        messagebox.showinfo("Success", f"Performance by site exported to:\n{filepath}")
    
    def export_purchases_detail(self):
        """Export purchase details with FIFO status"""
        import csv
        from pathlib import Path
        
        try:
            tax_year = int(self.export_year_var.get())
        except:
            tax_year = date.today().year
        
        conn = self.db.get_connection()
        c = conn.cursor()
        
        c.execute('''
            SELECT 
                p.purchase_date as Date,
                p.purchase_time as Time,
                u.name as User,
                s.name as Site,
                c.name as Card,
                p.amount as "Purchase Amount",
                p.sc_received as "SC Received",
                p.starting_sc_balance as "Starting Balance",
                p.remaining_amount as "Remaining Basis",
                (p.amount - p.remaining_amount) as "Consumed Basis",
                p.notes as Notes
            FROM purchases p
            JOIN sites s ON p.site_id = s.id
            JOIN users u ON p.user_id = u.id
            JOIN cards c ON p.card_id = c.id
            WHERE strftime('%Y', p.purchase_date) = ?
            ORDER BY p.purchase_date DESC, p.purchase_time DESC
        ''', (str(tax_year),))
        
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            messagebox.showinfo("No Data", f"No purchases for {tax_year}")
            return
        
        filename = f"Purchases_Detail_{tax_year}.csv"
        filepath = Path.home() / "Desktop" / filename
        
        if not filepath.parent.exists():
            filepath = Path(filename)
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Date', 'Time', 'User', 'Site', 'Card', 'Amount', 'SC Received',
                           'Starting Balance', 'Remaining Basis', 'Consumed Basis', 'Notes'])
            for row in rows:
                writer.writerow([
                    row[0], row[1], row[2], row[3], row[4],
                    f"${row[5]:.2f}", f"{row[6]:.2f}", f"{row[7]:.2f}",
                    f"${row[8]:.2f}", f"${row[9]:.2f}",
                    row[10] or ''
                ])
        
        messagebox.showinfo("Success", f"Purchases detail exported to:\n{filepath}")
    
    
    def export_game_sessions_summary(self):
        """Export all game sessions with full detail"""
        import csv
        from pathlib import Path
        
        try:
            tax_year = int(self.export_year_var.get())
        except:
            tax_year = date.today().year
        
        conn = self.db.get_connection()
        c = conn.cursor()
        
        c.execute('''
            SELECT 
                gs.session_date as "Date",
                gs.start_time as "Start Time",
                gs.end_time as "End Time",
                u.name as "User",
                s.name as "Site",
                gs.game_type as "Game Type",
                gs.starting_sc_balance as "Starting SC",
                gs.ending_sc_balance as "Ending SC",
                gs.delta_total as "Delta Total",
                gs.delta_redeem as "Delta Redeemable",
                gs.total_taxable as "Net Taxable",
                gs.notes as "Notes"
            FROM game_sessions gs
            JOIN sites s ON gs.site_id = s.id
            JOIN users u ON gs.user_id = u.id
            WHERE gs.status = 'Closed' AND strftime('%Y', gs.session_date) = ?
            ORDER BY gs.session_date ASC, gs.start_time ASC
        ''', (str(tax_year),))
        
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            messagebox.showinfo("No Data", f"No game sessions found for {tax_year}")
            return
        
        filename = f"Game_Sessions_{tax_year}.csv"
        filepath = Path.home() / "Desktop" / filename
        
        if not filepath.parent.exists():
            filepath = Path(filename)
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Date', 'Start Time', 'End Time', 'User', 'Site', 'Game Type',
                           'Starting SC', 'Ending SC', 'Delta Total (SC)', 'Delta Redeemable (SC)',
                           'Net Taxable', 'Notes'])
            for row in rows:
                writer.writerow([
                    row[0], row[1], row[2], row[3], row[4], row[5],
                    f"{row[6]:.2f}", f"{row[7]:.2f}", 
                    f"{(row[8] or 0):+.2f}", f"{(row[9] or 0):+.2f}", f"{(row[10] or 0):+.2f}",
                    row[11] or ''
                ])
        
        messagebox.showinfo("Success", 
            f"Game sessions exported to:\n{filepath}\n\n"
            f"{len(rows)} sessions exported")
    
    def export_daily_tax_sessions(self):
        """Export daily tax session rollups"""
        import csv
        from pathlib import Path
        
        try:
            tax_year = int(self.export_year_var.get())
        except:
            tax_year = date.today().year
        
        conn = self.db.get_connection()
        c = conn.cursor()
        
        c.execute('''
            SELECT 
                dts.session_date as "Date",
                u.name as "User",
                dts.total_session_pnl as "Total Session P/L",
                dts.total_other_income as "Other Income",
                dts.net_daily_pnl as "Net Daily P/L",
                dts.status as "Status",
                dts.num_game_sessions as "Game Sessions",
                dts.num_other_income_items as "Other Income Items"
            FROM daily_tax_sessions dts
            JOIN users u ON dts.user_id = u.id
            WHERE strftime('%Y', dts.session_date) = ?
            ORDER BY dts.session_date ASC, u.name
        ''', (str(tax_year),))
        
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            messagebox.showinfo("No Data", f"No daily tax sessions found for {tax_year}")
            return
        
        filename = f"Daily_Tax_Sessions_{tax_year}.csv"
        filepath = Path.home() / "Desktop" / filename
        
        if not filepath.parent.exists():
            filepath = Path(filename)
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Date', 'User', 'Total Session P/L', 'Other Income',
                           'Net Daily P/L', 'Status', 'Game Sessions', 'Other Income Items'])
            for row in rows:
                writer.writerow([
                    row[0], row[1],
                    f"{(row[2] or 0):+.2f}", f"{(row[3] or 0):+.2f}",
                    f"{(row[4] or 0):+.2f}", row[5],
                    row[6], row[7]
                ])
        
        messagebox.showinfo("Success", 
            f"Daily tax sessions exported to:\n{filepath}\n\n"
            f"{len(rows)} daily sessions exported")
    
    def export_redemptions_detail(self):
        """Export all redemptions"""
        import csv
        from pathlib import Path
        
        try:
            tax_year = int(self.export_year_var.get())
        except:
            tax_year = date.today().year
        
        conn = self.db.get_connection()
        c = conn.cursor()
        
        c.execute('''
            SELECT 
                r.redemption_date as "Date",
                r.redemption_time as "Time",
                u.name as "User",
                s.name as "Site",
                r.amount as "Amount",
                r.receipt_date as "Receipt Date",
                rm.name as "Method",
                CASE WHEN r.is_free_sc = 1 THEN 'Yes' ELSE 'No' END as "Free SC",
                r.notes as "Notes"
            FROM redemptions r
            JOIN sites s ON r.site_id = s.id
            JOIN users u ON r.user_id = u.id
            LEFT JOIN redemption_methods rm ON r.redemption_method_id = rm.id
            WHERE strftime('%Y', r.redemption_date) = ?
            ORDER BY r.redemption_date ASC, r.redemption_time ASC
        ''', (str(tax_year),))
        
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            messagebox.showinfo("No Data", f"No redemptions found for {tax_year}")
            return
        
        filename = f"Redemptions_{tax_year}.csv"
        filepath = Path.home() / "Desktop" / filename
        
        if not filepath.parent.exists():
            filepath = Path(filename)
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Date', 'Time', 'User', 'Site', 'Amount', 'Receipt Date',
                           'Method', 'Free SC', 'Notes'])
            for row in rows:
                writer.writerow([
                    row[0], row[1], row[2], row[3],
                    f"{row[4]:.2f}",
                    row[5] or '', row[6] or '', row[7], row[8] or ''
                ])
        
        messagebox.showinfo("Success", 
            f"Redemptions exported to:\n{filepath}\n\n"
            f"{len(rows)} redemptions exported")
    
    def export_all_tax_data(self):
        """Export complete database as ZIP with all tables (session-based)"""
        import zipfile
        from pathlib import Path
        import tempfile
        import csv
        
        try:
            tax_year = int(self.export_year_var.get())
        except:
            tax_year = date.today().year
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            conn = self.db.get_connection()
            
            # Helper function to write CSV
            def write_csv(filename, query, headers, params=()):
                c = conn.cursor()
                c.execute(query, params)
                rows = c.fetchall()
                if rows:
                    with open(tmppath / filename, 'w', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(headers)
                        for row in rows:
                            writer.writerow(row)
                    return len(rows)
                return 0
            
            # Export counts for summary
            counts = {}
            
            # === TAX YEAR SPECIFIC EXPORTS ===
            
            # Game Sessions
            counts['Game Sessions'] = write_csv(
                f"Game_Sessions_{tax_year}.csv",
                '''SELECT gs.session_date, gs.start_time, gs.end_time,
                   u.name, s.name, gs.game_type, gs.starting_sc_balance, gs.ending_sc_balance,
                   gs.delta_total, gs.delta_redeem, gs.total_taxable, gs.notes
                   FROM game_sessions gs
                   JOIN sites s ON gs.site_id = s.id
                   JOIN users u ON gs.user_id = u.id
                   WHERE gs.status = 'Closed' AND strftime('%Y', gs.session_date) = ?
                   ORDER BY gs.session_date, gs.start_time''',
                ['Date', 'Start Time', 'End Time', 'User', 'Site', 'Game Type',
                 'Starting SC', 'Ending SC', 'Delta Total (SC)', 'Delta Redeemable (SC)', 'Net Taxable', 'Notes'],
                (str(tax_year),)
            )
            
            # Daily Tax Sessions
            counts['Daily Tax Sessions'] = write_csv(
                f"Daily_Tax_Sessions_{tax_year}.csv",
                '''SELECT dts.session_date, u.name,
                   dts.total_session_pnl, dts.total_other_income, dts.net_daily_pnl,
                   dts.status, dts.num_game_sessions, dts.num_other_income_items
                   FROM daily_tax_sessions dts
                   JOIN users u ON dts.user_id = u.id
                   WHERE strftime('%Y', dts.session_date) = ?
                   ORDER BY dts.session_date, u.name''',
                ['Date', 'User', 'Total Session P/L', 'Other Income', 'Net Daily P/L',
                 'Status', 'Game Sessions', 'Other Income Items'],
                (str(tax_year),)
            )
            
            # Purchases
            counts['Purchases'] = write_csv(
                f"Purchases_{tax_year}.csv",
                '''SELECT p.purchase_date, p.purchase_time, u.name, s.name, c.name,
                   p.amount, p.sc_received, p.starting_sc_balance, p.remaining_amount, p.notes
                   FROM purchases p
                   JOIN sites s ON p.site_id = s.id
                   JOIN users u ON p.user_id = u.id
                   JOIN cards c ON p.card_id = c.id
                   WHERE strftime('%Y', p.purchase_date) = ?
                   ORDER BY p.purchase_date, p.purchase_time''',
                ['Date', 'Time', 'User', 'Site', 'Card', 'Amount', 'SC Received',
                 'Starting SC', 'Remaining Basis', 'Notes'],
                (str(tax_year),)
            )
            
            # Redemptions
            counts['Redemptions'] = write_csv(
                f"Redemptions_{tax_year}.csv",
                '''SELECT r.redemption_date, r.redemption_time, u.name, s.name,
                   r.amount, r.receipt_date, rm.name, 
                   CASE WHEN r.is_free_sc = 1 THEN 'Yes' ELSE 'No' END, r.notes
                   FROM redemptions r
                   JOIN sites s ON r.site_id = s.id
                   JOIN users u ON r.user_id = u.id
                   LEFT JOIN redemption_methods rm ON r.redemption_method_id = rm.id
                   WHERE strftime('%Y', r.redemption_date) = ?
                   ORDER BY r.redemption_date, r.redemption_time''',
                ['Date', 'Time', 'User', 'Site', 'Amount', 'Receipt Date', 'Method', 'Free SC', 'Notes'],
                (str(tax_year),)
            )
            
            # Expenses
            counts['Expenses'] = write_csv(
                f"Expenses_{tax_year}.csv",
                '''SELECT e.expense_date, e.vendor, e.category, e.description, e.amount,
                   u.name
                   FROM expenses e
                   LEFT JOIN users u ON e.user_id = u.id
                   WHERE strftime('%Y', e.expense_date) = ?
                   ORDER BY e.category, e.expense_date''',
                ['Date', 'Vendor', 'Category', 'Description', 'Amount', 'User'],
                (str(tax_year),)
            )
            
            # Income Summary
            counts['Income Summary'] = write_csv(
                f"Income_Summary_{tax_year}.csv",
                '''SELECT strftime('%Y-%m', session_date) as Month,
                   COUNT(*) as Sessions,
                   SUM(delta_total) as "Total Delta Total",
                   SUM(delta_redeem) as "Total Delta Redeemable",
                   SUM(total_taxable) as "Total Net Taxable"
                   FROM game_sessions
                   WHERE status = 'Closed' AND strftime('%Y', session_date) = ?
                   GROUP BY strftime('%Y-%m', session_date)
                   ORDER BY Month''',
                ['Month', 'Sessions', 'Delta Total (SC)', 'Delta Redeemable (SC)', 'Net Taxable'],
                (str(tax_year),)
            )
            
            # Performance by Site
            counts['Site Performance'] = write_csv(
                f"Performance_By_Site_{tax_year}.csv",
                '''SELECT s.name,
                   COUNT(*) as sessions,
                   SUM(CASE WHEN gs.total_taxable >= 0 THEN 1 ELSE 0 END) as wins,
                   SUM(gs.total_taxable) as total_pl,
                   AVG(gs.total_taxable) as avg_pl
                   FROM game_sessions gs
                   JOIN sites s ON gs.site_id = s.id
                   WHERE gs.status = 'Closed' AND strftime('%Y', gs.session_date) = ?
                   GROUP BY s.name
                   ORDER BY total_pl DESC''',
                ['Site', 'Sessions', 'Wins', 'Total P/L', 'Avg P/L'],
                (str(tax_year),)
            )
            
            # === REFERENCE DATA (not year-specific) ===
            
            # Users
            write_csv(
                "Users.csv",
                "SELECT name, active FROM users ORDER BY name",
                ['Name', 'Active']
            )
            
            # Sites
            write_csv(
                "Sites.csv",
                "SELECT name, sc_rate, active FROM sites ORDER BY name",
                ['Name', 'SC Rate', 'Active']
            )
            
            # Cards
            write_csv(
                "Cards.csv",
                '''SELECT c.name, u.name, c.last_four, c.cashback_rate, c.active
                   FROM cards c
                   JOIN users u ON c.user_id = u.id
                   ORDER BY u.name, c.name''',
                ['Card Name', 'User', 'Last Four', 'Cashback %', 'Active']
            )
            
            # Redemption Methods
            write_csv(
                "Redemption_Methods.csv",
                '''SELECT name, active FROM redemption_methods ORDER BY name''',
                ['Method', 'Active']
            )
            
            conn.close()
            
            # Create ZIP
            zip_filename = f"Complete_Tax_Package_{tax_year}.zip"
            zip_filepath = Path.home() / "Desktop" / zip_filename
            
            if not zip_filepath.parent.exists():
                zip_filepath = Path(zip_filename)
            
            with zipfile.ZipFile(zip_filepath, 'w') as zipf:
                for file in tmppath.glob("*.csv"):
                    zipf.write(file, file.name)
            
            # Build summary message
            summary = f"Complete tax package exported to:\n{zip_filepath}\n\n"
            summary += f"📁 Tax Year {tax_year} Data:\n"
            for name, count in counts.items():
                if count > 0:
                    summary += f"  • {name}: {count} records\n"
            summary += f"\n📋 Reference Data: Users, Sites, Cards, Methods"
            
            messagebox.showinfo("Export Complete", summary)
    
    
    # ========================================================================
    # DATABASE MAINTENANCE TOOLS
    # ========================================================================
    
    def backup_database(self):
        """Create a backup of the database"""
        from tkinter import filedialog
        import shutil
        from datetime import datetime
        
        # Suggest filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"session_backup_{timestamp}.db"
        
        filepath = filedialog.asksaveasfilename(
            title="Save Database Backup",
            defaultextension=".db",
            initialfile=default_filename,
            filetypes=[("Database files", "*.db"), ("All files", "*.*")]
        )
        
        if not filepath:
            return
        
        try:
            # Close any open connections first
            if hasattr(self.db, 'conn') and self.db.conn:
                self.db.conn.close()
            
            # Copy database file
            shutil.copy2('casino_accounting.db', filepath)
            
            messagebox.showinfo("Success", f"Database backed up to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Backup Error", f"Failed to backup database:\n{str(e)}")
    
    def reconcile_imported_data(self):
        """
        Reconcile all imported purchases, redemptions, and sessions.
        
        This comprehensive function:
        1. Validates data integrity
        2. Processes purchases (creates FIFO basis)
        3. Processes redemptions (consumes FIFO basis)
        4. Recomputes all session metrics (canonical engine)
        5. Updates daily tax sessions
        6. Marks everything as processed
        
        Use after importing CSV files to finalize all data.
        """
        from tkinter import messagebox
        import tkinter as tk
        
        try:
            conn = self.db.get_connection()
            c = conn.cursor()
            
            # === STEP 1: COUNT UNPROCESSED RECORDS ===
            c.execute("SELECT COUNT(*) FROM purchases WHERE processed = 0")
            unprocessed_purchases = c.fetchone()[0]
            
            c.execute("SELECT COUNT(*) FROM redemptions WHERE processed = 0")
            unprocessed_redemptions = c.fetchone()[0]
            
            c.execute("SELECT COUNT(*) FROM game_sessions WHERE processed = 0 AND status = 'Closed'")
            unprocessed_sessions = c.fetchone()[0]
            
            total = unprocessed_purchases + unprocessed_redemptions + unprocessed_sessions
            
            if total == 0:
                conn.close()
                messagebox.showinfo("Nothing to Reconcile", 
                    "No unprocessed data found.\n\n"
                    "All purchases, redemptions, and sessions have been reconciled.\n\n"
                    "Import CSV files first, then run reconciliation.")
                return
            
            # === STEP 2: CONFIRM WITH USER ===
            response = messagebox.askyesno(
                "Reconcile Imported Data",
                f"Found unprocessed data:\n"
                f"• {unprocessed_purchases} purchases\n"
                f"• {unprocessed_redemptions} redemptions\n"
                f"• {unprocessed_sessions} game sessions\n\n"
                f"Total: {total} records to process\n\n"
                "This will:\n"
                "✓ Calculate FIFO cost basis for purchases\n"
                "✓ Process redemptions in chronological order\n"
                "✓ Recompute all session tax metrics\n"
                "✓ Update daily tax sessions\n\n"
                "Continue?"
            )
            
            if not response:
                conn.close()
                return
            
            # === STEP 3: CREATE PROGRESS WINDOW ===
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Reconciling Data")
            progress_window.geometry("600x200")
            progress_window.transient(self.root)
            progress_window.grab_set()
            
            progress_frame = ttk.Frame(progress_window, padding="20")
            progress_frame.pack(fill='both', expand=True)
            
            status_label = ttk.Label(progress_frame, text="Reconciling imported data...", 
                                    font=('Arial', 11, 'bold'))
            status_label.pack(pady=10)
            
            detail_label = ttk.Label(progress_frame, text="", font=('Arial', 9))
            detail_label.pack(pady=5)
            
            progress_bar = ttk.Progressbar(progress_frame, mode='determinate', length=500)
            progress_bar.pack(pady=10)
            progress_bar['maximum'] = 5  # 5 main steps
            
            progress_window.update()
            
            # === STEP 4: VALIDATE DATA INTEGRITY ===
            detail_label.config(text="Step 1/5: Validating data integrity...")
            progress_window.update()
            
            issues = []
            
            # Check for orphaned purchases (no user/site)
            c.execute('''
                SELECT COUNT(*) FROM purchases 
                WHERE processed = 0 AND (user_id NOT IN (SELECT id FROM users) 
                                        OR site_id NOT IN (SELECT id FROM sites))
            ''')
            if c.fetchone()[0] > 0:
                issues.append("⚠️ Some purchases reference non-existent users or sites")
            
            # Check for orphaned redemptions
            c.execute('''
                SELECT COUNT(*) FROM redemptions 
                WHERE processed = 0 AND (user_id NOT IN (SELECT id FROM users) 
                                        OR site_id NOT IN (SELECT id FROM sites))
            ''')
            if c.fetchone()[0] > 0:
                issues.append("⚠️ Some redemptions reference non-existent users or sites")
            
            # Check for orphaned sessions
            c.execute('''
                SELECT COUNT(*) FROM game_sessions 
                WHERE processed = 0 AND status = 'Closed' 
                AND (user_id NOT IN (SELECT id FROM users) 
                     OR site_id NOT IN (SELECT id FROM sites))
            ''')
            if c.fetchone()[0] > 0:
                issues.append("⚠️ Some sessions reference non-existent users or sites")
            
            if issues:
                progress_window.destroy()
                conn.close()
                messagebox.showerror("Data Integrity Issues", 
                    "Cannot reconcile due to data integrity issues:\n\n" + "\n".join(issues) +
                    "\n\nPlease fix these issues before reconciling.")
                return
            
            progress_bar['value'] = 1
            progress_window.update()
            
            # === STEP 5: PROCESS PURCHASES (mark as processed) ===
            detail_label.config(text="Step 2/5: Processing purchases...")
            progress_window.update()
            
            c.execute("UPDATE purchases SET processed = 1 WHERE processed = 0")
            purchases_processed = c.rowcount
            
            progress_bar['value'] = 2
            progress_window.update()
            
            # === STEP 6: PROCESS REDEMPTIONS (mark as processed, FIFO already handled) ===
            detail_label.config(text="Step 3/5: Processing redemptions...")
            progress_window.update()
            
            c.execute("UPDATE redemptions SET processed = 1 WHERE processed = 0")
            redemptions_processed = c.rowcount
            
            progress_bar['value'] = 3
            progress_window.update()
            
            # === STEP 7: RECOMPUTE SESSION METRICS ===
            detail_label.config(text="Step 4/5: Recomputing session metrics...")
            progress_window.update()

            conn.commit()
            conn.close()

            summary = self.session_mgr.rebuild_all_derived(rebuild_fifo=True, rebuild_sessions=True)
            sessions_processed = summary.get("sessions_processed", 0) if isinstance(summary, dict) else 0
            progress_bar['value'] = 4
            progress_window.update()
            
            # === STEP 8: MARK PROCESSED FLAGS ===
            detail_label.config(text="Step 5/5: Marking sessions as processed...")
            progress_window.update()
            conn = self.db.get_connection()
            c = conn.cursor()
            c.execute("UPDATE game_sessions SET processed = 1 WHERE status = 'Closed' AND processed = 0")
            sessions_marked = c.rowcount
            conn.commit()
            conn.close()
            
            progress_bar['value'] = 5
            progress_window.update()
            
            # === STEP 9: SHOW RESULTS ===
            progress_window.destroy()
            
            result_msg = "✅ Reconciliation Complete!\n\n"
            result_msg += f"Processed:\n"
            result_msg += f"• {purchases_processed} purchases\n"
            result_msg += f"• {redemptions_processed} redemptions\n"
            result_msg += f"• {sessions_processed} game sessions recalculated\n"
            result_msg += f"• {sessions_marked} sessions marked processed\n\n"
            result_msg += "All data has been reconciled and is ready for tax reporting."
            
            messagebox.showinfo("Reconciliation Complete", result_msg)
            
            # Refresh all views
            self.refresh_all_views()
            self.refresh_global_stats()
            
        except Exception as e:
            if 'progress_window' in locals():
                progress_window.destroy()
            if 'conn' in locals():
                conn.close()
            
            messagebox.showerror("Reconciliation Error", 
                f"An error occurred during reconciliation:\n\n{str(e)}\n\n"
                "Database changes have been rolled back.")
            import traceback
            traceback.print_exc()
        """
        Process all unprocessed purchases and redemptions in chronological order.
        Uses the SAME business logic as manual entry.
        
        This is called by:
        1. Import CSV â†’ Process button
        2. Refactor Database
        """
        from tkinter import messagebox
        import tkinter as tk
        
        try:
            conn = self.db.get_connection()
            c = conn.cursor()
            
            # Get counts
            c.execute("SELECT COUNT(*) FROM purchases WHERE processed = 0")
            unprocessed_purchases = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM redemptions WHERE processed = 0")
            unprocessed_redemptions = c.fetchone()[0]
            
            total = unprocessed_purchases + unprocessed_redemptions
            
            if total == 0:
                conn.close()
                messagebox.showinfo("Nothing to Process", 
                    "No unprocessed purchases or redemptions found.\n\n"
                    "All transactions have already been processed.")
                return
            
            # Confirm with user
            response = messagebox.askyesno(
                "Process Imported Transactions",
                f"Found {unprocessed_purchases} unprocessed purchases and "
                f"{unprocessed_redemptions} unprocessed redemptions.\n\n"
                f"Total: {total} transactions to process.\n\n"
                "This will calculate cost basis and create tax sessions.\n\n"
                "Continue?"
            )
            
            if not response:
                conn.close()
                return
            
            # Create progress window
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Processing Transactions")
            progress_window.geometry("500x150")
            progress_window.transient(self.root)
            progress_window.grab_set()
            
            # Progress bar
            progress_frame = ttk.Frame(progress_window, padding="20")
            progress_frame.pack(fill='both', expand=True)
            
            status_label = ttk.Label(progress_frame, text="Processing transactions...", 
                                    font=('Arial', 10, 'bold'))
            status_label.pack(pady=10)
            
            detail_label = ttk.Label(progress_frame, text="")
            detail_label.pack(pady=5)
            
            progress_bar = ttk.Progressbar(progress_frame, mode='determinate', length=400)
            progress_bar.pack(pady=10)
            progress_bar['maximum'] = total
            
            progress_window.update()
            
            # Get all unprocessed transactions
            c.execute('''
                SELECT 'purchase' as txn_type, id, purchase_date as date, purchase_time as time,
                       site_id, user_id, amount, sc_received, starting_sc_balance, card_id, notes
                FROM purchases 
                WHERE processed = 0
            ''')
            purchases = [dict(row) for row in c.fetchall()]
            
            c.execute('''
                SELECT 'redemption' as txn_type, id, redemption_date as date, redemption_time as time,
                       site_id, user_id, amount, is_free_sc, more_remaining,
                       receipt_date, redemption_method_id, notes
                FROM redemptions
                WHERE processed = 0
            ''')
            redemptions = [dict(row) for row in c.fetchall()]
            
            # Merge and sort by timestamp
            # Tie-breaker: purchases before redemptions at same time (to establish cost basis first)
            all_txns = purchases + redemptions
            def sort_key(x):
                date = x['date']
                time = x['time'] if x['time'] else '00:00:00'
                # Type tie-breaker: purchases (0) before redemptions (1) at same timestamp
                type_order = 0 if x['txn_type'] == 'purchase' else 1
                txn_id = x['id']
                return (date, time, type_order, txn_id)
            
            all_txns.sort(key=sort_key)
            
            conn.close()
            
            # Process each transaction
            processed_count = 0
            for idx, txn in enumerate(all_txns):
                detail_label.config(text=f"Processing {txn['txn_type']} {idx+1}/{total}...")
                progress_bar['value'] = idx + 1
                progress_window.update()
                
                try:
                    if txn['txn_type'] == 'purchase':
                        # Process purchase - add to session
                        session_id = self.session_mgr.get_or_create_site_session(
                            txn['site_id'], txn['user_id'], txn['date']
                        )
                        self.session_mgr.add_purchase_to_session(session_id, txn['amount'])
                        
                        # Mark as processed
                        conn = self.db.get_connection()
                        c = conn.cursor()
                        c.execute("UPDATE purchases SET processed = 1 WHERE id = ?", (txn['id'],))
                        conn.commit()
                        conn.close()
                        
                    else:  # redemption
                        # Process redemption using existing business logic
                        more_remaining = bool(txn.get('more_remaining', 0))
                        is_free_sc = bool(txn.get('is_free_sc', 0))
                        
                        self.session_mgr.process_redemption(
                            txn['id'],
                            txn['site_id'],
                            txn['amount'],
                            txn['date'],
                            txn['time'] or '00:00:00',
                            txn['user_id'],
                            is_free_sc,
                            more_remaining
                        )
                    
                    processed_count += 1
                    
                except Exception as e:
                    print(f"Error processing {txn['txn_type']} {txn['id']}: {e}")
                    import traceback
                    traceback.print_exc()
                    # Continue processing other transactions
            
            progress_window.destroy()
            
            # Refresh views
            self.refresh_all_views()
            
            messagebox.showinfo("Success", 
                f"✓… Processing complete!\n\n"
                f"Processed: {processed_count}/{total} transactions\n"
                f"• Purchases: {unprocessed_purchases}\n"
                f"• Redemptions: {unprocessed_redemptions}")
            
        except Exception as e:
            if 'progress_window' in locals():
                progress_window.destroy()
            import traceback
            traceback.print_exc()
    
    
    def process_imported_transactions(self):
        """
        Process all unprocessed purchases and redemptions in chronological order.
        Uses the SAME business logic as manual entry.
        
        This is called by:
        1. Import CSV → Process button
        2. Refactor Database
        """
        from tkinter import messagebox
        import tkinter as tk
        
        try:
            conn = self.db.get_connection()
            c = conn.cursor()
            
            # Get counts
            c.execute("SELECT COUNT(*) FROM purchases WHERE processed = 0")
            unprocessed_purchases = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM redemptions WHERE processed = 0")
            unprocessed_redemptions = c.fetchone()[0]
            
            total = unprocessed_purchases + unprocessed_redemptions
            
            if total == 0:
                conn.close()
                messagebox.showinfo("Nothing to Process", 
                    "No unprocessed purchases or redemptions found.\n\n"
                    "All transactions have already been processed.")
                return
            
            # Confirm with user
            response = messagebox.askyesno(
                "Process Imported Transactions",
                f"Found {unprocessed_purchases} unprocessed purchases and "
                f"{unprocessed_redemptions} unprocessed redemptions.\n\n"
                f"Total: {total} transactions to process.\n\n"
                "This will calculate cost basis and create tax sessions.\n\n"
                "Continue?"
            )
            
            if not response:
                conn.close()
                return
            
            # Create progress window
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Processing Transactions")
            progress_window.geometry("500x150")
            progress_window.transient(self.root)
            progress_window.grab_set()
            
            # Progress bar
            progress_frame = ttk.Frame(progress_window, padding="20")
            progress_frame.pack(fill='both', expand=True)
            
            status_label = ttk.Label(progress_frame, text="Processing transactions...", 
                                    font=('Arial', 10, 'bold'))
            status_label.pack(pady=10)
            
            detail_label = ttk.Label(progress_frame, text="")
            detail_label.pack(pady=5)
            
            progress_bar = ttk.Progressbar(progress_frame, mode='determinate', length=400)
            progress_bar.pack(pady=10)
            progress_bar['maximum'] = total
            
            progress_window.update()
            
            # Get all unprocessed transactions
            c.execute('''
                SELECT 'purchase' as txn_type, id, purchase_date as date, purchase_time as time,
                       site_id, user_id, amount, sc_received, starting_sc_balance, card_id, notes
                FROM purchases 
                WHERE processed = 0
            ''')
            purchases = [dict(row) for row in c.fetchall()]
            
            c.execute('''
                SELECT 'redemption' as txn_type, id, redemption_date as date, redemption_time as time,
                       site_id, user_id, amount, is_free_sc, more_remaining,
                       receipt_date, redemption_method_id, notes
                FROM redemptions
                WHERE processed = 0
            ''')
            redemptions = [dict(row) for row in c.fetchall()]
            
            # Merge and sort by timestamp
            # Tie-breaker: purchases before redemptions at same time (to establish cost basis first)
            all_txns = purchases + redemptions
            def sort_key(x):
                date = x['date']
                time = x['time'] if x['time'] else '00:00:00'
                # Type tie-breaker: purchases (0) before redemptions (1) at same timestamp
                type_order = 0 if x['txn_type'] == 'purchase' else 1
                txn_id = x['id']
                return (date, time, type_order, txn_id)
            
            all_txns.sort(key=sort_key)
            
            conn.close()
            
            # Process each transaction
            processed_count = 0
            for idx, txn in enumerate(all_txns):
                detail_label.config(text=f"Processing {txn['txn_type']} {idx+1}/{total}...")
                progress_bar['value'] = idx + 1
                progress_window.update()
                
                try:
                    if txn['txn_type'] == 'purchase':
                        # Process purchase - add to session
                        session_id = self.session_mgr.get_or_create_site_session(
                            txn['site_id'], txn['user_id'], txn['date']
                        )
                        self.session_mgr.add_purchase_to_session(session_id, txn['amount'])
                        
                        # Mark as processed
                        conn = self.db.get_connection()
                        c = conn.cursor()
                        c.execute("UPDATE purchases SET processed = 1 WHERE id = ?", (txn['id'],))
                        conn.commit()
                        conn.close()
                        
                    else:  # redemption
                        # Process redemption using existing business logic
                        more_remaining = bool(txn.get('more_remaining', 0))
                        is_free_sc = bool(txn.get('is_free_sc', 0))
                        
                        self.session_mgr.process_redemption(
                            txn['id'],
                            txn['site_id'],
                            txn['amount'],
                            txn['date'],
                            txn['time'] or '00:00:00',
                            txn['user_id'],
                            is_free_sc,
                            more_remaining
                        )
                    
                    processed_count += 1
                    
                except Exception as e:
                    print(f"Error processing {txn['txn_type']} {txn['id']}: {e}")
                    import traceback
                    traceback.print_exc()
                    # Continue processing other transactions
            
            progress_window.destroy()
            
            # Refresh views
            self.refresh_all_views()
            
            messagebox.showinfo("Success", 
                f"✅ Processing complete!\n\n"
                f"Processed: {processed_count}/{total} transactions\n"
                f"• Purchases: {unprocessed_purchases}\n"
                f"• Redemptions: {unprocessed_redemptions}")
            
        except Exception as e:
            if 'progress_window' in locals():
                progress_window.destroy()
            
            import traceback
            traceback.print_exc()
            messagebox.showerror("Processing Error", 
                f"Failed to process transactions:\n\n{str(e)}")
    
    def refactor_database(self):
        """
        Recalculate all sessions, cost basis, and FIFO from scratch.
        
        This is essentially: Reset everything + Process Imported Transactions
        Uses the SAME business logic as manual entry and CSV imports.
        """
        from tkinter import messagebox
        
        # Confirm with user
        response = messagebox.askyesnocancel(
            "Refactor Database",
            "⚠️¸ WARNING: This will recalculate all tax sessions and cost basis.\n\n"
            "This process:\n"
            "• Deletes all tax_sessions\n"
            "• Resets all site_sessions\n"
            "• Resets all purchase remaining_amounts\n"
            "• Marks all transactions as unprocessed\n"
            "• Reprocesses everything in chronological order\n\n"
            "This uses the SAME logic as manual entry.\n"
            "All data will be preserved.\n\n"
            "💾 RECOMMENDED: Backup your database first!\n\n"
            "Continue with refactor?"
        )
        
        if response is None:  # Cancel
            return
        elif response is False:  # No
            return
        
        try:
            import tkinter as tk
            
            # Create progress window
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Refactoring Database")
            progress_window.geometry("600x200")
            progress_window.transient(self.root)
            progress_window.grab_set()
            
            # Progress bar
            progress_frame = ttk.Frame(progress_window, padding="20")
            progress_frame.pack(fill='both', expand=True)
            
            title_label = ttk.Label(progress_frame, text="Refactoring Database", 
                                   font=('Arial', 12, 'bold'))
            title_label.pack(pady=10)
            
            detail_label = ttk.Label(progress_frame, text="", font=('Arial', 10))
            detail_label.pack(pady=5)
            
            progress_bar = ttk.Progressbar(progress_frame, mode='indeterminate', length=500)
            progress_bar.pack(pady=15)
            progress_bar.start(10)
            
            progress_window.update()
            
            # Log refactor start
            self.log_audit('REFACTOR', 'database', None, 'Refactor started', None)
            
            conn = self.db.get_connection()
            c = conn.cursor()
            
            # Step 1: Delete all tax_sessions
            detail_label.config(text="Step 1/5: Clearing tax sessions...")
            progress_window.update()
            c.execute("DELETE FROM tax_sessions")
            conn.commit()
            
            # Step 2: Delete all site_sessions  
            detail_label.config(text="Step 2/5: Clearing site sessions...")
            progress_window.update()
            c.execute("DELETE FROM site_sessions")
            conn.commit()
            
            # Step 3: Reset all purchase remaining_amounts
            detail_label.config(text="Step 3/5: Resetting purchase amounts...")
            progress_window.update()
            c.execute("UPDATE purchases SET remaining_amount = amount, processed = 0")
            conn.commit()
            
            # Step 4: Reset redemption links and flags
            detail_label.config(text="Step 4/5: Resetting redemption links...")
            progress_window.update()
            c.execute("UPDATE redemptions SET site_session_id = NULL, processed = 0")
            conn.commit()
            
            conn.close()
            
            # Step 5: Reprocess everything
            detail_label.config(text="Step 5/5: Reprocessing all transactions...")
            progress_window.update()
            
            progress_bar.stop()
            progress_window.destroy()
            
            # Use the same processing function as CSV import
            self.process_imported_transactions()
            
            # Log refactor completion
            self.log_audit('REFACTOR', 'database', None, 'Refactor completed', None)
            
        except Exception as e:
            if 'progress_window' in locals():
                try:
                    progress_window.destroy()
                except:
                    pass
            
            import traceback
            traceback.print_exc()
            messagebox.showerror("Refactor Error", 
                f"Failed to refactor database:\n\n{str(e)}")
    
    def reset_database(self):
        """Delete all transaction data (keep users/sites/cards/methods)"""
        from tkinter import messagebox
        
        # Confirm with user
        response = messagebox.askyesnocancel(
            "Reset Database",
            "⚠️¸ DANGER: This will permanently delete ALL:\n\n"
            "• Purchases and redemptions\n"
            "• Sessions (open and closed)\n"
            "• Tax records\n"
            "• Expenses\n\n"
            "Users, sites, cards, and redemption methods will be preserved.\n\n"
            "This CANNOT be undone!\n\n"
            "Would you like to create a backup first?\n\n"
            "YES = Backup then reset\n"
            "NO = Reset without backup\n"
            "CANCEL = Abort"
        )
        
        if response is None:  # Cancel
            return
        
        if response is True:  # Yes - backup first
            self.backup_database()
        
        # Double confirmation with typed confirmation
        confirm_dialog = tk.Toplevel(self.root)
        confirm_dialog.title("Final Confirmation")
        confirm_dialog.geometry("400x200")
        confirm_dialog.transient(self.root)
        confirm_dialog.grab_set()
        
        frame = ttk.Frame(confirm_dialog, padding=20)
        frame.pack(fill='both', expand=True)
        
        ttk.Label(frame, text="⚠️¸ FINAL WARNING", 
                 font=('Arial', 12, 'bold'), foreground='red').pack(pady=(0, 10))
        
        ttk.Label(frame, text='Type "DELETE" to confirm:', 
                 font=('Arial', 10)).pack(pady=(0, 5))
        
        confirm_entry = ttk.Entry(frame, width=20)
        confirm_entry.pack(pady=(0, 15))
        confirm_entry.focus()
        
        result = {'confirmed': False}
        
        def check_and_proceed():
            if confirm_entry.get().strip() == "DELETE":
                result['confirmed'] = True
                confirm_dialog.destroy()
            else:
                messagebox.showerror("Invalid", 'You must type "DELETE" exactly')
        
        def cancel():
            confirm_dialog.destroy()
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack()
        
        ttk.Button(btn_frame, text="Confirm Reset", command=check_and_proceed).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=cancel).pack(side='left', padx=5)
        
        confirm_entry.bind('<Return>', lambda e: check_and_proceed())
        
        self.root.wait_window(confirm_dialog)
        
        if not result['confirmed']:
            return
        
        try:
            conn = self.db.get_connection()
            c = conn.cursor()
            
            # Delete all transaction data (including new tables)
            c.execute("DELETE FROM daily_tax_sessions")
            c.execute("DELETE FROM other_income")
            c.execute("DELETE FROM game_sessions")
            c.execute("DELETE FROM tax_sessions")
            c.execute("DELETE FROM redemptions")
            c.execute("DELETE FROM purchases")
            c.execute("DELETE FROM site_sessions")
            c.execute("DELETE FROM expenses")
            
            conn.commit()
            conn.close()
            
            # Refresh all views
            self.refresh_all_views()
            
            messagebox.showinfo(
                "Reset Complete",
                "✓… Database reset successfully!\n\n"
                "All transaction data has been deleted.\n"
                "Users, sites, cards, and redemption methods preserved."
            )
            
        except Exception as e:
            messagebox.showerror("Reset Error", f"Failed to reset database:\n{str(e)}")
    
    def recalculate_everything(self):
        """Recalculate ALL derived accounting (FIFO + sessions + daily totals) using a single engine."""
        from tkinter import messagebox

        response = messagebox.askyesno(
            "Recalculate Everything",
            "This will rebuild ALL calculations from scratch:\n\n"
            "1. FIFO cost basis for all redemptions\n"
            "2. Session taxable P/L (redeemable-based)\n"
            "3. Daily totals\n\n"
            "This may take a moment for large databases.\n\n"
            "Continue?"
        )

        if not response:
            return

        try:
            summary = self.session_mgr.rebuild_all_derived(rebuild_fifo=True, rebuild_sessions=True)

            # Refresh all views
            self.refresh_all_views()

            pairs = summary.get("pairs_processed", 0) if isinstance(summary, dict) else 0
            messagebox.showinfo(
                "Success",
                f"✅ Recalculation complete!\n\nRebuilt calculations for {pairs} site/user pair(s)."
            )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to recalculate:\n\n{str(e)}")
            import traceback
            traceback.print_exc()

    def recalculate_redemptions_silent(self):
        """Recalculate FIFO for redemptions without showing success dialog (for use in batch operations)"""
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Reset all purchase remaining_amounts
        c.execute("UPDATE purchases SET remaining_amount = amount")
        
        # Delete all tax_sessions linked to redemptions
        c.execute("DELETE FROM tax_sessions WHERE redemption_id IS NOT NULL")
        
        conn.commit()
        conn.close()
        
        # Get all redemptions in chronological order
        conn = self.db.get_connection()
        c = conn.cursor()
        
        c.execute('''
            SELECT id, site_id, user_id, redemption_date, redemption_time,
                   amount, is_free_sc, more_remaining
            FROM redemptions
            ORDER BY redemption_date ASC, redemption_time ASC, id ASC
        ''')
        
        redemptions = c.fetchall()
        conn.close()
        
        # Reprocess each redemption using FIFO
        for redemption in redemptions:
            try:
                # Skip "Balance Closed" redemptions - they're handled separately below
                if redemption['amount'] == 0:
                    continue
                    
                self.session_mgr.process_redemption(
                    redemption['id'],
                    redemption['site_id'],
                    redemption['amount'],
                    redemption['redemption_date'],
                    redemption['redemption_time'] or '00:00:00',
                    redemption['user_id'],
                    bool(redemption['is_free_sc']),
                    more_remaining=bool(redemption['more_remaining']),  # Use actual value from DB
                    is_edit=True
                )
            except Exception as e:
                print(f"Error processing redemption {redemption['id']}: {e}")
        
        # Handle "Balance Closed" redemptions separately
        # These have amount=0 but need tax_sessions showing the loss
        conn = self.db.get_connection()
        c = conn.cursor()
        
        c.execute('''
            SELECT id, site_id, user_id, redemption_date, notes
            FROM redemptions
            WHERE amount = 0 AND notes LIKE '%Balance Closed%'
        ''')
        
        balance_closed_redemptions = c.fetchall()
        
        for bc_redemption in balance_closed_redemptions:
            # Extract the net loss from notes (format: "Balance Closed - Net Loss: $X.XX ...")
            notes = bc_redemption['notes'] or ''
            if 'Net Loss: $' in notes:
                try:
                    # Parse the net loss amount from notes
                    loss_str = notes.split('Net Loss: $')[1].split(' ')[0]
                    net_loss = float(loss_str)
                    
                    # Create tax_session for this balance closed redemption
                    c.execute('''
                        INSERT INTO tax_sessions
                        (session_date, site_id, redemption_id, cost_basis, payout, net_pl, user_id)
                        VALUES (?, ?, ?, ?, 0, ?, ?)
                    ''', (bc_redemption['redemption_date'], bc_redemption['site_id'], 
                          bc_redemption['id'], net_loss, -net_loss, bc_redemption['user_id']))
                except Exception as e:
                    print(f"Error recreating tax_session for balance closed redemption {bc_redemption['id']}: {e}")
        
        conn.commit()
        conn.close()
    
    def recalculate_game_sessions_silent(self):
        """Recalculate game sessions without showing success dialog (for use in batch operations)"""
        self.session_mgr.rebuild_all_derived(rebuild_fifo=False, rebuild_sessions=True)
    
    def recalculate_redemptions(self):
        """Recalculate FIFO cost basis for all redemptions"""
        from tkinter import messagebox
        
        response = messagebox.askyesno(
            "Recalculate Redemptions",
            "This will recalculate FIFO cost basis for ALL redemptions.\n\n"
            "This process:\n"
            "• Resets all purchase remaining_amounts\n"
            "• Deletes all tax_sessions for redemptions\n"
            "• Reprocesses all redemptions in chronological order\n\n"
            "Game sessions and daily tax sessions are NOT affected.\n\n"
            "Continue?"
        )
        
        if not response:
            return
        
        try:
            conn = self.db.get_connection()
            c = conn.cursor()
            
            # Get count of redemptions
            c.execute('SELECT COUNT(*) as count FROM redemptions')
            redemption_count = c.fetchone()['count']
            
            if redemption_count == 0:
                conn.close()
                messagebox.showinfo("No Redemptions", "No redemptions found to recalculate.")
                return
            
            # Step 1: Reset all purchase remaining_amounts
            c.execute("UPDATE purchases SET remaining_amount = amount")
            
            # Step 2: Delete all tax_sessions linked to redemptions
            c.execute("DELETE FROM tax_sessions WHERE redemption_id IS NOT NULL")
            
            conn.commit()
            conn.close()
            
            # Step 3: Get all redemptions in chronological order
            conn = self.db.get_connection()
            c = conn.cursor()
            
            c.execute('''
                SELECT id, site_id, user_id, redemption_date, redemption_time,
                       amount, is_free_sc, more_remaining
                FROM redemptions
                ORDER BY redemption_date ASC, redemption_time ASC, id ASC
            ''')
            
            redemptions = c.fetchall()
            conn.close()
            
            # Step 4: Reprocess each redemption using FIFO
            processed = 0
            for redemption in redemptions:
                try:
                    # Skip "Balance Closed" redemptions (they have amount=0 and special handling)
                    if redemption['amount'] == 0:
                        continue
                    
                    # Use actual more_remaining value from database
                    self.session_mgr.process_redemption(
                        redemption['id'],
                        redemption['site_id'],
                        redemption['amount'],
                        redemption['redemption_date'],
                        redemption['redemption_time'] or '00:00:00',
                        redemption['user_id'],
                        bool(redemption['is_free_sc']),
                        more_remaining=bool(redemption['more_remaining']),  # Use actual value from DB
                        is_edit=True  # Don't update site_session totals
                    )
                    processed += 1
                except Exception as e:
                    print(f"Error processing redemption {redemption['id']}: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Handle "Balance Closed" redemptions separately
            # These have amount=0 but need tax_sessions showing the loss
            conn = self.db.get_connection()
            c = conn.cursor()
            
            c.execute('''
                SELECT id, site_id, user_id, redemption_date, notes
                FROM redemptions
                WHERE amount = 0 AND notes LIKE '%Balance Closed%'
            ''')
            
            balance_closed_redemptions = c.fetchall()
            
            for bc_redemption in balance_closed_redemptions:
                # Extract the net loss from notes (format: "Balance Closed - Net Loss: $X.XX ...")
                notes = bc_redemption['notes'] or ''
                if 'Net Loss: $' in notes:
                    try:
                        # Parse the net loss amount from notes
                        loss_str = notes.split('Net Loss: $')[1].split(' ')[0]
                        net_loss = float(loss_str)
                        
                        # Create tax_session for this balance closed redemption
                        c.execute('''
                            INSERT INTO tax_sessions
                            (session_date, site_id, redemption_id, cost_basis, payout, net_pl, user_id)
                            VALUES (?, ?, ?, ?, 0, ?, ?)
                        ''', (bc_redemption['redemption_date'], bc_redemption['site_id'], 
                              bc_redemption['id'], net_loss, -net_loss, bc_redemption['user_id']))
                    except Exception as e:
                        print(f"Error recreating tax_session for balance closed redemption {bc_redemption['id']}: {e}")
            
            conn.commit()
            conn.close()
            
            self.refresh_all_views()
            
            messagebox.showinfo("Success", 
                f"Recalculated {processed} redemption{'s' if processed != 1 else ''}.\n\n"
                f"FIFO cost basis has been updated.")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to recalculate redemptions:\n\n{str(e)}")
            import traceback
            traceback.print_exc()
    
    def recalculate_game_sessions(self):
        """Recalculate session metrics for all closed game sessions"""
        from tkinter import messagebox
        
        response = messagebox.askyesno(
            "Recalculate Game Sessions",
            "This will recalculate session metrics for ALL closed game sessions.\n\n"
            "This uses the current canonical calculation method.\n\n"
            "Continue?"
        )
        
        if not response:
            return
        
        try:
            # Use the silent version which has all the logic
            self.recalculate_game_sessions_silent()
            
            # Refresh views
            self.refresh_all_views()
            
            messagebox.showinfo(
                "Recalculation Complete",
                "✅ Successfully recalculated all game sessions!\n\n"
                "Net taxable and delta amounts have been updated.\n"
                "Daily tax sessions have been refreshed."
            )
            
        except Exception as e:
            messagebox.showerror("Recalculation Error", f"Failed to recalculate sessions:\n{str(e)}")


def main():
    """Main entry point"""
    root = tk.Tk()
    app = CasinoApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
