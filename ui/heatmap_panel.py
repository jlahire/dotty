"""
heatmap_panel.py - activity heatmap visualization panel
displays file access, email, browser, and prefetch activity over time
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
from collections import defaultdict
import math
from ui.font_config import get_font


class HeatmapPanel(tk.Frame):
    """heatmap visualization for temporal activity analysis"""
    
    def __init__(self, parent, callback=None):
        super().__init__(parent, bg='#1e1e1e')
        
        self.callback = callback
        self.data = {}
        self.view_type = tk.StringVar(value='day')
        self.data_source = tk.StringVar(value='files')
        self.max_value = 0
        
        # Add trace to update title when source changes
        self.data_source.trace('w', self.update_title)
        
        self.setup_ui()
    
    def update_title(self, *args):
        """update panel title with current data source"""
        source = self.data_source.get()
        source_names = {
            'files': 'File Activity',
            'git': 'Git Commits',
            'browser': 'Browser History',
            'email': 'Email Activity',
            'prefetch': 'Prefetch (Windows)'
        }
        title_text = f"Activity Heatmap - {source_names.get(source, 'Unknown')}"
        if hasattr(self, 'title_label'):
            self.title_label.config(text=title_text)
    
    def setup_ui(self):
        """create heatmap interface"""
        # Title (will be updated dynamically)
        self.title_label = tk.Label(self, text="Activity Heatmap - File Activity", 
                                    font=get_font('title', bold=True),
                                    bg='#1e1e1e', fg='#4fc3f7')
        self.title_label.pack(pady=10)
        
        # Controls frame
        controls = tk.Frame(self, bg='#2d2d30')
        controls.pack(fill=tk.X, padx=10, pady=5)
        
        # Data source selection
        tk.Label(controls, text="data source:", bg='#2d2d30', fg='#9cdcfe',
                font=get_font('small', bold=True)).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        
        sources = [
            ('File Activity', 'files'),
            ('Git Commits', 'git'),
            ('Browser History', 'browser'),
            ('Email Activity', 'email'),
            ('Prefetch (Windows)', 'prefetch')
        ]
        
        for idx, (label, value) in enumerate(sources):
            rb = tk.Radiobutton(controls, text=label, variable=self.data_source,
                               value=value, bg='#2d2d30', fg='#d4d4d4',
                               font=get_font('small'), selectcolor='#1e1e1e',
                               command=self.refresh_heatmap)
            rb.grid(row=0, column=idx+1, padx=5, pady=5)
        
        # View type selection
        tk.Label(controls, text="granularity:", bg='#2d2d30', fg='#9cdcfe',
                font=get_font('small', bold=True)).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        
        views = [
            ('Hourly', 'hour'),
            ('Daily', 'day'),
            ('Weekly', 'week'),
            ('Monthly', 'month')
        ]
        
        for idx, (label, value) in enumerate(views):
            rb = tk.Radiobutton(controls, text=label, variable=self.view_type,
                               value=value, bg='#2d2d30', fg='#d4d4d4',
                               font=get_font('small'), selectcolor='#1e1e1e',
                               command=self.refresh_heatmap)
            rb.grid(row=1, column=idx+1, padx=5, pady=5)
        
        # Statistics display
        self.stats_label = tk.Label(self, text="No data loaded",
                                    bg='#2d2d30', fg='#d4d4d4',
                                    font=get_font('small'), justify=tk.LEFT)
        self.stats_label.pack(fill=tk.X, padx=10, pady=5)
        
        # Canvas for heatmap
        canvas_frame = tk.Frame(self, bg='#252526')
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.canvas = tk.Canvas(canvas_frame, bg='#252526', highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Scrollbar
        scrollbar = tk.Scrollbar(canvas_frame, orient='vertical', command=self.canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        # Bind events
        self.canvas.bind('<Configure>', self.on_resize)
        self.canvas.bind('<Button-1>', self.on_click)
        self.canvas.bind('<Motion>', self.on_hover)
        
        # Color legend
        legend_frame = tk.Frame(self, bg='#2d2d30')
        legend_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(legend_frame, text="Activity Level:", bg='#2d2d30', fg='#9cdcfe',
                font=get_font('small')).pack(side=tk.LEFT, padx=5)
        
        # Create color gradient legend
        legend_colors = self.get_color_gradient(10)
        for i, color in enumerate(legend_colors):
            canvas_legend = tk.Canvas(legend_frame, width=30, height=20,
                                     bg=color, highlightthickness=1,
                                     highlightbackground='#666666')
            canvas_legend.pack(side=tk.LEFT, padx=1)
        
        tk.Label(legend_frame, text="Low", bg='#2d2d30', fg='#666666',
                font=get_font('tiny')).pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(legend_frame, text="High", bg='#2d2d30', fg='#666666',
                font=get_font('tiny')).pack(side=tk.LEFT)
        
        # Tooltip
        self.tooltip = None
    
    def load_data(self, data_dict):
        """
        Load activity data from various sources
        data_dict format: {
            'files': {timestamp_str: count, ...},
            'browser': {timestamp_str: count, ...},
            'email': {timestamp_str: count, ...},
            'prefetch': {timestamp_str: count, ...}
        }
        """
        self.data = data_dict
        self.refresh_heatmap()
    
    def load_from_analyzer(self, analyzer, source_type):
        """
        Load data from analyzer objects
        analyzer: BrowserAnalyzer, EmailAnalyzer, or PrefetchAnalyzer
        source_type: 'browser', 'email', or 'prefetch'
        """
        interval = self.view_type.get()
        timeline_data = analyzer.get_timeline_data(interval)
        
        if source_type not in self.data:
            self.data[source_type] = {}
        
        self.data[source_type] = timeline_data
        
        if self.data_source.get() == source_type:
            self.refresh_heatmap()
    
    def load_from_graph(self, graph, git_analyzer=None):
        """Load file activity data from graph and optionally git data"""
        timeline = defaultdict(int)
        interval = self.view_type.get()
        
        # Load file modification times
        for node in graph.files.values():
            if not node.is_folder:
                modified = node.info.get('modified')
                if modified:
                    try:
                        timestamp = datetime.fromisoformat(modified)
                        
                        if interval == 'hour':
                            key = timestamp.strftime('%Y-%m-%d %H:00')
                        elif interval == 'day':
                            key = timestamp.strftime('%Y-%m-%d')
                        elif interval == 'week':
                            key = timestamp.strftime('%Y-W%W')
                        elif interval == 'month':
                            key = timestamp.strftime('%Y-%m')
                        
                        timeline[key] += 1
                    except:
                        pass
        
        self.data['files'] = dict(timeline)
        
        # Load git data if available
        if git_analyzer and git_analyzer.is_git_repo:
            git_timeline = git_analyzer.get_timeline_data(interval)
            self.data['git'] = git_timeline
        
        if self.data_source.get() == 'files':
            self.refresh_heatmap()
        elif self.data_source.get() == 'git' and git_analyzer:
            self.refresh_heatmap()
    
    def refresh_heatmap(self):
        """redraw heatmap with current settings"""
        source = self.data_source.get()
        
        if source not in self.data or not self.data[source]:
            self.canvas.delete('all')
            
            # Show appropriate message based on source
            if source == 'git':
                message = "No git data available\n(not a git repository or no commits)"
            else:
                message = f"No {source} data available"
            
            self.canvas.create_text(
                200, 100,
                text=message,
                font=get_font('text'),
                fill='#666666'
            )
            return
        
        current_data = self.data[source]
        self.max_value = max(current_data.values()) if current_data else 1
        
        # Update statistics with source-specific labels
        total_events = sum(current_data.values())
        time_periods = len(current_data)
        avg_events = total_events / time_periods if time_periods > 0 else 0
        
        # Source-specific labels
        event_labels = {
            'files': 'File Modifications',
            'git': 'Git Commits',
            'browser': 'Page Visits',
            'email': 'Emails',
            'prefetch': 'Program Executions'
        }
        
        event_label = event_labels.get(source, 'Events')
        
        stats_text = (f"Total {event_label}: {total_events} | "
                     f"Time Periods: {time_periods} | "
                     f"Average: {avg_events:.1f} per period")
        self.stats_label.config(text=stats_text)
        
        # Draw heatmap
        self.draw_heatmap(current_data)
    
    def draw_heatmap(self, data):
        """draw the heatmap visualization"""
        self.canvas.delete('all')
        
        if not data:
            return
        
        # Sort data by timestamp
        sorted_data = sorted(data.items())
        
        # Determine layout based on view type
        view = self.view_type.get()
        
        if view == 'hour':
            self.draw_hourly_heatmap(sorted_data)
        elif view == 'day':
            self.draw_daily_heatmap(sorted_data)
        elif view == 'week':
            self.draw_weekly_heatmap(sorted_data)
        elif view == 'month':
            self.draw_monthly_heatmap(sorted_data)
    
    def draw_daily_heatmap(self, sorted_data):
        """draw daily heatmap (calendar style)"""
        canvas_width = self.canvas.winfo_width() or 600
        
        # Cell dimensions
        cell_width = 40
        cell_height = 40
        margin = 5
        left_margin = 50
        top_margin = 30
        
        # Parse dates
        dates = []
        for timestamp_str, count in sorted_data:
            try:
                date = datetime.strptime(timestamp_str, '%Y-%m-%d')
                dates.append((date, count))
            except:
                pass
        
        if not dates:
            return
        
        # Group by week
        weeks = defaultdict(list)
        for date, count in dates:
            week_key = date.strftime('%Y-W%W')
            weekday = date.weekday()
            weeks[week_key].append((weekday, date, count))
        
        # Draw header (day names)
        day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        for i, day_name in enumerate(day_names):
            x = left_margin + i * (cell_width + margin)
            self.canvas.create_text(
                x + cell_width // 2, top_margin - 10,
                text=day_name,
                font=get_font('tiny'),
                fill='#9cdcfe'
            )
        
        # Draw cells
        y = top_margin
        for week_key in sorted(weeks.keys()):
            week_data = weeks[week_key]
            
            # Week label
            self.canvas.create_text(
                10, y + cell_height // 2,
                text=week_key.split('-W')[1],
                font=get_font('tiny'),
                fill='#666666',
                anchor=tk.W
            )
            
            # Days in week
            for weekday, date, count in week_data:
                x = left_margin + weekday * (cell_width + margin)
                
                # Color based on activity
                color = self.value_to_color(count)
                
                # Draw cell
                rect_id = self.canvas.create_rectangle(
                    x, y, x + cell_width, y + cell_height,
                    fill=color,
                    outline='#3c3c3c',
                    tags=('cell', f'data_{date.strftime("%Y-%m-%d")}_{count}')
                )
                
                # Date number
                self.canvas.create_text(
                    x + cell_width // 2, y + cell_height // 2,
                    text=str(date.day),
                    font=get_font('small'),
                    fill='#ffffff' if count > self.max_value * 0.5 else '#000000'
                )
            
            y += cell_height + margin
        
        # Update scroll region
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))
    
    def draw_hourly_heatmap(self, sorted_data):
        """draw hourly heatmap (24-hour grid)"""
        left_margin = 80
        top_margin = 30
        cell_width = 30
        cell_height = 20
        margin = 2
        
        # Group by date and hour
        by_date = defaultdict(dict)
        for timestamp_str, count in sorted_data:
            try:
                dt = datetime.strptime(timestamp_str, '%Y-%m-%d %H:00')
                date_key = dt.strftime('%Y-%m-%d')
                hour = dt.hour
                by_date[date_key][hour] = count
            except:
                pass
        
        if not by_date:
            return
        
        # Draw hour labels (0-23)
        for hour in range(24):
            x = left_margin + hour * (cell_width + margin)
            self.canvas.create_text(
                x + cell_width // 2, top_margin - 10,
                text=str(hour),
                font=get_font('tiny'),
                fill='#9cdcfe'
            )
        
        # Draw rows (one per day)
        y = top_margin
        for date_key in sorted(by_date.keys()):
            # Date label
            self.canvas.create_text(
                10, y + cell_height // 2,
                text=date_key,
                font=get_font('tiny'),
                fill='#666666',
                anchor=tk.W
            )
            
            hour_data = by_date[date_key]
            
            for hour in range(24):
                x = left_margin + hour * (cell_width + margin)
                count = hour_data.get(hour, 0)
                
                color = self.value_to_color(count)
                
                self.canvas.create_rectangle(
                    x, y, x + cell_width, y + cell_height,
                    fill=color,
                    outline='#3c3c3c',
                    tags=('cell', f'data_{date_key}_{hour}_{count}')
                )
            
            y += cell_height + margin
        
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))
    
    def draw_weekly_heatmap(self, sorted_data):
        """draw weekly heatmap (bar chart style)"""
        left_margin = 100
        top_margin = 30
        bar_height = 30
        margin = 5
        max_bar_width = 400
        
        y = top_margin
        
        for timestamp_str, count in sorted_data[:50]:  # Limit to 50 weeks
            # Week label
            self.canvas.create_text(
                10, y + bar_height // 2,
                text=timestamp_str,
                font=get_font('tiny'),
                fill='#9cdcfe',
                anchor=tk.W
            )
            
            # Bar width based on count
            bar_width = (count / self.max_value) * max_bar_width if self.max_value > 0 else 0
            
            color = self.value_to_color(count)
            
            self.canvas.create_rectangle(
                left_margin, y,
                left_margin + bar_width, y + bar_height,
                fill=color,
                outline='#3c3c3c',
                tags=('cell', f'data_{timestamp_str}_{count}')
            )
            
            # Count label
            self.canvas.create_text(
                left_margin + bar_width + 5, y + bar_height // 2,
                text=str(count),
                font=get_font('tiny'),
                fill='#d4d4d4',
                anchor=tk.W
            )
            
            y += bar_height + margin
        
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))
    
    def draw_monthly_heatmap(self, sorted_data):
        """draw monthly heatmap"""
        # Similar to weekly but by month
        self.draw_weekly_heatmap(sorted_data)
    
    def value_to_color(self, value):
        """convert activity value to heat color"""
        if self.max_value == 0:
            return '#1a1a2e'
        
        # Normalize value (0-1)
        normalized = min(value / self.max_value, 1.0)
        
        # Color gradient: dark blue -> cyan -> yellow -> red
        if normalized < 0.25:
            # Dark blue to blue
            ratio = normalized / 0.25
            return self.interpolate_color('#1a1a2e', '#0f3460', ratio)
        elif normalized < 0.5:
            # Blue to cyan
            ratio = (normalized - 0.25) / 0.25
            return self.interpolate_color('#0f3460', '#16213e', ratio)
        elif normalized < 0.75:
            # Cyan to yellow
            ratio = (normalized - 0.5) / 0.25
            return self.interpolate_color('#16213e', '#e94560', ratio)
        else:
            # Yellow to red
            ratio = (normalized - 0.75) / 0.25
            return self.interpolate_color('#e94560', '#ff0000', ratio)
    
    def interpolate_color(self, color1, color2, ratio):
        """interpolate between two hex colors"""
        # Convert hex to RGB
        r1 = int(color1[1:3], 16)
        g1 = int(color1[3:5], 16)
        b1 = int(color1[5:7], 16)
        
        r2 = int(color2[1:3], 16)
        g2 = int(color2[3:5], 16)
        b2 = int(color2[5:7], 16)
        
        # Interpolate
        r = int(r1 + (r2 - r1) * ratio)
        g = int(g1 + (g2 - g1) * ratio)
        b = int(b1 + (b2 - b1) * ratio)
        
        return f'#{r:02x}{g:02x}{b:02x}'
    
    def get_color_gradient(self, steps):
        """get color gradient for legend"""
        colors = []
        for i in range(steps):
            normalized = i / (steps - 1)
            color = self.value_to_color(normalized * self.max_value if self.max_value > 0 else 0)
            colors.append(color)
        return colors
    
    def on_resize(self, event):
        """handle canvas resize"""
        self.refresh_heatmap()
    
    def on_click(self, event):
        """handle cell click"""
        item = self.canvas.find_closest(event.x, event.y)
        if item:
            tags = self.canvas.gettags(item[0])
            for tag in tags:
                if tag.startswith('data_'):
                    # Extract data from tag
                    parts = tag.split('_')
                    if len(parts) >= 3:
                        # Notify callback if exists
                        if self.callback:
                            self.callback(tag)
    
    def on_hover(self, event):
        """show tooltip on hover"""
        item = self.canvas.find_closest(event.x, event.y)
        if item:
            tags = self.canvas.gettags(item[0])
            for tag in tags:
                if tag.startswith('data_'):
                    parts = tag.replace('data_', '').rsplit('_', 1)
                    if len(parts) == 2:
                        timestamp, count = parts
                        
                        # Create source-specific tooltip text
                        source = self.data_source.get()
                        
                        if source == 'git':
                            tooltip_text = f"{timestamp}\nCommits: {count}"
                        elif source == 'browser':
                            tooltip_text = f"{timestamp}\nVisits: {count}"
                        elif source == 'email':
                            tooltip_text = f"{timestamp}\nEmails: {count}"
                        elif source == 'prefetch':
                            tooltip_text = f"{timestamp}\nExecutions: {count}"
                        else:  # files
                            tooltip_text = f"{timestamp}\nModifications: {count}"
                        
                        self.show_tooltip(event.x, event.y, tooltip_text)
                    return
        
        self.hide_tooltip()
    
    def show_tooltip(self, x, y, text):
        """display tooltip"""
        self.hide_tooltip()
        
        self.tooltip = self.canvas.create_rectangle(
            x + 10, y - 30, x + 150, y - 5,
            fill='#2d2d30', outline='#4fc3f7', width=2
        )
        
        self.tooltip_text = self.canvas.create_text(
            x + 80, y - 17,
            text=text,
            font=get_font('tiny'),
            fill='#ffffff'
        )
    
    def hide_tooltip(self):
        """hide tooltip"""
        if self.tooltip:
            self.canvas.delete(self.tooltip)
            self.canvas.delete(self.tooltip_text)
            self.tooltip = None