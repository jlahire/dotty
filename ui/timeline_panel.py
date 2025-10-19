"""
timeline_panel.py - timeline slider for git repositories
shows file evolution over time
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime
from ui.font_config import get_font


class TimelinePanel(tk.Frame):
    """timeline slider for viewing git history"""
    
    def __init__(self, parent, callback=None):
        super().__init__(parent, bg='#1e1e1e')
        
        self.callback = callback
        self.git_events = []  # list of (timestamp, event_type, file_info)
        self.min_date = None
        self.max_date = None
        self.current_timestamp = None
        
        # title
        tk.Label(self, text="timeline (git only)", font=get_font('button', bold=True),
                bg='#1e1e1e', fg='#4fc3f7').pack(pady=5)
        
        # info label
        self.info_label = tk.Label(self, text="no git repository",
                                   bg='#2d2d30', fg='#d4d4d4',
                                   font=get_font('small'))
        self.info_label.pack(fill=tk.X, padx=10, pady=5)
        
        # slider frame
        slider_frame = tk.Frame(self, bg='#2d2d30')
        slider_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # date labels
        self.min_label = tk.Label(slider_frame, text="earliest",
                                  bg='#2d2d30', fg='#666666',
                                  font=get_font('tiny'))
        self.min_label.pack(side=tk.LEFT, padx=5)
        
        self.max_label = tk.Label(slider_frame, text="latest",
                                  bg='#2d2d30', fg='#666666',
                                  font=get_font('tiny'))
        self.max_label.pack(side=tk.RIGHT, padx=5)
        
        # slider
        self.slider = tk.Scale(self, from_=0, to=100, orient=tk.HORIZONTAL,
                              bg='#2d2d30', fg='#d4d4d4',
                              highlightthickness=0, troughcolor='#1e1e1e',
                              command=self.on_slider_change)
        self.slider.pack(fill=tk.X, padx=10, pady=5)
        self.slider.set(100)  # default to latest
        
        # current date display
        self.current_label = tk.Label(self, text="current: latest",
                                      bg='#2d2d30', fg='#4fc3f7',
                                      font=get_font('small', bold=True))
        self.current_label.pack(fill=tk.X, padx=10, pady=5)
        
        # stats
        self.stats_label = tk.Label(self, text="",
                                    bg='#2d2d30', fg='#9cdcfe',
                                    font=get_font('tiny'), justify=tk.LEFT)
        self.stats_label.pack(fill=tk.X, padx=10, pady=5)
        
        # controls
        btn_frame = tk.Frame(self, bg='#1e1e1e')
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Button(btn_frame, text="reset to latest", bg='#37373d',
                 fg='#d4d4d4', font=get_font('small'),
                 command=self.reset_timeline).pack(fill=tk.X, pady=2)
        
        # initially disabled
        self.slider.config(state=tk.DISABLED)
    
    def load_git_timeline(self, graph, git_analyzer):
        """load timeline from git analyzer"""
        if not git_analyzer or not git_analyzer.is_git_repo:
            self.info_label.config(text="no git repository")
            self.slider.config(state=tk.DISABLED)
            return
        
        self.git_events = []
        
        # collect all git events (creation and deletion)
        
        # get file creation dates from git
        for file_path, history in git_analyzer.file_history.items():
            if history:
                # first commit = file creation
                first_commit = history[-1]
                try:
                    timestamp = datetime.fromisoformat(first_commit['date'])
                    node = self.find_node_by_path(graph, file_path)
                    if node:
                        self.git_events.append({
                            'timestamp': timestamp,
                            'type': 'created',
                            'node_id': node.id,
                            'file_path': file_path,
                            'commit': first_commit
                        })
                except:
                    pass
        
        # get file deletion dates
        for file_path, git_info in git_analyzer.deleted_files.items():
            try:
                timestamp = datetime.fromisoformat(git_info['deleted_date'])
                # find deleted node
                node = self.find_deleted_node(graph, file_path)
                if node:
                    self.git_events.append({
                        'timestamp': timestamp,
                        'type': 'deleted',
                        'node_id': node.id,
                        'file_path': file_path,
                        'commit': git_info
                    })
            except:
                pass
        
        if not self.git_events:
            self.info_label.config(text="no git events found")
            self.slider.config(state=tk.DISABLED)
            return
        
        # sort by timestamp
        self.git_events.sort(key=lambda e: e['timestamp'])
        
        self.min_date = self.git_events[0]['timestamp']
        self.max_date = self.git_events[-1]['timestamp']
        self.current_timestamp = self.max_date
        
        # update labels
        self.min_label.config(text=self.min_date.strftime('%Y-%m-%d'))
        self.max_label.config(text=self.max_date.strftime('%Y-%m-%d'))
        
        total_days = (self.max_date - self.min_date).days + 1
        self.info_label.config(text=f"git timeline: {total_days} days, {len(self.git_events)} events")
        
        # enable slider
        self.slider.config(state=tk.NORMAL)
        self.slider.set(100)
        self.update_stats()
    
    def find_node_by_path(self, graph, file_path):
        """find node by relative path"""
        for node in graph.files.values():
            try:
                if hasattr(node, 'path') and hasattr(graph, 'root_path'):
                    rel_path = str(node.path.relative_to(graph.root_path))
                    if rel_path == file_path:
                        return node
            except:
                pass
        return None
    
    def find_deleted_node(self, graph, file_path):
        """find deleted node by path"""
        for node in graph.files.values():
            if hasattr(node, 'is_deleted') and node.is_deleted:
                if file_path in str(node.path):
                    return node
        return None
    
    def on_slider_change(self, value):
        """handle slider movement"""
        if not self.git_events:
            return
        
        # convert slider value (0-100) to timestamp
        percentage = float(value) / 100.0
        time_range = (self.max_date - self.min_date).total_seconds()
        target_seconds = self.min_date.timestamp() + (time_range * percentage)
        # create a timestamp that matches the timezone-awareness of the git events
        # if the loaded dates are timezone-aware, produce an aware datetime here
        try:
            tz = None
            if hasattr(self.max_date, 'tzinfo') and self.max_date.tzinfo is not None:
                tz = self.max_date.tzinfo
            if tz is not None:
                # create an aware datetime with the same tz as the git events
                self.current_timestamp = datetime.fromtimestamp(target_seconds, tz=tz)
            else:
                # naive datetime
                self.current_timestamp = datetime.fromtimestamp(target_seconds)
        except Exception:
            # fallback to naive timestamp if anything unexpected happens
            self.current_timestamp = datetime.fromtimestamp(target_seconds)
        
        # update display
        self.current_label.config(text=f"current: {self.current_timestamp.strftime('%Y-%m-%d %H:%M')}")
        
        self.update_stats()
        
        # notify callback
        if self.callback:
            self.callback(self.current_timestamp)
    
    def update_stats(self):
        """update statistics for current time"""
        if not self.git_events or not self.current_timestamp:
            return
        
        created_count = 0
        deleted_count = 0
        
        for event in self.git_events:
            if event['timestamp'] <= self.current_timestamp:
                if event['type'] == 'created':
                    created_count += 1
                elif event['type'] == 'deleted':
                    deleted_count += 1
        
        existing = created_count - deleted_count
        
        stats = f"at this time:\n"
        stats += f"  created: {created_count}\n"
        stats += f"  deleted: {deleted_count}\n"
        stats += f"  existing: {existing}"
        
        self.stats_label.config(text=stats)
    
    def reset_timeline(self):
        """reset to latest time"""
        self.slider.set(100)
    
    def get_visible_nodes_at_time(self, graph):
        """return set of node ids that existed at current time"""
        if not self.current_timestamp or not self.git_events:
            # no timeline active, show everything
            return None
        
        visible = set()
        
        # track which files are created/deleted by this time
        created_files = set()
        deleted_files = set()
        
        for event in self.git_events:
            if event['timestamp'] <= self.current_timestamp:
                if event['type'] == 'created':
                    created_files.add(event['node_id'])
                elif event['type'] == 'deleted':
                    deleted_files.add(event['node_id'])
        
        # files that existed at this time
        visible = created_files - deleted_files
        
        # add all non-git-tracked files (always visible)
        for node in graph.files.values():
            if not hasattr(node, 'git_info') or node.git_info is None:
                visible.add(node.id)
        
        return visible