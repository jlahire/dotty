"""
config_manager.py - manages persistent configuration including panel sizes
"""

import json
from pathlib import Path


class ConfigManager:
    """manages application configuration"""
    
    def __init__(self, config_file=Path(__file__).parent.parent / 'dotty_config.json'):
        self.config_file = Path(config_file)
        self.config = self.load_config()
    
    def load_config(self):
        """load configuration from file"""
        default_config = {
            'window': {
                'width': 1400,
                'height': 900,
                'x': None,  # None means center
                'y': None
            },
            'panels': {
                'left_width': 250,
                'right_width': 300,
                'tree_height': 400,
                'timeline_height': 200,
                'heatmap_height': 200
            },
            'view': {
                'zoom_level': 1.0,
                'show_hidden': True,
                'show_deleted': True
            },
            'recent_paths': [],
            'max_recent': 10
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    loaded = json.load(f)
                    # Merge with defaults to handle new keys
                    self._merge_dicts(default_config, loaded)
                    return default_config
            except Exception as e:
                print(f"Error loading config: {e}")
                return default_config
        
        return default_config
    
    def _merge_dicts(self, base, overlay):
        """recursively merge overlay into base"""
        for key, value in overlay.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_dicts(base[key], value)
            else:
                base[key] = value
    
    def save_config(self):
        """save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def get_window_geometry(self):
        """get window geometry string"""
        w = self.config['window']
        if w['x'] is not None and w['y'] is not None:
            return f"{w['width']}x{w['height']}+{w['x']}+{w['y']}"
        else:
            return f"{w['width']}x{w['height']}"
    
    def save_window_state(self, root):
        """save window position and size"""
        self.config['window']['width'] = root.winfo_width()
        self.config['window']['height'] = root.winfo_height()
        self.config['window']['x'] = root.winfo_x()
        self.config['window']['y'] = root.winfo_y()
        self.save_config()
    
    def save_panel_sizes(self, main_paned, left_paned, right_paned):
        """save panel sizes from PanedWindow widgets"""
        try:
            # Get sash positions from main paned (left | center | right)
            if len(main_paned.panes()) >= 2:
                # Left panel width
                self.config['panels']['left_width'] = main_paned.sash_coord(0)[0]
                
            if len(main_paned.panes()) >= 3:
                # Right panel is measured from right edge
                total_width = main_paned.winfo_width()
                right_sash = main_paned.sash_coord(1)[0]
                self.config['panels']['right_width'] = total_width - right_sash
            
            # Left paned (tree | timeline)
            if left_paned and len(left_paned.panes()) >= 1:
                self.config['panels']['tree_height'] = left_paned.sash_coord(0)[1]
            
            # Right paned (info | heatmap)
            if right_paned and len(right_paned.panes()) >= 1:
                # Calculate heatmap height
                total_height = right_paned.winfo_height()
                info_height = right_paned.sash_coord(0)[1]
                self.config['panels']['heatmap_height'] = total_height - info_height
            
            self.save_config()
        except Exception as e:
            print(f"Error saving panel sizes: {e}")
    
    def restore_panel_sizes(self, main_paned, left_paned, right_paned):
        """restore panel sizes to PanedWindow widgets"""
        try:
            # Restore after a short delay to let windows render
            def do_restore():
                p = self.config['panels']
                
                # Main paned
                if len(main_paned.panes()) >= 2:
                    main_paned.sash_place(0, p['left_width'], 0)
                
                if len(main_paned.panes()) >= 3:
                    total_width = main_paned.winfo_width()
                    right_pos = total_width - p['right_width']
                    main_paned.sash_place(1, right_pos, 0)
                
                # Left paned
                if left_paned and len(left_paned.panes()) >= 1:
                    left_paned.sash_place(0, 0, p['tree_height'])
                
                # Right paned
                if right_paned and len(right_paned.panes()) >= 1:
                    total_height = right_paned.winfo_height()
                    info_pos = total_height - p['heatmap_height']
                    right_paned.sash_place(0, 0, info_pos)
            
            # Schedule restore after 100ms
            main_paned.after(100, do_restore)
        except Exception as e:
            print(f"Error restoring panel sizes: {e}")
    
    def add_recent_path(self, path):
        """add path to recent paths list"""
        path_str = str(path)
        
        # Remove if already in list
        if path_str in self.config['recent_paths']:
            self.config['recent_paths'].remove(path_str)
        
        # Add to front
        self.config['recent_paths'].insert(0, path_str)
        
        # Trim to max
        self.config['recent_paths'] = self.config['recent_paths'][:self.config['max_recent']]
        
        self.save_config()
    
    def get_recent_paths(self):
        """get list of recent paths"""
        return self.config['recent_paths']
    
    def set(self, key_path, value):
        """set a config value using dot notation (e.g., 'view.zoom_level')"""
        keys = key_path.split('.')
        current = self.config
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
        self.save_config()
    
    def get(self, key_path, default=None):
        """get a config value using dot notation"""
        keys = key_path.split('.')
        current = self.config
        
        for key in keys:
            if key not in current:
                return default
            current = current[key]
        
        return current