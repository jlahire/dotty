"""
device_capture_dialog.py - dialog for selecting and capturing from devices
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from scanning.device_capture import DeviceCapture, PSUTIL_AVAILABLE
from datetime import datetime
from pathlib import Path
from ui.font_config import get_font


class DeviceCaptureDialog(tk.Toplevel):
    """dialog for device detection and capture"""
    
    def __init__(self, parent):
        super().__init__(parent)
        
        self.title("device capture")
        self.geometry("900x700")
        self.configure(bg='#252526')
        self.resizable(True, True)
        
        # center on parent
        self.transient(parent)
        self.grab_set()
        
        self.device_capture = DeviceCapture()
        self.selected_device = None
        self.capture_type = tk.StringVar(value='ram')
        self.result = None
        
        # Dictionary to store device info
        self.device_info_map = {}
        
        self.setup_ui()
        
        # center window
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 450
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 350
        self.geometry(f"+{x}+{y}")
        
        # Auto-detect devices
        self.after(100, self.detect_devices)
    
    def setup_ui(self):
        """create dialog UI"""
        # title
        title = tk.Label(self, text="device capture & forensic imaging",
                        font=get_font('title', bold=True),
                        bg='#252526', fg='#4fc3f7')
        title.pack(pady=15)
        
        # subtitle
        subtitle = tk.Label(self, 
                           text="detect connected devices and create forensic images or RAM captures",
                           font=get_font('text'),
                           bg='#252526', fg='#9cdcfe')
        subtitle.pack(pady=5)
        
        # Main container
        main_frame = tk.Frame(self, bg='#252526')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Left side - device list
        left_frame = tk.LabelFrame(main_frame, text="detected devices",
                                   bg='#2d2d30', fg='#d4d4d4',
                                   font=get_font('button', bold=True))
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Device list with treeview
        tree_frame = tk.Frame(left_frame, bg='#2d2d30')
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        columns = ('type', 'method', 'status')
        self.device_tree = ttk.Treeview(tree_frame, columns=columns, 
                                        show='tree headings', height=15)
        
        self.device_tree.heading('#0', text='Device')
        self.device_tree.heading('type', text='Type')
        self.device_tree.heading('method', text='Connection')
        self.device_tree.heading('status', text='Status')
        
        self.device_tree.column('#0', width=250)
        self.device_tree.column('type', width=120)
        self.device_tree.column('method', width=100)
        self.device_tree.column('status', width=80)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical',
                                 command=self.device_tree.yview)
        self.device_tree.configure(yscrollcommand=scrollbar.set)
        
        self.device_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind selection
        self.device_tree.bind('<<TreeviewSelect>>', self.on_device_select)
        
        # Refresh button
        tk.Button(left_frame, text="🔄 refresh devices",
                 bg='#37373d', fg='#d4d4d4',
                 font=get_font('small', bold=True),
                 command=self.detect_devices).pack(pady=10)
        
        # Right side - capture options
        right_frame = tk.LabelFrame(main_frame, text="capture options",
                                    bg='#2d2d30', fg='#d4d4d4',
                                    font=get_font('button', bold=True))
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Device info
        info_frame = tk.Frame(right_frame, bg='#2d2d30')
        info_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(info_frame, text="selected device:",
                font=get_font('small', bold=True),
                bg='#2d2d30', fg='#9cdcfe').pack(anchor=tk.W)
        
        self.device_info_label = tk.Label(info_frame,
                                          text="no device selected",
                                          font=get_font('small'),
                                          bg='#2d2d30', fg='#d4d4d4',
                                          justify=tk.LEFT,
                                          wraplength=300)
        self.device_info_label.pack(anchor=tk.W, pady=5)
        
        # Separator
        ttk.Separator(right_frame, orient='horizontal').pack(fill=tk.X, padx=10, pady=10)
        
        # Capture type selection
        type_frame = tk.Frame(right_frame, bg='#2d2d30')
        type_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(type_frame, text="capture type:",
                font=get_font('small', bold=True),
                bg='#2d2d30', fg='#9cdcfe').pack(anchor=tk.W)
        
        # RAM capture option
        ram_radio = tk.Radiobutton(type_frame,
                                   text="💾 RAM capture (memory dump)",
                                   variable=self.capture_type,
                                   value='ram',
                                   bg='#2d2d30', fg='#d4d4d4',
                                   selectcolor='#1e1e1e',
                                   font=get_font('small'),
                                   command=self.update_capture_info)
        ram_radio.pack(anchor=tk.W, pady=5)
        
        # Disk image option
        disk_radio = tk.Radiobutton(type_frame,
                                    text="💿 forensic disk image (full copy)",
                                    variable=self.capture_type,
                                    value='disk',
                                    bg='#2d2d30', fg='#d4d4d4',
                                    selectcolor='#1e1e1e',
                                    font=get_font('small'),
                                    command=self.update_capture_info)
        disk_radio.pack(anchor=tk.W, pady=5)
        
        # Logical backup option (for mobile)
        logical_radio = tk.Radiobutton(type_frame,
                                       text="📱 logical backup (files only)",
                                       variable=self.capture_type,
                                       value='logical',
                                       bg='#2d2d30', fg='#d4d4d4',
                                       selectcolor='#1e1e1e',
                                       font=get_font('small'),
                                       command=self.update_capture_info)
        logical_radio.pack(anchor=tk.W, pady=5)
        
        # Capture info text
        self.capture_info_text = tk.Text(right_frame,
                                         height=6,
                                         bg='#1e1e1e', fg='#d4d4d4',
                                         font=get_font('tiny'),
                                         wrap=tk.WORD)
        self.capture_info_text.pack(fill=tk.X, padx=10, pady=10)
        self.capture_info_text.config(state=tk.DISABLED)
        
        # Output path
        output_frame = tk.Frame(right_frame, bg='#2d2d30')
        output_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(output_frame, text="output location:",
                font=get_font('small', bold=True),
                bg='#2d2d30', fg='#9cdcfe').pack(anchor=tk.W)
        
        path_entry_frame = tk.Frame(output_frame, bg='#2d2d30')
        path_entry_frame.pack(fill=tk.X, pady=5)
        
        self.output_path = tk.StringVar(value=str(Path.home() / "forensic_capture"))
        tk.Entry(path_entry_frame, textvariable=self.output_path,
                bg='#3c3c3c', fg='#d4d4d4',
                font=get_font('small')).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        tk.Button(path_entry_frame, text="browse",
                 bg='#37373d', fg='#d4d4d4',
                 font=get_font('tiny'),
                 command=self.browse_output).pack(side=tk.RIGHT, padx=(5, 0))
        
        # Warning box
        warning_frame = tk.Frame(right_frame, bg='#3c2415')
        warning_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(warning_frame, text="⚠ WARNING",
                font=get_font('small', bold=True),
                bg='#3c2415', fg='#ff9800').pack(pady=5)
        
        tk.Label(warning_frame,
                text="• Ensure you have proper authorization\n"
                     "• Captures may require administrator/root access\n"
                     "• Some operations may take significant time\n"
                     "• Ensure sufficient storage space",
                font=get_font('tiny'),
                bg='#3c2415', fg='#ffcc80',
                justify=tk.LEFT).pack(padx=10, pady=5)
        
        # Buttons
        btn_frame = tk.Frame(self, bg='#252526')
        btn_frame.pack(pady=15)
        
        tk.Button(btn_frame, text="start capture",
                 bg='#4fc3f7', fg='#1e1e1e',
                 font=get_font('button', bold=True), width=15,
                 command=self.start_capture).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="cancel",
                 bg='#37373d', fg='#d4d4d4',
                 font=get_font('button'), width=12,
                 command=self.on_cancel).pack(side=tk.LEFT, padx=5)
        
        # Initial capture info
        self.update_capture_info()
    
    def detect_devices(self):
        """detect all available devices"""
        # Clear tree
        for item in self.device_tree.get_children():
            self.device_tree.delete(item)
        
        # Dictionary to store device info (item_id -> device_info)
        self.device_info_map = {}
        
        # Detect local system
        local_info = self.device_capture.detect_local_system()
        device_name = f"{local_info['hostname']} (This Computer)"
        device_type = local_info['os']
        
        if local_info.get('is_vm'):
            device_type += " (VM)"
        
        local_item = self.device_tree.insert('', 'end',
                                             text=device_name,
                                             values=(device_type, 'local', '✓ Ready'),
                                             tags=('local',))
        
        # Store device info in our dictionary
        self.device_info_map[local_item] = local_info
        
        # Detect USB devices
        usb_devices = self.device_capture.detect_usb_devices()
        
        for device in usb_devices:
            device_name = device.get('model', device.get('device', 'Unknown Device'))
            device_type = device.get('type', 'unknown')
            method = device.get('method', 'usb')
            status = '✓ Ready' if device.get('available') else '✗ Unavailable'
            
            item = self.device_tree.insert('', 'end',
                                          text=device_name,
                                          values=(device_type, method, status),
                                          tags=(device_type,))
            
            # Store device info in our dictionary
            self.device_info_map[item] = device
            
        # Configure tag colors
        self.device_tree.tag_configure('android', foreground='#a4c639')
        self.device_tree.tag_configure('ios', foreground='#007aff')
        self.device_tree.tag_configure('local', foreground='#4fc3f7')
    
    def on_device_select(self, event):
        """handle device selection"""
        selection = self.device_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        device_name = self.device_tree.item(item, 'text')
        device_type = self.device_tree.item(item, 'values')[0]
        
        # Update info label
        info_text = f"Device: {device_name}\nType: {device_type}"
        self.device_info_label.config(text=info_text)
        
        self.selected_device = item
        self.update_capture_info()
    
    def update_capture_info(self):
        """update capture information text"""
        capture_type = self.capture_type.get()
        
        self.capture_info_text.config(state=tk.NORMAL)
        self.capture_info_text.delete('1.0', tk.END)
        
        if capture_type == 'ram':
            info = (
                "RAM CAPTURE\n"
                "Creates a complete memory dump of the device.\n\n"
                "Requirements:\n"
                "• Administrator/root access\n"
                "• RAM capture tool (winpmem, LiME, etc.)\n"
                "• Storage space = device RAM size\n\n"
                "Captures: Running processes, encryption keys, passwords, "
                "network connections, open files"
            )
        elif capture_type == 'disk':
            info = (
                "FORENSIC DISK IMAGE\n"
                "Creates a bit-for-bit copy of the entire disk.\n\n"
                "Requirements:\n"
                "• Administrator/root access\n"
                "• Imaging tool (dd, FTK Imager)\n"
                "• Storage space = disk size\n\n"
                "Captures: All files, deleted files, file slack, "
                "unallocated space, system areas"
            )
        else:  # logical
            info = (
                "LOGICAL BACKUP\n"
                "Copies accessible files and data (no deleted files).\n\n"
                "Requirements:\n"
                "• Device unlocked and authorized\n"
                "• USB debugging (Android) or Trust (iOS)\n"
                "• Storage space = used space\n\n"
                "Captures: User files, app data, media, "
                "contacts, messages (device-dependent)"
            )
        
        self.capture_info_text.insert('1.0', info)
        self.capture_info_text.config(state=tk.DISABLED)
    
    def browse_output(self):
        """browse for output directory"""
        directory = filedialog.askdirectory(
            title="Select output location",
            initialdir=self.output_path.get()
        )
        
        if directory:
            self.output_path.set(directory)
    
    def start_capture(self):
        """start the capture process"""
        if not self.selected_device:
            messagebox.showwarning("No Device", "Please select a device first")
            return
        
        capture_type = self.capture_type.get()
        output_dir = Path(self.output_path.get())
        
        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        device_name = self.device_tree.item(self.selected_device, 'text')
        safe_name = "".join(c for c in device_name if c.isalnum() or c in (' ', '-', '_'))
        
        if capture_type == 'ram':
            filename = f"{safe_name}_{timestamp}.mem"
        elif capture_type == 'disk':
            filename = f"{safe_name}_{timestamp}.dd"
        else:
            filename = f"{safe_name}_{timestamp}_backup"
        
        output_path = output_dir / filename
        
        # Confirm
        confirm = messagebox.askyesno(
            "Confirm Capture",
            f"Start {capture_type} capture?\n\n"
            f"Device: {device_name}\n"
            f"Output: {output_path}\n\n"
            f"This may take a long time and requires elevated privileges."
        )
        
        if not confirm:
            return
        
        # Store result and close
        self.result = {
            'capture_type': capture_type,
            'device': device_name,
            'output_path': str(output_path),
            'selected_device_item': self.selected_device
        }
        
        self.destroy()
    
    def on_cancel(self):
        """cancel dialog"""
        self.result = None
        self.destroy()
    
    def get_result(self):
        """return capture configuration"""
        self.wait_window()
        return self.result