"""
splash_screen.py - welcome screen shown before loading
NOW WITH LIST LAYOUT for better organization
"""

import tkinter as tk
import random
import math
from ui.font_config import get_font, FONTS


class SplashScreen(tk.Frame):
    """animated splash screen with analysis mode selection"""
    
    def __init__(self, parent, live_callback=None, forensic_callback=None, 
                 memory_callback=None, iso_callback=None, device_callback=None,
                 browser_callback=None, email_callback=None, prefetch_callback=None):
        super().__init__(parent, bg='#252526')
        
        self.live_callback = live_callback
        self.forensic_callback = forensic_callback
        self.memory_callback = memory_callback
        self.iso_callback = iso_callback
        self.device_callback = device_callback
        self.browser_callback = browser_callback
        self.email_callback = email_callback
        self.prefetch_callback = prefetch_callback
        
        # canvas for animated background
        self.canvas = tk.Canvas(self, bg='#252526', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.dots = []
        self.animation_running = True
        
        # create animated dots
        self.create_dots()
        
        # create UI elements
        self.create_ui()
        
        # start animation
        self.animate()
    
    def create_dots(self):
        """create random colored dots"""
        colors = ['#3776ab', '#f7df1e', '#e34c26', '#264de4', '#00ff00',
                 '#89e051', '#4fc3f7', '#ce93d8', '#ff69b4', '#ff1493',
                 '#ffaa00', '#ff0000', '#00add8']
        
        # create 20 random dots
        for i in range(20):
            x = random.randint(100, 700)
            y = random.randint(100, 500)
            size = random.randint(5, 25)
            color = random.choice(colors)
            
            # random velocity
            vx = random.uniform(-2, 2)
            vy = random.uniform(-2, 2)
            
            dot = {
                'x': x,
                'y': y,
                'size': size,
                'color': color,
                'vx': vx,
                'vy': vy
            }
            self.dots.append(dot)
    
    def create_ui(self):
        """create splash UI elements"""
        # Get canvas dimensions (will be updated in animate)
        self.center_x = 400
        self.center_y = 300
        
        # Bind to configure event to handle window resizing
        self.canvas.bind('<Configure>', self.on_resize)
        
        # Create all UI elements (will be positioned in on_resize)
        self.create_ui_elements()
    
    def create_ui_elements(self):
        """create all UI elements on canvas"""
        # Title - draw directly on canvas for transparency
        self.title_text = self.canvas.create_text(
            self.center_x, self.center_y - 280,
            text="dotty",
            font=get_font('splash_title', bold=True),
            fill='#4fc3f7',
            tags='ui'
        )
        
        # Animated dots after title
        self.dot1_text = self.canvas.create_text(
            self.center_x - 40, self.center_y - 230,
            text="●",
            font=(FONTS['splash_subtitle']),
            fill='#4fc3f7',
            tags='ui'
        )
        
        self.dot2_text = self.canvas.create_text(
            self.center_x, self.center_y - 230,
            text="●",
            font=(FONTS['splash_subtitle']),
            fill='#4fc3f7',
            tags='ui'
        )
        
        self.dot3_text = self.canvas.create_text(
            self.center_x + 40, self.center_y - 230,
            text="●",
            font=(FONTS['splash_subtitle']),
            fill='#4fc3f7',
            tags='ui'
        )
        
        self.dot_frame = 0
        
        # Subtitle
        self.subtitle_text = self.canvas.create_text(
            self.center_x, self.center_y - 195,
            text="filesystem visualization & forensic analysis",
            font=get_font('splash_subtitle'),
            fill='#9cdcfe',
            tags='ui'
        )
        
        # Create button frame on canvas with semi-transparent background
        self.button_bg = self.canvas.create_rectangle(
            self.center_x - 320, self.center_y - 170,
            self.center_x + 320, self.center_y + 230,
            fill='#1e1e1e',
            outline='#3c3c3c',
            width=2,
            tags='ui'
        )
        
        # Section label: Select Analysis Mode
        self.mode_label = self.canvas.create_text(
            self.center_x, self.center_y - 150,
            text="SELECT ANALYSIS MODE",
            font=get_font('small', bold=True),
            fill='#666666',
            tags='ui'
        )
        
        # Define button spacing for vertical list
        button_spacing = 45
        start_y = self.center_y - 110
        
        # List of analysis options
        options = [
            {
                'text': '🗂️  Live Analysis',
                'color': '#4fc3f7',
                'callback': self.on_live_analysis
            },
            {
                'text': '💾  Forensic Image',
                'color': '#ce93d8',
                'callback': self.on_forensic_analysis
            },
            {
                'text': '🧠  Memory Dump',
                'color': '#ff6b6b',
                'callback': self.on_memory_analysis
            },
            {
                'text': '💿  ISO Image',
                'color': '#ffd93d',
                'callback': self.on_iso_analysis
            },
            {
                'text': '📱  Device Capture',
                'color': '#89e051',
                'callback': self.on_device_capture
            },
            {
                'text': '🌐  Browser History',
                'color': '#ff9800',
                'callback': self.on_browser_analysis
            },
            {
                'text': '📧  Email Forensics',
                'color': '#e91e63',
                'callback': self.on_email_analysis
            },
            {
                'text': '⚡  Prefetch Analysis',
                'color': '#00bcd4',
                'callback': self.on_prefetch_analysis
            }
        ]
        
        # Create buttons in vertical list
        self.option_buttons = []
        
        for i, option in enumerate(options):
            y_pos = start_y + (i * button_spacing)
            
            # Create button
            btn = tk.Button(self.canvas,
                          text=option['text'],
                          font=get_font('text', bold=True),
                          bg=option['color'],
                          fg='#1e1e1e',
                          width=28,
                          height=1,
                          relief=tk.FLAT,
                          cursor='hand2',
                          anchor='w',
                          padx=10,
                          command=option['callback'])
            
            btn_window = self.canvas.create_window(
                self.center_x - 150, y_pos,
                window=btn,
                anchor='w',
                tags='ui'
            )
            
            self.option_buttons.append({
                'button': btn,
                'window': btn_window
            })
        
        # Info text at bottom
        self.info_text = self.canvas.create_text(
            self.center_x, self.center_y + 250,
            text="Or use File → Export JSON to save existing results",
            font=get_font('text', italic=True),
            fill='#555555',
            tags='ui'
        )
    
    def on_resize(self, event):
        """handle window resize to keep UI centered"""
        # Calculate new center
        new_center_x = event.width // 2
        new_center_y = event.height // 2
        
        # Calculate offset from old center
        dx = new_center_x - self.center_x
        dy = new_center_y - self.center_y
        
        # Update center
        self.center_x = new_center_x
        self.center_y = new_center_y
        
        # Move all UI elements
        self.canvas.move('ui', dx, dy)
    
    def animate(self):
        """animate the splash screen"""
        if not self.animation_running:
            return
        
        # Only delete and redraw the background dots, not the UI
        self.canvas.delete('dot')
        
        # update and draw floating dots
        width = self.canvas.winfo_width() or 800
        height = self.canvas.winfo_height() or 600
        
        for dot in self.dots:
            # update position
            dot['x'] += dot['vx']
            dot['y'] += dot['vy']
            
            # bounce off edges
            if dot['x'] < 0 or dot['x'] > width:
                dot['vx'] *= -1
            if dot['y'] < 0 or dot['y'] > height:
                dot['vy'] *= -1
            
            # keep in bounds
            dot['x'] = max(0, min(width, dot['x']))
            dot['y'] = max(0, min(height, dot['y']))
            
            # draw dot BEHIND the UI elements
            size = dot['size']
            self.canvas.create_oval(
                dot['x'] - size, dot['y'] - size,
                dot['x'] + size, dot['y'] + size,
                fill=dot['color'],
                outline='',
                tags='dot'
            )
        
        # Raise UI elements to front so dots go behind them
        self.canvas.tag_raise('ui')
        
        # animate the three dots after "dotty"
        self.dot_frame += 1
        
        # pulse effect for dots
        for i, dot_id in enumerate([self.dot1_text, self.dot2_text, self.dot3_text]):
            opacity = 0.3 + 0.7 * abs(math.sin((self.dot_frame + i * 20) * 0.05))
            # simulate opacity with color intensity
            color_val = int(79 + (195 - 79) * opacity)
            color = f'#{color_val:02x}{color_val + 50:02x}{247:02x}'
            self.canvas.itemconfig(dot_id, fill=color)
        
        # continue animation
        self.after(50, self.animate)
    
    def on_live_analysis(self):
        """handle live analysis button click"""
        if self.live_callback:
            self.live_callback()
    
    def on_forensic_analysis(self):
        """handle forensic image button click"""
        if self.forensic_callback:
            self.forensic_callback()
    
    def on_memory_analysis(self):
        """handle memory dump button click"""
        if self.memory_callback:
            self.memory_callback()
    
    def on_iso_analysis(self):
        """handle ISO image button click"""
        if self.iso_callback:
            self.iso_callback()
    
    def on_device_capture(self):
        """handle device capture button click"""
        if self.device_callback:
            self.device_callback()
    
    def on_browser_analysis(self):
        """handle browser history button click"""
        if self.browser_callback:
            self.browser_callback()
        else:
            print("⚠ Browser analysis not yet implemented")
    
    def on_email_analysis(self):
        """handle email forensics button click"""
        if self.email_callback:
            self.email_callback()
        else:
            print("⚠ Email analysis not yet implemented")
    
    def on_prefetch_analysis(self):
        """handle prefetch analysis button click"""
        if self.prefetch_callback:
            self.prefetch_callback()
        else:
            print("⚠ Prefetch analysis not yet implemented")
    
    def stop(self):
        """stop the animation"""
        self.animation_running = False