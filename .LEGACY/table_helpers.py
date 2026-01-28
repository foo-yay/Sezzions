"""
table_helpers.py - Search and sort functionality for Treeview tables
"""
import tkinter as tk
from tkinter import ttk


class SearchableTreeview:
    """Adds Excel-like search and sort to ttk.Treeview"""
    
    def __init__(self, tree, columns, search_frame=None, enable_filters=True):
        """
        Initialize searchable treeview
        
        Args:
            tree: ttk.Treeview widget
            columns: List of column identifiers
            search_frame: Optional frame to add search box to (if None, creates one)
            enable_filters: Enable Excel-style column filters
        """
        self.tree = tree
        self.columns = columns
        self.all_data = []  # Store all rows with their tags: [(values, tags), ...]
        self.sort_reverse = {}  # Track sort direction per column
        self.current_sort_column = None  # Track which column is currently sorted
        
        # Excel-style filtering
        self.enable_filters = enable_filters
        self.active_filters = {}  # {column: set(selected_values)} - empty set = all selected
        self.unique_values_cache = {}  # {column: sorted_list_of_unique_values}
        
        # Create search UI
        if search_frame is None:
            # Create search frame above tree
            parent = tree.master
            search_frame = ttk.Frame(parent)
            search_frame.pack(fill='x', padx=5, pady=(5, 0))
        
        ttk.Label(search_frame, text="Search:").pack(side='left', padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        self.search_entry.pack(side='left', padx=(0, 10))
        
        ttk.Button(search_frame, text="Clear", command=self.clear_search, width=8).pack(side='left')
        
        # Add "Clear All Filters" button if filters enabled
        if self.enable_filters:
            ttk.Button(search_frame, text="Clear Filters", 
                      command=self.clear_all_filters, width=12).pack(side='left', padx=(5, 0))
        
        # Bind search (using trace_add for Tcl 9 compatibility)
        self.search_var.trace_add('write', lambda *args: self.apply_filter())
        
        # Bind column headers
        for col in columns:
            self.sort_reverse[col] = False
            if self.enable_filters:
                # Add filter capability to header
                self.tree.heading(col, command=lambda c=col: self.show_column_menu(c))
            else:
                # Just sorting
                self.tree.heading(col, command=lambda c=col: self.sort_by_column(c))
    
    def set_data(self, data_with_tags, children_callback=None):
        """
        Set the data for the table
        
        Args:
            data_with_tags: List of tuples: [(values, tags), ...] or [(values, tags, text), ...]
            children_callback: Optional function(parent_id, values) to add children after parent is inserted
        """
        # Handle both formats: with tags or without, optionally with text
        self.all_data = []
        for item in data_with_tags:
            if isinstance(item, tuple) and len(item) >= 2:
                if len(item) == 2 and isinstance(item[1], tuple):
                    # Format: (values, tags)
                    self.all_data.append((item[0], item[1], ''))
                elif len(item) == 3:
                    # Format: (values, tags, text)
                    self.all_data.append(item)
                else:
                    # Fallback
                    self.all_data.append((item[0], item[1] if isinstance(item[1], tuple) else (), ''))
            else:
                # Format: just values, no tags or text
                self.all_data.append((item, (), ''))
        
        # Store children callback
        self.children_callback = children_callback
        
        # Clear filter cache when data changes
        self.unique_values_cache = {}
        
        # Apply filter to rebuild tree
        self.apply_filter()
        
        # Reapply sort IMMEDIATELY (synchronously, no delay)
        if self.current_sort_column:
            self._reapply_sort()
    
    def apply_filter(self):
        """Filter data based on search term AND active column filters"""
        search_term = self.search_var.get().lower()
        
        # Clear tree
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Filter and display
        for item_data in self.all_data:
            # Unpack data (handles both 2-tuple and 3-tuple formats)
            if len(item_data) == 3:
                values, tags, text = item_data
            else:
                values, tags = item_data
                text = ''
            
            # Check search term (if any)
            if search_term and not any(search_term in str(val).lower() for val in values):
                continue
            
            # Check column filters (if any active)
            if self.enable_filters and self.active_filters:
                passes_filters = True
                for col, selected_values in self.active_filters.items():
                    if selected_values:  # Empty set means "all selected", don't filter
                        col_index = self.columns.index(col)
                        if values[col_index] not in selected_values:
                            passes_filters = False
                            break
                
                if not passes_filters:
                    continue
            
            # Row passes all filters - display it with text
            parent_id = self.tree.insert('', 'end', text=text, values=values, tags=tags)
            
            # If there's a children callback, call it to add children
            if hasattr(self, 'children_callback') and self.children_callback:
                self.children_callback(parent_id, values)
        
        # Update column headers to show filter status
        if self.enable_filters:
            self.update_column_headers()
    
    def clear_search(self):
        """Clear search field"""
        self.search_var.set('')
    
    def clear_all_filters(self):
        """Clear all column filters and search"""
        self.active_filters = {}
        self.search_var.set('')
        self.apply_filter()
    
    def get_unique_values(self, column):
        """Get sorted unique values for a column"""
        if column in self.unique_values_cache:
            return self.unique_values_cache[column]
        
        col_index = self.columns.index(column)
        values = set()
        for item_data in self.all_data:
            # Handle both 2-tuple and 3-tuple formats
            row_values = item_data[0]
            values.add(str(row_values[col_index]))
        
        # Sort values (try numeric first, fall back to string)
        try:
            sorted_values = sorted(values, key=lambda x: float(x.replace('$', '').replace(',', '').replace('%', '') or 0))
        except (ValueError, AttributeError):
            sorted_values = sorted(values)
        
        self.unique_values_cache[column] = sorted_values
        return sorted_values
    
    def show_column_menu(self, column):
        """Show menu with Sort and Filter options"""
        menu = tk.Menu(self.tree, tearoff=0)
        menu.add_command(label=f"Sort {column} â–²", command=lambda: self.sort_by_column(column))
        menu.add_separator()
        menu.add_command(label=f"Filter {column}...", command=lambda: self.show_filter_dialog(column))
        
        # Show menu at mouse position
        try:
            menu.tk_popup(self.tree.winfo_pointerx(), self.tree.winfo_pointery())
        finally:
            menu.grab_release()
    
    def show_filter_dialog(self, column):
        """Show filter dialog for column"""
        FilterDialog(self.tree, column, self.get_unique_values(column), 
                    self.active_filters.get(column, set()), self.on_filter_changed)
    
    def on_filter_changed(self, column, selected_values):
        """Callback when filter selection changes"""
        if selected_values:
            # Store selected values (non-empty means filtering is active)
            self.active_filters[column] = selected_values
        else:
            # Empty selection means "all" - remove filter for this column
            if column in self.active_filters:
                del self.active_filters[column]
        
        self.apply_filter()
    
    def update_column_headers(self):
        """Update column headers to show filter status"""
        import re
        for col in self.columns:
            # Get current header text (without filter indicator)
            current_text = str(self.tree.heading(col)['text'])
            # Remove any existing filter indicators (e.g., " ðŸ”½(3)", " â–¼(5)")
            current_text = re.sub(r'\s*[ðŸ”½â–¼]\(\d+\)', '', current_text)
            
            # Add filter indicator if this column is filtered
            if col in self.active_filters and self.active_filters[col]:
                num_selected = len(self.active_filters[col])
                new_text = f"{current_text} ðŸ”½({num_selected})"
            else:
                new_text = current_text
            
            self.tree.heading(col, text=new_text)
    
    def sort_by_column(self, col):
        """Sort tree by column"""
        col_index = self.columns.index(col)
        
        # Remember this column for future refreshes
        self.current_sort_column = col
        
        # Get current data from tree
        data = [(self.tree.set(item, col), item) for item in self.tree.get_children('')]
        
        # Determine sort type (numeric if possible)
        try:
            # Try to convert first value to float
            if data:
                test_val = data[0][0].replace('$', '').replace(',', '').replace('%', '')
                float(test_val)
                # Numeric sort
                data.sort(key=lambda x: float(x[0].replace('$', '').replace(',', '').replace('%', '') or 0), 
                         reverse=self.sort_reverse[col])
        except (ValueError, AttributeError):
            # String sort
            data.sort(key=lambda x: x[0].lower(), reverse=self.sort_reverse[col])
        
        # Rearrange items
        for index, (val, item) in enumerate(data):
            self.tree.move(item, '', index)
        
        # Toggle sort direction
        self.sort_reverse[col] = not self.sort_reverse[col]
        
        # Update heading to show sort direction
        self._update_heading_arrow(col)
    
    def _update_heading_arrow(self, col):
        """Update column heading to show sort direction"""
        # First, clear arrows from all other columns
        for other_col in self.columns:
            if other_col != col:
                # Remove any arrows from other columns
                current_text = str(self.tree.heading(other_col)['text'])
                clean_text = current_text.replace(' â–¼', '').replace(' â–²', '')
                self.tree.heading(other_col, text=clean_text)
        
        # Now set the arrow for the sorted column
        heading_text = col
        if self.sort_reverse[col]:
            heading_text = f"{col} â–¼"
        else:
            heading_text = f"{col} â–²"
        self.tree.heading(col, text=heading_text)
    
    def _reapply_sort(self):
        """Reapply the current sort after data refresh"""
        if not self.current_sort_column:
            return
        
        col = self.current_sort_column
        
        # Get all items with their sort values
        items = []
        for item_id in self.tree.get_children(''):
            sort_val = self.tree.set(item_id, col)
            items.append((sort_val, item_id))
        
        if not items:
            return
        
        # Determine sort type and sort the list
        # IMPORTANT: sort_reverse was already toggled by the original sort_by_column call
        # So we need to use the OPPOSITE direction to match what the user sees
        reverse_direction = not self.sort_reverse[col]
        
        try:
            # Try numeric sort
            test_val = items[0][0].replace('$', '').replace(',', '').replace('%', '').replace('â³', '').strip()
            if test_val:
                float(test_val)
                # Numeric sort
                items.sort(
                    key=lambda x: float(x[0].replace('$', '').replace(',', '').replace('%', '').replace('â³', '').strip() or '0'), 
                    reverse=reverse_direction
                )
            else:
                # String sort (for empty values)
                items.sort(key=lambda x: x[0].lower(), reverse=reverse_direction)
        except (ValueError, AttributeError):
            # String sort
            items.sort(key=lambda x: x[0].lower(), reverse=reverse_direction)
        
        # Reorder items in tree by detaching and re-inserting in sorted order
        for item_id in self.tree.get_children():
            self.tree.detach(item_id)
        
        for idx, (sort_val, item_id) in enumerate(items):
            self.tree.move(item_id, '', idx)
        
        # Update heading arrow
        self._update_heading_arrow(col)
    
    def refresh_from_tree(self):
        """Refresh all_data from current tree contents (useful after external updates)"""
        self.all_data = []
        for item in self.tree.get_children():
            values = self.tree.item(item)['values']
            self.all_data.append(values)


def add_search_sort_to_tree(tree, columns, parent_frame=None):
    """
    Convenience function to add search/sort to existing tree
    
    Args:
        tree: ttk.Treeview widget
        columns: List of column identifiers
        parent_frame: Frame containing the tree (if None, uses tree.master)
    
    Returns:
        SearchableTreeview instance
    """
    if parent_frame is None:
        parent_frame = tree.master
    
    # Create search frame
    search_frame = ttk.Frame(parent_frame)
    
    # Pack search frame above tree (find tree's pack info)
    tree.pack_forget()
    search_frame.pack(fill='x', padx=5, pady=(5, 0))
    tree.pack(fill='both', expand=True)
    
    # Create searchable wrapper
    return SearchableTreeview(tree, columns, search_frame)


def enable_multi_select(tree):
    """
    Enable multi-select on a treeview with Ctrl+Click and Shift+Click
    
    Args:
        tree: ttk.Treeview widget
    """
    # Store last selected item for shift-click range selection
    tree._last_selected = None
    
    def on_click(event):
        """Handle click with modifiers"""
        # Get clicked item
        item = tree.identify_row(event.y)
        if not item:
            return
        
        # Check modifiers
        ctrl_pressed = (event.state & 0x4) != 0  # Ctrl key
        shift_pressed = (event.state & 0x1) != 0  # Shift key
        
        if ctrl_pressed:
            # Ctrl+Click: Toggle selection
            if item in tree.selection():
                tree.selection_remove(item)
            else:
                tree.selection_add(item)
            tree._last_selected = item
        elif shift_pressed:
            # Shift+Click: Range selection
            if tree._last_selected and tree._last_selected in tree.get_children():
                # Get all items
                all_items = tree.get_children()
                
                # Find indices
                try:
                    start_idx = all_items.index(tree._last_selected)
                    end_idx = all_items.index(item)
                    
                    # Ensure start < end
                    if start_idx > end_idx:
                        start_idx, end_idx = end_idx, start_idx
                    
                    # Select range
                    tree.selection_set(all_items[start_idx:end_idx + 1])
                except ValueError:
                    # Item not found, just select clicked item
                    tree.selection_set(item)
            else:
                tree.selection_set(item)
            tree._last_selected = item
        else:
            # Normal click: Single selection
            tree.selection_set(item)
            tree._last_selected = item
        
        return "break"  # Prevent default behavior
    
    # Bind click event
    tree.bind('<Button-1>', on_click)


def export_tree_to_csv(tree, filename_prefix, parent_window=None):
    """
    Export treeview data to CSV file
    
    Args:
        tree: ttk.Treeview widget
        filename_prefix: Suggested filename prefix (e.g., "purchases", "expenses")
        parent_window: Parent window for dialog (optional)
    """
    from tkinter import filedialog, messagebox
    import csv
    from datetime import datetime
    
    # Suggest filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_filename = f"{filename_prefix}_{timestamp}.csv"
    
    filepath = filedialog.asksaveasfilename(
        title=f"Export {filename_prefix.replace('_', ' ').title()}",
        defaultextension=".csv",
        initialfile=default_filename,
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        parent=parent_window
    )
    
    if not filepath:
        return
    
    try:
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write headers
            columns = tree['columns']
            if columns:
                headers = [tree.heading(col)['text'] for col in columns]
            else:
                # Fallback if no columns defined
                headers = ['Data']
            writer.writerow(headers)
            
            # Write visible rows
            for item in tree.get_children():
                values = tree.item(item)['values']
                writer.writerow(values)
        
        messagebox.showinfo("Export Success", 
            f"Exported {len(tree.get_children())} row(s) to:\n{filepath}",
            parent=parent_window)
    except Exception as e:
        messagebox.showerror("Export Error", f"Failed to export:\n{str(e)}", parent=parent_window)


class FilterDialog:
    """Excel-style filter dialog with checkboxes for unique values"""
    
    def __init__(self, parent, column_name, unique_values, current_selection, callback):
        """
        Create filter dialog
        
        Args:
            parent: Parent widget
            column_name: Name of column being filtered
            unique_values: List of unique values to show
            current_selection: Set of currently selected values
            callback: Function(column_name, selected_set) to call on OK
        """
        self.column_name = column_name
        self.unique_values = unique_values
        self.current_selection = current_selection.copy() if current_selection else set()
        self.callback = callback
        
        # Detect if this is a date column
        self.is_date_column = self._detect_date_column(unique_values)
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Filter: {column_name}")
        self.dialog.geometry("300x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Main frame
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill='both', expand=True)
        
        # Top buttons
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Button(top_frame, text="Select All", command=self.select_all, width=12).pack(side='left', padx=(0, 5))
        ttk.Button(top_frame, text="Clear All", command=self.clear_all, width=12).pack(side='left')
        
        # Search box for filtering values
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill='x', pady=(0, 5))
        ttk.Label(search_frame, text="Search:").pack(side='left', padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', lambda *args: self.filter_items())
        ttk.Entry(search_frame, textvariable=self.search_var, width=20).pack(side='left', fill='x', expand=True)
        
        # Use Treeview for hierarchical date structure or checkboxes for non-dates
        if self.is_date_column:
            self._create_date_tree(main_frame)
        else:
            self._create_checkbox_list(main_frame)
        
        # Bottom buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Button(button_frame, text="OK", command=self.on_ok, width=10).pack(side='right', padx=(5, 0))
        ttk.Button(button_frame, text="Cancel", command=self.on_cancel, width=10).pack(side='right')
        
        # Center dialog on parent
        self.dialog.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (self.dialog.winfo_width() // 2)
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")
    
    def _parse_date_value(self, value):
        """Parse date/time values into components"""
        import re
        from datetime import datetime
        
        text = str(value).strip()
        if not text:
            return None
        
        m = re.match(r'^(\d{4}-\d{2}-\d{2})(?:\s+(\d{1,2}:\d{2}(?::\d{2})?))?', text)
        date_fmt = None
        if m:
            date_part = m.group(1)
            time_part = m.group(2)
            date_fmt = "%Y-%m-%d"
        else:
            m = re.match(r'^(\d{1,2}/\d{1,2}/\d{2})(?:\s+(\d{1,2}:\d{2}(?::\d{2})?))?', text)
            if not m:
                return None
            date_part = m.group(1)
            time_part = m.group(2)
            date_fmt = "%m/%d/%y"
        
        try:
            date_obj = datetime.strptime(date_part, date_fmt).date()
        except ValueError:
            return None
        
        suffix = text[m.end():].strip()
        return date_obj, time_part, suffix, text

    def _detect_date_column(self, values):
        """Detect if values are dates or datetimes"""
        if not values:
            return False
        
        # Check first few values
        sample = list(values)[:min(10, len(values))]
        matches = sum(1 for v in sample if self._parse_date_value(v))
        
        # If >70% parse as date, treat as date column
        return matches / len(sample) > 0.7
    
    def _create_date_tree(self, parent):
        """Create hierarchical date tree (Year > Month > Day > Time)"""
        # Frame for treeview
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill='both', expand=True)
        
        # Create treeview with checkboxes
        self.tree = ttk.Treeview(tree_frame, show='tree', selectmode='none', height=12)
        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side='right', fill='y')
        self.tree.pack(side='left', fill='both', expand=True)
        
        # Organize dates hierarchically
        date_hierarchy = {}  # {year: {month: {day: [(time_label, full_value)]}}}
        parsed_entries = []
        for date_str in self.unique_values:
            parsed = self._parse_date_value(date_str)
            if not parsed:
                continue
            parsed_entries.append(parsed)
        
        self.has_time_values = any(entry[1] for entry in parsed_entries)
        
        for date_obj, time_part, suffix, full_value in parsed_entries:
            year = str(date_obj.year)
            month = f"{date_obj.month:02d}"
            day = f"{date_obj.day:02d}"
            
            if year not in date_hierarchy:
                date_hierarchy[year] = {}
            if month not in date_hierarchy[year]:
                date_hierarchy[year][month] = {}
            if day not in date_hierarchy[year][month]:
                date_hierarchy[year][month][day] = []
            
            if self.has_time_values:
                time_label = time_part or "00:00"
                if suffix:
                    time_label = f"{time_label}{suffix}"
                date_hierarchy[year][month][day].append((time_label, full_value))
            else:
                date_hierarchy[year][month][day].append((None, full_value))
        
        # Track checkboxes: {item_id: (type, value, values)}
        self.tree_items = {}
        self.check_vars = {}
        
        # Month names for display
        month_names = {
            '01': 'January', '02': 'February', '03': 'March', '04': 'April',
            '05': 'May', '06': 'June', '07': 'July', '08': 'August',
            '09': 'September', '10': 'October', '11': 'November', '12': 'December'
        }
        
        # Build tree
        for year in sorted(date_hierarchy.keys(), reverse=True):
            year_values = []
            for month_map in date_hierarchy[year].values():
                for day_entries in month_map.values():
                    year_values.extend([full for _, full in day_entries])
            
            year_id = self.tree.insert('', 'end', text=f"â˜ {year}", tags=('year', year))
            self.tree_items[year_id] = ('year', year, year_values)
            
            for month in sorted(date_hierarchy[year].keys()):
                month_name = month_names.get(month, month)
                month_values = []
                for day_entries in date_hierarchy[year][month].values():
                    month_values.extend([full for _, full in day_entries])
                
                month_id = self.tree.insert(year_id, 'end', text=f"â˜ {month_name}", tags=('month', f"{year}-{month}"))
                self.tree_items[month_id] = ('month', f"{year}-{month}", month_values)
                
                for day in sorted(date_hierarchy[year][month].keys(), reverse=True):
                    day_entries = date_hierarchy[year][month][day]
                    day_values = [full for _, full in day_entries]
                    
                    if self.has_time_values:
                        day_id = self.tree.insert(month_id, 'end', text=f"â˜ {day}", tags=('day', f"{year}-{month}-{day}"))
                        self.tree_items[day_id] = ('day', f"{year}-{month}-{day}", day_values)
                        
                        def _time_key(item):
                            label = item[0] or ""
                            return label
                        
                        for time_label, full_value in sorted(day_entries, key=_time_key):
                            label = time_label or "00:00"
                            time_id = self.tree.insert(day_id, 'end', text=f"â˜ {label}", tags=('time', full_value))
                            self.tree_items[time_id] = ('time', full_value, [full_value])
                    else:
                        date_id = self.tree.insert(month_id, 'end', text=f"â˜ {day}", tags=('date', f"{year}-{month}-{day}"))
                        self.tree_items[date_id] = ('date', f"{year}-{month}-{day}", day_values)
        
        # Update month/year checkboxes based on dates
        self._update_tree_checkboxes()
        
        # Bind click event
        self.tree.bind('<Button-1>', self._on_tree_click)
    
    def _create_checkbox_list(self, parent):
        """Create simple checkbox list for non-date columns"""
        # Scrollable frame for checkboxes
        canvas_frame = ttk.Frame(parent)
        canvas_frame.pack(fill='both', expand=True)
        
        canvas = tk.Canvas(canvas_frame, height=250)
        scrollbar = ttk.Scrollbar(canvas_frame, orient='vertical', command=canvas.yview)
        self.checkbox_frame = ttk.Frame(canvas)
        
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        
        canvas_window = canvas.create_window((0, 0), window=self.checkbox_frame, anchor='nw')
        
        # Update scroll region when frame changes
        def configure_scroll(event):
            canvas.configure(scrollregion=canvas.bbox('all'))
        self.checkbox_frame.bind('<Configure>', configure_scroll)
        
        # Create checkboxes for each unique value
        self.checkbox_vars = {}
        self.checkbox_widgets = {}
        
        for value in self.unique_values:
            var = tk.BooleanVar(value=(not self.current_selection or value in self.current_selection))
            self.checkbox_vars[value] = var
            
            cb = ttk.Checkbutton(self.checkbox_frame, text=str(value), variable=var)
            cb.pack(anchor='w', padx=5, pady=2)
            self.checkbox_widgets[value] = cb
    
    def _on_tree_click(self, event):
        """Handle click on tree item"""
        item = self.tree.identify_row(event.y)
        if not item:
            return
        
        # Check if clicked on the checkbox area (first 20 pixels)
        column = self.tree.identify_column(event.x)
        if column != '#0':
            return
        
        # Toggle checkbox
        item_type, value, dates = self.tree_items.get(item, (None, None, []))
        if not item_type:
            return
        
        # Get current state
        current_text = self.tree.item(item, 'text')
        is_checked = 'â˜‘' in current_text
        
        # Toggle state
        new_checked = not is_checked
        symbol = 'â˜‘' if new_checked else 'â˜'
        display_text = current_text.replace('â˜‘', '').replace('â˜', '').strip()
        self.tree.item(item, text=f"{symbol} {display_text}")
        
        # Update children recursively
        if item_type in ('year', 'month'):
            self._toggle_children(item, new_checked)
        
        # Update parents
        self._update_parents(item)
    
    def _toggle_children(self, item, checked):
        """Recursively toggle all children"""
        symbol = 'â˜‘' if checked else 'â˜'
        
        for child in self.tree.get_children(item):
            current_text = self.tree.item(child, 'text')
            display_text = current_text.replace('â˜‘', '').replace('â˜', '').strip()
            self.tree.item(child, text=f"{symbol} {display_text}")
            
            # Recurse
            if self.tree.get_children(child):
                self._toggle_children(child, checked)
    
    def _update_parents(self, item):
        """Update parent checkboxes based on children"""
        parent = self.tree.parent(item)
        if not parent:
            return
        
        # Check if all children are checked
        children = self.tree.get_children(parent)
        all_checked = all('â˜‘' in self.tree.item(child, 'text') for child in children)
        any_checked = any('â˜‘' in self.tree.item(child, 'text') for child in children)
        
        # Update parent
        current_text = self.tree.item(parent, 'text')
        display_text = current_text.replace('â˜‘', '').replace('â˜', '').replace('â˜’', '').strip()
        
        if all_checked:
            symbol = 'â˜‘'
        elif any_checked:
            symbol = 'â˜’'  # Partial selection
        else:
            symbol = 'â˜'
        
        self.tree.item(parent, text=f"{symbol} {display_text}")
        
        # Recurse to grandparent
        self._update_parents(parent)
    
    def _update_tree_checkboxes(self):
        """Update all checkboxes based on current_selection"""
        if not self.is_date_column:
            return
        
        for item_id, (item_type, value, values) in self.tree_items.items():
            if item_type in ('date', 'time'):
                checked = (all(v in self.current_selection for v in values)
                           if self.current_selection else True)
                symbol = 'â˜‘' if checked else 'â˜'
                current_text = self.tree.item(item_id, 'text')
                display_text = current_text.replace('â˜‘', '').replace('â˜', '').strip()
                self.tree.item(item_id, text=f"{symbol} {display_text}")
        
        # Update parents from bottom up
        for item_id in reversed(list(self.tree_items.keys())):
            if self.tree.get_children(item_id):
                self._update_parents_from_children(item_id)
    
    def _update_parents_from_children(self, item):
        """Update item based on its children"""
        children = self.tree.get_children(item)
        if not children:
            return
        
        all_checked = all('â˜‘' in self.tree.item(child, 'text') for child in children)
        any_checked = any('â˜‘' in self.tree.item(child, 'text') or 'â˜’' in self.tree.item(child, 'text') for child in children)
        
        current_text = self.tree.item(item, 'text')
        display_text = current_text.replace('â˜‘', '').replace('â˜', '').replace('â˜’', '').strip()
        
        if all_checked:
            symbol = 'â˜‘'
        elif any_checked:
            symbol = 'â˜’'
        else:
            symbol = 'â˜'
        
        self.tree.item(item, text=f"{symbol} {display_text}")
    
    def select_all(self):
        """Select all visible items"""
        if self.is_date_column:
            # Select all tree items
            for item in self.tree.get_children():
                self._set_tree_item_checked(item, True)
        else:
            # Select all checkboxes
            for value, var in self.checkbox_vars.items():
                if self.checkbox_widgets[value].winfo_viewable():
                    var.set(True)
    
    def clear_all(self):
        """Clear all visible items"""
        if self.is_date_column:
            # Clear all tree items
            for item in self.tree.get_children():
                self._set_tree_item_checked(item, False)
        else:
            # Clear all checkboxes
            for value, var in self.checkbox_vars.items():
                if self.checkbox_widgets[value].winfo_viewable():
                    var.set(False)
    
    def _set_tree_item_checked(self, item, checked):
        """Recursively set tree item and children to checked/unchecked"""
        symbol = 'â˜‘' if checked else 'â˜'
        current_text = self.tree.item(item, 'text')
        display_text = current_text.replace('â˜‘', '').replace('â˜', '').replace('â˜’', '').strip()
        self.tree.item(item, text=f"{symbol} {display_text}")
        
        # Recurse to children
        for child in self.tree.get_children(item):
            self._set_tree_item_checked(child, checked)
    
    def filter_items(self):
        """Filter visible items based on search"""
        if self.is_date_column:
            # Filter tree items (hide non-matching)
            search_term = self.search_var.get().lower()
            self._filter_tree_recursive('', search_term)
        else:
            # Filter checkboxes
            search_term = self.search_var.get().lower()
            for value, cb in self.checkbox_widgets.items():
                if not search_term or search_term in str(value).lower():
                    cb.pack(anchor='w', padx=5, pady=2)
                else:
                    cb.pack_forget()
    
    def _filter_tree_recursive(self, parent, search_term):
        """Recursively filter tree items based on search"""
        for item in self.tree.get_children(parent):
            text = self.tree.item(item, 'text').lower()
            
            # Check if this item or any children match
            matches = not search_term or search_term in text
            
            # Check children recursively
            children = self.tree.get_children(item)
            if children:
                child_matches = self._filter_tree_recursive(item, search_term)
                matches = matches or child_matches
            
            # Show/hide based on match
            if matches:
                self.tree.reattach(item, parent, 'end')
            else:
                self.tree.detach(item)
        
        return any(not self.tree.detached(item) for item in self.tree.get_children(parent))
    
    def on_ok(self):
        """Apply filter and close"""
        if self.is_date_column:
            # Get selected dates from tree
            selected = self._get_selected_dates()
        else:
            # Get selected values from checkboxes
            selected = {value for value, var in self.checkbox_vars.items() if var.get()}
        
        # If all are selected, treat as "no filter" (pass empty set)
        if len(selected) == len(self.unique_values):
            selected = set()
        
        # Call callback
        self.callback(self.column_name, selected)
        self.dialog.destroy()
    
    def _get_selected_dates(self):
        """Get all selected date/time values from tree"""
        selected = set()
        
        for item_id, (item_type, value, values) in self.tree_items.items():
            if item_type in ('date', 'time'):
                # Check if this date is selected
                text = self.tree.item(item_id, 'text')
                if 'â˜‘' in text:
                    for val in values:
                        selected.add(val)
        
        return selected
    
    def on_cancel(self):
        """Close without changes"""
        self.dialog.destroy()

