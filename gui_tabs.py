"""
gui_tabs.py - GUI tab building functions (Part 1)
Import this in main_app.py
"""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, date, timedelta

def create_date_filter_bar(parent, app, start_var_name, end_var_name, refresh_callback):
    """
    Create a standardized date filter bar with:
    - From/To fields with calendar pickers
    - Apply, Clear buttons
    - Today, Last 30 Days, This Month, This Year quick buttons
    
    Args:
        parent: Parent widget
        app: Main app object
        start_var_name: Attribute name for start date entry (e.g., 'p_filter_start')
        end_var_name: Attribute name for end date entry (e.g., 'p_filter_end')
        refresh_callback: Function to call when applying filter
    """
    filter_frame = ttk.LabelFrame(parent, text="🎯 Date Filter", padding=5)
    filter_frame.pack(fill='x', padx=10, pady=(10, 0))
    
    # From date
    ttk.Label(filter_frame, text="From:").pack(side='left', padx=5)
    start_frame = ttk.Frame(filter_frame)
    start_frame.pack(side='left')
    
    start_entry = ttk.Entry(start_frame, width=12)
    start_entry.pack(side='left')
    setattr(app, start_var_name, start_entry)
    
    def pick_start():
        try:
            from tkcalendar import Calendar
            top = tk.Toplevel(app.root)
            top.title("Select Start Date")
            top.geometry("300x300")
            cal = Calendar(top, selectmode='day', date_pattern='y-mm-dd')
            cal.pack(pady=20)
            def select():
                start_entry.delete(0, tk.END)
                start_entry.insert(0, cal.get_date())
                top.destroy()
            ttk.Button(top, text="Select", command=select).pack(pady=10)
            ttk.Button(top, text="Cancel", command=top.destroy).pack()
        except ImportError:
            pass
    
    ttk.Button(start_frame, text="📅", width=3, command=pick_start).pack(side='left', padx=2)
    
    # To date
    ttk.Label(filter_frame, text="To:").pack(side='left', padx=5)
    end_frame = ttk.Frame(filter_frame)
    end_frame.pack(side='left')
    
    end_entry = ttk.Entry(end_frame, width=12)
    end_entry.pack(side='left')
    setattr(app, end_var_name, end_entry)
    
    def pick_end():
        try:
            from tkcalendar import Calendar
            top = tk.Toplevel(app.root)
            top.title("Select End Date")
            top.geometry("300x300")
            cal = Calendar(top, selectmode='day', date_pattern='y-mm-dd')
            cal.pack(pady=20)
            def select():
                end_entry.delete(0, tk.END)
                end_entry.insert(0, cal.get_date())
                top.destroy()
            ttk.Button(top, text="Select", command=select).pack(pady=10)
            ttk.Button(top, text="Cancel", command=top.destroy).pack()
        except ImportError:
            pass
    
    ttk.Button(end_frame, text="📅", width=3, command=pick_end).pack(side='left', padx=2)
    
    # Action buttons
    ttk.Button(filter_frame, text="Apply", 
              command=refresh_callback).pack(side='left', padx=5)
    ttk.Button(filter_frame, text="Clear", 
              command=lambda: (
                  start_entry.delete(0, tk.END),
                  end_entry.delete(0, tk.END),
                  refresh_callback()
              )).pack(side='left', padx=5)
    
    # Quick date buttons
    ttk.Button(filter_frame, text="Today", 
              command=lambda: (
                  start_entry.delete(0, tk.END),
                  start_entry.insert(0, date.today().strftime("%Y-%m-%d")),
                  end_entry.delete(0, tk.END),
                  end_entry.insert(0, date.today().strftime("%Y-%m-%d")),
                  refresh_callback()
              )).pack(side='left', padx=5)
    
    ttk.Button(filter_frame, text="Last 30 Days", 
              command=lambda: (
                  start_entry.delete(0, tk.END),
                  start_entry.insert(0, (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")),
                  end_entry.delete(0, tk.END),
                  end_entry.insert(0, date.today().strftime("%Y-%m-%d")),
                  refresh_callback()
              )).pack(side='left', padx=5)
    
    ttk.Button(filter_frame, text="This Month", 
              command=lambda: (
                  start_entry.delete(0, tk.END),
                  start_entry.insert(0, date.today().replace(day=1).strftime("%Y-%m-%d")),
                  end_entry.delete(0, tk.END),
                  end_entry.insert(0, date.today().strftime("%Y-%m-%d")),
                  refresh_callback()
              )).pack(side='left', padx=5)
    
    ttk.Button(filter_frame, text="This Year", 
              command=lambda: (
                  start_entry.delete(0, tk.END),
                  start_entry.insert(0, date.today().replace(month=1, day=1).strftime("%Y-%m-%d")),
                  end_entry.delete(0, tk.END),
                  end_entry.insert(0, date.today().strftime("%Y-%m-%d")),
                  refresh_callback()
              )).pack(side='left', padx=5)
    
    return filter_frame

def parse_date(date_str):
    """Parse various date formats with smart defaults"""
    date_str = date_str.strip()
    
    # If format is MM/DD or M/D, assume current year
    if '/' in date_str:
        parts = date_str.split('/')
        if len(parts) == 2:
            # MM/DD â†’ MM/DD/YYYY
            date_str = f"{parts[0]}/{parts[1]}/{date.today().year}"
        elif len(parts) == 3 and len(parts[2]) == 2:
            # MM/DD/YY â†’ convert 2-digit year
            pass  # Will be handled by existing format
    
    # If format is MM-DD or M-D, assume current year
    if '-' in date_str:
        parts = date_str.split('-')
        if len(parts) == 2:
            # MM-DD â†’ YYYY-MM-DD
            date_str = f"{date.today().year}-{parts[0]}-{parts[1]}"
    
    formats = ["%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y", "%m-%d-%y", "%Y/%m/%d"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unable to parse date: {date_str}")


def enable_excel_autosuggest(combo):
    """Excel-like inline autosuggest for preset ttk.Combobox values.

    - Allows typing (forces state='normal')
    - Typing suggests the first prefix match and selects only the suggested remainder
    - Backspace/Delete never forces re-fill; it only refilters
    - Tab/Enter accepts and closes dropdown
    - Focus-out enforces valid values (clears if invalid)
    """
    import tkinter as tk

    try:
        combo.configure(state='normal')
    except Exception:
        pass

    # Keep a stable master list (never overwrite it with filtered values)
    if not hasattr(combo, '_excel_master'):
        try:
            combo._excel_master = list(combo.cget('values'))
        except Exception:
            combo._excel_master = []

    def refresh_master_if_needed():
        try:
            current = list(combo.cget('values'))
        except Exception:
            current = []
        # only refresh master if current looks like a full list (same or larger)
        if current and (len(current) >= len(combo._excel_master)):
            combo._excel_master = current

    def master():
        refresh_master_if_needed()
        return combo._excel_master

    def committed_prefix():
        s = combo.get()
        try:
            if combo.selection_present():
                start = combo.index('sel.first')
                return s[:start]
        except Exception:
            pass
        try:
            cur = combo.index(tk.INSERT)
        except Exception:
            cur = len(s)
        return s[:cur]

    def set_values(filtered):
        combo['values'] = filtered if filtered else master()

    def matches(prefix):
        vals = master()
        if not prefix:
            return vals
        p = prefix.lower()
        return [v for v in vals if v.lower().startswith(p)]

    def post_dropdown():
        try:
            combo.event_generate('<Down>')
        except Exception:
            pass
        try:
            combo.after_idle(combo.focus_set)
        except Exception:
            pass

    def unpost_dropdown():
        try:
            combo.tk.call('ttk::combobox::unpost', combo)
        except Exception:
            try:
                combo.event_generate('<Escape>')
            except Exception:
                pass

    def on_keypress(event):
        # allow navigation keys
        if event.keysym in ('Left','Right','Up','Down','Home','End','Escape'):
            return None
        # allow deletion; we'll refilter on keyrelease
        if event.keysym in ('BackSpace','Delete'):
            return None
        if event.keysym in ('Return','Tab'):
            return None
        if not event.char or ord(event.char) < 32:
            return None

        prefix = committed_prefix() + event.char
        ms = matches(prefix)
        set_values(ms)

        if ms:
            best = ms[0]
            combo.set(best)
            try:
                combo.icursor(len(prefix))
                combo.selection_range(len(prefix), tk.END)
            except Exception:
                pass
            post_dropdown()
        else:
            combo.set(prefix)
            try:
                combo.selection_clear()
            except Exception:
                pass
            set_values([])

        return 'break'

    def on_keyrelease(event):
        # filter only, never inline-fill here
        text = combo.get()
        ms = matches(text)
        set_values(ms)
        try:
            combo.selection_clear()
        except Exception:
            pass
        if ms and event.keysym not in ('BackSpace','Delete'):
            post_dropdown()

    def accept(event):
        text = combo.get()
        ms = matches(text)
        set_values(ms)
        if ms and text not in master():
            combo.set(ms[0])
        try:
            combo.selection_clear()
        except Exception:
            pass
        unpost_dropdown()
        return None

    def validate(_):
        if combo.get() and combo.get() not in master():
            combo.set('')
        set_values(master())

    combo.bind('<KeyPress>', on_keypress, add='+')
    combo.bind('<KeyRelease>', on_keyrelease, add='+')
    combo.bind('<Return>', accept, add='+')
    combo.bind('<Tab>', accept, add='+')
    combo.bind('<FocusOut>', validate, add='+')



def build_purchases_tab(app):
    """Build purchases tab with User field IN the form"""
    
    # Date Range Filter - using standardized helper
    create_date_filter_bar(
        app.purchases_tab, 
        app, 
        'p_filter_start', 
        'p_filter_end', 
        lambda: app.refresh_purchases()
    )
    
    form = ttk.LabelFrame(app.purchases_tab, text="Add/Edit Purchase", padding=10)
    form.pack(fill='x', padx=10, pady=10)
    
    # Row 0: Date and User side by side
    ttk.Label(form, text="Date:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
    
    date_frame = ttk.Frame(form)
    date_frame.grid(row=0, column=1, sticky='w', padx=5, pady=5)
    
    app.p_date = ttk.Entry(date_frame, width=12)
    app.p_date.insert(0, date.today().strftime("%Y-%m-%d"))
    app.p_date.pack(side='left')
    
    def pick_purchase_date():
        try:
            from tkcalendar import Calendar
            top = tk.Toplevel(app.root)
            top.title("Select Date")
            top.geometry("300x300")
            
            cal = Calendar(top, selectmode='day', date_pattern='y-mm-dd')
            cal.pack(pady=20)
            
            def select_date():
                app.p_date.delete(0, tk.END)
                app.p_date.insert(0, cal.get_date())
                top.destroy()
            
            ttk.Button(top, text="Select", command=select_date).pack(pady=10)
            ttk.Button(top, text="Cancel", command=top.destroy).pack()
        except ImportError:
            # Fallback if tkcalendar not installed - just set to today
            app.p_date.delete(0, tk.END)
            app.p_date.insert(0, date.today().strftime("%Y-%m-%d"))
    
    ttk.Button(date_frame, text="📅", width=3, command=pick_purchase_date).pack(side='left', padx=2)
    
    # Time field (24-hour format HH:MM:SS)
    ttk.Label(date_frame, text="Time:").pack(side='left', padx=(10, 5))
    app.p_time = ttk.Entry(date_frame, width=10)
    from datetime import datetime
    app.p_time.insert(0, datetime.now().strftime("%H:%M:%S"))
    app.p_time.pack(side='left')
    
    def set_purchase_time_now():
        from datetime import datetime
        app.p_time.delete(0, tk.END)
        app.p_time.insert(0, datetime.now().strftime("%H:%M:%S"))
    
    ttk.Button(date_frame, text="Now", width=5, command=set_purchase_time_now).pack(side='left', padx=2)
    
    ttk.Label(form, text="User:").grid(row=0, column=2, sticky='w', padx=5, pady=5)
    app.p_user = ttk.Combobox(form, width=20, state='normal')
    enable_excel_autosuggest(app.p_user)
    app.p_user.bind('<<ComboboxSelected>>', app.on_purchase_user_selected)
    app.p_user.bind('<FocusOut>', app.on_purchase_user_selected)  # Trigger when tabbing away
    app.p_user.bind('<Return>', app.on_purchase_user_selected)    # Trigger when pressing Enter
    app.p_user.grid(row=0, column=3, sticky='w', padx=5, pady=5)
    
    # Row 1
    ttk.Label(form, text="Site:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
    app.p_site = ttk.Combobox(form, width=20, state='normal')
    enable_excel_autosuggest(app.p_site)
    app.p_site.grid(row=1, column=1, sticky='w', padx=5, pady=5)
    
    ttk.Label(form, text="$ Amount:").grid(row=1, column=2, sticky='w', padx=5, pady=5)
    app.p_amount = ttk.Entry(form, width=15)
    app.p_amount.grid(row=1, column=3, sticky='w', padx=5, pady=5)
    
    # Row 2
    ttk.Label(form, text="SC Received:").grid(row=2, column=0, sticky='w', padx=5, pady=5)
    app.p_sc = ttk.Entry(form, width=15)
    app.p_sc.grid(row=2, column=1, sticky='w', padx=5, pady=5)
    
    ttk.Label(form, text="Starting SC:").grid(row=2, column=2, sticky='w', padx=5, pady=5)
    app.p_start_sc = ttk.Entry(form, width=15)
    app.p_start_sc.insert(0, "0")
    app.p_start_sc.grid(row=2, column=3, sticky='w', padx=5, pady=5)
    
    # Row 3
    ttk.Label(form, text="Card:").grid(row=3, column=0, sticky='w', padx=5, pady=5)
    app.p_card = ttk.Combobox(form, width=20, state='normal')
    enable_excel_autosuggest(app.p_card)
    app.p_card.grid(row=3, column=1, sticky='w', padx=5, pady=5)
    
    # Row 4 - Notes
    ttk.Label(form, text="Notes:").grid(row=4, column=0, sticky='nw', padx=5, pady=5)
    app.p_notes = tk.Text(form, height=3, width=50)
    app.p_notes.grid(row=4, column=1, columnspan=3, sticky='ew', padx=5, pady=5)
    
    # Row 5 - Buttons (smart Save button)
    btn_frame = ttk.Frame(form)
    btn_frame.grid(row=5, column=0, columnspan=4, pady=10)
    
    ttk.Button(btn_frame, text="Save", command=app.smart_save_purchase, width=12).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="Delete", command=app.delete_purchase, width=12).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="Clear", command=app.clear_purchase_form, width=12).pack(side='left', padx=5)
    
    # Initialize edit tracking
    app.p_edit_id = None
    
    # Escape key clears current field
    def clear_current_field(e):
        widget = app.root.focus_get()
        if isinstance(widget, (ttk.Entry, tk.Entry, ttk.Combobox)):
            if isinstance(widget, ttk.Combobox):
                widget.set('')
            else:
                widget.delete(0, tk.END)
    
    form.bind('<Escape>', clear_current_field)
    
    # List
    list_frame = ttk.LabelFrame(app.purchases_tab, text="Purchases", padding=10)
    list_frame.pack(fill='both', expand=True, padx=10, pady=10)
    
    # Add search frame
    from table_helpers import SearchableTreeview, export_tree_to_csv
    search_frame = ttk.Frame(list_frame)
    search_frame.pack(fill='x', padx=5, pady=(0, 5))
    
    # Add export button to search frame (will be populated by SearchableTreeview)
    ttk.Button(search_frame, text="📤 Export CSV", 
              command=lambda: export_tree_to_csv(app.p_tree, "purchases", app.root),
              width=15).pack(side='right', padx=5)
    
    cols = ('Date', 'Time', 'Site', 'User', 'Game Type', 'Duration',
            'Start Total', 'End Total', 'Start Redeem', 'End Redeem',
            'Δ Total', 'Δ Redeem', 'Basis Consumed', 'Net P/L', 'Status', 'Notes')
    app.p_tree = ttk.Treeview(list_frame, columns=cols, show='headings', height=15)
    for col in cols:
        app.p_tree.heading(col, text=col)
        if col == 'Notes':
            app.p_tree.column(col, width=200)
        else:
            app.p_tree.column(col, width=100)
    
    scroll = ttk.Scrollbar(list_frame, orient='vertical', command=app.p_tree.yview)
    app.p_tree.configure(yscrollcommand=scroll.set)
    app.p_tree.pack(side='left', fill='both', expand=True)
    scroll.pack(side='right', fill='y')
    
    # Initialize search/sort
    app.p_searchable = SearchableTreeview(app.p_tree, cols, search_frame)
    
    # Enable multi-select (Ctrl+Click, Shift+Click)
    from table_helpers import enable_multi_select
    enable_multi_select(app.p_tree)
    
    # Double-click to load into form for editing (bind AFTER SearchableTreeview)
    def on_double_click(e):
        app.edit_purchase()
        return 'break'  # Stop event propagation
    
    app.p_tree.bind('<Double-Button-1>', on_double_click)


def build_redemptions_tab(app):
    """Build redemptions tab with User field IN the form"""
    
    # Date Range Filter - using standardized helper
    create_date_filter_bar(
        app.redemptions_tab,
        app,
        'r_filter_start',
        'r_filter_end',
        lambda: app.refresh_redemptions()
    )
    
    form = ttk.LabelFrame(app.redemptions_tab, text="Log/Edit Redemption", padding=10)
    form.pack(fill='x', padx=10, pady=10)
    
    # Row 0: Date and User side by side
    ttk.Label(form, text="Date:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
    
    date_frame = ttk.Frame(form)
    date_frame.grid(row=0, column=1, sticky='w', padx=5, pady=5)
    
    app.r_date = ttk.Entry(date_frame, width=12)
    app.r_date.insert(0, date.today().strftime("%Y-%m-%d"))
    app.r_date.pack(side='left')
    
    def pick_redemption_date():
        try:
            from tkcalendar import Calendar
            top = tk.Toplevel(app.root)
            top.title("Select Redemption Date")
            top.geometry("300x300")
            
            cal = Calendar(top, selectmode='day', date_pattern='y-mm-dd')
            cal.pack(pady=20)
            
            def select_date():
                app.r_date.delete(0, tk.END)
                app.r_date.insert(0, cal.get_date())
                top.destroy()
            
            ttk.Button(top, text="Select", command=select_date).pack(pady=10)
            ttk.Button(top, text="Cancel", command=top.destroy).pack()
        except ImportError:
            app.r_date.delete(0, tk.END)
            app.r_date.insert(0, date.today().strftime("%Y-%m-%d"))
    
    ttk.Button(date_frame, text="📅", width=3, command=pick_redemption_date).pack(side='left', padx=2)
    
    # Time field (24-hour format HH:MM:SS)
    ttk.Label(date_frame, text="Time:").pack(side='left', padx=(10, 5))
    app.r_time = ttk.Entry(date_frame, width=10)
    from datetime import datetime
    app.r_time.insert(0, datetime.now().strftime("%H:%M:%S"))
    app.r_time.pack(side='left')
    
    def set_redemption_time_now():
        from datetime import datetime
        app.r_time.delete(0, tk.END)
        app.r_time.insert(0, datetime.now().strftime("%H:%M:%S"))
    
    ttk.Button(date_frame, text="Now", width=5, command=set_redemption_time_now).pack(side='left', padx=2)
    
    ttk.Label(form, text="User:").grid(row=0, column=2, sticky='w', padx=5, pady=5)
    app.r_user = ttk.Combobox(form, width=20, state='normal')
    enable_excel_autosuggest(app.r_user)
    app.r_user.bind('<<ComboboxSelected>>', app.on_r_user_sel)
    app.r_user.bind('<FocusOut>', app.on_r_user_sel)  # Trigger when tabbing away
    app.r_user.bind('<Return>', app.on_r_user_sel)    # Trigger when pressing Enter
    app.r_user.grid(row=0, column=3, sticky='w', padx=5, pady=5)
    
    # Row 1
    ttk.Label(form, text="Site:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
    app.r_site = ttk.Combobox(form, width=20, state='normal')
    enable_excel_autosuggest(app.r_site)
    app.r_site.bind('<<ComboboxSelected>>', app.on_r_site_sel)
    app.r_site.grid(row=1, column=1, sticky='w', padx=5, pady=5)
    
    app.r_info = ttk.Label(form, text="", foreground='blue')
    app.r_info.grid(row=1, column=2, columnspan=2, sticky='w', padx=5, pady=5)
    
    # Row 2
    ttk.Label(form, text="Amount:").grid(row=2, column=0, sticky='w', padx=5, pady=5)
    app.r_amount = ttk.Entry(form, width=15)
    app.r_amount.grid(row=2, column=1, sticky='w', padx=5, pady=5)
    
    ttk.Label(form, text="Receipt Date:").grid(row=2, column=2, sticky='w', padx=5, pady=5)
    
    receipt_frame = ttk.Frame(form)
    receipt_frame.grid(row=2, column=3, sticky='w', padx=5, pady=5)
    
    app.r_receipt = ttk.Entry(receipt_frame, width=12)
    app.r_receipt.pack(side='left')
    
    def pick_receipt_date():
        try:
            from tkcalendar import Calendar
            top = tk.Toplevel(app.root)
            top.title("Select Receipt Date")
            top.geometry("300x300")
            
            cal = Calendar(top, selectmode='day', date_pattern='y-mm-dd')
            cal.pack(pady=20)
            
            def select_date():
                app.r_receipt.delete(0, tk.END)
                app.r_receipt.insert(0, cal.get_date())
                top.destroy()
            
            ttk.Button(top, text="Select", command=select_date).pack(pady=10)
            ttk.Button(top, text="Cancel", command=top.destroy).pack()
        except ImportError:
            app.r_receipt.delete(0, tk.END)
            app.r_receipt.insert(0, date.today().strftime("%Y-%m-%d"))
    
    ttk.Button(receipt_frame, text="📅", width=3, command=pick_receipt_date).pack(side='left', padx=2)
    
    # Row 3
    ttk.Label(form, text="Method:").grid(row=3, column=0, sticky='w', padx=5, pady=5)
    app.r_method = ttk.Combobox(form, width=20, state='normal')
    enable_excel_autosuggest(app.r_method)
    app.r_method.grid(row=3, column=1, sticky='w', padx=5, pady=5)
    
    # Row 4 - Checkboxes
    app.r_more = tk.BooleanVar()
    ttk.Checkbutton(form, text="More balance remaining", variable=app.r_more).grid(
        row=4, column=0, columnspan=2, sticky='w', padx=5, pady=5)
    
    app.r_free = tk.BooleanVar()
    ttk.Checkbutton(form, text="Free SC", variable=app.r_free).grid(
        row=4, column=2, sticky='w', padx=5, pady=5)
    
    app.r_processed = tk.BooleanVar()
    ttk.Checkbutton(form, text="Processed", variable=app.r_processed).grid(
        row=4, column=3, sticky='w', padx=5, pady=5)
    
    # Row 5 - Notes
    ttk.Label(form, text="Notes:").grid(row=5, column=0, sticky='nw', padx=5, pady=5)
    app.r_notes = tk.Text(form, height=3, width=50)
    app.r_notes.grid(row=5, column=1, columnspan=3, sticky='ew', padx=5, pady=5)
    
    # Row 6 - Buttons (smart Save button)
    btn_frame = ttk.Frame(form)
    btn_frame.grid(row=6, column=0, columnspan=5, pady=10)
    
    ttk.Button(btn_frame, text="Save", command=app.smart_save_redemption, width=12).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="Delete", command=app.delete_redemption, width=12).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="Clear", command=app.clear_redemption_form, width=12).pack(side='left', padx=5)
    
    # Initialize edit tracking
    app.r_edit_id = None
    
    # Escape key clears current field
    def clear_current_field(e):
        widget = app.root.focus_get()
        if isinstance(widget, (ttk.Entry, tk.Entry)):
            widget.delete(0, tk.END)
    
    form.bind('<Escape>', clear_current_field)
    
    # List
    list_frame = ttk.LabelFrame(app.redemptions_tab, text="Redemptions", padding=10)
    list_frame.pack(fill='both', expand=True, padx=10, pady=10)
    
    # Add search frame
    from table_helpers import SearchableTreeview, export_tree_to_csv
    search_frame = ttk.Frame(list_frame)
    search_frame.pack(fill='x', padx=5, pady=(0, 5))
    
    # Add export button
    ttk.Button(search_frame, text="📤 Export CSV", 
              command=lambda: export_tree_to_csv(app.r_tree, "redemptions", app.root),
              width=15).pack(side='right', padx=5)
    
    cols = ('User', 'Date', 'Site', 'Amount', 'Receipt', 'Method', 'Free', 'Processed', 'Notes')
    app.r_tree = ttk.Treeview(list_frame, columns=cols, show='headings', height=15)
    for col in cols:
        app.r_tree.heading(col, text=col)
        if col == 'Notes':
            app.r_tree.column(col, width=200)
        elif col in ('Free', 'Processed'):
            app.r_tree.column(col, width=80)
        else:
            app.r_tree.column(col, width=110)
    
    scroll = ttk.Scrollbar(list_frame, orient='vertical', command=app.r_tree.yview)
    app.r_tree.configure(yscrollcommand=scroll.set)
    app.r_tree.pack(side='left', fill='both', expand=True)
    scroll.pack(side='right', fill='y')
    
    # Initialize search/sort
    app.r_searchable = SearchableTreeview(app.r_tree, cols, search_frame)
    
    # Enable multi-select
    from table_helpers import enable_multi_select
    enable_multi_select(app.r_tree)
    
    # Double-click to load for editing
    def on_double_click(e):
        app.edit_redemption()
        return 'break'  # Stop event propagation
    
    app.r_tree.bind('<Double-Button-1>', on_double_click)


def build_setup_tab(app):
    """Build setup tab with all CRUD operations"""
    nb = ttk.Notebook(app.setup_tab)
    nb.pack(fill='both', expand=True, padx=10, pady=10)
    
    # Users subtab
    users_frame = ttk.Frame(nb)
    nb.add(users_frame, text="Users")
    build_users_section(app, users_frame)
    
    # Sites subtab
    sites_frame = ttk.Frame(nb)
    nb.add(sites_frame, text="Sites")
    build_sites_section(app, sites_frame)
    
    # Cards subtab
    cards_frame = ttk.Frame(nb)
    nb.add(cards_frame, text="Cards")
    build_cards_section(app, cards_frame)
    
    # Methods subtab
    methods_frame = ttk.Frame(nb)
    nb.add(methods_frame, text="Redemption Methods")
    build_methods_section(app, methods_frame)
    
    # Tools subtab (Import CSV + Database Tools)
    tools_frame = ttk.Frame(nb)
    nb.add(tools_frame, text="Tools")
    build_tools_section(app, tools_frame)


def build_users_section(app, parent):
    """Build users management section with list + add/edit/delete (matches Sites/Cards)."""
    form = ttk.Frame(parent, padding=10)
    form.pack(fill='x')

    ttk.Label(form, text="User Name:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
    name_entry = ttk.Entry(form, width=30)
    name_entry.grid(row=0, column=1, sticky='w', padx=5, pady=5)

    active_var = tk.IntVar(value=1)
    ttk.Checkbutton(form, text="Active", variable=active_var).grid(row=0, column=2, sticky='w', padx=10, pady=5)

    selected = {"user_id": None}

    def clear_form():
        name_entry.delete(0, tk.END)
        active_var.set(1)
        selected["user_id"] = None

    def refresh_list():
        conn = app.db.get_connection()
        c = conn.cursor()
        rows = c.execute("SELECT id, name, active FROM users ORDER BY name").fetchall()
        conn.close()
        
        data = []
        for r in rows:
            values = (r["name"], "Yes" if r["active"] else "No")
            tags = (r["id"],)
            data.append((values, tags))
        
        searchable.set_data(data)

    def on_select(_=None):
        sel = tree.selection()
        if not sel:
            return
        # Check if multiple selected
        if len(sel) > 1:
            messagebox.showwarning("Multiple Selection", 
                "Please select only one user to edit.\n\n"
                "Tip: Use Ctrl+Click or Shift+Click to select multiple items for deletion.")
            return
        uid = tree.item(sel[0])["tags"][0]
        conn = app.db.get_connection()
        c = conn.cursor()
        r = c.execute("SELECT id, name, active FROM users WHERE id=?", (uid,)).fetchone()
        conn.close()
        if not r:
            return
        selected["user_id"] = r["id"]
        name_entry.delete(0, tk.END)
        name_entry.insert(0, r["name"])
        active_var.set(int(r["active"] or 0))

    def add_user():
        name = name_entry.get().strip()
        if not name:
            return
        conn = app.db.get_connection()
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (name, active) VALUES (?, ?)", (name, int(active_var.get())))
            conn.commit()
            clear_form()
            refresh_list()
            app.refresh_dropdowns()
            app.refresh_all_views()
            messagebox.showinfo("Success", "User added")
        except Exception:
            messagebox.showerror("Error", "User already exists or invalid")
        finally:
            conn.close()

    def update_user():
        if not selected["user_id"]:
            messagebox.showwarning("Select", "Select a user to update")
            return
        name = name_entry.get().strip()
        if not name:
            return
        conn = app.db.get_connection()
        c = conn.cursor()
        try:
            c.execute("UPDATE users SET name=?, active=? WHERE id=?",
                      (name, int(active_var.get()), selected["user_id"]))
            conn.commit()
            refresh_list()
            app.refresh_dropdowns()
            app.refresh_all_views()
            messagebox.showinfo("Success", "User updated")
        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            conn.close()
    
    def smart_save():
        if selected["user_id"]:
            update_user()
        else:
            add_user()

    def delete_user():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select user(s) to delete")
            return
        
        # Check if multiple selected
        if len(sel) > 1:
            if not messagebox.askyesno("Confirm", 
                f"⚠️ WARNING: Delete {len(sel)} users?\n\n"
                "This will also delete all their purchases, redemptions, and tax data.\n"
                "This CANNOT be undone!"):
                return
        
        deleted_count = 0
        error_messages = []
        
        for item in sel:
            uid = tree.item(item)["tags"][0]
            
            # Get counts and totals for warning message (only for single delete)
            conn = app.db.get_connection()
            c = conn.cursor()
            
            if len(sel) == 1:  # Only show detailed warning for single delete
                # Count purchases and get total amount
                c.execute("SELECT COUNT(*) as count, COALESCE(SUM(amount), 0) as total FROM purchases WHERE user_id = ?", (uid,))
                purchase_data = c.fetchone()
                purchase_count = purchase_data['count']
                purchase_total = float(purchase_data['total'])
                
                # Count redemptions and get total amount
                c.execute("SELECT COUNT(*) as count, COALESCE(SUM(amount), 0) as total FROM redemptions WHERE user_id = ?", (uid,))
                redemption_data = c.fetchone()
                redemption_count = redemption_data['count']
                redemption_total = float(redemption_data['total'])
                
                # Count tax sessions
                c.execute("SELECT COUNT(*) as count FROM tax_sessions WHERE user_id = ?", (uid,))
                tax_count = c.fetchone()['count']
                
                # Count cards
                c.execute("SELECT COUNT(*) as count FROM cards WHERE user_id = ?", (uid,))
                card_count = c.fetchone()['count']
                
                # If user has data, show scary warning
                if purchase_count > 0 or redemption_count > 0 or card_count > 0:
                    warning_msg = (
                        f"⚠️ WARNING: Deleting this user will permanently delete:\n\n"
                        f"  â€¢ {purchase_count} purchase(s) (${purchase_total:,.2f})\n"
                        f"  â€¢ {redemption_count} redemption(s) (${redemption_total:,.2f})\n"
                        f"  â€¢ {tax_count} tax session(s)\n"
                        f"  â€¢ {card_count} card(s)\n\n"
                        f"This will affect your tax records and CANNOT be undone.\n\n"
                        f"Are you sure you want to proceed?"
                    )
                    
                    if not messagebox.askyesno("⚠️ Delete All User Data", warning_msg, icon='warning'):
                        conn.close()
                        continue
            
            # CASCADE DELETE in proper order
            c.execute("DELETE FROM tax_sessions WHERE user_id = ?", (uid,))
            c.execute("DELETE FROM redemptions WHERE user_id = ?", (uid,))
            c.execute("DELETE FROM purchases WHERE user_id = ?", (uid,))
            c.execute("DELETE FROM cards WHERE user_id = ?", (uid,))
            c.execute("DELETE FROM site_sessions WHERE user_id = ?", (uid,))
            c.execute("DELETE FROM users WHERE id = ?", (uid,))
            
            conn.commit()
            conn.close()
            deleted_count += 1
        
        clear_form()
        refresh_list()
        app.refresh_dropdowns()
        app.refresh_all_views()
        
        if deleted_count > 1:
            messagebox.showinfo("Success", f"Deleted {deleted_count} users and all associated data")
        elif deleted_count == 1:
            messagebox.showinfo("Success", "User and all associated data deleted")

    btns = ttk.Frame(form)
    btns.grid(row=1, column=0, columnspan=3, sticky='w', padx=5, pady=5)
    ttk.Button(btns, text="Save", command=smart_save, width=12).pack(side='left', padx=5)
    ttk.Button(btns, text="Delete", command=delete_user, width=12).pack(side='left', padx=5)
    ttk.Button(btns, text="Clear", command=clear_form, width=12).pack(side='left', padx=5)

    list_frame = ttk.LabelFrame(parent, text="Users", padding=10)
    list_frame.pack(fill='both', expand=True, padx=10, pady=10)
    
    # Add search frame
    search_frame = ttk.Frame(list_frame)
    search_frame.pack(fill='x', padx=5, pady=(0, 5))
    
    # Add export button
    from table_helpers import export_tree_to_csv
    ttk.Button(search_frame, text="📤 Export CSV", 
              command=lambda: export_tree_to_csv(tree, "users", app.root),
              width=15).pack(side='right', padx=5)

    tree = ttk.Treeview(list_frame, columns=("Name", "Active"), show="headings", height=15)
    tree.heading("Name", text="Name")
    tree.heading("Active", text="Active")
    tree.column("Name", width=260)
    tree.column("Active", width=100)

    scroll = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    
    # Add SearchableTreeview for sorting and searching
    from table_helpers import SearchableTreeview, enable_multi_select
    searchable = SearchableTreeview(tree, ["Name", "Active"], search_frame)
    enable_multi_select(tree)

    tree.bind('<Double-Button-1>', on_select)

    refresh_list()

def build_sites_section(app, parent):
    """Build sites management section with list + add/edit/delete (matches Users/Cards)."""
    form = ttk.Frame(parent, padding=10)
    form.pack(fill='x')

    ttk.Label(form, text="Site Name:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
    name_entry = ttk.Entry(form, width=24)
    name_entry.grid(row=0, column=1, sticky='w', padx=5, pady=5)

    ttk.Label(form, text="SC Rate (USD/SC):").grid(row=0, column=2, sticky='w', padx=5, pady=5)
    sc_rate_entry = ttk.Entry(form, width=10)
    sc_rate_entry.grid(row=0, column=3, sticky='w', padx=5, pady=5)
    sc_rate_entry.insert(0, "1.0")

    active_var = tk.IntVar(value=1)
    ttk.Checkbutton(form, text="Active", variable=active_var).grid(row=0, column=4, sticky='w', padx=10, pady=5)

    selected = {"site_id": None}

    def clear_form():
        name_entry.delete(0, tk.END)
        sc_rate_entry.delete(0, tk.END)
        sc_rate_entry.insert(0, "1.0")
        active_var.set(1)
        selected["site_id"] = None

    def refresh_list():
        conn = app.db.get_connection()
        c = conn.cursor()
        rows = c.execute("SELECT id, name, sc_rate, active FROM sites ORDER BY name").fetchall()
        conn.close()
        
        data = []
        for r in rows:
            values = (r["name"], f'{(r["sc_rate"] or 1.0):.4f}', "Yes" if r["active"] else "No")
            tags = (r["id"],)
            data.append((values, tags))
        
        searchable.set_data(data)

    def on_select(_=None):
        sel = tree.selection()
        if not sel:
            return
        # Check if multiple selected
        if len(sel) > 1:
            messagebox.showwarning("Multiple Selection", 
                "Please select only one site to edit.\n\n"
                "Tip: Use Ctrl+Click or Shift+Click to select multiple items for deletion.")
            return
        sid = tree.item(sel[0])["tags"][0]
        conn = app.db.get_connection()
        c = conn.cursor()
        r = c.execute("SELECT id, name, sc_rate, active FROM sites WHERE id=?", (sid,)).fetchone()
        conn.close()
        if not r:
            return
        selected["site_id"] = r["id"]
        name_entry.delete(0, tk.END)
        name_entry.insert(0, r["name"])
        sc_rate_entry.delete(0, tk.END)
        sc_rate_entry.insert(0, str(r["sc_rate"] if r["sc_rate"] is not None else 1.0))
        active_var.set(int(r["active"] or 0))

    def add_site():
        name = name_entry.get().strip()
        if not name:
            return
        sc_rate_str = sc_rate_entry.get().strip() or "1.0"
        try:
            sc_rate = float(sc_rate_str)
            if sc_rate <= 0:
                messagebox.showwarning("Invalid", "SC Rate must be greater than 0")
                return
        except ValueError:
            messagebox.showwarning("Invalid", "SC Rate must be a number")
            return
        conn = app.db.get_connection()
        c = conn.cursor()
        try:
            c.execute("INSERT INTO sites (name, sc_rate, active) VALUES (?, ?, ?)",
                      (name, sc_rate, int(active_var.get())))
            conn.commit()
            clear_form()
            refresh_list()
            app.refresh_dropdowns()
            app.refresh_all_views()
            messagebox.showinfo("Success", "Site added")
        except Exception:
            messagebox.showerror("Error", "Site already exists or invalid")
        finally:
            conn.close()

    def update_site():
        if not selected["site_id"]:
            messagebox.showwarning("Select", "Select a site to update")
            return
        name = name_entry.get().strip()
        if not name:
            return
        sc_rate_str = sc_rate_entry.get().strip() or "1.0"
        try:
            sc_rate = float(sc_rate_str)
            if sc_rate <= 0:
                messagebox.showwarning("Invalid", "SC Rate must be greater than 0")
                return
        except ValueError:
            messagebox.showwarning("Invalid", "SC Rate must be a number")
            return
        conn = app.db.get_connection()
        c = conn.cursor()
        try:
            c.execute("UPDATE sites SET name=?, sc_rate=?, active=? WHERE id=?",
                      (name, sc_rate, int(active_var.get()), selected["site_id"]))
            conn.commit()
            refresh_list()
            app.refresh_dropdowns()
            app.refresh_all_views()
            messagebox.showinfo("Success", "Site updated")
        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            conn.close()
    
    def smart_save():
        if selected["site_id"]:
            update_site()
        else:
            add_site()

    def delete_site():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select site(s) to delete")
            return
        
        # For multiple selections, show bulk warning
        if len(sel) > 1:
            if not messagebox.askyesno("Confirm", 
                f"⚠️ WARNING: Delete {len(sel)} sites?\n\n"
                "This will also delete all purchases, redemptions, and tax data for these sites.\n"
                "This CANNOT be undone!"):
                return
        
        deleted_count = 0
        
        for item in sel:
            sid = tree.item(item)["tags"][0]
            
            # For single selection, show detailed warning
            if len(sel) == 1:
                conn = app.db.get_connection()
                c = conn.cursor()
                
                c.execute("SELECT COUNT(*) as count, COALESCE(SUM(amount), 0) as total FROM purchases WHERE site_id = ?", (sid,))
                purchase_data = c.fetchone()
                purchase_count = purchase_data['count']
                purchase_total = float(purchase_data['total'])
                
                c.execute("SELECT COUNT(*) as count, COALESCE(SUM(amount), 0) as total FROM redemptions WHERE site_id = ?", (sid,))
                redemption_data = c.fetchone()
                redemption_count = redemption_data['count']
                redemption_total = float(redemption_data['total'])
                
                c.execute("SELECT COUNT(*) as count FROM tax_sessions WHERE site_id = ?", (sid,))
                tax_count = c.fetchone()['count']
                
                conn.close()
                
                if purchase_count > 0 or redemption_count > 0:
                    warning_msg = (
                        f"⚠️ WARNING: Deleting this site will permanently delete:\n\n"
                        f"  â€¢ {purchase_count} purchase(s) (${purchase_total:,.2f})\n"
                        f"  â€¢ {redemption_count} redemption(s) (${redemption_total:,.2f})\n"
                        f"  â€¢ {tax_count} tax session(s)\n\n"
                        f"This will affect your tax records and CANNOT be undone.\n\n"
                        f"Are you sure you want to proceed?"
                    )
                    
                    if not messagebox.askyesno("⚠️ Delete All Site Data", warning_msg, icon='warning'):
                        continue
            
            # CASCADE DELETE
            conn = app.db.get_connection()
            c = conn.cursor()
            c.execute("DELETE FROM tax_sessions WHERE site_id = ?", (sid,))
            c.execute("DELETE FROM redemptions WHERE site_id = ?", (sid,))
            c.execute("DELETE FROM purchases WHERE site_id = ?", (sid,))
            c.execute("DELETE FROM site_sessions WHERE site_id = ?", (sid,))
            c.execute("DELETE FROM sites WHERE id = ?", (sid,))
            conn.commit()
            conn.close()
            deleted_count += 1
        
        clear_form()
        refresh_list()
        app.refresh_dropdowns()
        app.refresh_all_views()
        
        if deleted_count > 1:
            messagebox.showinfo("Success", f"Deleted {deleted_count} sites and all associated data")
        elif deleted_count == 1:
            messagebox.showinfo("Success", "Site and all associated data deleted")

    btns = ttk.Frame(form)
    btns.grid(row=1, column=0, columnspan=3, sticky='w', padx=5, pady=5)
    ttk.Button(btns, text="Save", command=smart_save, width=12).pack(side='left', padx=5)
    ttk.Button(btns, text="Delete", command=delete_site, width=12).pack(side='left', padx=5)
    ttk.Button(btns, text="Clear", command=clear_form, width=12).pack(side='left', padx=5)

    list_frame = ttk.LabelFrame(parent, text="Sites", padding=10)
    list_frame.pack(fill='both', expand=True, padx=10, pady=10)
    
    # Add search frame
    search_frame = ttk.Frame(list_frame)
    search_frame.pack(fill='x', padx=5, pady=(0, 5))
    
    # Add export button
    from table_helpers import export_tree_to_csv
    ttk.Button(search_frame, text="📤 Export CSV", 
              command=lambda: export_tree_to_csv(tree, "sites", app.root),
              width=15).pack(side='right', padx=5)

    tree = ttk.Treeview(list_frame, columns=("Name", "SC Rate", "Active"), show="headings", height=15)
    tree.heading("Name", text="Name")
    tree.heading("SC Rate", text="SC Rate")
    tree.heading("Active", text="Active")
    tree.column("Name", width=260)
    tree.column("SC Rate", width=100)
    tree.column("Active", width=100)

    scroll = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    
    # Add SearchableTreeview for sorting and searching
    from table_helpers import SearchableTreeview, enable_multi_select
    searchable = SearchableTreeview(tree, ["Name", "SC Rate", "Active"], search_frame)
    enable_multi_select(tree)

    tree.bind('<Double-Button-1>', on_select)

    refresh_list()

def build_cards_section(app, parent):
    """Build cards management section with list + add/edit/delete (matches Users/Sites)."""
    form = ttk.Frame(parent, padding=10)
    form.pack(fill='x')

    ttk.Label(form, text="Card Name:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
    name_entry = ttk.Entry(form, width=22)
    name_entry.grid(row=0, column=1, sticky='w', padx=5, pady=5)

    ttk.Label(form, text="Cashback %:").grid(row=0, column=2, sticky='w', padx=5, pady=5)
    cb_entry = ttk.Entry(form, width=10)
    cb_entry.grid(row=0, column=3, sticky='w', padx=5, pady=5)

    ttk.Label(form, text="User:").grid(row=0, column=4, sticky='w', padx=5, pady=5)
    user_combo = ttk.Combobox(form, width=18, state='normal')
    enable_excel_autosuggest(user_combo)
    user_combo.grid(row=0, column=5, sticky='w', padx=5, pady=5)

    active_var = tk.IntVar(value=1)
    ttk.Checkbutton(form, text="Active", variable=active_var).grid(row=0, column=6, sticky='w', padx=10, pady=5)

    selected = {"card_id": None}

    def refresh_users():
        conn = app.db.get_connection()
        c = conn.cursor()
        users = [r['name'] for r in c.execute("SELECT name FROM users WHERE active=1 ORDER BY name").fetchall()]
        conn.close()
        user_combo['values'] = users
        # Sync autosuggest master list
        if hasattr(user_combo, '_excel_master'):
            user_combo._excel_master = users
        # DON'T auto-select first user - let user type/choose
    
    # Store on app object so refresh_dropdowns can call it
    app.refresh_card_users = refresh_users

    def clear_form():
        name_entry.delete(0, tk.END)
        cb_entry.delete(0, tk.END)
        user_combo.set('')  # Clear user selection
        active_var.set(1)
        selected["card_id"] = None

    def refresh_list():
        conn = app.db.get_connection()
        c = conn.cursor()
        rows = c.execute(
            """SELECT cards.id, cards.name, cards.cashback_rate, cards.active,
                      users.name as user_name
                 FROM cards
                 LEFT JOIN users ON users.id = cards.user_id
                 ORDER BY cards.name"""
        ).fetchall()
        conn.close()
        
        data = []
        for r in rows:
            values = (r["name"], f'{(r["cashback_rate"] or 0):.2f}', r["user_name"] or "", "Yes" if r["active"] else "No")
            tags = (r["id"],)
            data.append((values, tags))
        
        searchable.set_data(data)

    def on_select(_=None):
        sel = tree.selection()
        if not sel:
            return
        # Check if multiple selected
        if len(sel) > 1:
            messagebox.showwarning("Multiple Selection", 
                "Please select only one card to edit.\n\n"
                "Tip: Use Ctrl+Click or Shift+Click to select multiple items for deletion.")
            return
        cid = tree.item(sel[0])["tags"][0]
        conn = app.db.get_connection()
        c = conn.cursor()
        r = c.execute(
            """SELECT cards.id, cards.name, cards.cashback_rate, cards.user_id, cards.active,
                      users.name as user_name
                 FROM cards
                 LEFT JOIN users ON users.id = cards.user_id
                 WHERE cards.id=?""", (cid,)
        ).fetchone()
        conn.close()
        if not r:
            return
        selected["card_id"] = r["id"]
        name_entry.delete(0, tk.END)
        name_entry.insert(0, r["name"])
        cb_entry.delete(0, tk.END)
        cb_entry.insert(0, str(r["cashback_rate"] or 0))
        refresh_users()
        if r["user_name"]:
            user_combo.set(r["user_name"])
        active_var.set(int(r["active"] or 0))

    def add_card():
        name = name_entry.get().strip()
        cb = cb_entry.get().strip() or "0"
        user_name = user_combo.get().strip()
        if not name or not user_name:
            messagebox.showwarning("Missing", "Fill Card Name and User")
            return
        try:
            cb_val = float(cb)
            if cb_val < 0 or cb_val > 100:
                messagebox.showwarning("Invalid", "Cashback % must be between 0 and 100")
                return
        except ValueError:
            messagebox.showwarning("Invalid", "Cashback % must be a number")
            return

        conn = app.db.get_connection()
        c = conn.cursor()
        try:
            user_id = c.execute("SELECT id FROM users WHERE name=?", (user_name,)).fetchone()["id"]
            c.execute(
                "INSERT INTO cards (name, cashback_rate, user_id, active) VALUES (?, ?, ?, ?)",
                (name, cb_val, user_id, int(active_var.get()))
            )
            conn.commit()
            clear_form()
            refresh_list()
            app.refresh_dropdowns()
            app.refresh_all_views()  # Refresh all views including Reports tab
            messagebox.showinfo("Success", "Card added")
        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            conn.close()

    def update_card():
        if not selected["card_id"]:
            messagebox.showwarning("Select", "Select a card to update")
            return
        name = name_entry.get().strip()
        cb = cb_entry.get().strip() or "0"
        user_name = user_combo.get().strip()
        if not name or not user_name:
            messagebox.showwarning("Missing", "Fill Card Name and User")
            return
        try:
            cb_val = float(cb)
            if cb_val < 0 or cb_val > 100:
                messagebox.showwarning("Invalid", "Cashback % must be between 0 and 100")
                return
        except ValueError:
            messagebox.showwarning("Invalid", "Cashback % must be a number")
            return

        conn = app.db.get_connection()
        c = conn.cursor()
        try:
            user_id = c.execute("SELECT id FROM users WHERE name=?", (user_name,)).fetchone()["id"]
            c.execute(
                "UPDATE cards SET name=?, cashback_rate=?, user_id=?, active=? WHERE id=?",
                (name, cb_val, user_id, int(active_var.get()), selected["card_id"])
            )
            conn.commit()
            refresh_list()
            app.refresh_dropdowns()
            app.refresh_all_views()  # Refresh all views including Reports tab
            messagebox.showinfo("Success", "Card updated")
        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            conn.close()
    
    def smart_save():
        if selected["card_id"]:
            update_card()
        else:
            add_card()

    def delete_card():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select card(s) to delete")
            return
        
        # Check if multiple items selected
        if len(sel) > 1:
            if not messagebox.askyesno("Confirm", f"Delete {len(sel)} cards?"):
                return
        else:
            if not messagebox.askyesno("Confirm", "Delete this card?"):
                return
        
        deleted_count = 0
        error_messages = []
        
        for item in sel:
            cid = tree.item(item)["tags"][0]
            
            # Check for purchases using this card
            conn = app.db.get_connection()
            c = conn.cursor()
            
            c.execute("SELECT COUNT(*) as count FROM purchases WHERE card_id = ?", (cid,))
            purchase_count = c.fetchone()['count']
            
            if purchase_count > 0:
                # Get card name for error message
                c.execute("SELECT name FROM cards WHERE id = ?", (cid,))
                card_row = c.fetchone()
                card_name = card_row['name'] if card_row else f"Card ID {cid}"
                error_messages.append(f"{card_name} has {purchase_count} purchase(s) - mark as Inactive instead")
                conn.close()
                continue
            
            # Empty card - delete it
            c.execute("DELETE FROM cards WHERE id=?", (cid,))
            conn.commit()
            conn.close()
            deleted_count += 1
        
        clear_form()
        refresh_list()
        app.refresh_dropdowns()
        app.refresh_all_views()
        
        if error_messages:
            error_text = "\n".join(error_messages)
            messagebox.showwarning("Partial Success", 
                f"Deleted {deleted_count} card(s).\n\nCannot delete:\n{error_text}")
        else:
            if deleted_count > 1:
                messagebox.showinfo("Success", f"Deleted {deleted_count} cards")
            else:
                messagebox.showinfo("Success", "Card deleted")

    btns = ttk.Frame(form)
    btns.grid(row=1, column=0, columnspan=7, sticky='w', padx=5, pady=5)
    ttk.Button(btns, text="Save", command=smart_save, width=12).pack(side='left', padx=5)
    ttk.Button(btns, text="Delete", command=delete_card, width=12).pack(side='left', padx=5)
    ttk.Button(btns, text="Clear", command=clear_form, width=12).pack(side='left', padx=5)

    list_frame = ttk.LabelFrame(parent, text="Cards", padding=10)
    list_frame.pack(fill='both', expand=True, padx=10, pady=10)
    
    # Add search frame
    search_frame = ttk.Frame(list_frame)
    search_frame.pack(fill='x', padx=5, pady=(0, 5))
    
    # Add export button
    from table_helpers import export_tree_to_csv
    ttk.Button(search_frame, text="📤 Export CSV", 
              command=lambda: export_tree_to_csv(tree, "cards", app.root),
              width=15).pack(side='right', padx=5)

    tree = ttk.Treeview(list_frame, columns=("Name", "Cashback", "User", "Active"), show="headings", height=15)
    tree.heading("Name", text="Name")
    tree.heading("Cashback", text="Cashback %")
    tree.heading("User", text="User")
    tree.heading("Active", text="Active")

    tree.column("Name", width=220)
    tree.column("Cashback", width=110)
    tree.column("User", width=180)
    tree.column("Active", width=80)

    scroll = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    
    # Add SearchableTreeview for sorting and searching
    from table_helpers import SearchableTreeview, enable_multi_select
    searchable = SearchableTreeview(tree, ["Name", "Cashback", "User", "Active"], search_frame)
    enable_multi_select(tree)

    tree.bind('<Double-Button-1>', on_select)

    refresh_users()
    refresh_list()

def build_methods_section(app, parent):
    """Build redemption methods management section with list + add/edit/delete"""
    form = ttk.Frame(parent, padding=10)
    form.pack(fill='x')

    ttk.Label(form, text="Method Name:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
    method_entry = ttk.Entry(form, width=30)
    method_entry.grid(row=0, column=1, sticky='w', padx=5, pady=5)
    
    ttk.Label(form, text="User:").grid(row=0, column=2, sticky='w', padx=5, pady=5)
    user_var = tk.StringVar()
    user_combo = ttk.Combobox(form, textvariable=user_var, width=20)
    user_combo.grid(row=0, column=3, sticky='w', padx=5, pady=5)
    
    active_var = tk.BooleanVar(value=True)
    active_check = ttk.Checkbutton(form, text="Active", variable=active_var)
    active_check.grid(row=0, column=4, sticky='w', padx=5, pady=5)
    
    def refresh_users():
        """Populate user dropdown"""
        conn = app.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT name FROM users WHERE active = 1 ORDER BY name")
        users = [r['name'] for r in c.fetchall()]
        conn.close()
        user_combo['values'] = users
        if users:
            user_combo.set(users[0])  # Default to first user
    
    refresh_users()
    
    # Add Excel-like autosuggest to user dropdown
    enable_excel_autosuggest(user_combo)

    selected = {"method_id": None}

    def clear_form():
        method_entry.delete(0, tk.END)
        # Reset to first user
        conn = app.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT name FROM users WHERE active = 1 ORDER BY name LIMIT 1")
        first_user = c.fetchone()
        conn.close()
        if first_user:
            user_var.set(first_user['name'])
        active_var.set(True)
        selected["method_id"] = None

    def add_method():
        name = method_entry.get().strip()
        if not name:
            messagebox.showwarning("Missing Name", "Please enter a method name")
            return
        
        # User is now REQUIRED
        if not user_var.get():
            messagebox.showwarning("Missing User", "Please select a user for this redemption method")
            return
        
        # Get user_id
        conn = app.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE name = ?", (user_var.get(),))
        user_row = c.fetchone()
        
        if not user_row:
            conn.close()
            messagebox.showerror("Error", "Selected user not found")
            return
        
        user_id = user_row['id']
        
        try:
            c.execute("INSERT INTO redemption_methods (name, user_id, active) VALUES (?, ?, ?)", 
                     (name, user_id, int(active_var.get())))
            conn.commit()
            clear_form()
            refresh_list()
            app.refresh_dropdowns()
            app.refresh_all_views()
            messagebox.showinfo("Success", "Method added")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add method: {str(e)}")
        finally:
            conn.close()

    def update_method():
        mid = selected["method_id"]
        if not mid:
            return
        name = method_entry.get().strip()
        if not name:
            messagebox.showwarning("Missing Name", "Please enter a method name")
            return
        
        # User is now REQUIRED
        if not user_var.get():
            messagebox.showwarning("Missing User", "Please select a user for this redemption method")
            return
        
        # Get user_id
        conn = app.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE name = ?", (user_var.get(),))
        user_row = c.fetchone()
        
        if not user_row:
            conn.close()
            messagebox.showerror("Error", "Selected user not found")
            return
        
        user_id = user_row['id']
        
        try:
            c.execute("UPDATE redemption_methods SET name=?, user_id=?, active=? WHERE id=?", 
                     (name, user_id, int(active_var.get()), mid))
            conn.commit()
            clear_form()
            refresh_list()
            app.refresh_dropdowns()
            app.refresh_all_views()
            messagebox.showinfo("Success", "Method updated")
        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            conn.close()

    def smart_save():
        if selected["method_id"]:
            update_method()
        else:
            add_method()
    
    def delete_selected():
        sel = method_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select method(s) to delete")
            return
        
        # Check if multiple items selected
        if len(sel) > 1:
            if not messagebox.askyesno("Confirm", f"Delete {len(sel)} redemption methods?"):
                return
        else:
            if not messagebox.askyesno("Confirm", "Delete this method?"):
                return
        
        deleted_count = 0
        error_messages = []
        
        for item in sel:
            mid = method_tree.item(item)["tags"][0]
            
            # Check for redemptions using this method
            conn = app.db.get_connection()
            c = conn.cursor()
            
            c.execute("SELECT COUNT(*) as count FROM redemptions WHERE redemption_method_id = ?", (mid,))
            redemption_count = c.fetchone()['count']
            
            if redemption_count > 0:
                # Get method name for error message
                c.execute("SELECT name FROM redemption_methods WHERE id = ?", (mid,))
                method_row = c.fetchone()
                method_name = method_row['name'] if method_row else f"Method ID {mid}"
                error_messages.append(f"{method_name} has {redemption_count} redemption(s) - mark as Inactive instead")
                conn.close()
                continue
            
            # Empty method - delete it
            c.execute("DELETE FROM redemption_methods WHERE id=?", (mid,))
            conn.commit()
            conn.close()
            deleted_count += 1
        
        clear_form()
        refresh_list()
        app.refresh_dropdowns()
        app.refresh_all_views()
        
        if error_messages:
            error_text = "\n".join(error_messages)
            messagebox.showwarning("Partial Success", 
                f"Deleted {deleted_count} method(s).\n\nCannot delete:\n{error_text}")
        else:
            if deleted_count > 1:
                messagebox.showinfo("Success", f"Deleted {deleted_count} methods")
            else:
                messagebox.showinfo("Success", "Method deleted")

    # Buttons on separate row (matching other sections)
    btns = ttk.Frame(form)
    btns.grid(row=1, column=0, columnspan=2, sticky='w', padx=5, pady=5)
    ttk.Button(btns, text="Save", command=smart_save, width=12).pack(side='left', padx=5)
    ttk.Button(btns, text="Delete", command=delete_selected, width=12).pack(side='left', padx=5)
    ttk.Button(btns, text="Clear", command=clear_form, width=12).pack(side='left', padx=5)

    list_frame = ttk.Frame(parent, padding=10)
    list_frame.pack(fill='both', expand=True)
    
    # Add search frame
    search_frame = ttk.Frame(list_frame)
    search_frame.pack(fill='x', padx=5, pady=(0, 5))
    
    # Add export button
    from table_helpers import export_tree_to_csv
    ttk.Button(search_frame, text="📤 Export CSV", 
              command=lambda: export_tree_to_csv(method_tree, "redemption_methods", app.root),
              width=15).pack(side='right', padx=5)

    method_tree = ttk.Treeview(list_frame, columns=("Name", "User", "Active"), show="headings", height=12)
    method_tree.heading("Name", text="Name")
    method_tree.heading("User", text="User")
    method_tree.heading("Active", text="Active")
    method_tree.column("Name", width=250)
    method_tree.column("User", width=150)
    method_tree.column("Active", width=80)

    scroll = ttk.Scrollbar(list_frame, orient='vertical', command=method_tree.yview)
    method_tree.configure(yscrollcommand=scroll.set)
    method_tree.pack(side='left', fill='both', expand=True)
    scroll.pack(side='right', fill='y')
    
    # Add SearchableTreeview for sorting and searching
    from table_helpers import SearchableTreeview, enable_multi_select
    searchable = SearchableTreeview(method_tree, ["Name", "User", "Active"], search_frame)
    enable_multi_select(method_tree)

    def refresh_list():
        conn = app.db.get_connection()
        c = conn.cursor()
        c.execute('''
            SELECT rm.id, rm.name, rm.active, u.name as user_name
            FROM redemption_methods rm
            LEFT JOIN users u ON rm.user_id = u.id
            ORDER BY rm.name
        ''')
        
        data = []
        for row in c.fetchall():
            active_text = "Yes" if row["active"] else "No"
            user_text = row["user_name"] or "(None)"  # Show (None) for legacy methods without user
            values = (row["name"], user_text, active_text)
            tags = (str(row["id"]),)
            data.append((values, tags))
        
        conn.close()
        searchable.set_data(data)

    def on_select(_evt=None):
        sel = method_tree.selection()
        if not sel:
            return
        # Check if multiple selected
        if len(sel) > 1:
            messagebox.showwarning("Multiple Selection", 
                "Please select only one method to edit.\n\n"
                "Tip: Use Ctrl+Click or Shift+Click to select multiple items for deletion.")
            return
        mid = method_tree.item(sel[0])["tags"][0]
        conn = app.db.get_connection()
        c = conn.cursor()
        c.execute('''
            SELECT rm.id, rm.name, rm.active, u.name as user_name
            FROM redemption_methods rm
            LEFT JOIN users u ON rm.user_id = u.id
            WHERE rm.id=?
        ''', (mid,))
        row = c.fetchone()
        conn.close()
        if not row:
            return
        selected["method_id"] = row["id"]
        method_entry.delete(0, tk.END)
        method_entry.insert(0, row["name"])
        
        # Set user - if legacy method has no user, require selection for update
        if row["user_name"]:
            user_var.set(row["user_name"])
        else:
            # Legacy method without user - show warning and require user selection
            messagebox.showwarning("User Required", 
                "This method was created without a user assignment.\n"
                "Please select a user before saving.")
            # Set to first available user
            conn = app.db.get_connection()
            c = conn.cursor()
            c.execute("SELECT name FROM users WHERE active = 1 ORDER BY name LIMIT 1")
            first_user = c.fetchone()
            conn.close()
            if first_user:
                user_var.set(first_user['name'])
        
        active_var.set(bool(row["active"]))

    method_tree.bind('<Double-Button-1>', on_select)

    # Populate list on initial build
    refresh_list()


def build_verify_section(app, parent):
    """Build database verification tool"""
    main_frame = ttk.Frame(parent, padding=20)
    main_frame.pack(fill='both', expand=True)
    
    # Header
    header = ttk.Label(main_frame, 
                      text="🎯 Database Integrity Verification",
                      font=('Arial', 14, 'bold'))
    header.pack(pady=(0, 10))
    
    info = ttk.Label(main_frame,
                    text="Run checks to verify your database is healthy and consistent.",
                    font=('Arial', 10),
                    foreground='gray')
    info.pack(pady=(0, 20))
    
    # Run Verification Button
    verify_btn = ttk.Button(main_frame, 
                           text="▶ Run Verification",
                           command=lambda: run_verification(app, results_text),
                           width=20)
    verify_btn.pack(pady=(0, 20))
    
    # Results text area
    results_frame = ttk.LabelFrame(main_frame, text="Results", padding=10)
    results_frame.pack(fill='both', expand=True)
    
    results_text = tk.Text(results_frame, height=20, width=80, font=('Courier', 10), wrap='word')
    results_text.pack(side='left', fill='both', expand=True)
    
    scroll = ttk.Scrollbar(results_frame, orient='vertical', command=results_text.yview)
    results_text.configure(yscrollcommand=scroll.set)
    scroll.pack(side='right', fill='y')
    
    results_text.insert('1.0', "Click 'Run Verification' to check database integrity...")
    results_text.config(state='disabled')


def run_verification(app, results_text):
    """Run all database integrity checks"""
    results_text.config(state='normal')
    results_text.delete('1.0', tk.END)
    results_text.insert('1.0', "Running verification checks...\n\n")
    results_text.update()
    
    conn = app.db.get_connection()
    c = conn.cursor()
    
    issues = []
    checks_passed = 0
    
    # CHECK 1: Orphaned Redemptions
    results_text.insert(tk.END, "Checking for orphaned redemptions... ")
    results_text.update()
    
    c.execute('''
        SELECT r.id, r.redemption_date, r.amount, r.site_session_id
        FROM redemptions r
        LEFT JOIN site_sessions ss ON r.site_session_id = ss.id
        WHERE r.site_session_id IS NOT NULL AND ss.id IS NULL
    ''')
    orphaned_redemptions = c.fetchall()
    
    if orphaned_redemptions:
        issues.append(f"⚠️ Orphaned Redemptions: {len(orphaned_redemptions)}")
        for r in orphaned_redemptions[:5]:  # Show first 5
            issues.append(f"  - Redemption #{r['id']} (${r['amount']:.2f} on {r['redemption_date']}) points to non-existent session #{r['site_session_id']}")
        if len(orphaned_redemptions) > 5:
            issues.append(f"  ... and {len(orphaned_redemptions) - 5} more")
        results_text.insert(tk.END, f"âŒ FOUND {len(orphaned_redemptions)}\n")
    else:
        results_text.insert(tk.END, "✓ PASS\n")
        checks_passed += 1
    results_text.update()
    
    # CHECK 2: Orphaned Tax Sessions
    results_text.insert(tk.END, "Checking for orphaned tax sessions... ")
    results_text.update()
    
    c.execute('''
        SELECT ts.id, ts.session_date, ts.redemption_id
        FROM tax_sessions ts
        LEFT JOIN redemptions r ON ts.redemption_id = r.id
        WHERE r.id IS NULL
    ''')
    orphaned_tax = c.fetchall()
    
    if orphaned_tax:
        issues.append(f"⚠️ Orphaned Tax Sessions: {len(orphaned_tax)}")
        for t in orphaned_tax[:5]:
            issues.append(f"  - Tax session #{t['id']} points to non-existent redemption #{t['redemption_id']}")
        if len(orphaned_tax) > 5:
            issues.append(f"  ... and {len(orphaned_tax) - 5} more")
        results_text.insert(tk.END, f"âŒ FOUND {len(orphaned_tax)}\n")
    else:
        results_text.insert(tk.END, "✓ PASS\n")
        checks_passed += 1
    results_text.update()
    
    # CHECK 3: Session Total Mismatches
    results_text.insert(tk.END, "Checking session totals... ")
    results_text.update()
    
    c.execute('''
        SELECT ss.id, ss.total_buyin, ss.total_redeemed,
               COALESCE(SUM(p.amount), 0) as actual_buyin,
               COALESCE(SUM(r.amount), 0) as actual_redeemed
        FROM site_sessions ss
        LEFT JOIN purchases p ON p.site_id = ss.site_id AND p.user_id = ss.user_id
        LEFT JOIN redemptions r ON r.site_session_id = ss.id
        GROUP BY ss.id
        HAVING ABS(ss.total_buyin - actual_buyin) > 0.01 OR ABS(ss.total_redeemed - actual_redeemed) > 0.01
    ''')
    mismatched_sessions = c.fetchall()
    
    if mismatched_sessions:
        issues.append(f"⚠️ Session Total Mismatches: {len(mismatched_sessions)}")
        for s in mismatched_sessions[:5]:
            issues.append(f"  - Session #{s['id']}: Recorded buy-in ${s['total_buyin']:.2f}, actual ${s['actual_buyin']:.2f}; "
                         f"Recorded redeemed ${s['total_redeemed']:.2f}, actual ${s['actual_redeemed']:.2f}")
        if len(mismatched_sessions) > 5:
            issues.append(f"  ... and {len(mismatched_sessions) - 5} more")
        results_text.insert(tk.END, f"âŒ FOUND {len(mismatched_sessions)}\n")
    else:
        results_text.insert(tk.END, "✓ PASS\n")
        checks_passed += 1
    results_text.update()
    
    # CHECK 4: Negative Remaining Amounts
    results_text.insert(tk.END, "Checking for negative balances... ")
    results_text.update()
    
    c.execute('''
        SELECT id, purchase_date, amount, remaining_amount
        FROM purchases
        WHERE remaining_amount < 0
    ''')
    negative_remaining = c.fetchall()
    
    if negative_remaining:
        issues.append(f"⚠️ Negative Remaining Amounts: {len(negative_remaining)}")
        for p in negative_remaining[:5]:
            issues.append(f"  - Purchase #{p['id']} (${p['amount']:.2f} on {p['purchase_date']}) has remaining: ${p['remaining_amount']:.2f}")
        if len(negative_remaining) > 5:
            issues.append(f"  ... and {len(negative_remaining) - 5} more")
        results_text.insert(tk.END, f"âŒ FOUND {len(negative_remaining)}\n")
    else:
        results_text.insert(tk.END, "✓ PASS\n")
        checks_passed += 1
    results_text.update()
    
    # CHECK 5: FIFO Math
    results_text.insert(tk.END, "Checking FIFO math... ")
    results_text.update()
    
    c.execute('SELECT COALESCE(SUM(amount), 0) as total_purchased FROM purchases')
    total_purchased = float(c.fetchone()['total_purchased'])
    
    c.execute('SELECT COALESCE(SUM(cost_basis), 0) as total_consumed FROM tax_sessions')
    total_consumed = float(c.fetchone()['total_consumed'])
    
    c.execute('SELECT COALESCE(SUM(remaining_amount), 0) as total_remaining FROM purchases')
    total_remaining = float(c.fetchone()['total_remaining'])
    
    expected_remaining = total_purchased - total_consumed
    fifo_diff = abs(total_remaining - expected_remaining)
    
    if fifo_diff > 0.01:  # Allow 1 cent tolerance for floating point
        issues.append(f"⚠️ FIFO Math Error: Total purchased ${total_purchased:.2f}, consumed ${total_consumed:.2f}, "
                     f"but remaining is ${total_remaining:.2f} (expected ${expected_remaining:.2f})")
        results_text.insert(tk.END, f"âŒ DIFFERENCE: ${fifo_diff:.2f}\n")
    else:
        results_text.insert(tk.END, "✓ PASS\n")
        checks_passed += 1
    results_text.update()
    
    # CHECK 6: Missing Tax Sessions
    results_text.insert(tk.END, "Checking for missing tax sessions... ")
    results_text.update()
    
    c.execute('''
        SELECT r.id, r.redemption_date, r.amount
        FROM redemptions r
        LEFT JOIN tax_sessions ts ON r.id = ts.redemption_id
        WHERE r.is_free_sc = 0 AND ts.id IS NULL
    ''')
    missing_tax = c.fetchall()
    
    if missing_tax:
        issues.append(f"⚠️ Missing Tax Sessions: {len(missing_tax)}")
        for r in missing_tax[:5]:
            issues.append(f"  - Redemption #{r['id']} (${r['amount']:.2f} on {r['redemption_date']}) has no tax session")
        if len(missing_tax) > 5:
            issues.append(f"  ... and {len(missing_tax) - 5} more")
        results_text.insert(tk.END, f"âŒ FOUND {len(missing_tax)}\n")
    else:
        results_text.insert(tk.END, "✓ PASS\n")
        checks_passed += 1
    results_text.update()
    
    conn.close()
    
    # Summary
    results_text.insert(tk.END, "\n" + "="*80 + "\n")
    results_text.insert(tk.END, "VERIFICATION COMPLETE\n")
    results_text.insert(tk.END, "="*80 + "\n\n")
    
    total_checks = 6
    if len(issues) == 0:
        results_text.insert(tk.END, f"✓ ALL CHECKS PASSED ({total_checks}/{total_checks})\n\n")
        results_text.insert(tk.END, "Your database is healthy and consistent!")
    else:
        results_text.insert(tk.END, f"⚠️ Issues Found: {len(issues)}\n")
        results_text.insert(tk.END, f"✓ Checks Passed: {checks_passed}/{total_checks}\n\n")
        results_text.insert(tk.END, "ISSUES DETAILS:\n")
        results_text.insert(tk.END, "-" * 80 + "\n")
        for issue in issues:
            results_text.insert(tk.END, issue + "\n")
    
    results_text.config(state='disabled')
    results_text.see('1.0')  # Scroll to top


def build_tools_section(app, parent):
    """Build Tools section with Import CSV and Database Tools"""
    
    # Create scrollable frame
    import tkinter as tk
    canvas = tk.Canvas(parent)
    scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)
    
    def on_frame_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))
    
    def on_canvas_configure(event):
        # Set the canvas window width to match canvas width
        canvas.itemconfig(canvas_window, width=event.width)
    
    scrollable_frame.bind("<Configure>", on_frame_configure)
    canvas.bind("<Configure>", on_canvas_configure)
    
    canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    
    main_frame = ttk.Frame(scrollable_frame, padding=20)
    main_frame.pack(fill='both', expand=True)
    
    # === IMPORT CSV SECTION ===
    import_section = ttk.LabelFrame(main_frame, text="Import CSV", padding=15)
    import_section.pack(fill='x', pady=(0, 20))
    
    ttk.Label(import_section, text="Import Purchases & Redemptions", 
             font=('Arial', 11, 'bold')).pack(anchor='w', pady=(0, 10))
    
    # Purchases
    purchase_frame = ttk.Frame(import_section)
    purchase_frame.pack(fill='x', pady=5)
    ttk.Button(purchase_frame, text="📂 Upload Purchases CSV", 
              command=lambda: app.import_csv('purchases')).pack(side='left', padx=(0, 10))
    ttk.Label(purchase_frame, text="Import purchase history",
             font=('Arial', 9), foreground='gray').pack(side='left')
    
    # Redemptions
    redemption_frame = ttk.Frame(import_section)
    redemption_frame.pack(fill='x', pady=5)
    ttk.Button(redemption_frame, text="📂 Upload Redemptions CSV", 
              command=lambda: app.import_csv('redemptions')).pack(side='left', padx=(0, 10))
    ttk.Label(redemption_frame, text="Import redemption history",
             font=('Arial', 9), foreground='gray').pack(side='left')
    
    # Sessions
    session_frame = ttk.Frame(import_section)
    session_frame.pack(fill='x', pady=5)
    ttk.Button(session_frame, text="📂 Upload Sessions CSV", 
              command=lambda: app.import_csv('sessions')).pack(side='left', padx=(0, 10))
    ttk.Label(session_frame, text="Import game session history",
             font=('Arial', 9), foreground='gray').pack(side='left')
    
    # Process button (prominent)
    ttk.Separator(import_section, orient='horizontal').pack(fill='x', pady=10)
    
    process_btn = ttk.Button(import_section, 
                            text="🔄 Process Imported Data (Purchases, Redemptions, Sessions)",
                            command=app.process_imported_transactions)
    process_btn.pack(anchor='w', ipady=5, pady=5)
    
    ttk.Label(import_section, 
             text="⚠️ Click after uploading to calculate cost basis and create tax sessions",
             font=('Arial', 8), foreground='blue').pack(anchor='w', pady=(5, 10))
    
    # Expenses (separate)
    ttk.Separator(import_section, orient='horizontal').pack(fill='x', pady=10)
    
    ttk.Label(import_section, text="Import Expenses", 
             font=('Arial', 11, 'bold')).pack(anchor='w', pady=(10, 10))
    
    expense_frame = ttk.Frame(import_section)
    expense_frame.pack(fill='x', pady=5)
    ttk.Button(expense_frame, text="📂 Upload Expenses CSV", 
              command=lambda: app.import_csv('expenses')).pack(side='left', padx=(0, 10))
    ttk.Label(expense_frame, text="Import business expenses",
             font=('Arial', 9), foreground='gray').pack(side='left')
    
    # Download Templates
    ttk.Separator(import_section, orient='horizontal').pack(fill='x', pady=10)
    
    ttk.Label(import_section, text="Download CSV Templates", 
             font=('Arial', 11, 'bold')).pack(anchor='w', pady=(10, 10))
    
    template_frame = ttk.Frame(import_section)
    template_frame.pack(fill='x', pady=5)
    
    ttk.Button(template_frame, text="Purchases Template", 
              command=lambda: app.download_template('purchases')).pack(side='left', padx=(0, 10))
    ttk.Button(template_frame, text="Redemptions Template", 
              command=lambda: app.download_template('redemptions')).pack(side='left', padx=(0, 10))
    ttk.Button(template_frame, text="Sessions Template", 
              command=lambda: app.download_template('sessions')).pack(side='left', padx=(0, 10))
    ttk.Button(template_frame, text="Expenses Template", 
              command=lambda: app.download_template('expenses')).pack(side='left')
    
    # === DATABASE TOOLS SECTION ===
    db_tools_section = ttk.LabelFrame(main_frame, text="Database Tools", padding=15)
    db_tools_section.pack(fill='x', pady=(0, 20))
    
    # Backup & Restore
    backup_frame = ttk.LabelFrame(db_tools_section, text="Backup & Restore", padding=10)
    backup_frame.pack(fill='x', pady=(0, 10))
    
    ttk.Label(backup_frame, 
             text="Create backups and restore from previous backups",
             font=('Arial', 9), foreground='gray').pack(anchor='w', pady=(0, 10))
    
    btn_row = ttk.Frame(backup_frame)
    btn_row.pack(anchor='w')
    
    ttk.Button(btn_row, text="💾 Backup Database", 
              command=app.backup_database).pack(side='left', padx=(0, 10))
    ttk.Button(btn_row, text="📂 Restore Database", 
              command=app.restore_database).pack(side='left')
    
    # Refactor Database
    refactor_frame = ttk.LabelFrame(db_tools_section, text="Refactor Database", padding=10)
    refactor_frame.pack(fill='x', pady=(0, 10))
    
    ttk.Label(refactor_frame, 
             text="Recalculate all sessions and cost basis from scratch.\n"
                  "Uses the same logic as manual entry and CSV import processing.",
             font=('Arial', 9), foreground='gray', wraplength=500, justify='left').pack(anchor='w', pady=(0, 10))
    
    ttk.Button(refactor_frame, text="♻️ Refactor Database", 
              command=app.refactor_database).pack(anchor='w')
    
    # Recalculate Tools
    recalc_frame = ttk.LabelFrame(db_tools_section, text="🔄 Recalculate Tax Data", padding=10)
    recalc_frame.pack(fill='x', pady=(0, 10))
    
    ttk.Label(recalc_frame, 
             text="Fix tax calculations after importing data or making bulk changes.",
             font=('Arial', 9), foreground='gray', wraplength=500, justify='left').pack(anchor='w', pady=(0, 10))
    
    # Combined button (recommended)
    ttk.Button(recalc_frame, text="🔄 Recalculate Everything (Recommended)", 
              command=app.recalculate_everything).pack(anchor='w', pady=(0, 10))
    
    ttk.Label(recalc_frame, 
             text="Or recalculate specific items:",
             font=('Arial', 9), foreground='gray').pack(anchor='w', pady=(0, 5))
    
    ttk.Button(recalc_frame, text="🎯 Recalculate Game Sessions Only", 
              command=app.recalculate_game_sessions).pack(anchor='w', pady=(0, 5))
    
    ttk.Button(recalc_frame, text="💰 Recalculate Redemptions (FIFO) Only", 
              command=app.recalculate_redemptions).pack(anchor='w')
    
    # Reset Database
    reset_frame = ttk.LabelFrame(db_tools_section, text="⚠️ Reset Database", padding=10)
    reset_frame.pack(fill='x', pady=(0, 10))
    reset_frame.configure(relief='solid', borderwidth=2)
    
    ttk.Label(reset_frame, 
             text="Delete ALL transaction data and start fresh.\n"
                  "Users, Sites, Cards, and Methods will be preserved.\n"
                  "This CANNOT be undone!",
             font=('Arial', 9), foreground='red', wraplength=500, justify='left').pack(anchor='w', pady=(0, 10))
    
    ttk.Button(reset_frame, text="🗝️ Reset Database", 
              command=app.reset_database).pack(anchor='w')


# ============================================================================
# GAME SESSIONS TAB
# ============================================================================

def build_game_sessions_tab(app):
    """Build game sessions tab with inline form for data entry"""
    
    # Date filter at top
    create_date_filter_bar(
        app.game_sessions_tab,
        app,
        'gs_filter_start',
        'gs_filter_end',
        lambda: app.refresh_game_sessions()
    )
    
    main_frame = ttk.Frame(app.game_sessions_tab, padding=10)
    main_frame.pack(fill='both', expand=True)
    
    # ========================================================================
    # FORM SECTION
    # ========================================================================
    
    form_section = ttk.LabelFrame(main_frame, text="📝 Session Entry", padding=10)
    form_section.pack(fill='x', pady=(0, 10))
    
    form = ttk.Frame(form_section)
    form.pack(fill='x')
    
    # Configure grid columns for consistent width
    for i in range(6):
        form.columnconfigure(i, weight=1)
    
    # Row 0: Date, Time, Site
    ttk.Label(form, text="Date:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
    app.gs_date = ttk.Entry(form, width=12)
    from datetime import date
    app.gs_date.insert(0, date.today().strftime("%Y-%m-%d"))
    app.gs_date.grid(row=0, column=1, sticky='w', padx=5, pady=5)
    
    ttk.Label(form, text="Start Time:").grid(row=0, column=2, sticky='w', padx=5, pady=5)
    
    time_frame = ttk.Frame(form)
    time_frame.grid(row=0, column=3, sticky='w', padx=5, pady=5)
    
    app.gs_start_time = ttk.Entry(time_frame, width=10)
    from datetime import datetime
    app.gs_start_time.insert(0, datetime.now().strftime("%H:%M:%S"))
    app.gs_start_time.pack(side='left')
    
    def set_gs_start_time_now():
        from datetime import datetime
        app.gs_start_time.delete(0, tk.END)
        app.gs_start_time.insert(0, datetime.now().strftime("%H:%M:%S"))
    
    ttk.Button(time_frame, text="Now", width=5, command=set_gs_start_time_now).pack(side='left', padx=2)
    
    ttk.Label(form, text="Site:").grid(row=0, column=4, sticky='w', padx=5, pady=5)
    app.gs_site = ttk.Combobox(form, width=18, state='normal')
    enable_excel_autosuggest(app.gs_site)
    app.gs_site.grid(row=0, column=5, sticky='w', padx=5, pady=5)
    
    # Row 1: User, Game Type, Starting SC
    ttk.Label(form, text="User:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
    app.gs_user = ttk.Combobox(form, width=18, state='normal')
    enable_excel_autosuggest(app.gs_user)
    app.gs_user.grid(row=1, column=1, sticky='w', padx=5, pady=5)
    
    ttk.Label(form, text="Game Type:").grid(row=1, column=2, sticky='w', padx=5, pady=5)
    app.gs_game_type = ttk.Combobox(form, width=18, state='normal')
    app.gs_game_type['values'] = ['Slots', 'Table Games', 'Poker', 'Live Dealer', 'Sports', 'Other']
    app.gs_game_type.set('')  # Start blank
    enable_excel_autosuggest(app.gs_game_type)
    app.gs_game_type.grid(row=1, column=3, sticky='w', padx=5, pady=5)
    
    ttk.Label(form, text="Starting Total SC:").grid(row=1, column=4, sticky='w', padx=5, pady=5)
    app.gs_starting_sc = ttk.Entry(form, width=12)
    app.gs_starting_sc.grid(row=1, column=5, sticky='w', padx=5, pady=5)
    
    ttk.Label(form, text="Starting Redeemable:").grid(row=1, column=6, sticky='w', padx=5, pady=5)
    app.gs_starting_redeemable = ttk.Entry(form, width=12)
    app.gs_starting_redeemable.grid(row=1, column=7, sticky='w', padx=5, pady=5)
    
    # Auto-fill redeemable = total by default
    def sync_redeemable(*args):
        """Auto-fill redeemable with total if empty"""
        if app.gs_starting_sc.get() and not app.gs_starting_redeemable.get():
            app.gs_starting_redeemable.delete(0, tk.END)
            app.gs_starting_redeemable.insert(0, app.gs_starting_sc.get())
    
    app.gs_starting_sc.bind('<FocusOut>', sync_redeemable)
    
    # Row 2: Freebie detection info (read-only label)
    app.gs_freebie_label = ttk.Label(form, text="", foreground='blue', wraplength=600)
    app.gs_freebie_label.grid(row=2, column=0, columnspan=8, sticky='w', padx=5, pady=5)
    
    # Bind freebie detection to starting SC changes
    def check_freebies(*args):
        """Check for freebies when starting SC is entered"""
        try:
            if not app.gs_site.get() or not app.gs_user.get() or not app.gs_starting_sc.get():
                app.gs_freebie_label.config(text="")
                return
            
            starting_sc = float(app.gs_starting_sc.get())
            
            # Get site and user IDs
            conn = app.db.get_connection()
            c = conn.cursor()
            c.execute("SELECT id FROM sites WHERE name = ?", (app.gs_site.get(),))
            site_row = c.fetchone()
            if not site_row:
                conn.close()
                return
            site_id = site_row['id']
            
            c.execute("SELECT id FROM users WHERE name = ?", (app.gs_user.get(),))
            user_row = c.fetchone()
            if not user_row:
                conn.close()
                return
            user_id = user_row['id']
            conn.close()
            
            # Detect freebies
            freebies_sc, freebies_dollar, last_balance = app.session_mgr.detect_freebies(
                site_id, user_id, starting_sc,
                session_date=app.gs_date.get().strip() or None,
                session_time=app.gs_start_time.get().strip() or None
            )
            
            if freebies_dollar > 0:  # Positive freebies
                app.gs_freebie_label.config(
                    text=f"+ Detected {freebies_sc:.2f} SC in freebies (${freebies_dollar:.2f}) - will be taxed when session ends.",
                    foreground='green'
                )
            elif freebies_dollar < 0:  # Negative (missing balance)
                app.gs_freebie_label.config(
                    text=f"- WARNING: Starting balance is ${abs(freebies_dollar):.2f} LESS than expected! You may have forgotten to record a redemption or loss.",
                    foreground='red'
                )
            else:  # Exactly zero difference
                if last_balance is None:
                    # First session for this site/user
                    app.gs_freebie_label.config(
                        text=f"First session - {starting_sc:.2f} SC will be taxed when session ends.",
                        foreground='blue'
                    )
                else:
                    # Continuing from prior session
                    app.gs_freebie_label.config(
                        text=f"No change from expected (last balance: {last_balance:.2f} SC)",
                        foreground='gray'
                    )
        except:
            app.gs_freebie_label.config(text="")
    
    app.gs_starting_sc.bind('<KeyRelease>', check_freebies)
    app.gs_site.bind('<<ComboboxSelected>>', check_freebies)
    app.gs_user.bind('<<ComboboxSelected>>', check_freebies)
    
    # Row 3: Notes
    ttk.Label(form, text="Notes:").grid(row=3, column=0, sticky='nw', padx=5, pady=5)
    app.gs_notes = tk.Text(form, height=2, width=50, wrap='word')
    app.gs_notes.grid(row=3, column=1, columnspan=5, sticky='ew', padx=5, pady=5)
    
    # Row 4: Buttons
    btn_frame = ttk.Frame(form)
    btn_frame.grid(row=4, column=0, columnspan=6, pady=10)
    
    # Start/Edit button (text changes based on edit mode)
    app.gs_save_btn = ttk.Button(btn_frame, text="Start Session", 
                                  command=app.save_game_session_start, width=15)
    app.gs_save_btn.pack(side='left', padx=5)
    
    ttk.Button(btn_frame, text="End Session", command=app.save_game_session_end, width=15).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="Edit Closed", command=app.edit_closed_session_full, width=12).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="Delete", command=app.delete_game_session, width=12).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="Clear", command=app.clear_game_session_form, width=12).pack(side='left', padx=5)
    
    # Active sessions indicator
    app.active_sessions_label = ttk.Label(btn_frame, text="Active Sessions: 0", 
                                          font=('Arial', 9, 'bold'), foreground='gray')
    app.active_sessions_label.pack(side='right', padx=10)
    
    # ========================================================================
    # BOTTOM: TABLE SECTION
    # ========================================================================
    
    table_section = ttk.Frame(main_frame)
    table_section.pack(fill='both', expand=True)
    
    # Search frame
    search_frame = ttk.Frame(table_section)
    search_frame.pack(fill='x', pady=(0, 5))
    
    # Export button
    button_row = ttk.Frame(table_section)
    button_row.pack(fill='x', pady=(0, 5))
    
    from table_helpers import export_tree_to_csv
    ttk.Button(button_row, text="📤 Export CSV", 
              command=lambda: export_tree_to_csv(app.gs_tree, "game_sessions", app.root),
              width=15).pack(side='right', padx=5)
    
    # Tree
    tree_frame = ttk.Frame(table_section)
    tree_frame.pack(fill='both', expand=True)
    
    cols = ('Date', 'Time', 'Site', 'User', 'Game Type', 'Duration', 'Start Total',
            'End Total', 'Start Redeem', 'End Redeem', 'Δ Total', 'Δ Redeem',
            'Basis Consumed', 'Net P/L', 'Status', 'Notes')
    
    app.gs_tree = ttk.Treeview(tree_frame, columns=cols, show='headings', height=15)
    
    for col in cols:
        app.gs_tree.heading(col, text=col)
        if col == 'Status':
            app.gs_tree.column(col, width=70)
        elif col == 'Notes':
            app.gs_tree.column(col, width=60)
        elif col in ('Net P/L', 'Basis Consumed'):
            app.gs_tree.column(col, width=110)
        elif col in ('Start Total', 'End Total', 'Start Redeem', 'End Redeem', 'Δ Total', 'Δ Redeem'):
            app.gs_tree.column(col, width=95)
        elif col in ('Time', 'Duration'):
            app.gs_tree.column(col, width=85)
        elif col in ('Site', 'User', 'Game Type'):
            app.gs_tree.column(col, width=100)
        else:
            app.gs_tree.column(col, width=90)

    scroll = ttk.Scrollbar(tree_frame, orient='vertical', command=app.gs_tree.yview)
    app.gs_tree.configure(yscrollcommand=scroll.set)

    app.gs_tree.pack(side='left', fill='both', expand=True)
    scroll.pack(side='right', fill='y')
    
    # Double-click to edit
    def on_double_click(event):
        app.edit_game_session()
        return 'break'
    
    app.gs_tree.bind('<Double-Button-1>', on_double_click)
    
    # Initialize searchable
    from table_helpers import SearchableTreeview
    app.gs_searchable = SearchableTreeview(app.gs_tree, cols, search_frame)
    
    # Color tags
    app.gs_tree.tag_configure('win', foreground='green')
    app.gs_tree.tag_configure('loss', foreground='red')
    app.gs_tree.tag_configure('active', foreground='blue')
    
    # Store edit ID
    app.gs_edit_id = None



# ============================================================================
# DAILY SESSIONS TAB
# ============================================================================

def build_daily_tax_tab(app):
    """Build daily sessions tab - hierarchical view of daily tax events"""
    
    main_frame = ttk.Frame(app.daily_tax_tab, padding=10)
    main_frame.pack(fill='both', expand=True)
    
    # Info
    ttk.Label(main_frame, text="Daily sessions automatically roll up game sessions and other income for tax reporting",
             font=('Arial', 10, 'italic'), foreground='gray').pack(pady=(0, 5))
    
    # Filter by Date Range
    filter_section = ttk.LabelFrame(main_frame, text="🎯 Filters", padding=5)
    filter_section.pack(fill='x', pady=(0, 5))
    
    filter_frame = ttk.Frame(filter_section)
    filter_frame.pack(fill='x')
    
    # First row: Date filters
    date_row = ttk.Frame(filter_frame)
    date_row.pack(fill='x', pady=(0, 5))
    
    # Start Date
    start_frame = ttk.Frame(date_row)
    start_frame.pack(side='left', padx=5)
    ttk.Label(start_frame, text="From:").pack(side='left', padx=(0, 5))
    app.dt_filter_start = ttk.Entry(start_frame, width=12)
    app.dt_filter_start.pack(side='left')
    
    def pick_dt_filter_start():
        try:
            from tkcalendar import Calendar
            top = tk.Toplevel(app.root)
            top.title("Select Start Date")
            top.geometry("300x300")
            cal = Calendar(top, selectmode='day', date_pattern='y-mm-dd')
            cal.pack(pady=20)
            def select():
                app.dt_filter_start.delete(0, tk.END)
                app.dt_filter_start.insert(0, cal.get_date())
                top.destroy()
            ttk.Button(top, text="Select", command=select).pack(pady=10)
            ttk.Button(top, text="Cancel", command=top.destroy).pack()
        except ImportError:
            pass
    
    ttk.Button(start_frame, text="📅", width=3, command=pick_dt_filter_start).pack(side='left', padx=2)
    
    # End Date
    end_frame = ttk.Frame(date_row)
    end_frame.pack(side='left', padx=5)
    ttk.Label(end_frame, text="To:").pack(side='left', padx=(0, 5))
    app.dt_filter_end = ttk.Entry(end_frame, width=12)
    app.dt_filter_end.pack(side='left')
    
    def pick_dt_filter_end():
        try:
            from tkcalendar import Calendar
            top = tk.Toplevel(app.root)
            top.title("Select End Date")
            top.geometry("300x300")
            cal = Calendar(top, selectmode='day', date_pattern='y-mm-dd')
            cal.pack(pady=20)
            def select():
                app.dt_filter_end.delete(0, tk.END)
                app.dt_filter_end.insert(0, cal.get_date())
                top.destroy()
            ttk.Button(top, text="Select", command=select).pack(pady=10)
            ttk.Button(top, text="Cancel", command=top.destroy).pack()
        except ImportError:
            pass
    
    ttk.Button(end_frame, text="📅", width=3, command=pick_dt_filter_end).pack(side='left', padx=2)
    
    # Quick date buttons on first row
    from datetime import timedelta, date
    ttk.Button(date_row, text="Today", 
              command=lambda: (
                  app.dt_filter_start.delete(0, tk.END),
                  app.dt_filter_start.insert(0, date.today().strftime("%Y-%m-%d")),
                  app.dt_filter_end.delete(0, tk.END),
                  app.dt_filter_end.insert(0, date.today().strftime("%Y-%m-%d")),
                  app.refresh_daily_tax_sessions()
              )).pack(side='left', padx=5)
    ttk.Button(date_row, text="Last 30 Days", 
              command=lambda: (
                  app.dt_filter_start.delete(0, tk.END),
                  app.dt_filter_start.insert(0, (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")),
                  app.dt_filter_end.delete(0, tk.END),
                  app.dt_filter_end.insert(0, date.today().strftime("%Y-%m-%d")),
                  app.refresh_daily_tax_sessions()
              )).pack(side='left', padx=5)
    ttk.Button(date_row, text="This Month", 
              command=lambda: (
                  app.dt_filter_start.delete(0, tk.END),
                  app.dt_filter_start.insert(0, date.today().replace(day=1).strftime("%Y-%m-%d")),
                  app.dt_filter_end.delete(0, tk.END),
                  app.dt_filter_end.insert(0, date.today().strftime("%Y-%m-%d")),
                  app.refresh_daily_tax_sessions()
              )).pack(side='left', padx=5)
    ttk.Button(date_row, text="This Year", 
              command=lambda: (
                  app.dt_filter_start.delete(0, tk.END),
                  app.dt_filter_start.insert(0, date.today().replace(month=1, day=1).strftime("%Y-%m-%d")),
                  app.dt_filter_end.delete(0, tk.END),
                  app.dt_filter_end.insert(0, date.today().strftime("%Y-%m-%d")),
                  app.refresh_daily_tax_sessions()
              )).pack(side='left', padx=5)
    
    # Second row: User/Site filters and action buttons
    filter_row2 = ttk.Frame(filter_frame)
    filter_row2.pack(fill='x')
    
    # User Filter (checkbox style like Realized)
    user_frame = ttk.Frame(filter_row2)
    user_frame.pack(side='left', padx=5)
    ttk.Label(user_frame, text="Users:").pack(side='left', padx=(0, 5))
    ttk.Button(user_frame, text="Filter Users...", 
              command=app.show_dt_user_filter, width=15).pack(side='left', padx=(0, 10))
    app.dt_user_filter_label = ttk.Label(user_frame, text="All", foreground='gray')
    app.dt_user_filter_label.pack(side='left')
    
    # Site Filter (checkbox style like Realized)
    site_frame = ttk.Frame(filter_row2)
    site_frame.pack(side='left', padx=5)
    ttk.Label(site_frame, text="Sites:").pack(side='left', padx=(0, 5))
    ttk.Button(site_frame, text="Filter Sites...", 
              command=app.show_dt_site_filter, width=15).pack(side='left', padx=(0, 10))
    app.dt_site_filter_label = ttk.Label(site_frame, text="All", foreground='gray')
    app.dt_site_filter_label.pack(side='left')
    
    # Initialize filter sets (empty = all)
    app.dt_selected_sites = set()
    app.dt_selected_users = set()
    
    # Filter Buttons
    ttk.Button(filter_row2, text="Apply", 
              command=lambda: app.refresh_daily_tax_sessions()).pack(side='left', padx=5)
    ttk.Button(filter_row2, text="Clear", 
              command=lambda: (
                  app.dt_filter_start.delete(0, tk.END),
                  app.dt_filter_end.delete(0, tk.END),
                  setattr(app, 'dt_selected_users', set()),
                  setattr(app, 'dt_selected_sites', set()),
                  app.dt_user_filter_label.config(text="All", foreground='gray'),
                  app.dt_site_filter_label.config(text="All", foreground='gray'),
                  app.refresh_daily_tax_sessions()
              )).pack(side='left', padx=5)
    
    # Search and buttons frame
    search_frame = ttk.Frame(main_frame)
    search_frame.pack(fill='x', pady=(5, 5))
    
    ttk.Label(search_frame, text="Search:").pack(side='left', padx=(0, 5))
    app.dt_search_var = tk.StringVar()
    app.dt_search_entry = ttk.Entry(search_frame, textvariable=app.dt_search_var, width=30)
    app.dt_search_entry.pack(side='left', padx=(0, 10))
    
    ttk.Button(search_frame, text="Clear Search", 
              command=lambda: (app.dt_search_var.set(''), app.refresh_daily_tax_sessions()), 
              width=12).pack(side='left')
    
    # Add export button
    from table_helpers import export_tree_to_csv
    ttk.Button(search_frame, text="📤 Export CSV", 
              command=lambda: export_tree_to_csv(app.dt_tree, "daily_sessions", app.root),
              width=15).pack(side='right', padx=5)
    
    # Expand/Collapse buttons
    ttk.Button(search_frame, text="⬇️ Expand All", 
              command=app.expand_all_daily_tax,
              width=15).pack(side='right', padx=5)
    
    ttk.Button(search_frame, text="⬆️ Collapse All", 
              command=app.collapse_all_daily_tax,
              width=15).pack(side='right', padx=5)
    
    # Add Notes button
    ttk.Button(search_frame, text="📝 Add/Edit Notes", 
              command=app.add_daily_session_notes,
              width=18).pack(side='right', padx=5)
    
    # Bind search to refresh
    app.dt_search_var.trace_add('write', lambda *args: app.refresh_daily_tax_sessions())
    
    # Tree
    tree_frame = ttk.Frame(main_frame)
    tree_frame.pack(fill='both', expand=True)
    
    cols = ('Date/User/Session', 'Delta Total (SC)', 'Net Taxable', 'Status', 'Details', 'Notes')
    app.dt_tree = ttk.Treeview(tree_frame, columns=cols, show='tree headings', height=20)
    
    # Initialize sort tracking
    app.dt_sort_column = None
    app.dt_sort_reverse = False
    
    def sort_dt_column(col):
        """Sort Daily Sessions by column (parent dates only)"""
        # Toggle sort direction if same column clicked
        if app.dt_sort_column == col:
            app.dt_sort_reverse = not app.dt_sort_reverse
        else:
            app.dt_sort_column = col
            app.dt_sort_reverse = False
        
        # Get all parent items (dates) with their values
        items = []
        for item_id in app.dt_tree.get_children():
            values = app.dt_tree.item(item_id)['values']
            if values:  # Make sure it has values
                items.append((values, item_id))
        
        # Sort based on column
        col_index = cols.index(col)
        try:
            # For currency columns, strip $ and commas
            if col in ('Delta Total (SC)', 'Net Taxable'):
                items.sort(
                    key=lambda x: float(x[0][col_index].replace('$', '').replace(',', '').replace('+', '').replace('(', '-').replace(')', '') if x[0][col_index] != '-' else '0'),
                    reverse=app.dt_sort_reverse
                )
            else:
                # String sort for dates
                items.sort(key=lambda x: x[0][col_index], reverse=app.dt_sort_reverse)
        except:
            # Fallback to string sort
            items.sort(key=lambda x: str(x[0][col_index]), reverse=app.dt_sort_reverse)
        
        # Reorder items
        for idx, (val, item_id) in enumerate(items):
            app.dt_tree.move(item_id, '', idx)
        
        # Update headings to show sort direction
        for c in cols:
            heading_text = c
            if c == col:
                heading_text = f"{c} {'▼' if app.dt_sort_reverse else '▲'}"
            app.dt_tree.heading(c, text=heading_text, command=lambda col=c: sort_dt_column(col))
    
    for col in cols:
        app.dt_tree.heading(col, text=col, command=lambda col=col: sort_dt_column(col))
        if col in ('Delta Total (SC)', 'Net Taxable'):
            app.dt_tree.column(col, width=120)
        elif col == 'Notes':
            app.dt_tree.column(col, width=50)
        elif col == 'Date/User/Session':
            app.dt_tree.column(col, width=250)
        else:
            app.dt_tree.column(col, width=100)
    
    app.dt_tree.column('#0', width=30)  # For expand/collapse arrows
    
    scroll = ttk.Scrollbar(tree_frame, orient='vertical', command=app.dt_tree.yview)
    app.dt_tree.configure(yscrollcommand=scroll.set)
    app.dt_tree.pack(side='left', fill='both', expand=True)
    scroll.pack(side='right', fill='y')
    
    # Bind double-click to add notes
    app.dt_tree.bind('<Double-Button-1>', lambda e: app.add_daily_session_notes())
    
    # Initialize SearchableTreeview for filtering
    from table_helpers import SearchableTreeview
    app.dt_searchable = SearchableTreeview(app.dt_tree, cols, search_frame, enable_filters=True)
    
    # Color tags
    app.dt_tree.tag_configure('win', foreground='green')
    app.dt_tree.tag_configure('loss', foreground='red')
    app.dt_tree.tag_configure('month_header', foreground='black')



# ============================================================================
# UNREALIZED POSITIONS TAB (formerly Open Sessions)
# ============================================================================

def build_unrealized_positions_tab(app):
    """Build unrealized positions tab (formerly Open Sessions)"""
    
    # Title
    title_frame = ttk.Frame(app.unrealized_tab, padding=(10, 10, 10, 0))
    title_frame.pack(fill='x')
    ttk.Label(title_frame, 
              text="Unrealized Positions - Sites With Remaining Basis",
              font=('Arial', 11, 'bold')).pack()
    
    # Date filter - using standardized helper
    create_date_filter_bar(
        app.unrealized_tab,
        app,
        'unreal_filter_start',
        'unreal_filter_end',
        lambda: app.refresh_unrealized_positions()
    )
    
    main_frame = ttk.Frame(app.unrealized_tab, padding=10)
    main_frame.pack(fill='both', expand=True)
    
    # Search and buttons
    search_frame = ttk.Frame(main_frame)
    search_frame.pack(fill='x', pady=(5, 5))
    
    # Close Balance button on left
    ttk.Button(search_frame, text="🔒 Close Balance", 
              command=app.close_unrealized_balance,
              width=18).pack(side='left', padx=5)
    
    # Notes and Export buttons on right
    ttk.Button(search_frame, text="📝 Add Notes", 
              command=app.add_unrealized_notes,
              width=15).pack(side='right', padx=5)
    
    from table_helpers import export_tree_to_csv
    ttk.Button(search_frame, text="📤 Export CSV", 
              command=lambda: export_tree_to_csv(app.unreal_tree, "unrealized_positions", app.root),
              width=15).pack(side='right', padx=5)
    
    # Tree
    tree_frame = ttk.Frame(main_frame)
    tree_frame.pack(fill='both', expand=True)
    
    cols = ('Site', 'User', 'Start', 'Purchase Basis', 'Current SC', 'Current Value', 
            'Unrealized P/L', 'Last Activity', 'Notes')
    
    app.unreal_tree = ttk.Treeview(tree_frame, columns=cols, show='headings', height=20)
    
    # Make columns sortable
    for col in cols:
        app.unreal_tree.heading(col, text=col, command=lambda c=col: app.sort_unrealized_column(c))
        if col == 'Notes':
            app.unreal_tree.column(col, width=50)
        elif col in ('Purchase Basis', 'Current Value', 'Unrealized P/L'):
            app.unreal_tree.column(col, width=120)
        else:
            app.unreal_tree.column(col, width=100)
    
    scroll = ttk.Scrollbar(tree_frame, orient='vertical', command=app.unreal_tree.yview)
    app.unreal_tree.configure(yscrollcommand=scroll.set)
    app.unreal_tree.pack(side='left', fill='both', expand=True)
    scroll.pack(side='right', fill='y')
    
    # Bind double-click
    app.unreal_tree.bind('<Double-Button-1>', lambda e: app.add_unrealized_notes())
    
    # Color tags
    app.unreal_tree.tag_configure('profit', foreground='green')
    app.unreal_tree.tag_configure('loss', foreground='red')
    app.unreal_tree.tag_configure('unknown', foreground='gray')
    
    # Initialize searchable
    from table_helpers import SearchableTreeview
    app.unreal_searchable = SearchableTreeview(app.unreal_tree, cols, search_frame)
    
    # Initialize sort tracking
    app.unreal_sort_column = None
    app.unreal_sort_reverse = False
