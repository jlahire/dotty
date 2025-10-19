"""
info_panel.py - sidebar showing file info
imports: graph_stuff.py for Graph
"""

import tkinter as tk
from tkinter import scrolledtext
from ui.font_config import get_font, get_code_font
from ui.dialogs.file_preview import FilePreview


class InfoPanel(tk.Frame):
    """sidebar with file details and search"""
    
    def __init__(self, parent, graph, callback=None):
        super().__init__(parent, bg='#1e1e1e')
        
        self.graph = graph
        self.callback = callback
        self.current_node = None  # Initialize current_node
        
        # title
        tk.Label(self, text="dotty", font=get_font('title', bold=True),
                bg='#1e1e1e', fg='#4fc3f7').pack(pady=10)
        
        # search box at top
        tk.Label(self, text="search:", bg='#1e1e1e', fg='#d4d4d4',
                font=get_font('text', bold=True)).pack(anchor=tk.W, padx=10)
        
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.search)
        tk.Entry(self, textvariable=self.search_var, bg='#3c3c3c',
                fg='#d4d4d4', font=get_font('text')).pack(fill=tk.X, padx=10, pady=5)
        
        # search results
        self.results_area = tk.Frame(self, bg='#1e1e1e')
        self.results_area.pack(fill=tk.BOTH, padx=10)
        
        # stats below search
        self.stats = tk.Label(self, text="no graph", bg='#2d2d30',
                             fg='#d4d4d4', font=get_font('text'))
        self.stats.pack(fill=tk.X, padx=10, pady=10)
        
        # Create notebook for tabs
        self.notebook = tk.Frame(self, bg='#1e1e1e')
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Tab buttons
        tab_frame = tk.Frame(self.notebook, bg='#2d2d30', height=30)
        tab_frame.pack(side=tk.TOP, fill=tk.X)
        tab_frame.pack_propagate(False)

        self.info_tab_btn = tk.Button(tab_frame, text="Info", 
                                      bg='#4fc3f7', fg='#1e1e1e',
                                      font=get_font('small', bold=True),
                                      relief=tk.FLAT, width=10,
                                      command=self.show_info_tab)
        self.info_tab_btn.pack(side=tk.LEFT, padx=2, pady=2)

        self.preview_tab_btn = tk.Button(tab_frame, text="Preview", 
                                         bg='#37373d', fg='#d4d4d4',
                                         font=get_font('small', bold=True),
                                         relief=tk.FLAT, width=10,
                                         command=self.show_preview_tab)
        self.preview_tab_btn.pack(side=tk.LEFT, padx=2, pady=2)

        # Content area
        self.content_area = tk.Frame(self.notebook, bg='#1e1e1e')
        self.content_area.pack(fill=tk.BOTH, expand=True)

        # Info display (default tab)
        self.info_frame = tk.Frame(self.content_area, bg='#1e1e1e')
        self.info_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(self.info_frame, text="file info:", bg='#1e1e1e', fg='#d4d4d4',
                font=get_font('text', bold=True)).pack(anchor=tk.W, padx=0, pady=(10,5))

        self.info_text = tk.Text(
            self.info_frame, bg='#2d2d30', fg='#d4d4d4',
            font=get_code_font('code'), wrap=tk.WORD, height=20)
        self.info_text.pack(fill=tk.BOTH, expand=True, padx=0, pady=5)

        # Preview widget (hidden by default)
        self.preview_frame = None
        self.current_tab = 'info'
        
        # setup color tags
        self.setup_tags()
        
        self.info_text.insert('1.0', "click a node to see details")
        self.info_text.config(state=tk.DISABLED)
    
    def setup_tags(self):
        """setup text tags for color coding"""
        # labels (field names)
        self.info_text.tag_config('label', foreground='#9cdcfe', font=get_code_font('code'))
        
        # values
        self.info_text.tag_config('value', foreground='#d4d4d4')
        
        # file name
        self.info_text.tag_config('filename', foreground='#4fc3f7', font=get_code_font('code'))
        
        # file type
        self.info_text.tag_config('type_file', foreground='#ce93d8')
        self.info_text.tag_config('type_folder', foreground='#4fc3f7')
        
        # size
        self.info_text.tag_config('size', foreground='#b5cea8')
        
        # extension
        self.info_text.tag_config('extension', foreground='#f7df1e')
        
        # dates
        self.info_text.tag_config('date', foreground='#dcdcaa')
        
        # path
        self.info_text.tag_config('path', foreground='#89e051')
        
        # section headers
        self.info_text.tag_config('header', foreground='#ff6b6b', font=get_code_font('code'))
        
        # connection types
        self.info_text.tag_config('conn_name', foreground='#ce93d8')
        self.info_text.tag_config('conn_type', foreground='#666666', font=get_code_font('code'))
        
        # hidden indicator
        self.info_text.tag_config('hidden', foreground='#ff4500', font=get_code_font('code'))
    
    def update_stats(self):
        """update the stats display"""
        if self.graph:
            text = f"files: {len(self.graph.files)}\nlinks: {len(self.graph.links)}"
            self.stats.config(text=text)
        
    def show_info(self, node):
        """show info about a file"""
        self.current_node = node
        
        # Update preview if preview tab is active
        if self.current_tab == 'preview' and self.preview_frame:
            self.preview_frame.preview_file(node)
        
        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete('1.0', tk.END)
        
        # file name
        self.insert_colored("name: ", 'label')
        self.insert_colored(f"{node.name}\n", 'filename')
        
        # type
        self.insert_colored("type: ", 'label')
        if node.is_folder:
            self.insert_colored("folder\n", 'type_folder')
        else:
            self.insert_colored("file\n", 'type_file')
        
        # hidden status
        if node.is_hidden:
            self.insert_colored("hidden: ", 'label')
            self.insert_colored("YES\n", 'hidden')
        
        self.insert_colored("\n", 'value')
        
        # size
        self.insert_colored("size: ", 'label')
        self.insert_colored(f"{self.format_size(node.info.get('size', 0))}\n", 'size')
        
        # extension
        ext = node.info.get('extension') or 'none'
        self.insert_colored("extension: ", 'label')
        self.insert_colored(f"{ext}\n", 'extension')
        
        # modified date
        modified = node.info.get('modified', 'unknown')[:19]
        self.insert_colored("modified: ", 'label')
        self.insert_colored(f"{modified}\n", 'date')
        
        # path
        self.insert_colored("\npath:\n", 'header')
        self.insert_colored(f"{node.info.get('full_path', 'unknown')}\n", 'path')
        
        # connections - FIXED TO HANDLE DICT
        if hasattr(node, 'connections') and node.connections:
            # Handle both dict and list for backwards compatibility
            if isinstance(node.connections, dict):
                self.insert_colored("\nconnections:\n", 'header')
                for conn_type, targets in node.connections.items():
                    self.insert_colored(f"  {conn_type}: ", 'conn_type')
                    for t in targets[:5]:
                        target_node = self.graph.files.get(t)
                        if target_node:
                            self.insert_colored(f"{target_node.name} ", 'conn_name')
                    if len(targets) > 5:
                        self.insert_colored(f"... ({len(targets)-5} more)", 'value')
                    self.insert_colored("\n", 'value')
            elif isinstance(node.connections, list) and len(node.connections) > 0:
                # Fallback for old list format
                self.insert_colored("\nconnections:\n", 'header')
                self.insert_colored(f"  linked to {len(node.connections)} nodes\n", 'value')
    
        self.info_text.config(state=tk.DISABLED)
    
    def insert_colored(self, text, tag):
        """insert text with a specific color tag"""
        self.info_text.insert(tk.END, text, tag)
    
    def search(self, *args):
        """search for files matching the query"""
        query = self.search_var.get().lower()
        
        # clear previous results
        for widget in self.results_area.winfo_children():
            widget.destroy()
        
        if not query or not self.graph:
            return
        
        # search in file names
        results = []
        for node in self.graph.files.values():
            if query in node.name.lower():
                results.append(node)
        
        # show results
        if results:
            tk.Label(self.results_area, text=f"found {len(results)}:",
                    bg='#1e1e1e', fg='#4fc3f7',
                    font=get_font('small')).pack(anchor=tk.W, pady=2)
            
            for node in results[:10]:
                # show hidden indicator in search results too
                icon = '[H]' if node.is_hidden else ('[d]' if node.is_folder else '[f]')
                fg_color = '#ff4500' if node.is_hidden else '#d4d4d4'
                
                btn = tk.Button(self.results_area,
                               text=f"{icon} {node.name}",
                               bg='#37373d', fg=fg_color, relief=tk.FLAT, anchor=tk.W,
                               font=get_font('small'),
                               command=lambda n=node.id: self.select(n))
                btn.pack(fill=tk.X, pady=1)
    
    def select(self, node_id):
        """handle selecting a search result"""
        if self.callback:
            self.callback(node_id)
        node = self.graph.files.get(node_id)
        if node:
            self.show_info(node)
    
    def show_info_tab(self):
        """switch to info tab"""
        self.current_tab = 'info'
        self.info_tab_btn.config(bg='#4fc3f7', fg='#1e1e1e')
        self.preview_tab_btn.config(bg='#37373d', fg='#d4d4d4')
        
        if self.preview_frame:
            self.preview_frame.pack_forget()
        self.info_frame.pack(fill=tk.BOTH, expand=True)

    def show_preview_tab(self):
        """switch to preview tab"""
        self.current_tab = 'preview'
        self.info_tab_btn.config(bg='#37373d', fg='#d4d4d4')
        self.preview_tab_btn.config(bg='#4fc3f7', fg='#1e1e1e')
        
        self.info_frame.pack_forget()
        
        if not self.preview_frame:
            self.preview_frame = FilePreview(self.content_area)
        
        self.preview_frame.pack(fill=tk.BOTH, expand=True)
        
        # Preview the current node if one is selected
        if self.current_node:
            self.preview_frame.preview_file(self.current_node)
    
    @staticmethod
    def format_size(bytes):
        """format bytes to readable size"""
        if bytes == 0:
            return '0 B'
        units = ['B', 'KB', 'MB', 'GB']
        i = 0
        while bytes >= 1024 and i < len(units)-1:
            bytes /= 1024
            i += 1
        return f"{bytes:.2f} {units[i]}"