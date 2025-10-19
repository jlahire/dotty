"""
main.py - entry point that ties everything together
imports all other modules and creates the gui
NOW INCLUDES: Browser, Email, and Prefetch analysis
UPDATED: New menu system, fixed panels, filter dialog, file preview

REFACTORED: Now uses error_handler, dependency_manager, and progress_manager
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import datetime
import platform

# Import centralized management modules
from core.error_handler import (
    DottyError,
    FileSystemError,
    ForensicImageError,
    MemoryDumpError,
    ISOImageError,
    log_error_report,
    logger
)
from core.dependency_manager import is_available, check_feature, get_dependency_manager
from core.progress_manager import ProgressTracker, MultiStepProgressTracker

# Import our modules
from graph.layout import calculate_positions, calculate_force_directed_layout, auto_select_focus_node
from scanning.scanner import scan_folder
from models.graph_stuff import Graph
from graph.linker import create_all_links
from ui.display import GraphCanvas
from ui.info_panel import InfoPanel
from ui.tree_view import TreeView
from ui.filter_panel import FilterPanel
from ui.dialogs.filter_dialog import FilterDialog
from ui.splash_screen import SplashScreen
from ui.timeline_panel import TimelinePanel
from scanning.forensic_scanner import ForensicScanner
from analyzers.forensic_analyzer import ForensicAnalyzer
from analyzers.memory_analyzer import MemoryAnalyzer
from analyzers.iso_analyzer import ISOAnalyzer
from scanning.device_capture import DeviceCapture
from ui.dialogs.device_capture_dialog import DeviceCaptureDialog
from models.file_stuff import (ForensicFileNode, MemoryFileNode, MemoryProcessNode, ISOFileNode,
                        BrowserHistoryNode, BrowserBookmarkNode, BrowserDownloadNode,
                        EmailMessageNode, EmailAttachmentNode, PrefetchProgramNode)
from models.case_manager import CaseInfo
from ui.dialogs.case_dialog import CaseDialog
from core.config_manager import ConfigManager

# Import advanced forensic analyzers
from analyzers.browser_analyzer import BrowserAnalyzer
from analyzers.email_analyzer import EmailAnalyzer
from analyzers.prefetch_analyzer import PrefetchAnalyzer
from ui.heatmap_panel import HeatmapPanel


class DottyApp:
    """Main application window"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("dotty - filesystem graph")
        self.config = ConfigManager()
        self.root.geometry(self.config.get_window_geometry())
        self.root.configure(bg='#1e1e1e')
        
        # Core components
        self.graph = None
        self.canvas = None
        self.info = None
        self.tree = None
        self.filters = None
        self.timeline = None
        self.splash = None
        self.git_analyzer = None
        
        self.zettelkasten_mode = True  # Default to zettelkasten layout
        self.focus_mode_var = tk.BooleanVar(value=True)  # For checkbox
        self.layout_mode_var = tk.StringVar(value="zettelkasten")  # For radio buttons
        
        # Forensic analyzers
        self.forensic_scanner = None
        self.memory_analyzer = None
        self.iso_analyzer = None
        self.browser_analyzer = None
        self.email_analyzer = None
        self.prefetch_analyzer = None
        
        # Case management
        self.case_info = None
        self.analysis_mode = None  # 'live', 'forensic', 'memory', 'iso', 'browser', 'email', 'prefetch'
        
        # UI components
        self.heatmap = None
        self.progress_window = None
        self.progress_bar = None
        self.progress_label = None
        
        logger.info("DottyApp initializing...")
        
        self.setup_menu()
        self.setup_ui()
        self.show_splash()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        logger.info("DottyApp initialized successfully")
        
    def on_closing(self):
        """Handle application closing - save configuration"""
        try:
            logger.info("Application closing - saving configuration...")
            
            # Save window state
            self.config.save_window_state(self.root)
            
            # Save panel sizes
            self.config.save_panel_sizes(
                self.main_paned,
                self.left_paned if hasattr(self, 'left_paned') else None,
                self.center_paned if hasattr(self, 'center_paned') else None  # Note: use center_paned for right info
            )
            
            logger.info("Configuration saved successfully")
        except Exception as e:
            logger.warning(f"Error saving configuration: {e}")
        
        # Continue with normal cleanup
        logger.info("Application shutting down")
        
        if hasattr(self, 'forensic_scanner') and self.forensic_scanner:
            self.forensic_scanner.close()
        if hasattr(self, 'iso_analyzer') and self.iso_analyzer:
            self.iso_analyzer.close()
        
        self.root.destroy()
    
    def setup_menu(self):
        """Create menu bar"""
        menu = tk.Menu(self.root)
        self.root.config(menu=menu)
        
        # File Menu
        file_menu = tk.Menu(menu, tearoff=0)
        menu.add_cascade(label="File", menu=file_menu)
        
        # Open submenu
        open_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="Open...", menu=open_menu)
        open_menu.add_command(label="Live Directory", command=self.start_live_analysis, accelerator="Ctrl+O")
        open_menu.add_command(label="Forensic Image", command=self.start_forensic_analysis, accelerator="Ctrl+Shift+O")
        open_menu.add_command(label="Memory Dump", command=self.start_memory_analysis)
        open_menu.add_command(label="ISO Image", command=self.start_iso_analysis)
        open_menu.add_separator()
        open_menu.add_command(label="Browser History", command=self.start_browser_analysis)
        open_menu.add_command(label="Email Files", command=self.start_email_analysis)
        open_menu.add_command(label="Prefetch (Windows)", command=self.start_prefetch_analysis)
        
        file_menu.add_separator()
        file_menu.add_command(label="Export JSON...", command=self.export, accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self.root.quit, accelerator="Ctrl+Q")
        
        # View Menu
        view_menu = tk.Menu(menu, tearoff=0)
        menu.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Zoom In", command=self.zoom_in, accelerator="Ctrl++")
        view_menu.add_command(label="Zoom Out", command=self.zoom_out, accelerator="Ctrl+-")
        view_menu.add_command(label="Reset View", command=self.reset_view, accelerator="Ctrl+0")
        view_menu.add_separator()
        view_menu.add_command(label="Configure Filters...", command=self.show_filter_dialog, accelerator="Ctrl+F")
        view_menu.add_command(label="Graph Statistics", command=self.show_statistics)
        view_menu.add_separator()
        view_menu.add_command(label="Save Panel Layout", command=self.save_panel_layout) 
        
        # Tools Menu
        tools_menu = tk.Menu(menu, tearoff=0)
        menu.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Device Capture...", command=self.start_device_capture)
        tools_menu.add_command(label="Dependency Status", command=self.show_dependency_status)
        
        # Help Menu
        help_menu = tk.Menu(menu, tearoff=0)
        menu.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Keyboard Shortcuts", command=self.show_shortcuts, accelerator="F1")
        help_menu.add_separator()
        help_menu.add_command(label="About Dotty", command=self.show_about)
        
        # Bind keyboard shortcuts
        self.root.bind('<Control-o>', lambda e: self.start_live_analysis())
        self.root.bind('<Control-O>', lambda e: self.start_forensic_analysis())
        self.root.bind('<Control-s>', lambda e: self.export())
        self.root.bind('<Control-q>', lambda e: self.root.quit())
        self.root.bind('<Control-f>', lambda e: self.show_filter_dialog())
        self.root.bind('<Control-plus>', lambda e: self.zoom_in())
        self.root.bind('<Control-minus>', lambda e: self.zoom_out())
        self.root.bind('<Control-0>', lambda e: self.reset_view())
        self.root.bind('<F1>', lambda e: self.show_shortcuts())
        self.root.bind('<Control-l>', lambda e: self.save_panel_layout())
    
    def setup_ui(self):
        """Create the interface with resizable panels using PanedWindow"""
        
        # Control panel at top (stays the same)
        self.control_panel = tk.Frame(self.root, bg='#2d2d30', height=50)
        self.control_panel.pack(side=tk.TOP, fill=tk.X)
        self.control_panel.pack_propagate(False)
        
        # Status bar at bottom
        self.status = tk.Label(self.root, text="ready", bd=1,
                            relief=tk.SUNKEN, anchor=tk.W,
                            bg='#2d2d30', fg='#d4d4d4')
        self.status.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Main container - create but DON'T pack yet (will pack after splash)
        self.main_container = tk.Frame(self.root, bg='#1e1e1e')
        
        # Create horizontal PanedWindow for main 3-column layout
        self.main_paned = tk.PanedWindow(self.main_container, orient=tk.HORIZONTAL,
                                        bg='#1e1e1e', sashwidth=5, 
                                        sashrelief=tk.RAISED, bd=0)
        
        # ====================================================================
        # LEFT PANEL - File Structure + Timeline
        # ====================================================================
        self.left_frame = tk.Frame(self.main_paned, bg='#252526', width=250)
        
        # Add collapse/expand button for left panel
        left_header = tk.Frame(self.left_frame, bg='#252526', height=30)
        left_header.pack(side=tk.TOP, fill=tk.X)
        left_header.pack_propagate(False)
        
        self.left_collapsed = False
        self.left_toggle_btn = tk.Button(left_header, text="◀", 
                                        bg='#37373d', fg='#4fc3f7',
                                        font=('Arial', 10, 'bold'),
                                        relief=tk.FLAT, 
                                        command=self.toggle_left_panel,
                                        width=2)
        self.left_toggle_btn.pack(side=tk.RIGHT, padx=5, pady=3)
        
        # Create vertical PanedWindow for tree and timeline
        self.left_paned = tk.PanedWindow(self.left_frame, orient=tk.VERTICAL,
                                        bg='#252526', sashwidth=4,
                                        sashrelief=tk.RAISED, bd=0)
        self.left_paned.pack(fill=tk.BOTH, expand=True)
        
        # Tree view section
        tree_section = tk.Frame(self.left_paned, bg='#252526')
        
        tree_label = tk.Label(tree_section, text="File Structure",
                            bg='#252526', fg='#4fc3f7',
                            font=('Arial', 11, 'bold'))
        tree_label.pack(pady=5)
        
        self.tree_content_frame = tk.Frame(tree_section, bg='#1e1e1e')
        self.tree_content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Timeline section
        timeline_section = tk.Frame(self.left_paned, bg='#252526')
        
        timeline_label = tk.Label(timeline_section, text="Timeline",
                                bg='#252526', fg='#4fc3f7',
                                font=('Arial', 11, 'bold'))
        timeline_label.pack(pady=5)
        
        self.timeline_content_frame = tk.Frame(timeline_section, bg='#1e1e1e')
        self.timeline_content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Add both sections to left paned window
        self.left_paned.add(tree_section, minsize=100)
        self.left_paned.add(timeline_section, minsize=100, height=200)
        
        # Add left frame to main paned window
        self.main_paned.add(self.left_frame, minsize=200, width=250)
        
        # ====================================================================
        # CENTER PANEL - Graph + Heatmap
        # ====================================================================
        self.center_container = tk.Frame(self.main_paned, bg='#1e1e1e')
        
        # Create vertical PanedWindow for graph and heatmap
        self.center_paned = tk.PanedWindow(self.center_container, orient=tk.VERTICAL,
                                        bg='#1e1e1e', sashwidth=4,
                                        sashrelief=tk.RAISED, bd=0)
        self.center_paned.pack(fill=tk.BOTH, expand=True)
        
        # Canvas for graph
        self.canvas_frame = tk.Frame(self.center_paned, bg='#1e1e1e')
        
        # Heatmap section
        self.heatmap_frame = tk.Frame(self.center_paned, bg='#252526')
        
        heatmap_header = tk.Frame(self.heatmap_frame, bg='#2d2d30', height=30)
        heatmap_header.pack(side=tk.TOP, fill=tk.X)
        heatmap_header.pack_propagate(False)
        
        tk.Label(heatmap_header, text="Activity Heatmap",
                font=('Arial', 10, 'bold'),
                bg='#2d2d30', fg='#4fc3f7').pack(side=tk.LEFT, padx=10)
        
        # Heatmap collapse button
        self.heatmap_collapsed = False
        self.heatmap_toggle_btn = tk.Button(heatmap_header, text="▼",
                                        bg='#37373d', fg='#4fc3f7',
                                        font=('Arial', 10, 'bold'),
                                        relief=tk.FLAT,
                                        command=self.toggle_heatmap,
                                        width=2)
        self.heatmap_toggle_btn.pack(side=tk.RIGHT, padx=5)
        
        self.heatmap_content_frame = tk.Frame(self.heatmap_frame, bg='#1e1e1e')
        self.heatmap_content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Add both sections to center paned window
        self.center_paned.add(self.canvas_frame, minsize=300)
        self.center_paned.add(self.heatmap_frame, minsize=100, height=400)
        
        # Add center to main paned window
        self.main_paned.add(self.center_container, minsize=400)
        
        # ====================================================================
        # RIGHT PANEL - Info Panel
        # ====================================================================
        self.right_frame = tk.Frame(self.main_paned, bg='#252526', width=350)
        
        # Add collapse/expand button for right panel
        right_header = tk.Frame(self.right_frame, bg='#252526', height=30)
        right_header.pack(side=tk.TOP, fill=tk.X)
        right_header.pack_propagate(False)
        
        self.right_collapsed = False
        self.right_toggle_btn = tk.Button(right_header, text="▶",
                                        bg='#37373d', fg='#4fc3f7',
                                        font=('Arial', 10, 'bold'),
                                        relief=tk.FLAT,
                                        command=self.toggle_right_panel,
                                        width=2)
        self.right_toggle_btn.pack(side=tk.LEFT, padx=5, pady=3)
        
        self.info_content_frame = tk.Frame(self.right_frame, bg='#1e1e1e')
        self.info_content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Add right frame to main paned window
        self.main_paned.add(self.right_frame, minsize=200, width=350)
    
    def toggle_left_panel(self):
        """Toggle collapse/expand left panel"""
        if self.left_collapsed:
            # Expand
            self.main_paned.paneconfigure(self.left_frame, minsize=200, width=250)
            self.left_toggle_btn.config(text="◀")
            self.left_collapsed = False
            # Show content
            self.left_paned.pack(fill=tk.BOTH, expand=True)
        else:
            # Collapse
            self.main_paned.paneconfigure(self.left_frame, minsize=30, width=30)
            self.left_toggle_btn.config(text="▶")
            self.left_collapsed = True
            # Hide content
            self.left_paned.pack_forget()
    
    def toggle_right_panel(self):
        """Toggle collapse/expand right panel"""
        if self.right_collapsed:
            # Expand
            self.main_paned.paneconfigure(self.right_frame, minsize=200, width=350)
            self.right_toggle_btn.config(text="▶")
            self.right_collapsed = False
            # Show content
            self.info_content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        else:
            # Collapse
            self.main_paned.paneconfigure(self.right_frame, minsize=30, width=30)
            self.right_toggle_btn.config(text="◀")
            self.right_collapsed = True
            # Hide content
            self.info_content_frame.pack_forget()
    
    def toggle_heatmap(self):
        """Toggle collapse/expand heatmap"""
        if self.heatmap_collapsed:
            # Expand
            self.center_paned.paneconfigure(self.heatmap_frame, minsize=100, height=400)
            self.heatmap_toggle_btn.config(text="▼")
            self.heatmap_collapsed = False
            # Show content
            self.heatmap_content_frame.pack(fill=tk.BOTH, expand=True)
        else:
            # Collapse
            self.center_paned.paneconfigure(self.heatmap_frame, minsize=30, height=30)
            self.heatmap_toggle_btn.config(text="▲")
            self.heatmap_collapsed = True
            # Hide content
            self.heatmap_content_frame.pack_forget()
    
    def hide_splash(self):
        """Hide splash and show main interface with resizable panels"""
        if self.splash:
            self.splash.stop()
            self.splash.destroy()
            self.splash = None
        
        # Now pack the main UI
        logger.info("Displaying main UI panels")
        
        # Pack the main container
        self.main_container.pack(fill=tk.BOTH, expand=True)
        
        # Pack the main paned window - this contains all 3 columns
        self.main_paned.pack(fill=tk.BOTH, expand=True)
        
        # Create control buttons AFTER UI is visible
        self.create_control_buttons()
        
        # RESTORE PANEL SIZES FROM CONFIG - ADD THESE LINES
        self.root.update_idletasks()  # Ensure widgets are rendered
        self.config.restore_panel_sizes(
            self.main_paned,
            self.left_paned if hasattr(self, 'left_paned') else None,
            self.center_paned if hasattr(self, 'center_paned') else None
        )
        
    
    def create_control_buttons(self):
        """Create mode control buttons in top panel"""
        
        # Left section - Layout mode
        left_frame = tk.Frame(self.control_panel, bg='#2d2d30')
        left_frame.pack(side=tk.LEFT, padx=10, pady=5)
        
        tk.Label(
            left_frame,
            text="Layout:",
            bg='#2d2d30',
            fg='#d4d4d4',
            font=('Arial', 10, 'bold')
        ).pack(side=tk.LEFT, padx=5)
        
        # Zettelkasten radio button
        tk.Radiobutton(
            left_frame,
            text="Zettelkasten",
            variable=self.layout_mode_var,
            value="zettelkasten",
            command=self.on_layout_mode_change,
            bg='#2d2d30',
            fg='#d4d4d4',
            selectcolor='#094771',
            activebackground='#2d2d30',
            activeforeground='#ffffff',
            font=('Arial', 9)
        ).pack(side=tk.LEFT, padx=5)
        
        # Force-directed radio button
        tk.Radiobutton(
            left_frame,
            text="Force-Directed",
            variable=self.layout_mode_var,
            value="force",
            command=self.on_layout_mode_change,
            bg='#2d2d30',
            fg='#d4d4d4',
            selectcolor='#094771',
            activebackground='#2d2d30',
            activeforeground='#ffffff',
            font=('Arial', 9)
        ).pack(side=tk.LEFT, padx=5)
        
        # Separator
        tk.Frame(left_frame, bg='#555555', width=2, height=30).pack(side=tk.LEFT, padx=10)
        
        # Focus mode checkbox
        tk.Checkbutton(
            left_frame,
            text="Focus Mode (2-hop)",
            variable=self.focus_mode_var,
            command=self.on_focus_mode_change,
            bg='#2d2d30',
            fg='#d4d4d4',
            selectcolor='#094771',
            activebackground='#2d2d30',
            activeforeground='#ffffff',
            font=('Arial', 9)
        ).pack(side=tk.LEFT, padx=5)
        
        # Middle section - Action buttons
        middle_frame = tk.Frame(self.control_panel, bg='#2d2d30')
        middle_frame.pack(side=tk.LEFT, padx=20, pady=5)
        
        tk.Button(
            middle_frame,
            text="Set Focus Node",
            command=self.prompt_set_focus,
            bg='#0e639c',
            fg='#ffffff',
            relief=tk.FLAT,
            padx=15,
            pady=3,
            font=('Arial', 9)
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            middle_frame,
            text="User Legend",
            command=self.show_user_legend,
            bg='#0e639c',
            fg='#ffffff',
            relief=tk.FLAT,
            padx=15,
            pady=3,
            font=('Arial', 9)
        ).pack(side=tk.LEFT, padx=5)
        
        # Right section - View controls
        right_frame = tk.Frame(self.control_panel, bg='#2d2d30')
        right_frame.pack(side=tk.RIGHT, padx=10, pady=5)
        
        tk.Button(
            right_frame,
            text="Zoom In",
            command=self.zoom_in,
            bg='#3c3c3c',
            fg='#ffffff',
            relief=tk.FLAT,
            padx=10,
            pady=3,
            font=('Arial', 9)
        ).pack(side=tk.LEFT, padx=2)
        
        tk.Button(
            right_frame,
            text="Zoom Out",
            command=self.zoom_out,
            bg='#3c3c3c',
            fg='#ffffff',
            relief=tk.FLAT,
            padx=10,
            pady=3,
            font=('Arial', 9)
        ).pack(side=tk.LEFT, padx=2)
        
        tk.Button(
            right_frame,
            text="Reset View",
            command=self.reset_view,
            bg='#3c3c3c',
            fg='#ffffff',
            relief=tk.FLAT,
            padx=10,
            pady=3,
            font=('Arial', 9)
        ).pack(side=tk.LEFT, padx=2)
    
    def on_layout_mode_change(self):
        """Handle layout mode radio button change"""
        mode = self.layout_mode_var.get()
        self.zettelkasten_mode = (mode == "zettelkasten")
        
        if self.graph:
            # Recalculate layout
            from graph.layout import calculate_positions, calculate_force_directed_layout, auto_select_focus_node
            
            if self.zettelkasten_mode:
                focus_id = auto_select_focus_node(self.graph)
                calculate_positions(self.graph, focus_node_id=focus_id)
            else:
                calculate_force_directed_layout(self.graph)
            
            if self.canvas:
                self.canvas.draw()

    def on_focus_mode_change(self):
        """Handle focus mode checkbox change"""
        if self.canvas:
            self.canvas.focus_mode = self.focus_mode_var.get()
            
            if self.canvas.focus_mode:
                self.canvas.update_visible_for_focus()
                self.status.config(text="Focus mode: ON (2-hop)")
            else:
                self.canvas.visible_nodes = set(self.graph.files.keys())
                self.status.config(text="Focus mode: OFF (all nodes)")
            
            self.canvas.draw()

    def prompt_set_focus(self):
        """Prompt user to set a new focus node"""
        if not self.graph or not self.canvas:
            messagebox.showwarning("No Graph", "Load a graph first")
            return
        
        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Set Focus Node")
        dialog.geometry("500x400")
        dialog.configure(bg='#252526')
        
        # Center on parent
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 250
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 200
        dialog.geometry(f"+{x}+{y}")
        
        tk.Label(
            dialog,
            text="Select node to focus on:",
            bg='#252526',
            fg='#d4d4d4',
            font=('Arial', 12)
        ).pack(pady=10)
        
        # Listbox with all nodes
        frame = tk.Frame(dialog, bg='#252526')
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        listbox = tk.Listbox(
            frame,
            bg='#2d2d30',
            fg='#d4d4d4',
            selectbackground='#094771',
            font=('Courier', 10),
            yscrollcommand=scrollbar.set
        )
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)
        
        # Populate with nodes (user files first)
        node_list = []
        for node_id, node in self.graph.files.items():
            is_system = node.info.get('is_system_file', False)
            owner = node.info.get('owner_name', 'unknown')
            prefix = "[SYS]" if is_system else f"[{owner[:10]}]"
            display = f"{prefix} {node.name}"
            node_list.append((display, node_id))
        
        # Sort: user files first, then by name
        node_list.sort(key=lambda x: (
            self.graph.files[x[1]].info.get('is_system_file', False),
            x[0].lower()
        ))
        
        for display, node_id in node_list:
            listbox.insert(tk.END, display)
        
        def on_select():
            selection = listbox.curselection()
            if selection:
                idx = selection[0]
                node_id = node_list[idx][1]
                self.canvas.set_focus_node(node_id)
                dialog.destroy()
        
        # Buttons
        btn_frame = tk.Frame(dialog, bg='#252526')
        btn_frame.pack(pady=10)
        
        tk.Button(
            btn_frame,
            text="Set Focus",
            command=on_select,
            bg='#0e639c',
            fg='#ffffff',
            relief=tk.FLAT,
            padx=20,
            pady=5
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            btn_frame,
            text="Cancel",
            command=dialog.destroy,
            bg='#3c3c3c',
            fg='#ffffff',
            relief=tk.FLAT,
            padx=20,
            pady=5
        ).pack(side=tk.LEFT, padx=5)
        
        # Double-click to select
        listbox.bind('<Double-Button-1>', lambda e: on_select())

    def show_user_legend(self):
        """Show legend of user colors"""
        if not self.canvas or not self.graph:
            messagebox.showwarning("No Graph", "Load a graph first")
            return
        
        # Collect all unique users
        users = {}
        for node in self.graph.files.values():
            owner = node.info.get('owner_name', 'unknown')
            is_system = node.info.get('is_system_file', False)
            
            if owner not in users:
                users[owner] = {
                    'count': 0,
                    'is_system': is_system,
                    'color': self.canvas.get_user_color(owner) if not is_system else '#444444'
                }
            users[owner]['count'] += 1
        
        # Create legend window
        legend = tk.Toplevel(self.root)
        legend.title("User Legend")
        legend.geometry("400x500")
        legend.configure(bg='#252526')
        
        # Center on parent
        legend.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 200
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 250
        legend.geometry(f"+{x}+{y}")
        
        tk.Label(
            legend,
            text="File Owners / Users",
            bg='#252526',
            fg='#d4d4d4',
            font=('Arial', 14, 'bold')
        ).pack(pady=10)
        
        # Canvas for color swatches
        canvas = tk.Canvas(legend, bg='#2d2d30', highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar = tk.Scrollbar(legend, orient=tk.VERTICAL, command=canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Frame inside canvas
        frame = tk.Frame(canvas, bg='#2d2d30')
        canvas.create_window((0, 0), window=frame, anchor='nw')
        
        # Sort users: non-system first, then by count
        sorted_users = sorted(
            users.items(),
            key=lambda x: (x[1]['is_system'], -x[1]['count'])
        )
        
        y_pos = 0
        for owner, info in sorted_users:
            # Color swatch
            color_frame = tk.Frame(frame, bg=info['color'], width=30, height=20)
            color_frame.grid(row=y_pos, column=0, padx=10, pady=5, sticky='w')
            color_frame.grid_propagate(False)
            
            # Owner name
            label_text = f"{owner} ({info['count']} files)"
            if info['is_system']:
                label_text += " [SYSTEM]"
            
            tk.Label(
                frame,
                text=label_text,
                bg='#2d2d30',
                fg='#d4d4d4',
                font=('Arial', 10),
                anchor='w'
            ).grid(row=y_pos, column=1, padx=10, pady=5, sticky='w')
            
            y_pos += 1
        
        # Update scroll region
        frame.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox('all'))
        
        tk.Button(
            legend,
            text="Close",
            command=legend.destroy,
            bg='#3c3c3c',
            fg='#ffffff',
            relief=tk.FLAT,
            padx=20,
            pady=5
        ).pack(pady=10)

    
    # ========================================================================
    # Analysis Mode Starters
    # ========================================================================
    
    def start_live_analysis(self):
        """Start live directory analysis"""
        try:
            self.analysis_mode = 'live'
            logger.info("Starting live analysis")
            
            folder = filedialog.askdirectory(title="Select folder to analyze")
            if folder:
                self.open_live_folder(folder)
        
        except Exception as e:
            logger.error(f"Failed to start live analysis: {e}")
            log_error_report(e, context={'operation': 'start_live_analysis'})
            messagebox.showerror("Error", f"Failed to start analysis:\n\n{str(e)}")
    
    def start_forensic_analysis(self):
        """Start forensic image analysis"""
        try:
            self.analysis_mode = 'forensic'
            logger.info("Starting forensic analysis")
            
            # Check dependencies
            feature_check = check_feature('forensic')
            if not feature_check['available']:
                messagebox.showerror("Missing Dependencies", feature_check['message'])
                return
            
            # Show case info dialog
            dialog = CaseDialog(self.root)
            case_info = dialog.get_result()
            
            if not case_info:
                logger.info("Forensic analysis cancelled by user")
                return
            
            self.case_info = case_info
            
            # Select forensic image
            image_path = filedialog.askopenfilename(
                title="Select forensic image",
                filetypes=[
                    ("All Forensic Images", "*.e01 *.E01 *.dd *.DD *.raw *.img *.aff *.AFF"),
                    ("E01 Images", "*.e01 *.E01"),
                    ("DD/Raw Images", "*.dd *.DD *.raw *.img"),
                    ("AFF Images", "*.aff *.AFF"),
                    ("All Files", "*.*")
                ]
            )
            
            if image_path:
                self.open_forensic_image(image_path)
        
        except Exception as e:
            logger.error(f"Failed to start forensic analysis: {e}")
            log_error_report(e, context={'operation': 'start_forensic_analysis'})
            messagebox.showerror("Error", f"Failed to start forensic analysis:\n\n{str(e)}")
    
    def start_memory_analysis(self):
        """Start memory dump analysis"""
        try:
            self.analysis_mode = 'memory'
            logger.info("Starting memory analysis")
            
            # Check dependencies
            feature_check = check_feature('memory')
            if not feature_check['available']:
                messagebox.showerror("Missing Dependencies", feature_check['message'])
                return
            
            # Show case info dialog
            dialog = CaseDialog(self.root)
            case_info = dialog.get_result()
            
            if not case_info:
                logger.info("Memory analysis cancelled by user")
                return
            
            self.case_info = case_info
            
            # Select memory dump
            dump_path = filedialog.askopenfilename(
                title="Select memory dump",
                filetypes=[
                    ("Memory Dumps", "*.mem *.raw *.dmp *.dump"),
                    ("All Files", "*.*")
                ]
            )
            
            if dump_path:
                self.open_memory_dump(dump_path)
        
        except Exception as e:
            logger.error(f"Failed to start memory analysis: {e}")
            log_error_report(e, context={'operation': 'start_memory_analysis'})
            messagebox.showerror("Error", f"Failed to start memory analysis:\n\n{str(e)}")
    
    def start_iso_analysis(self):
        """Start ISO image analysis"""
        try:
            self.analysis_mode = 'iso'
            logger.info("Starting ISO analysis")
            
            # Check dependencies
            feature_check = check_feature('iso')
            if not feature_check['available']:
                messagebox.showerror("Missing Dependencies", feature_check['message'])
                return
            
            # Show case info dialog
            dialog = CaseDialog(self.root)
            case_info = dialog.get_result()
            
            if not case_info:
                logger.info("ISO analysis cancelled by user")
                return
            
            self.case_info = case_info
            
            # Select ISO file
            iso_path = filedialog.askopenfilename(
                title="Select ISO image",
                filetypes=[
                    ("ISO Images", "*.iso *.ISO"),
                    ("All Files", "*.*")
                ]
            )
            
            if iso_path:
                self.open_iso_image(iso_path)
        
        except Exception as e:
            logger.error(f"Failed to start ISO analysis: {e}")
            log_error_report(e, context={'operation': 'start_iso_analysis'})
            messagebox.showerror("Error", f"Failed to start ISO analysis:\n\n{str(e)}")
    
    def start_browser_analysis(self):
        """Start browser history analysis"""
        try:
            self.analysis_mode = 'browser'
            logger.info("Starting browser analysis")
            
            profile_path = filedialog.askdirectory(
                title="Select browser profile or user directory"
            )
            
            if profile_path:
                self.analyze_browser_history(profile_path)
        
        except Exception as e:
            logger.error(f"Failed to start browser analysis: {e}")
            log_error_report(e, context={'operation': 'start_browser_analysis'})
            messagebox.showerror("Error", f"Failed to start browser analysis:\n\n{str(e)}")
    
    def start_email_analysis(self):
        """Start email analysis"""
        try:
            self.analysis_mode = 'email'
            logger.info("Starting email analysis")
            
            email_path = filedialog.askdirectory(
                title="Select directory containing email files"
            )
            
            if email_path:
                self.analyze_email_files(email_path)
        
        except Exception as e:
            logger.error(f"Failed to start email analysis: {e}")
            log_error_report(e, context={'operation': 'start_email_analysis'})
            messagebox.showerror("Error", f"Failed to start email analysis:\n\n{str(e)}")
    
    def start_prefetch_analysis(self):
        """Start Windows Prefetch analysis"""
        try:
            self.analysis_mode = 'prefetch'
            logger.info("Starting prefetch analysis")
            
            prefetch_path = filedialog.askdirectory(
                title="Select Windows Prefetch directory"
            )
            
            if prefetch_path:
                self.analyze_prefetch_files(prefetch_path)
        
        except Exception as e:
            logger.error(f"Failed to start prefetch analysis: {e}")
            log_error_report(e, context={'operation': 'start_prefetch_analysis'})
            messagebox.showerror("Error", f"Failed to start prefetch analysis:\n\n{str(e)}")
    
    def start_device_capture(self):
        """Start device capture"""
        try:
            logger.info("Starting device capture")
            
            # Check dependencies
            if not is_available('psutil'):
                messagebox.showerror(
                    "Missing Dependencies",
                    "Device capture requires psutil.\n\nInstall with: pip install psutil"
                )
                return
            
            dialog = DeviceCaptureDialog(self.root)
            result = dialog.get_result()
            
            if result:
                logger.info(f"Device capture completed: {result}")
                messagebox.showinfo("Capture Complete", "Device capture completed successfully!")
        
        except Exception as e:
            logger.error(f"Device capture failed: {e}")
            log_error_report(e, context={'operation': 'start_device_capture'})
            messagebox.showerror("Error", f"Device capture failed:\n\n{str(e)}")
    
    # ========================================================================
    # Core Analysis Methods
    # ========================================================================
    
    def open_live_folder(self, folder):
        """Open and analyze a live folder"""
        if self.splash:
            self.hide_splash()
        
        self.show_progress()
        
        try:
            logger.info(f"Opening live folder: {folder}")
            
            self.update_progress(0, "Starting scan...")
            nodes, self.git_analyzer = scan_folder(folder, progress_callback=self.update_progress)
            
            logger.info(f"Scan complete: {len(nodes)} nodes found")
            
            self.update_progress(70, "Building graph...")
            self.build_and_display_graph(nodes, folder)
            
            self.status.config(
                text=f"ready - live analysis - {len(nodes)} files, {len(self.graph.links)} links"
            )
            
            self.hide_progress()
            logger.info("Live folder analysis complete")
        
        except FileSystemError as e:
            self.hide_progress()
            logger.error(f"Filesystem error: {e}")
            messagebox.showerror("Filesystem Error", e.get_user_message())
            self.status.config(text="error")
        
        except Exception as e:
            self.hide_progress()
            logger.error(f"Failed to load folder: {e}")
            log_error_report(e, context={'folder': folder})
            messagebox.showerror("Error", f"Failed to load folder:\n\n{str(e)}")
            self.status.config(text="error")
    
    def open_forensic_image(self, image_path):
        """Open and analyze a forensic image"""
        if self.splash:
            self.hide_splash()
        
        self.show_progress()
        
        try:
            logger.info(f"Opening forensic image: {image_path}")
            
            self.update_progress(0, "Opening forensic image...")
            
            # Initialize forensic scanner
            self.forensic_scanner = ForensicScanner(image_path)
            
            # Open the image
            self.forensic_scanner.open_image()
            
            # Store image info
            if self.case_info:
                self.case_info.image_path = image_path
                self.case_info.image_type = self.forensic_scanner.image_type
            
            self.update_progress(10, "Detecting filesystem...")
            
            # Detect filesystem
            self.forensic_scanner.detect_filesystem()
            
            if self.case_info:
                self.case_info.filesystem_type = self.forensic_scanner.filesystem_type
            
            self.update_progress(20, "Scanning files...")
            
            # Scan the filesystem
            entries = self.forensic_scanner.scan_filesystem(
                progress_callback=self.update_progress
            )
            
            logger.info(f"Found {len(entries)} entries in forensic image")
            
            self.update_progress(65, "Analyzing for deleted files...")
            
            # Initialize forensic analyzer
            forensic_analyzer = ForensicAnalyzer(self.forensic_scanner)
            deleted_files = forensic_analyzer.find_deleted_files()
            
            logger.info(f"Found {len(deleted_files)} deleted files")
            
            self.update_progress(70, "Building nodes...")
            
            # Create FileNode objects
            nodes = []
            
            # Active files
            for entry in entries:
                node = ForensicFileNode(entry, {'recovery_status': 'active'})
                nodes.append(node)
            
            # Deleted files
            for deleted in deleted_files:
                node = ForensicFileNode(
                    deleted['entry'],
                    deleted['forensic_info'],
                    base_path=str(image_path)
                )
                nodes.append(node)
            
            # Store image size
            if self.case_info and self.forensic_scanner.img_info:
                self.case_info.image_size = self.forensic_scanner.img_info.get_size()
            
            self.update_progress(75, "Building graph...")
            
            # Build and display graph
            self.build_and_display_graph(nodes, str(image_path))
            
            # Update status
            active_count = len(entries)
            deleted_count = len(deleted_files)
            self.status.config(
                text=f"ready - forensic analysis - {active_count} active, "
                    f"{deleted_count} deleted, {len(self.graph.links)} links"
            )
            
            self.hide_progress()
            logger.info("Forensic image analysis complete")
        
        except ForensicImageError as e:
            self.hide_progress()
            logger.error(f"Forensic image error: {e}")
            messagebox.showerror("Forensic Image Error", e.get_user_message())
            self.status.config(text="error")
        
        except Exception as e:
            self.hide_progress()
            logger.error(f"Failed to analyze forensic image: {e}")
            log_error_report(e, context={'image_path': image_path})
            messagebox.showerror("Error", f"Failed to analyze forensic image:\n\n{str(e)}")
            self.status.config(text="error")
    
    def open_memory_dump(self, dump_path):
        """Open and analyze a memory dump"""
        if self.splash:
            self.hide_splash()
        
        self.show_progress()
        
        try:
            logger.info(f"Opening memory dump: {dump_path}")
            
            self.update_progress(0, "Opening memory dump...")
            
            # Initialize memory analyzer
            self.memory_analyzer = MemoryAnalyzer(dump_path)
            
            # Store dump info
            if self.case_info:
                self.case_info.image_path = dump_path
                self.case_info.image_type = 'memory_dump'
            
            self.update_progress(5, "Detecting OS profile...")
            
            # Detect profile
            self.memory_analyzer.detect_profile(progress_callback=self.update_progress)
            
            if self.case_info:
                self.case_info.filesystem_type = f"Memory ({self.memory_analyzer.profile})"
            
            logger.info(f"Detected OS: {self.memory_analyzer.profile}")
            
            self.update_progress(20, "Extracting processes...")
            
            # Analyze processes
            self.memory_analyzer.analyze_processes(progress_callback=self.update_progress)
            
            self.update_progress(40, "Extracting file handles...")
            
            # Analyze files
            self.memory_analyzer.analyze_files(progress_callback=self.update_progress)
            
            self.update_progress(60, "Extracting network connections...")
            
            # Analyze network
            self.memory_analyzer.analyze_network(progress_callback=self.update_progress)
            
            logger.info(
                f"Memory analysis complete: {len(self.memory_analyzer.processes)} processes, "
                f"{len(self.memory_analyzer.files)} files"
            )
            
            self.update_progress(70, "Building nodes...")
            
            # Create nodes from memory analysis
            nodes = []
            
            # Process nodes
            for proc in self.memory_analyzer.processes:
                proc_node = MemoryProcessNode(proc)
                nodes.append(proc_node)
            
            # File nodes
            for file_data in self.memory_analyzer.files:
                # Find associated process
                process_info = None
                for proc in self.memory_analyzer.processes:
                    if proc.get('pid') == file_data.get('pid'):
                        process_info = proc
                        break
                
                file_node = MemoryFileNode(file_data, process_info)
                nodes.append(file_node)
            
            self.update_progress(75, "Building graph...")
            
            # Build and display
            self.build_and_display_graph(nodes, f"memory_{dump_path}")
            
            # Update status
            self.status.config(
                text=f"ready - memory analysis - {len(self.memory_analyzer.processes)} processes, "
                    f"{len(self.memory_analyzer.files)} files, {len(self.graph.links)} links"
            )
            
            self.hide_progress()
            logger.info("Memory dump analysis complete")
        
        except MemoryDumpError as e:
            self.hide_progress()
            logger.error(f"Memory dump error: {e}")
            messagebox.showerror("Memory Dump Error", e.get_user_message())
            self.status.config(text="error")
        
        except Exception as e:
            self.hide_progress()
            logger.error(f"Failed to analyze memory dump: {e}")
            log_error_report(e, context={'dump_path': dump_path})
            messagebox.showerror("Error", f"Failed to analyze memory dump:\n\n{str(e)}")
            self.status.config(text="error")
    
    def open_iso_image(self, iso_path):
        """Open and analyze an ISO image"""
        if self.splash:
            self.hide_splash()
        
        self.show_progress()
        
        try:
            logger.info(f"Opening ISO image: {iso_path}")
            
            self.update_progress(0, "Opening ISO image...")
            
            # Initialize ISO analyzer
            self.iso_analyzer = ISOAnalyzer(iso_path)
            
            # Open ISO
            self.iso_analyzer.open_iso()
            
            # Store ISO info
            if self.case_info:
                self.case_info.image_path = iso_path
                self.case_info.image_type = 'iso_image'
                self.case_info.filesystem_type = 'ISO 9660'
            
            self.update_progress(10, "Scanning ISO contents...")
            
            # Scan ISO
            entries = self.iso_analyzer.scan_iso(progress_callback=self.update_progress)
            
            # Get ISO statistics
            stats = self.iso_analyzer.get_statistics()
            
            logger.info(f"ISO analysis complete: {stats}")
            
            self.update_progress(70, "Building nodes...")
            
            # Create nodes
            nodes = []
            for entry in entries:
                node = ISOFileNode(entry)
                nodes.append(node)
            
            self.update_progress(75, "Building graph...")
            
            # Build and display
            self.build_and_display_graph(nodes, str(iso_path))
            
            # Update status
            self.status.config(
                text=f"ready - ISO analysis - {stats['file_count']} files, "
                    f"{stats['directory_count']} directories, {len(self.graph.links)} links"
            )
            
            self.hide_progress()
            logger.info("ISO image analysis complete")
        
        except ISOImageError as e:
            self.hide_progress()
            logger.error(f"ISO image error: {e}")
            messagebox.showerror("ISO Image Error", e.get_user_message())
            self.status.config(text="error")
        
        except Exception as e:
            self.hide_progress()
            logger.error(f"Failed to analyze ISO image: {e}")
            log_error_report(e, context={'iso_path': iso_path})
            messagebox.showerror("Error", f"Failed to analyze ISO image:\n\n{str(e)}")
            self.status.config(text="error")
    
    def analyze_browser_history(self, profile_path):
        """Analyze browser history from profile directory"""
        if self.splash:
            self.hide_splash()
        
        self.show_progress()
        
        try:
            logger.info(f"Analyzing browser history: {profile_path}")
            
            self.update_progress(0, "Initializing browser analyzer...")
            
            # Initialize browser analyzer
            self.browser_analyzer = BrowserAnalyzer()
            
            self.update_progress(10, "Scanning for browser data...")
            
            # Scan directory for browser databases
            found_browsers = self.browser_analyzer.scan_directory(
                profile_path,
                progress_callback=self.update_progress
            )
            
            if not found_browsers:
                self.hide_progress()
                messagebox.showwarning(
                    "No Browser Data",
                    "No browser history databases found in the selected directory.\n\n"
                    "Make sure you selected a user profile or home directory."
                )
                self.status.config(text="no browser data found")
                return
            
            logger.info(f"Found browser data: {found_browsers}")
            
            self.update_progress(70, "Building nodes...")
            
            # Create nodes from browser data
            nodes = []
            
            # History nodes
            for entry in self.browser_analyzer.history:
                node = BrowserHistoryNode(entry)
                nodes.append(node)
            
            # Bookmark nodes
            for bookmark in self.browser_analyzer.bookmarks:
                node = BrowserBookmarkNode(bookmark)
                nodes.append(node)
            
            # Download nodes
            for download in self.browser_analyzer.downloads:
                node = BrowserDownloadNode(download)
                nodes.append(node)
            
            logger.info(
                f"Browser analysis: {len(self.browser_analyzer.history)} history, "
                f"{len(self.browser_analyzer.bookmarks)} bookmarks, "
                f"{len(self.browser_analyzer.downloads)} downloads"
            )
            
            self.update_progress(75, "Building graph...")
            
            # Build and display
            self.build_and_display_graph(nodes, str(profile_path))
            
            # Update status
            self.status.config(
                text=f"ready - browser analysis - {len(self.browser_analyzer.history)} history entries, "
                    f"{len(self.graph.links)} links"
            )
            
            self.hide_progress()
            logger.info("Browser analysis complete")
        
        except Exception as e:
            self.hide_progress()
            logger.error(f"Browser analysis failed: {e}")
            log_error_report(e, context={'profile_path': profile_path})
            messagebox.showerror("Error", f"Browser analysis failed:\n\n{str(e)}")
            self.status.config(text="error")
    
    def analyze_email_files(self, email_path):
        """Analyze email files"""
        if self.splash:
            self.hide_splash()
        
        self.show_progress()
        
        try:
            logger.info(f"Analyzing email files: {email_path}")
            
            self.update_progress(0, "Initializing email analyzer...")
            
            # Initialize email analyzer
            self.email_analyzer = EmailAnalyzer(email_path)
            
            self.update_progress(10, "Analyzing email files...")
            
            # Analyze all emails
            self.email_analyzer.analyze_all(progress_callback=self.update_progress)
            
            logger.info(
                f"Email analysis: {len(self.email_analyzer.emails)} emails, "
                f"{len(self.email_analyzer.attachments)} attachments"
            )
            
            self.update_progress(70, "Building nodes...")
            
            # Create nodes from email data
            nodes = []
            
            # Email message nodes
            for email_data in self.email_analyzer.emails:
                node = EmailMessageNode(email_data)
                nodes.append(node)
            
            # Attachment nodes
            for attachment in self.email_analyzer.attachments:
                node = EmailAttachmentNode(attachment)
                nodes.append(node)
            
            self.update_progress(75, "Building graph...")
            
            # Build and display
            self.build_and_display_graph(nodes, str(email_path))
            
            # Update status
            self.status.config(
                text=f"ready - email analysis - {len(self.email_analyzer.emails)} emails, "
                    f"{len(self.email_analyzer.attachments)} attachments, {len(self.graph.links)} links"
            )
            
            self.hide_progress()
            logger.info("Email analysis complete")
        
        except Exception as e:
            self.hide_progress()
            logger.error(f"Email analysis failed: {e}")
            log_error_report(e, context={'email_path': email_path})
            messagebox.showerror("Error", f"Email analysis failed:\n\n{str(e)}")
            self.status.config(text="error")
    
    def analyze_prefetch_files(self, prefetch_path):
        """Analyze Windows Prefetch files"""
        if self.splash:
            self.hide_splash()
        
        self.show_progress()
        
        try:
            logger.info(f"Analyzing prefetch files: {prefetch_path}")
            
            self.update_progress(0, "Initializing prefetch analyzer...")
            
            # Initialize prefetch analyzer
            self.prefetch_analyzer = PrefetchAnalyzer(prefetch_path)
            
            self.update_progress(10, "Analyzing prefetch files...")
            
            # Analyze all prefetch files
            programs = self.prefetch_analyzer.analyze(progress_callback=self.update_progress)
            
            logger.info(
                f"Prefetch analysis: {len(programs)} programs, "
                f"{len(self.prefetch_analyzer.execution_timeline)} timeline entries"
            )
            
            self.update_progress(70, "Building nodes...")
            
            # Create nodes from prefetch data
            nodes = []
            
            for program_name, program_data in programs.items():
                node = PrefetchProgramNode(program_data)
                nodes.append(node)
            
            self.update_progress(75, "Building graph...")
            
            # Build and display
            self.build_and_display_graph(nodes, str(prefetch_path))
            
            # Update status
            self.status.config(
                text=f"ready - prefetch analysis - {len(programs)} programs, "
                    f"{len(self.graph.links)} links"
            )
            
            self.hide_progress()
            logger.info("Prefetch analysis complete")
        
        except Exception as e:
            self.hide_progress()
            logger.error(f"Prefetch analysis failed: {e}")
            log_error_report(e, context={'prefetch_path': prefetch_path})
            messagebox.showerror("Error", f"Prefetch analysis failed:\n\n{str(e)}")
            self.status.config(text="error")
    
    def build_and_display_graph(self, nodes, base_path):
        """Build graph from nodes and display it"""
        try:
            # CRITICAL: Destroy previous components before creating new ones
            self.cleanup_previous_analysis()
            
            self.update_progress(90, "Creating graph structure...")
            
            # Build graph
            self.graph = Graph()
            self.graph.set_root_path(base_path)
            for node in nodes:
                self.graph.add_file(node)
            
            logger.info(f"Scan complete: {len(nodes)} nodes found")
            
            self.update_progress(92, "Building graph links...")
            logger.info(f"Building graph with {len(nodes)} nodes")
            
            # Create connections
            create_all_links(self.graph)
            
            logger.info(f"Added {len(self.graph.files)} nodes to graph")
            logger.info(f"Created {sum(len(n.connections) for n in self.graph.files.values())} links")
            
            self.update_progress(94, "Calculating layout...")
            

            # Calculate positions based on mode
            if self.zettelkasten_mode:
                focus_id = auto_select_focus_node(self.graph)
                calculate_positions(self.graph, focus_node_id=focus_id)
            else:
                calculate_force_directed_layout(self.graph)
            # Create tree view
            self.tree = TreeView(
                self.tree_content_frame,
                self.graph,
                callback=self.node_clicked
            )
            self.tree.pack(fill=tk.BOTH, expand=True)
            self.tree.populate()
            
            # Create timeline
            self.timeline = TimelinePanel(
                self.timeline_content_frame,
                callback=self.on_timeline_change
            )
            self.timeline.pack(fill=tk.BOTH, expand=True)

            # Only load git timeline for live analysis
            if self.git_analyzer:
                self.timeline.load_git_timeline(self.graph, self.git_analyzer)

            # Create heatmap
            self.heatmap = HeatmapPanel(
                self.heatmap_content_frame,
                callback=self.on_heatmap_click
            )
            self.heatmap.pack(fill=tk.BOTH, expand=True)

            # Load heatmap data based on analysis type
            if self.git_analyzer:
                self.heatmap.load_from_graph(self.graph, self.git_analyzer)
            elif self.browser_analyzer:
                self.heatmap.load_from_analyzer(self.browser_analyzer, 'browser')
            elif self.email_analyzer:
                self.heatmap.load_from_analyzer(self.email_analyzer, 'email')
            elif self.prefetch_analyzer:
                self.heatmap.load_from_analyzer(self.prefetch_analyzer, 'prefetch')
            
            self.update_progress(96, "Rendering graph...")
            
            # Graph canvas
            self.canvas = GraphCanvas(
                self.canvas_frame, 
                self.graph, 
                callback=self.node_selected
            )
            self.canvas.pack(fill=tk.BOTH, expand=True)
            
            self.update_progress(97, "Finalizing...")
            
            # Info panel
            self.info = InfoPanel(
                self.info_content_frame, 
                self.graph,
                callback=self.node_clicked
            )
            self.info.pack(fill=tk.BOTH, expand=True)

            if self.filters:
                self.filters.destroy()

            self.filters = FilterPanel(
                self.root,  # parent (won't be visible)
                callback=self.update_visible_nodes
            )
            
            # FIX: Set initial visible nodes and draw
            self.update_visible_nodes()
            self.info.update_stats()
            
            self.update_progress(98, "Setting up focus mode...")
            
            # Set up canvas with focus mode
            if self.canvas and self.zettelkasten_mode:
                focus_id = auto_select_focus_node(self.graph)
                self.canvas.focus_node = focus_id
                if self.focus_mode_var.get():
                    self.canvas.update_visible_for_focus()
            
            # FINAL - only appears ONCE now
            self.update_progress(100, "Complete!")
            
            logger.info("Graph display complete")
            
        except Exception as e:
            logger.error(f"Failed to build and display graph: {e}")
            log_error_report(e, context={'base_path': base_path, 'node_count': len(nodes)})
            raise


    def cleanup_previous_analysis(self):
        """Clean up all components from previous analysis before loading new one"""
        logger.info("Cleaning up previous analysis...")
        
        # Destroy canvas
        if self.canvas:
            try:
                self.canvas.destroy()
            except Exception as e:
                logger.warning(f"Error destroying canvas: {e}")
            self.canvas = None
        
        # Clear canvas frame
        for widget in self.canvas_frame.winfo_children():
            try:
                widget.destroy()
            except Exception as e:
                logger.warning(f"Error destroying canvas widget: {e}")
        
        # Destroy info panel
        if self.info:
            try:
                self.info.destroy()
            except Exception as e:
                logger.warning(f"Error destroying info panel: {e}")
            self.info = None
        
        # Clear info frame
        for widget in self.info_content_frame.winfo_children():
            try:
                widget.destroy()
            except Exception as e:
                logger.warning(f"Error destroying info widget: {e}")
        
        # Destroy tree
        if self.tree:
            try:
                self.tree.destroy()
            except Exception as e:
                logger.warning(f"Error destroying tree: {e}")
            self.tree = None
        
        # Clear tree frame
        for widget in self.tree_content_frame.winfo_children():
            try:
                widget.destroy()
            except Exception as e:
                logger.warning(f"Error destroying tree widget: {e}")
        
        # Destroy timeline
        if self.timeline:
            try:
                self.timeline.destroy()
            except Exception as e:
                logger.warning(f"Error destroying timeline: {e}")
            self.timeline = None
        
        # Clear timeline frame
        for widget in self.timeline_content_frame.winfo_children():
            try:
                widget.destroy()
            except Exception as e:
                logger.warning(f"Error destroying timeline widget: {e}")
        
        # Destroy heatmap
        if self.heatmap:
            try:
                self.heatmap.destroy()
            except Exception as e:
                logger.warning(f"Error destroying heatmap: {e}")
            self.heatmap = None
        
        # Clear heatmap frame
        for widget in self.heatmap_content_frame.winfo_children():
            try:
                widget.destroy()
            except Exception as e:
                logger.warning(f"Error destroying heatmap widget: {e}")
        
        # Destroy filters
        if self.filters:
            try:
                self.filters.destroy()
            except Exception as e:
                logger.warning(f"Error destroying filters: {e}")
            self.filters = None
        
        # Clear graph reference
        self.graph = None
        
        # Force garbage collection
        import gc
        gc.collect()
        
        # Force UI update to clear any visual artifacts
        self.root.update_idletasks()
        
        logger.info("Cleanup complete")
    
    # ========================================================================
    # UI Event Handlers
    # ========================================================================
    
    def node_selected(self, node_id):
        """Handle node selection from canvas - receives node_id string"""
        # Convert node_id to node object
        if not self.graph:
            return
            
        node = self.graph.files.get(node_id)
        if not node:
            return
            
        # Update info panel
        if self.info:
            self.info.show_info(node)
        
        # Update tree selection
        if self.tree:
            self.tree.select_node(node_id)  
    
    def node_clicked(self, node_id):
        """Handle node click from tree view or canvas"""
        if not self.graph or node_id not in self.graph.files:
            return
        
        node = self.graph.files[node_id]
        
        # Update canvas selection
        if self.canvas:
            self.canvas.selected = node_id
            
            # In zettelkasten mode with focus mode ON, set as new focus
            if self.zettelkasten_mode and self.focus_mode_var.get():
                self.canvas.set_focus_node(node_id)
            else:
                self.canvas.draw()
        
        # Update info panel
        if self.info:
            self.info.show_info(node)
        
        # Highlight in tree view
        if self.tree:
            self.tree.select_node(node_id)
        
        logger.debug(f"Selected node: {node.name}")
    
    def on_timeline_change(self, start_date, end_date):
        """Handle timeline filter change"""
        if self.graph:
            self.update_visible_nodes()
    
    def on_heatmap_click(self, data_tag):
        """Handle heatmap click"""
        logger.debug(f"Heatmap clicked: {data_tag}")
    
    def update_visible_nodes(self):
        """Update which nodes are visible based on filters"""
        if self.canvas and self.graph:
            # Determine visible nodes based on filters
            if self.filters:
                # If filters exist, check each node
                visible_ids = set()
                for node_id, node in self.graph.files.items():
                    if self.filters.should_show_node(node):
                        visible_ids.add(node_id)
            else:
                # No filter - show all nodes
                visible_ids = set(self.graph.files.keys())
            
            logger.debug(f"Updating visible nodes: {len(visible_ids)} of {len(self.graph.files)} visible")
            
            # Update canvas with visible nodes - use set_visible_nodes, NOT refresh
            self.canvas.set_visible_nodes(visible_ids)
    
    # ========================================================================
    # Progress Bar Methods
    # ========================================================================
    
    def show_progress(self):
        """Show progress window"""
        self.progress_window = tk.Toplevel(self.root)
        self.progress_window.title("Processing...")
        self.progress_window.geometry("400x120")
        self.progress_window.configure(bg='#252526')
        self.progress_window.resizable(False, False)
        
        # Center on parent
        self.progress_window.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 200
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 60
        self.progress_window.geometry(f"+{x}+{y}")
        
        self.progress_label = tk.Label(
            self.progress_window,
            text="Starting...",
            bg='#252526',
            fg='#d4d4d4',
            font=('Arial', 10)
        )
        self.progress_label.pack(pady=20)
        
        # Progress bar style
        style = ttk.Style()
        style.theme_use('default')
        style.configure("Custom.Horizontal.TProgressbar",
                    troughcolor='#3c3c3c',
                    background='#4fc3f7',
                    bordercolor='#252526',
                    lightcolor='#4fc3f7',
                    darkcolor='#4fc3f7')
        
        self.progress_bar = ttk.Progressbar(
            self.progress_window,
            style="Custom.Horizontal.TProgressbar",
            length=350,
            mode='determinate',
            maximum=100
        )
        self.progress_bar.pack(pady=10, padx=25)
    
    def update_progress(self, value, text):
        """Update progress bar"""
        if self.progress_bar and self.progress_label:
            self.progress_bar['value'] = value
            self.progress_label.config(text=text)
            self.root.update()
    
    def hide_progress(self):
        """Hide progress window"""
        if self.progress_window:
            self.progress_window.destroy()
            self.progress_window = None
            self.progress_bar = None
            self.progress_label = None
    
    # ========================================================================
    # Menu Callbacks
    # ========================================================================
    
    def export(self):
        """Export graph to JSON"""
        if not self.graph:
            messagebox.showwarning("No Data", "No graph loaded to export")
            return
        
        try:
            filepath = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            
            if filepath:
                logger.info(f"Exporting graph to {filepath}")
                
                self.graph.save(filepath)
                
                # Also save case info if available
                if self.case_info:
                    case_file = filepath.replace('.json', '_case.json')
                    self.case_info.save_to_file(case_file)
                    logger.info(f"Saved case info to {case_file}")
                
                # Export analyzer data
                if self.analysis_mode == 'browser' and self.browser_analyzer:
                    browser_file = filepath.replace('.json', '_browser.json')
                    self.browser_analyzer.export_to_json(browser_file)
                
                if self.analysis_mode == 'email' and self.email_analyzer:
                    email_file = filepath.replace('.json', '_email.json')
                    self.email_analyzer.export_to_json(email_file)
                
                if self.analysis_mode == 'prefetch' and self.prefetch_analyzer:
                    prefetch_file = filepath.replace('.json', '_prefetch.json')
                    self.prefetch_analyzer.export_to_json(prefetch_file)
                
                messagebox.showinfo(
                    "Success",
                    f"Exported all analysis data to:\n{Path(filepath).parent}"
                )
                logger.info("Export complete")
        
        except Exception as e:
            logger.error(f"Export failed: {e}")
            log_error_report(e, context={'filepath': filepath if 'filepath' in locals() else 'unknown'})
            messagebox.showerror("Export Error", f"Failed to export:\n\n{str(e)}")
            
    def save_panel_layout(self):
        """Manually save current panel layout"""
        try:
            self.config.save_panel_sizes(
                self.main_paned,
                self.left_paned if hasattr(self, 'left_paned') else None,
                self.center_paned if hasattr(self, 'center_paned') else None
            )
            self.status.config(text="Panel layout saved")
            logger.info("Panel layout saved to config")
            
            # Show brief confirmation
            self.root.after(2000, lambda: self.status.config(text="ready"))
        except Exception as e:
            logger.error(f"Failed to save panel layout: {e}")
            messagebox.showerror("Error", f"Failed to save panel layout:\n\n{str(e)}")
    
    def show_filter_dialog(self):
        """Show filter configuration dialog"""
        if not self.graph:
            messagebox.showwarning("No Graph", "Load a graph first")
            return
        
        try:
            # Create filter panel if it doesn't exist
            if not self.filters:
                self.filters = FilterPanel(self.root, callback=self.update_visible_nodes)
                # Don't pack it - hidden, just for state
            
            dialog = FilterDialog(self.root, self.filters)
            if dialog.result:
                self.update_visible_nodes()
                logger.info("Filters updated")
        
        except Exception as e:
            logger.error(f"Filter dialog error: {e}")
            messagebox.showerror("Error", f"Filter dialog failed:\n\n{str(e)}")
            
            try:
                # Use the filter panel as the filter manager, or create a new one if it doesn't exist
                filter_manager = self.filters if self.filters else None
                
                if not filter_manager:
                    messagebox.showerror("Error", "Filter system not initialized")
                    return
                    
                dialog = FilterDialog(self.root, filter_manager)  # Pass the filter panel object
                if dialog.result:
                    self.update_visible_nodes()
                    logger.info("Filters updated")
            
            except Exception as e:
                logger.error(f"Filter dialog error: {e}")
                messagebox.showerror("Error", f"Filter dialog failed:\n\n{str(e)}")
    
    def zoom_in(self):
        """Zoom in on graph"""
        if self.canvas:
            # self.canvas.zoom is an attribute, not a method
            self.canvas.zoom *= 1.2
            self.canvas.draw()

    def zoom_out(self):
        """Zoom out on graph"""
        if self.canvas:
            # self.canvas.zoom is an attribute, not a method
            self.canvas.zoom *= 0.8
            self.canvas.draw()
    
    def reset_view(self):
        """Reset graph view"""
        if self.canvas:
            self.canvas.reset_view()
    
    def show_statistics(self):
        """Show graph statistics"""
        if not self.graph:
            messagebox.showwarning("No Graph", "Load a graph first")
            return
        
        try:
            stats_window = tk.Toplevel(self.root)
            stats_window.title("Graph Statistics")
            stats_window.geometry("500x400")
            stats_window.configure(bg='#252526')
            
            # Center on parent
            stats_window.update_idletasks()
            x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 250
            y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 200
            stats_window.geometry(f"+{x}+{y}")
            
            stats_text = tk.Text(
                stats_window,
                bg='#2d2d30',
                fg='#d4d4d4',
                font=('Courier', 10),
                wrap=tk.WORD
            )
            stats_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Build statistics
            total_files = len([n for n in self.graph.files.values() if not n.is_folder])
            total_folders = len([n for n in self.graph.files.values() if n.is_folder])
            total_links = len(self.graph.links)
            
            stats = f"""
{'='*50}
GRAPH STATISTICS
{'='*50}

Total Nodes:     {len(self.graph.files):,}
Files:         {total_files:,}
Folders:       {total_folders:,}

Total Links:     {total_links:,}

Analysis Mode:   {self.analysis_mode or 'unknown'}
{'='*50}
"""
            stats_text.insert('1.0', stats)
            stats_text.config(state=tk.DISABLED)
            
            tk.Button(
                stats_window,
                text="Close",
                bg='#37373d',
                fg='#d4d4d4',
                command=stats_window.destroy
            ).pack(pady=10)
        
        except Exception as e:
            logger.error(f"Statistics display error: {e}")
            messagebox.showerror("Error", f"Failed to show statistics:\n\n{str(e)}")
    
    def show_dependency_status(self):
        """Show dependency status"""
        try:
            dm = get_dependency_manager()
            status_report = dm.get_status_report()
            
            status_window = tk.Toplevel(self.root)
            status_window.title("Dependency Status")
            status_window.geometry("700x600")
            status_window.configure(bg='#252526')
            
            # Center on parent
            status_window.update_idletasks()
            x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 350
            y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 300
            status_window.geometry(f"+{x}+{y}")
            
            status_text = tk.Text(
                status_window,
                bg='#2d2d30',
                fg='#d4d4d4',
                font=('Courier', 9),
                wrap=tk.WORD
            )
            status_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            status_text.insert('1.0', status_report)
            status_text.config(state=tk.DISABLED)
            
            tk.Button(
                status_window,
                text="Close",
                bg='#37373d',
                fg='#d4d4d4',
                command=status_window.destroy
            ).pack(pady=10)
            
            logger.info("Displayed dependency status")
        
        except Exception as e:
            logger.error(f"Dependency status display error: {e}")
            messagebox.showerror("Error", f"Failed to show dependencies:\n\n{str(e)}")
    
    def show_shortcuts(self):
        """Show keyboard shortcuts"""
        doc_text = """
DOTTY - KEYBOARD SHORTCUTS

FILE OPERATIONS:
Ctrl+O          Open live directory
Ctrl+Shift+O    Open forensic image
Ctrl+S          Export JSON
Ctrl+Q          Quit

VIEW CONTROLS:
Ctrl+F          Configure filters
Ctrl++ / Ctrl+- Zoom in/out
Ctrl+0          Reset view

HELP:
F1              Show this help

MOUSE CONTROLS:
Double-click    Select node
Click + Drag    Pan view
Mouse Wheel     Zoom
"""
        
        doc_window = tk.Toplevel(self.root)
        doc_window.title("Keyboard Shortcuts")
        doc_window.geometry("500x450")
        doc_window.configure(bg='#252526')
        
        # Center on parent
        doc_window.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 250
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 225
        doc_window.geometry(f"+{x}+{y}")
        
        text = tk.Text(
            doc_window,
            bg='#2d2d30',
            fg='#d4d4d4',
            font=('Courier', 10),
            wrap=tk.WORD
        )
        text.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        text.insert('1.0', doc_text)
        text.config(state=tk.DISABLED)
        
        tk.Button(
            doc_window,
            text="Close",
            bg='#37373d',
            fg='#d4d4d4',
            command=doc_window.destroy
        ).pack(pady=10)
    
    def show_about(self):
        """Show about dialog"""
        about_text = """dotty - filesystem graph visualization tool

Version: 1.0
Author: @jlahire

A forensic analysis and visualization tool for filesystems.

Supports:
• Live directory scanning with Git history
• Forensic images (E01, DD, RAW)
• Memory dumps (with Volatility3)
• ISO images
• Browser history (Chrome, Firefox, Edge, Safari)
• Email files (PST, MBOX, EML)
• Windows Prefetch analysis

Built with Python + Tkinter"""
        
        about_window = tk.Toplevel(self.root)
        about_window.title("About Dotty")
        about_window.geometry("500x450")
        about_window.configure(bg='#252526')
        
        # Center on parent
        about_window.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 250
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 225
        about_window.geometry(f"+{x}+{y}")
        
        tk.Label(
            about_window,
            text="dotty",
            font=('Arial', 32, 'bold'),
            bg='#252526',
            fg='#4fc3f7'
        ).pack(pady=20)
        
        text = tk.Text(
            about_window,
            bg='#2d2d30',
            fg='#d4d4d4',
            font=('Arial', 10),
            wrap=tk.WORD
        )
        text.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        text.insert('1.0', about_text)
        text.config(state=tk.DISABLED)
        
        tk.Button(
            about_window,
            text="Close",
            bg='#37373d',
            fg='#d4d4d4',
            command=about_window.destroy
        ).pack(pady=10)
    
    # ========================================================================
    # Splash Screen Methods
    # ========================================================================
    
    def show_splash(self):
        """Show splash screen"""
        self.splash = SplashScreen(
            self.root,
            live_callback=self.start_live_analysis,
            forensic_callback=self.start_forensic_analysis,
            memory_callback=self.start_memory_analysis,
            iso_callback=self.start_iso_analysis,
            device_callback=self.start_device_capture,
            browser_callback=self.start_browser_analysis,
            email_callback=self.start_email_analysis,
            prefetch_callback=self.start_prefetch_analysis
        )
        self.splash.pack(fill=tk.BOTH, expand=True)
    
    
    # ========================================================================
    # Application Lifecycle
    # ========================================================================
    
    def run(self):
        """Start the application"""
        logger.info("Starting Dotty application")
        self.root.mainloop()
        
        # NOTE: Cleanup is now handled in on_closing method
        # This code only runs if mainloop exits without close button
        logger.info("Application terminated normally")


def main():
    """Entry point"""
    try:
        logger.info("="*60)
        logger.info("DOTTY - Filesystem Graph Visualization Tool")
        logger.info("="*60)
        
        app = DottyApp()
        app.run()
        
        logger.info("Application terminated normally")
    
    except Exception as e:
        logger.critical(f"Fatal error in main: {e}")
        log_error_report(e, context={'location': 'main'})
        raise




def main():
    """Main entry point"""
    logger.info("="*60)
    logger.info("DOTTY - Filesystem Graph Visualization Tool")
    logger.info("="*60)
    
    app = DottyApp()
    app.run()

if __name__ == '__main__':
    main()