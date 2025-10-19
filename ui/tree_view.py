"""
tree_view.py - shows file structure as a tree
imports: graph_stuff.py for Graph
"""

import tkinter as tk
from tkinter import ttk
from pathlib import Path
from ui.font_config import get_font, FONTS


def get_file_color(extension, is_hidden=False):
    """return color based on file type"""
    # hidden files always orange
    if is_hidden:
        return '#ff4500'
    
    ext = extension.lower()
    
    colors = {
        '.py': '#3776ab', '.js': '#f7df1e', '.html': '#e34c26',
        '.css': '#264de4', '.json': '#00ff00', '.sh': '#89e051',
        '.c': '#555555', '.cpp': '#f34b7d', '.java': '#b07219',
        '.cs': '#178600', '.go': '#00add8', '.rs': '#dea584',
        '.php': '#4f5d95', '.rb': '#701516', '.swift': '#ffac45',
        '.md': '#083fa1', '.txt': '#cccccc', '.docx': '#2b579a',
        '.doc': '#2b579a', '.pdf': '#ff0000', '.rtf': '#8b7355',
        '.odt': '#0080ff',
        '.jpg': '#ff69b4', '.jpeg': '#ff69b4', '.png': '#ff1493',
        '.gif': '#ff00ff', '.bmp': '#ffc0cb', '.svg': '#ffb13b',
        '.ico': '#00ffff', '.webp': '#ff6eb4',
        '.zip': '#ffaa00', '.tar': '#ffaa00', '.gz': '#ffaa00',
        '.rar': '#ff8800', '.7z': '#ff6600',
        '.exe': '#ff0000', '.dll': '#ff6666', '.so': '#ff6666',
        '.app': '#ff3333',
        '.csv': '#00ff00', '.xml': '#ff6600', '.yaml': '#cb171e',
        '.yml': '#cb171e', '.ini': '#d4d4d4', '.cfg': '#d4d4d4',
        '.conf': '#d4d4d4',
    }
    
    return colors.get(ext, '#ce93d8')


class TreeView(tk.Frame):
    """tree view showing folder structure"""
    
    def __init__(self, parent, graph, callback=None, expand_callback=None):
        super().__init__(parent, bg='#1e1e1e')
        
        self.graph = graph
        self.callback = callback
        self.expand_callback = expand_callback
        
        # title and buttons
        header = tk.Frame(self, bg='#1e1e1e')
        header.pack(fill=tk.X, pady=5)
        
        tk.Label(header, text="file structure", font=get_font('button', bold=True),
                bg='#1e1e1e', fg='#4fc3f7').pack(side=tk.LEFT, padx=5)
        
        # expand/collapse buttons with icons
        btn_frame = tk.Frame(header, bg='#1e1e1e')
        btn_frame.pack(side=tk.RIGHT, padx=5)
        
        # Expand all button with + icon
        expand_btn = tk.Button(btn_frame, text="⊕", bg='#37373d', fg='#4fc3f7',
                 font=('Arial', 14, 'bold'),
                 relief=tk.FLAT, command=self.expand_all,
                 width=2, height=1)
        expand_btn.pack(side=tk.LEFT, padx=2)
        self._create_tooltip(expand_btn, "Expand All")
        
        # Collapse all button with - icon
        collapse_btn = tk.Button(btn_frame, text="⊖", bg='#37373d', fg='#4fc3f7',
                 font=('Arial', 14, 'bold'),
                 relief=tk.FLAT, command=self.collapse_all,
                 width=2, height=1)
        collapse_btn.pack(side=tk.LEFT, padx=2)
        self._create_tooltip(collapse_btn, "Collapse All")
        
        # tree container
        tree_container = tk.Frame(self, bg='#2d2d30')
        tree_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # create tree
        self.tree = ttk.Treeview(tree_container, show='tree')
        self.tree.column('#0', width=300, minwidth=200, stretch=True)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # configure tree style
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Treeview',
                       background='#2d2d30',
                       foreground='#d4d4d4',
                       fieldbackground='#2d2d30',
                       font=get_font('tree'),
                       borderwidth=0)
        style.map('Treeview',
                 background=[('selected', '#37373d')],
                 foreground=[('selected', '#ffffff')])
        
        # scrollbar
        scroll = ttk.Scrollbar(tree_container, orient='vertical', command=self.tree.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scroll.set)
        
        # bind events
        self.tree.bind('<<TreeviewSelect>>', self.on_select)
        self.tree.bind('<<TreeviewOpen>>', self.on_expand)
        self.tree.bind('<<TreeviewClose>>', self.on_collapse)
        
        # store mappings
        self.item_to_node = {}
        self.node_to_item = {}
        
        # create color tags
        self.setup_color_tags()
    
    def _create_tooltip(self, widget, text):
        """Create a simple tooltip for a widget"""
        def on_enter(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            label = tk.Label(tooltip, text=text, background="#ffffe0", 
                           relief=tk.SOLID, borderwidth=1, font=('Arial', 9))
            label.pack()
            widget.tooltip = tooltip
        
        def on_leave(event):
            if hasattr(widget, 'tooltip'):
                widget.tooltip.destroy()
                del widget.tooltip
        
        widget.bind('<Enter>', on_enter)
        widget.bind('<Leave>', on_leave)
    
    def setup_color_tags(self):
        """create color tags for tree items"""
        # Calculate tree font size for bold variant
        tree_size = FONTS['tree']
        
        # hidden files/folders - bright orange
        self.tree.tag_configure('hidden', foreground='#ff4500', 
                               font=('TkDefaultFont', tree_size, 'bold'))
        
        # folder color
        self.tree.tag_configure('folder', foreground='#4fc3f7')
        
        # file colors
        extensions = [
            ('.py', '#3776ab'), ('.js', '#f7df1e'), ('.html', '#e34c26'),
            ('.css', '#264de4'), ('.json', '#00ff00'), ('.sh', '#89e051'),
            ('.md', '#083fa1'), ('.txt', '#cccccc'), ('.docx', '#2b579a'),
            ('.pdf', '#ff0000'), ('.jpg', '#ff69b4'), ('.png', '#ff1493'),
            ('.gif', '#ff00ff'), ('.zip', '#ffaa00'), ('.exe', '#ff0000'),
            ('.c', '#555555'), ('.cpp', '#f34b7d'), ('.java', '#b07219'),
            ('.xml', '#ff6600'), ('.csv', '#00ff00')
        ]
        
        for ext, color in extensions:
            self.tree.tag_configure(f'ext{ext}', foreground=color)
        
        # default
        self.tree.tag_configure('file', foreground='#ce93d8')
    
    def populate(self):
        """build tree from graph"""
        if not self.graph:
            return
        
        self.tree.delete(*self.tree.get_children())
        self.item_to_node = {}
        self.node_to_item = {}
        
        # FIX: Use root_path instead of root
        if not hasattr(self.graph, 'root_path') or not self.graph.root_path:
            return
        
        root_path = Path(self.graph.root_path)
        
        # build folder structure
        folders = {}
        
        # Store configured tags for quick lookup
        configured_tags = {
            '.py', '.js', '.html', '.css', '.json', '.sh', 
            '.md', '.txt', '.docx', '.pdf', '.jpg', '.png',
            '.gif', '.zip', '.exe', '.c', '.cpp', '.java',
            '.xml', '.csv'
        }
        
        for node_id, node in self.graph.files.items():
            if not hasattr(node, 'path'):
                continue
            
            # get path relative to root
            try:
                rel_path = Path(node.path).relative_to(root_path)
            except ValueError:
                rel_path = Path(node.path)
            
            # check if hidden
            is_hidden = any(part.startswith('.') for part in rel_path.parts)
            
            # add all parent folders
            current = root_path
            parent_item = ''
            
            for part in rel_path.parts[:-1]:
                current = current / part
                
                if current not in folders:
                    is_folder_hidden = part.startswith('.')
                    tag = 'hidden' if is_folder_hidden else 'folder'
                    
                    item = self.tree.insert(parent_item, 'end', text=f'📁 {part}',
                                          tags=(tag,), open=False)
                    folders[current] = item
                
                parent_item = folders[current]
            
            # add file
            filename = rel_path.parts[-1] if rel_path.parts else node.path
            ext = Path(filename).suffix
            
            if is_hidden:
                tag = 'hidden'
            elif ext and ext in configured_tags:
                tag = f'ext{ext}'
            else:
                tag = 'file'
            
            # show extension in tree
            item = self.tree.insert(parent_item, 'end', text=f'📄 {filename}',
                                  tags=(tag,))
            
            self.item_to_node[item] = node_id
            self.node_to_item[node_id] = item
    
    def expand_all(self):
        """expand all folders"""
        def expand_recursive(item):
            self.tree.item(item, open=True)
            for child in self.tree.get_children(item):
                expand_recursive(child)
     
        for item in self.tree.get_children():
            expand_recursive(item)
        
        if self.expand_callback:
            self.expand_callback()
    
    def collapse_all(self):
        """collapse all except root"""
        def collapse_recursive(item, is_root=False):
            if not is_root:
                self.tree.item(item, open=False)
            for child in self.tree.get_children(item):
                collapse_recursive(child, False)
        
        for item in self.tree.get_children():
            collapse_recursive(item, True)
        
        if self.expand_callback:
            self.expand_callback()
    
    def get_visible_nodes(self):
        """return visible node ids"""
        visible = set()
        
        def check_item(item, parent_visible=True):
            node_id = self.item_to_node.get(item)
            
            if node_id and parent_visible:
                visible.add(node_id)
            
            is_open = self.tree.item(item, 'open')
            children_visible = parent_visible and is_open
            
            for child in self.tree.get_children(item):
                check_item(child, children_visible)
        
        for item in self.tree.get_children():
            check_item(item, parent_visible=True)
        
        return visible
    
    def on_select(self, event):
        """handle selection"""
        selection = self.tree.selection()
        if selection and self.callback:
            item = selection[0]
            node_id = self.item_to_node.get(item)
            if node_id:
                self.callback(node_id)
    
    def on_expand(self, event):
        """handle expansion"""
        if self.expand_callback:
            self.expand_callback()
    
    def on_collapse(self, event):
        """handle collapse"""
        if self.expand_callback:
            self.expand_callback()
            
    def select_node(self, node_id):
        """Programmatically select a node in the tree"""
        if node_id in self.node_to_item:
            item_id = self.node_to_item[node_id]
            self.tree.selection_set(item_id)
            self.tree.see(item_id)  # Scroll to make it visible