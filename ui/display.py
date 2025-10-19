"""
display.py - handles the visual display
REFACTORED: Zettelkasten-style with focus mode and user attribution
- Circle nodes (small and clean)
- Color-coded by user/owner
- System vs user file distinction
- Focus mode showing only relevant nodes
"""

import tkinter as tk
import math
from ui.font_config import FONTS


def get_file_color(extension, is_hidden=False):
    """return color based on file type"""
    # hidden files get bright orange-red to stand out
    if is_hidden:
        return '#ff4500'
    
    ext = extension.lower()
    
    colors = {
        # code files
        '.py': '#3776ab', '.js': '#f7df1e', '.html': '#e34c26',
        '.css': '#264de4', '.json': '#00ff00', '.sh': '#89e051',
        '.c': '#555555', '.cpp': '#f34b7d', '.java': '#b07219',
        '.cs': '#178600', '.go': '#00add8', '.rs': '#dea584',
        '.php': '#4f5d95', '.rb': '#701516', '.swift': '#ffac45',
        
        # documents
        '.md': '#083fa1', '.txt': '#cccccc', '.docx': '#2b579a',
        '.doc': '#2b579a', '.pdf': '#ff0000', '.rtf': '#8b7355',
        '.odt': '#0080ff',
        
        # images
        '.jpg': '#ff69b4', '.jpeg': '#ff69b4', '.png': '#ff1493',
        '.gif': '#ff00ff', '.bmp': '#ffc0cb', '.svg': '#ffb13b',
        '.ico': '#00ffff', '.webp': '#ff6eb4',
        
        # archives
        '.zip': '#ffaa00', '.tar': '#ffaa00', '.gz': '#ffaa00',
        '.rar': '#ff8800', '.7z': '#ff6600',
        
        # executables
        '.exe': '#ff0000', '.dll': '#ff6666', '.so': '#ff6666',
        '.app': '#ff3333',
        
        # data
        '.csv': '#00ff00', '.xml': '#ff6600', '.yaml': '#cb171e',
        '.yml': '#cb171e', '.ini': '#d4d4d4', '.cfg': '#d4d4d4',
        '.conf': '#d4d4d4',
    }
    
    return colors.get(ext, '#ce93d8')


class GraphCanvas(tk.Canvas):
    """canvas that draws the zettelkasten-style graph"""
    
    def __init__(self, parent, graph, callback=None):
        super().__init__(parent, bg='#252526', highlightthickness=0)
        
        self.graph = graph
        self.callback = callback
        
        self.selected = None
        self.focus_node = None  # Current focus node for zettelkasten view
        self.node_items = {}
        self.edge_items = {}
        self.label_items = {}
        self.visible_nodes = set()
        
        # store node positions for hit detection
        self.node_positions = {}
        
        # view controls
        self.zoom = 1.0
        self.offset_x = 0
        self.offset_y = 0
        
        # focus mode settings
        self.focus_mode = True  # Default to focus mode
        self.max_hops = 2  # Show nodes within 2 hops of focus
        
        # user color mapping
        self.user_colors = {}
        
        # mouse controls
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.dragging = False
        self.drag_threshold = 5
        
        self.bind('<Button-1>', self.on_mouse_down)
        self.bind('<B1-Motion>', self.on_drag)
        self.bind('<ButtonRelease-1>', self.on_mouse_up)
        self.bind('<Double-Button-1>', self.on_double_click)
        self.bind('<MouseWheel>', self.scroll)
        self.bind('<Button-3>', self.on_right_click)  # Right-click to change focus
    
    def set_visible_nodes(self, visible_ids):
        """set which nodes should be visible"""
        self.visible_nodes = visible_ids
        self.draw()
    
    def set_focus_node(self, node_id):
        """Set new focus node and redraw in focus mode"""
        if node_id in self.graph.files:
            self.focus_node = node_id
            if self.focus_mode:
                self.update_visible_for_focus()
            self.draw()
    
    def toggle_focus_mode(self):
        """Toggle between focus mode and show-all mode"""
        self.focus_mode = not self.focus_mode
        if self.focus_mode:
            self.update_visible_for_focus()
        else:
            self.visible_nodes = set(self.graph.files.keys())
        self.draw()
    
    def update_visible_for_focus(self):
        """Update visible nodes based on current focus"""
        if not self.focus_node or self.focus_node not in self.graph.files:
            # Auto-select focus
            from graph.layout import auto_select_focus_node
            self.focus_node = auto_select_focus_node(self.graph)
        
        if not self.focus_node:
            self.visible_nodes = set(self.graph.files.keys())
            return
        
        # Find all nodes within max_hops
        from graph.layout import get_node_layers
        layers = get_node_layers(self.graph, self.focus_node, self.max_hops)
        
        visible = set()
        for hop, node_list in layers.items():
            visible.update(node_list)
        
        self.visible_nodes = visible
    
    def draw(self):
        """draw zettelkasten-style graph with circle nodes"""
        self.delete('all')
        self.node_items = {}
        self.edge_items = {}
        self.label_items = {}
        self.node_positions = {}
        
        if not self.graph:
            return
        
        # Get connected nodes if something is selected
        connected_ids = set()
        if self.selected and self.selected in self.graph.files:
            connected_ids.add(self.selected)
            for link in self.graph.links:
                if link.source == self.selected:
                    connected_ids.add(link.target)
                elif link.target == self.selected:
                    connected_ids.add(link.source)
        
        # Draw edges - ONLY if a node is selected
        if self.selected:
            for link in self.graph.links:
                src = self.graph.files.get(link.source)
                tgt = self.graph.files.get(link.target)
                
                if not (link.source in self.visible_nodes and link.target in self.visible_nodes):
                    continue
                
                # Only draw edges connected to the selected node
                is_connected = (link.source == self.selected or link.target == self.selected)
                
                if is_connected and src and tgt:
                    x1, y1 = self.transform(src.x, src.y)
                    x2, y2 = self.transform(tgt.x, tgt.y)
                    
                    # Color based on link type
                    if link.type == 'parent_folder':
                        color = '#00ff00'
                        width = 3
                    else:
                        color = '#ffff00'
                        width = 2
                    
                    edge_item = self.create_line(x1, y1, x2, y2, fill=color, width=width)
                    self.edge_items[(link.source, link.target)] = edge_item
        
        # Draw nodes as circles
        for node in self.graph.files.values():
            if node.id not in self.visible_nodes:
                continue
            
            x, y = self.transform(node.x, node.y)
            
            is_connected = node.id in connected_ids
            is_selected = node.id == self.selected
            is_focus = node.id == self.focus_node
            
            # Determine node appearance based on user/system
            is_system = node.info.get('is_system_file', False)
            owner = node.info.get('owner_name', 'unknown')
            
            # Draw node based on type (folder vs file)
            if node.is_folder:
                self.draw_folder_node(
                    x, y, node, is_system, owner, is_selected, is_focus, is_connected
                )
            else:
                self.draw_file_node(
                    x, y, node, is_system, owner, is_selected, is_focus, is_connected
                )
        
        # Highlight selected node
        if self.selected and self.selected in self.node_items:
            self.itemconfig(self.node_items[self.selected], width=4, outline='#ffff00')
        
        # Highlight focus node
        if self.focus_node and self.focus_node in self.node_items:
            self.itemconfig(self.node_items[self.focus_node], width=3, outline='#00ffff')
    
    def draw_file_node(self, x, y, node, is_system, owner, is_selected, is_focus, is_connected):
        """Draw a file node as a small circle"""
        size = 5 * self.zoom
        
        # Store position for hit detection
        self.node_positions[node.id] = {
            'x': x, 'y': y, 'size': size, 'shape': 'circle'
        }
        
        # Get color based on owner (for user files) or file type (for system)
        if is_system:
            # System files: dark gray
            fill_color = '#444444'
        else:
            # User files: color by owner
            fill_color = self.get_user_color(owner)
        
        # Dim non-connected nodes when something is selected
        if self.selected and not is_connected and not is_selected:
            fill_color = self.darken_color(fill_color)
        
        outline_color = '#ffffff'
        outline_width = 1
        
        if is_focus:
            outline_color = '#00ffff'
            outline_width = 3
        elif is_selected:
            outline_color = '#ffff00'
            outline_width = 4
        
        # Draw circle
        circle_item = self.create_oval(
            x - size, y - size, x + size, y + size,
            fill=fill_color, outline=outline_color, width=outline_width,
            tags=('node', node.id)
        )
        self.node_items[node.id] = circle_item
        
        # Draw text label (only if zoomed in enough)
        if self.zoom > 0.8:
            text_color = '#ffffff' if not (self.selected and not is_connected) else '#555555'
            font_size = int(FONTS['tiny'] * self.zoom)
            
            name_item = self.create_text(
                x, y + 15 * self.zoom,
                text=node.name[:20],
                fill=text_color,
                font=('Arial', font_size),
                tags=('label', node.id)
            )
            self.label_items[f'{node.id}_name'] = name_item
    
    def draw_folder_node(self, x, y, node, is_system, owner, is_selected, is_focus, is_connected):
        """Draw a folder node as a square"""
        size = 10 * self.zoom
        
        # Store position for hit detection
        self.node_positions[node.id] = {
            'x': x, 'y': y, 'size': size, 'shape': 'square'
        }
        
        # Folder color
        if node.is_hidden:
            fill_color = '#ff4500'
        elif is_system:
            fill_color = '#4fc3f7'  # System folders - cyan
        else:
            fill_color = self.get_user_color(owner)  # User folders - by owner
        
        # Dim non-connected nodes when something is selected
        if self.selected and not is_connected and not is_selected:
            fill_color = self.darken_color(fill_color)
        
        outline_color = '#ffffff'
        outline_width = 2
        
        if is_focus:
            outline_color = '#00ffff'
            outline_width = 3
        elif is_selected:
            outline_color = '#ffff00'
            outline_width = 4
        
        # Draw square
        square_item = self.create_rectangle(
            x - size, y - size, x + size, y + size,
            fill=fill_color, outline=outline_color, width=outline_width,
            tags=('node', node.id)
        )
        self.node_items[node.id] = square_item
        
        # Draw text label (only if zoomed in enough)
        if self.zoom > 0.8:
            text_color = '#ffffff' if not (self.selected and not is_connected) else '#555555'
            font_size = int(FONTS['tiny'] * self.zoom)
            
            name_item = self.create_text(
                x, y + size + 15 * self.zoom,
                text=node.name[:20],
                fill=text_color,
                font=('Arial', font_size),
                tags=('label', node.id)
            )
            self.label_items[f'{node.id}_name'] = name_item
    
    def get_user_color(self, owner_name):
        """Get consistent color for each user"""
        if owner_name not in self.user_colors:
            # Generate color from hash of owner name
            hash_val = hash(owner_name) % 360
            self.user_colors[owner_name] = self.hsl_to_hex(hash_val, 70, 45)
        
        return self.user_colors[owner_name]
    
    def hsl_to_hex(self, h, s, l):
        """Convert HSL to hex color"""
        # Normalize
        h = h / 360.0
        s = s / 100.0
        l = l / 100.0
        
        if s == 0:
            r = g = b = l
        else:
            def hue_to_rgb(p, q, t):
                if t < 0: t += 1
                if t > 1: t -= 1
                if t < 1/6: return p + (q - p) * 6 * t
                if t < 1/2: return q
                if t < 2/3: return p + (q - p) * (2/3 - t) * 6
                return p
            
            q = l * (1 + s) if l < 0.5 else l + s - l * s
            p = 2 * l - q
            r = hue_to_rgb(p, q, h + 1/3)
            g = hue_to_rgb(p, q, h)
            b = hue_to_rgb(p, q, h - 1/3)
        
        return f'#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}'
    
    def darken_color(self, hex_color, factor=0.4):
        """Darken a hex color"""
        # Remove #
        hex_color = hex_color.lstrip('#')
        
        # Convert to RGB
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        
        # Darken
        r = int(r * factor)
        g = int(g * factor)
        b = int(b * factor)
        
        return f'#{r:02x}{g:02x}{b:02x}'
    
    def find_node_at_position(self, x, y):
        """find which node is at position"""
        for node_id, pos in self.node_positions.items():
            dx = x - pos['x']
            dy = y - pos['y']
            dist = math.sqrt(dx*dx + dy*dy)
            
            if pos['shape'] == 'circle':
                if dist <= pos['size']:
                    return node_id
            else:  # square
                if abs(dx) <= pos['size'] and abs(dy) <= pos['size']:
                    return node_id
        
        return None
    
    def on_mouse_down(self, event):
        """handle mouse button press"""
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        self.dragging = False
    
    def on_drag(self, event):
        """handle mouse drag"""
        dx = event.x - self.drag_start_x
        dy = event.y - self.drag_start_y
        
        if abs(dx) > self.drag_threshold or abs(dy) > self.drag_threshold:
            self.dragging = True
            self.offset_x += dx
            self.offset_y += dy
            self.drag_start_x = event.x
            self.drag_start_y = event.y
            self.draw()
    
    def on_mouse_up(self, event):
        """handle mouse button release"""
        if not self.dragging:
            # Click - select node
            node_id = self.find_node_at_position(event.x, event.y)
            
            if node_id:
                self.selected = node_id
                self.draw()
                
                if self.callback:
                    self.callback(node_id)
        
        self.dragging = False
    
    def on_double_click(self, event):
        """handle double-click - set as new focus"""
        node_id = self.find_node_at_position(event.x, event.y)
        
        if node_id:
            self.set_focus_node(node_id)
            self.selected = node_id
            
            if self.callback:
                self.callback(node_id)
    
    def on_right_click(self, event):
        """handle right-click - change focus node"""
        node_id = self.find_node_at_position(event.x, event.y)
        
        if node_id:
            self.set_focus_node(node_id)
    
    def scroll(self, event):
        """handle zoom with mouse wheel"""
        if event.delta > 0:
            self.zoom *= 1.1
        else:
            self.zoom /= 1.1
        
        self.zoom = max(0.3, min(3.0, self.zoom))
        self.draw()
    
    def transform(self, x, y):
        """transform world coordinates to screen coordinates"""
        screen_x = x * self.zoom + self.offset_x
        screen_y = y * self.zoom + self.offset_y
        return screen_x, screen_y
    
    def reset_view(self):
        """reset zoom and pan"""
        self.zoom = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.draw()