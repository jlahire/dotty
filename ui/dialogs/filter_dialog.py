"""
filter_dialog.py - popup dialog for configuring filters
replaces the filter panel with a menu-accessible dialog
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
from ui.font_config import get_font


class FilterDialog(tk.Toplevel):
    """dialog for configuring graph filters"""
    
    def __init__(self, parent, filter_manager):
        super().__init__(parent)
        
        self.filter_manager = filter_manager
        self.result = False
        
        self.title("Configure Filters")
        self.geometry("600x700")
        self.configure(bg='#252526')
        self.resizable(False, False)
        
        # Center on parent
        self.transient(parent)
        self.grab_set()
        
        self.setup_ui()
        
        # Center window
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 300
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 350
        self.geometry(f"+{x}+{y}")
        
        # Load current filter state
        self.load_current_filters()
    
    def setup_ui(self):
        """create dialog UI"""
        # Title
        title = tk.Label(self, text="Filter Configuration",
                        font=get_font('title', bold=True),
                        bg='#252526', fg='#4fc3f7')
        title.pack(pady=15)
        
        # Subtitle
        subtitle = tk.Label(self, 
                           text="Select which files to display in the graph",
                           font=get_font('text'),
                           bg='#252526', fg='#9cdcfe')
        subtitle.pack(pady=5)
        
        # Main frame with scrollbar
        main_frame = tk.Frame(self, bg='#252526')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Canvas for scrolling
        canvas = tk.Canvas(main_frame, bg='#252526', highlightthickness=0)
        scrollbar = tk.Scrollbar(main_frame, orient='vertical', command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#252526')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # =================================================================
        # FILE TYPE FILTERS
        # =================================================================
        type_frame = tk.LabelFrame(scrollable_frame, text="File Types",
                                  bg='#2d2d30', fg='#d4d4d4',
                                  font=get_font('heading', bold=True))
        type_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Extension checkboxes in columns
        self.ext_vars = {}
        extensions = [
            # Code files
            ('.py', 'Python'), ('.js', 'JavaScript'), ('.html', 'HTML'),
            ('.css', 'CSS'), ('.java', 'Java'), ('.c', 'C/C++'),
            ('.cpp', 'C++'), ('.cs', 'C#'), ('.go', 'Go'),
            ('.rs', 'Rust'), ('.php', 'PHP'), ('.rb', 'Ruby'),
            ('.swift', 'Swift'), ('.sh', 'Shell'),
            # Documents
            ('.txt', 'Text'), ('.md', 'Markdown'), ('.pdf', 'PDF'),
            ('.docx', 'Word'), ('.doc', 'Word (old)'), ('.rtf', 'RTF'),
            ('.odt', 'OpenDocument'),
            # Images
            ('.jpg', 'JPEG'), ('.jpeg', 'JPEG'), ('.png', 'PNG'),
            ('.gif', 'GIF'), ('.bmp', 'Bitmap'), ('.svg', 'SVG'),
            ('.ico', 'Icon'), ('.webp', 'WebP'),
            # Archives
            ('.zip', 'ZIP'), ('.tar', 'TAR'), ('.gz', 'GZip'),
            ('.rar', 'RAR'), ('.7z', '7-Zip'),
            # Executables
            ('.exe', 'Executable'), ('.dll', 'DLL'), ('.so', 'Shared Lib'),
            # Data
            ('.json', 'JSON'), ('.xml', 'XML'), ('.csv', 'CSV'),
            ('.yaml', 'YAML'), ('.yml', 'YAML'), ('.ini', 'INI'),
            ('.cfg', 'Config'), ('.conf', 'Config')
        ]
        
        # Quick select buttons
        quick_frame = tk.Frame(type_frame, bg='#2d2d30')
        quick_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Button(quick_frame, text="Select All", bg='#37373d', fg='#d4d4d4',
                 font=get_font('small'), command=self.select_all_extensions).pack(side=tk.LEFT, padx=2)
        tk.Button(quick_frame, text="Deselect All", bg='#37373d', fg='#d4d4d4',
                 font=get_font('small'), command=self.deselect_all_extensions).pack(side=tk.LEFT, padx=2)
        tk.Button(quick_frame, text="Code Only", bg='#37373d', fg='#d4d4d4',
                 font=get_font('small'), command=self.select_code_only).pack(side=tk.LEFT, padx=2)
        tk.Button(quick_frame, text="Documents Only", bg='#37373d', fg='#d4d4d4',
                 font=get_font('small'), command=self.select_documents_only).pack(side=tk.LEFT, padx=2)
        
        # Extension grid (3 columns)
        ext_grid = tk.Frame(type_frame, bg='#2d2d30')
        ext_grid.pack(fill=tk.X, padx=10, pady=5)
        
        for idx, (ext, label) in enumerate(extensions):
            col = idx % 3
            row = idx // 3
            
            var = tk.BooleanVar(value=True)
            cb = tk.Checkbutton(ext_grid, text=f"{ext} ({label})",
                               variable=var,
                               bg='#2d2d30', fg='#d4d4d4',
                               font=get_font('small'),
                               selectcolor='#1e1e1e',
                               anchor='w')
            cb.grid(row=row, column=col, sticky='w', padx=5, pady=2)
            self.ext_vars[ext] = var
        
        # No extension option
        self.no_ext_var = tk.BooleanVar(value=True)
        tk.Checkbutton(ext_grid, text="(no extension)",
                      variable=self.no_ext_var,
                      bg='#2d2d30', fg='#d4d4d4',
                      font=get_font('small', bold=True),
                      selectcolor='#1e1e1e').grid(row=row+1, column=0, sticky='w', padx=5, pady=2)
        
        # =================================================================
        # DATE FILTERS
        # =================================================================
        date_frame = tk.LabelFrame(scrollable_frame, text="Modified Date",
                                  bg='#2d2d30', fg='#d4d4d4',
                                  font=get_font('heading', bold=True))
        date_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.date_var = tk.StringVar(value='all')
        
        dates = [
            ('All time', 'all'),
            ('Last 24 hours', 'day'),
            ('Last week', 'week'),
            ('Last month', 'month'),
            ('Last year', 'year')
        ]
        
        for label, value in dates:
            rb = tk.Radiobutton(date_frame, text=label,
                               variable=self.date_var, value=value,
                               bg='#2d2d30', fg='#d4d4d4',
                               font=get_font('text'),
                               selectcolor='#1e1e1e')
            rb.pack(anchor=tk.W, padx=10, pady=2)
        
        # =================================================================
        # SIZE FILTERS
        # =================================================================
        size_frame = tk.LabelFrame(scrollable_frame, text="File Size",
                                  bg='#2d2d30', fg='#d4d4d4',
                                  font=get_font('heading', bold=True))
        size_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.size_var = tk.StringVar(value='all')
        
        sizes = [
            ('All sizes', 'all'),
            ('< 1 MB (Small)', 'small'),
            ('1-10 MB (Medium)', 'medium'),
            ('10-100 MB (Large)', 'large'),
            ('> 100 MB (Huge)', 'huge')
        ]
        
        for label, value in sizes:
            rb = tk.Radiobutton(size_frame, text=label,
                               variable=self.size_var, value=value,
                               bg='#2d2d30', fg='#d4d4d4',
                               font=get_font('text'),
                               selectcolor='#1e1e1e')
            rb.pack(anchor=tk.W, padx=10, pady=2)
        
        # =================================================================
        # DISPLAY OPTIONS
        # =================================================================
        display_frame = tk.LabelFrame(scrollable_frame, text="Display Options",
                                     bg='#2d2d30', fg='#d4d4d4',
                                     font=get_font('heading', bold=True))
        display_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.show_folders_var = tk.BooleanVar(value=True)
        tk.Checkbutton(display_frame, text="Show folders/directories",
                      variable=self.show_folders_var,
                      bg='#2d2d30', fg='#d4d4d4',
                      font=get_font('text'),
                      selectcolor='#1e1e1e').pack(anchor=tk.W, padx=10, pady=2)
        
        self.show_deleted_var = tk.BooleanVar(value=True)
        tk.Checkbutton(display_frame, text="Show deleted files (Git)",
                      variable=self.show_deleted_var,
                      bg='#2d2d30', fg='#d4d4d4',
                      font=get_font('text'),
                      selectcolor='#1e1e1e').pack(anchor=tk.W, padx=10, pady=2)
        
        self.show_hidden_var = tk.BooleanVar(value=True)
        tk.Checkbutton(display_frame, text="Show hidden files",
                      variable=self.show_hidden_var,
                      bg='#2d2d30', fg='#d4d4d4',
                      font=get_font('text'),
                      selectcolor='#1e1e1e').pack(anchor=tk.W, padx=10, pady=2)
        
        # =================================================================
        # BUTTONS
        # =================================================================
        btn_frame = tk.Frame(self, bg='#252526')
        btn_frame.pack(pady=15)
        
        tk.Button(btn_frame, text="Apply Filters",
                 bg='#4fc3f7', fg='#1e1e1e',
                 font=get_font('button', bold=True), width=15,
                 command=self.apply_filters).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="Reset All",
                 bg='#ff9800', fg='#1e1e1e',
                 font=get_font('button', bold=True), width=12,
                 command=self.reset_all).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="Cancel",
                 bg='#37373d', fg='#d4d4d4',
                 font=get_font('button'), width=12,
                 command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        # Filter count display
        self.count_label = tk.Label(self, text="",
                                    bg='#252526', fg='#9cdcfe',
                                    font=get_font('small', italic=True))
        self.count_label.pack(pady=5)
        
        # Bind Escape key
        self.bind('<Escape>', lambda e: self.cancel())
    
    def load_current_filters(self):
        """load current filter state from filter manager"""
        # Load extensions
        for ext, var in self.ext_vars.items():
            var.set(ext in self.filter_manager.active_extensions)
        
        # Load date filter
        if self.filter_manager.date_filter is None:
            self.date_var.set('all')
        else:
            # Determine which range based on date
            now = datetime.now()
            delta = now - self.filter_manager.date_filter
            if delta.days < 1:
                self.date_var.set('day')
            elif delta.days < 7:
                self.date_var.set('week')
            elif delta.days < 30:
                self.date_var.set('month')
            else:
                self.date_var.set('year')
        
        # Load size filter
        if self.filter_manager.size_filter is None:
            self.size_var.set('all')
        else:
            min_size, max_size = self.filter_manager.size_filter
            if max_size <= 1024*1024:
                self.size_var.set('small')
            elif max_size <= 10*1024*1024:
                self.size_var.set('medium')
            elif max_size <= 100*1024*1024:
                self.size_var.set('large')
            else:
                self.size_var.set('huge')
        
        # Load display options
        self.show_folders_var.set(self.filter_manager.show_folders_var.get())
        self.show_deleted_var.set(self.filter_manager.show_deleted_var.get())
        
        self.update_count()
    
    def select_all_extensions(self):
        """select all extension checkboxes"""
        for var in self.ext_vars.values():
            var.set(True)
        self.no_ext_var.set(True)
        self.update_count()
    
    def deselect_all_extensions(self):
        """deselect all extension checkboxes"""
        for var in self.ext_vars.values():
            var.set(False)
        self.no_ext_var.set(False)
        self.update_count()
    
    def select_code_only(self):
        """select only code file extensions"""
        code_exts = {'.py', '.js', '.html', '.css', '.java', '.c', '.cpp',
                    '.cs', '.go', '.rs', '.php', '.rb', '.swift', '.sh'}
        for ext, var in self.ext_vars.items():
            var.set(ext in code_exts)
        self.no_ext_var.set(False)
        self.update_count()
    
    def select_documents_only(self):
        """select only document extensions"""
        doc_exts = {'.txt', '.md', '.pdf', '.docx', '.doc', '.rtf', '.odt'}
        for ext, var in self.ext_vars.items():
            var.set(ext in doc_exts)
        self.no_ext_var.set(False)
        self.update_count()
    
    def update_count(self):
        """update the filter count display"""
        active = sum(1 for var in self.ext_vars.values() if var.get())
        if self.no_ext_var.get():
            active += 1
        
        total = len(self.ext_vars) + 1
        self.count_label.config(text=f"{active}/{total} file types selected")
    
    def apply_filters(self):
        """apply filters to filter manager"""
        # Update extensions
        self.filter_manager.active_extensions.clear()
        for ext, var in self.ext_vars.items():
            if var.get():
                self.filter_manager.active_extensions.add(ext)
        
        # Update date filter
        value = self.date_var.get()
        now = datetime.now()
        
        if value == 'all':
            self.filter_manager.date_filter = None
        elif value == 'day':
            self.filter_manager.date_filter = now - timedelta(days=1)
        elif value == 'week':
            self.filter_manager.date_filter = now - timedelta(weeks=1)
        elif value == 'month':
            self.filter_manager.date_filter = now - timedelta(days=30)
        elif value == 'year':
            self.filter_manager.date_filter = now - timedelta(days=365)
        
        # Update size filter
        value = self.size_var.get()
        
        if value == 'all':
            self.filter_manager.size_filter = None
        elif value == 'small':
            self.filter_manager.size_filter = (0, 1024*1024)
        elif value == 'medium':
            self.filter_manager.size_filter = (1024*1024, 10*1024*1024)
        elif value == 'large':
            self.filter_manager.size_filter = (10*1024*1024, 100*1024*1024)
        elif value == 'huge':
            self.filter_manager.size_filter = (100*1024*1024, float('inf'))
        
        # Update display options
        self.filter_manager.show_folders_var.set(self.show_folders_var.get())
        self.filter_manager.show_deleted_var.set(self.show_deleted_var.get())
        self.filter_manager.no_ext_var.set(self.no_ext_var.get())
        
        # Notify callback
        self.filter_manager.filter_changed()
        
        self.result = True
        self.destroy()
    
    def reset_all(self):
        """reset all filters to defaults"""
        self.select_all_extensions()
        self.date_var.set('all')
        self.size_var.set('all')
        self.show_folders_var.set(True)
        self.show_deleted_var.set(True)
        self.show_hidden_var.set(True)
        self.update_count()
    
    def cancel(self):
        """cancel without applying"""
        self.result = False
        self.destroy()
    
    def get_result(self):
        """return whether filters were applied"""
        self.wait_window()
        return self.result