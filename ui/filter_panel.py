"""
filter_panel.py - filter controls for the graph
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
from ui.font_config import get_font


class FilterPanel(tk.Frame):
    """panel with filter controls"""
    
    def __init__(self, parent, callback=None):
        super().__init__(parent, bg='#1e1e1e')
        
        self.callback = callback  # called when filters change
        
        # filter state
        self.active_extensions = set()
        self.date_filter = None
        self.size_filter = None
        
        # title
        tk.Label(self, text="filters", font=get_font('button', bold=True),
                bg='#1e1e1e', fg='#4fc3f7').pack(pady=5)
        
        # extension filter
        ext_frame = tk.LabelFrame(self, text="file types", bg='#2d2d30',
                                 fg='#d4d4d4', font=get_font('small'))
        ext_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.ext_vars = {}
        extensions = ['.py', '.js', '.html', '.css', '.md', '.txt',
                     '.pdf', '.docx', '.jpg', '.png', '.json', '.sh']
        
        for ext in extensions:
            var = tk.BooleanVar(value=True)
            self.active_extensions.add(ext)
            cb = tk.Checkbutton(ext_frame, text=ext, variable=var,
                               bg='#2d2d30', fg='#d4d4d4',
                               font=get_font('small'),
                               selectcolor='#1e1e1e',
                               command=lambda e=ext, v=var: self.toggle_ext(e, v))
            cb.pack(anchor=tk.W, padx=5, pady=2)
            self.ext_vars[ext] = var
        
        # add "no extension" filter
        self.no_ext_var = tk.BooleanVar(value=True)
        cb = tk.Checkbutton(ext_frame, text="(no extension)", variable=self.no_ext_var,
                           bg='#2d2d30', fg='#d4d4d4',
                           font=get_font('small'),
                           selectcolor='#1e1e1e',
                           command=self.filter_changed)
        cb.pack(anchor=tk.W, padx=5, pady=2)
        
        # date filter
        date_frame = tk.LabelFrame(self, text="modified date", bg='#2d2d30',
                                  fg='#d4d4d4', font=get_font('small'))
        date_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.date_var = tk.StringVar(value='all')
        
        dates = [
            ('all time', 'all'),
            ('last 24 hours', 'day'),
            ('last week', 'week'),
            ('last month', 'month'),
            ('last year', 'year')
        ]
        
        for label, value in dates:
            rb = tk.Radiobutton(date_frame, text=label, variable=self.date_var,
                               value=value, bg='#2d2d30', fg='#d4d4d4',
                               font=get_font('small'),
                               selectcolor='#1e1e1e',
                               command=self.date_changed)
            rb.pack(anchor=tk.W, padx=5, pady=2)
        
        # size filter
        size_frame = tk.LabelFrame(self, text="file size", bg='#2d2d30',
                                  fg='#d4d4d4', font=get_font('small'))
        size_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.size_var = tk.StringVar(value='all')
        
        sizes = [
            ('all sizes', 'all'),
            ('< 1 MB', 'small'),
            ('1-10 MB', 'medium'),
            ('10-100 MB', 'large'),
            ('> 100 MB', 'huge')
        ]
        
        for label, value in sizes:
            rb = tk.Radiobutton(size_frame, text=label, variable=self.size_var,
                               value=value, bg='#2d2d30', fg='#d4d4d4',
                               font=get_font('small'),
                               selectcolor='#1e1e1e',
                               command=self.size_changed)
            rb.pack(anchor=tk.W, padx=5, pady=2)
        
        # display options
        folder_frame = tk.LabelFrame(self, text="display", bg='#2d2d30',
                                    fg='#d4d4d4', font=get_font('small'))
        folder_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.show_folders_var = tk.BooleanVar(value=True)
        tk.Checkbutton(folder_frame, text="show folders",
                      variable=self.show_folders_var,
                      bg='#2d2d30', fg='#d4d4d4',
                      font=get_font('small'),
                      selectcolor='#1e1e1e',
                      command=self.filter_changed).pack(anchor=tk.W, padx=5, pady=2)
        
        self.show_deleted_var = tk.BooleanVar(value=True)
        tk.Checkbutton(folder_frame, text="show deleted (git)",
                      variable=self.show_deleted_var,
                      bg='#2d2d30', fg='#d4d4d4',
                      font=get_font('small'),
                      selectcolor='#1e1e1e',
                      command=self.filter_changed).pack(anchor=tk.W, padx=5, pady=2)
        
        # reset button
        tk.Button(self, text="reset all filters", bg='#37373d', fg='#d4d4d4',
                 font=get_font('small'),
                 command=self.reset_filters).pack(fill=tk.X, padx=5, pady=10)
    
    def toggle_ext(self, ext, var):
        """toggle extension filter"""
        if var.get():
            self.active_extensions.add(ext)
        else:
            self.active_extensions.discard(ext)
        self.filter_changed()
    
    def date_changed(self):
        """handle date filter change"""
        value = self.date_var.get()
        now = datetime.now()
        
        if value == 'all':
            self.date_filter = None
        elif value == 'day':
            self.date_filter = now - timedelta(days=1)
        elif value == 'week':
            self.date_filter = now - timedelta(weeks=1)
        elif value == 'month':
            self.date_filter = now - timedelta(days=30)
        elif value == 'year':
            self.date_filter = now - timedelta(days=365)
        
        self.filter_changed()
    
    def size_changed(self):
        """handle size filter change"""
        value = self.size_var.get()
        
        if value == 'all':
            self.size_filter = None
        elif value == 'small':
            self.size_filter = (0, 1024*1024)
        elif value == 'medium':
            self.size_filter = (1024*1024, 10*1024*1024)
        elif value == 'large':
            self.size_filter = (10*1024*1024, 100*1024*1024)
        elif value == 'huge':
            self.size_filter = (100*1024*1024, float('inf'))
        
        self.filter_changed()
    
    def filter_changed(self):
        """notify callback that filters changed"""
        if self.callback:
            self.callback()
    
    def reset_filters(self):
        """reset all filters to default"""
        # reset extensions
        for ext, var in self.ext_vars.items():
            var.set(True)
            self.active_extensions.add(ext)
        
        # reset no extension
        self.no_ext_var.set(True)
        
        # reset date
        self.date_var.set('all')
        self.date_filter = None
        
        # reset size
        self.size_var.set('all')
        self.size_filter = None
        
        # reset folders
        self.show_folders_var.set(True)
        
        # reset deleted
        self.show_deleted_var.set(True)
        
        self.filter_changed()
    
    def should_show_node(self, node):
        """check if node passes all filters"""
        # deleted file filter
        if hasattr(node, 'is_deleted') and node.is_deleted:
            if not self.show_deleted_var.get():
                return False
        
        # folder filter
        if node.is_folder:
            return self.show_folders_var.get()
        
        # extension filter
        ext = node.info.get('extension', '').lower()
        
        # if no extension
        if not ext:
            return self.no_ext_var.get()
        
        # if has extension, check if it's in active list
        if ext not in self.active_extensions:
            return False
        
        # date filter
        if self.date_filter:
            try:
                mod_date = datetime.fromisoformat(node.info.get('modified', ''))
                if mod_date < self.date_filter:
                    return False
            except:
                pass
        
        # size filter
        if self.size_filter:
            size = node.info.get('size', 0)
            min_size, max_size = self.size_filter
            if not (min_size <= size < max_size):
                return False
        
        return True