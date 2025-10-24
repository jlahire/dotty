"""
case_dialog.py - popup dialog for collecting case information
IMPROVED: Better window resizing, scrollable content, smaller minimum size
"""

import tkinter as tk
from tkinter import scrolledtext
from models.case_manager import CaseInfo
from font_config import get_font


class CaseDialog(tk.Toplevel):
    """dialog for entering case information"""
    
    def __init__(self, parent):
        super().__init__(parent)
        
        self.title("forensic case information")
        self.geometry("500x550")
        self.configure(bg='#252526')
        self.resizable(True, True)
        
        # Set minimum size to ensure buttons are visible - reduced for smaller screens
        self.minsize(350, 400)
        
        # center on parent
        self.transient(parent)
        self.grab_set()
        
        # result
        self.case_info = None
        self.result = False
        
        self.setup_ui()
        
        # center window
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 250
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 275
        self.geometry(f"+{x}+{y}")
    
    def setup_ui(self):
        """create dialog UI with scrollable content"""
        # title - keep at top, not scrollable
        title = tk.Label(self, text="forensic case details",
                        font=get_font('title', bold=True),
                        bg='#252526', fg='#4fc3f7')
        title.pack(pady=15)
        
        # subtitle
        subtitle = tk.Label(self, text="enter information about this forensic analysis",
                           font=get_font('text'),
                           bg='#252526', fg='#9cdcfe')
        subtitle.pack(pady=5)
        
        # Create a canvas with scrollbar for the form content
        canvas_frame = tk.Frame(self, bg='#252526')
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        canvas = tk.Canvas(canvas_frame, bg='#252526', highlightthickness=0)
        scrollbar = tk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#252526')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Enable mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # form frame inside scrollable area
        form = tk.Frame(scrollable_frame, bg='#252526')
        form.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # case name (required)
        self.add_field(form, "case name*:", 0)
        self.case_name_entry = tk.Entry(form, bg='#3c3c3c', fg='#d4d4d4',
                                        font=get_font('text'), insertbackground='#d4d4d4')
        self.case_name_entry.grid(row=1, column=0, sticky='ew', pady=(0, 15))
        self.case_name_entry.focus()
        
        # examiner name (required)
        self.add_field(form, "examiner name*:", 2)
        self.examiner_entry = tk.Entry(form, bg='#3c3c3c', fg='#d4d4d4',
                                       font=get_font('text'), insertbackground='#d4d4d4')
        self.examiner_entry.grid(row=3, column=0, sticky='ew', pady=(0, 15))
        
        # case number (optional)
        self.add_field(form, "case number:", 4)
        self.case_number_entry = tk.Entry(form, bg='#3c3c3c', fg='#d4d4d4',
                                          font=get_font('text'), insertbackground='#d4d4d4')
        self.case_number_entry.grid(row=5, column=0, sticky='ew', pady=(0, 15))
        
        # description (optional) - reduced height
        self.add_field(form, "description:", 6)
        self.description_text = tk.Text(form, bg='#3c3c3c', fg='#d4d4d4',
                                       font=get_font('text'), height=3,
                                       insertbackground='#d4d4d4')
        self.description_text.grid(row=7, column=0, sticky='ew', pady=(0, 15))
        
        # notes (optional) - reduced height
        self.add_field(form, "notes:", 8)
        self.notes_text = tk.Text(form, bg='#3c3c3c', fg='#d4d4d4',
                                 font=get_font('text'), height=3,
                                 insertbackground='#d4d4d4')
        self.notes_text.grid(row=9, column=0, sticky='ew', pady=(0, 15))
        
        form.columnconfigure(0, weight=1)
        
        # required note - keep at bottom, not scrollable
        required = tk.Label(self, text="* required fields",
                           font=get_font('small', italic=True),
                           bg='#252526', fg='#666666')
        required.pack(pady=5)
        
        # buttons - keep at bottom, not scrollable
        btn_frame = tk.Frame(self, bg='#252526')
        btn_frame.pack(pady=15)
        
        tk.Button(btn_frame, text="continue", bg='#4fc3f7', fg='#1e1e1e',
                 font=get_font('button', bold=True), width=12,
                 command=self.on_continue).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="cancel", bg='#37373d', fg='#d4d4d4',
                 font=get_font('button'), width=12,
                 command=self.on_cancel).pack(side=tk.LEFT, padx=5)
        
        # bind enter key
        self.bind('<Return>', lambda e: self.on_continue())
        self.bind('<Escape>', lambda e: self.on_cancel())
    
    def add_field(self, parent, label_text, row):
        """add a field label"""
        label = tk.Label(parent, text=label_text,
                        font=get_font('label', bold=True),
                        bg='#252526', fg='#9cdcfe',
                        anchor='w')
        label.grid(row=row, column=0, sticky='w', pady=(0, 5))
    
    def on_continue(self):
        """validate and save case info"""
        case_name = self.case_name_entry.get().strip()
        examiner = self.examiner_entry.get().strip()
        
        # validate required fields
        if not case_name:
            self.show_error("case name is required")
            self.case_name_entry.focus()
            return
        
        if not examiner:
            self.show_error("examiner name is required")
            self.examiner_entry.focus()
            return
        
        # create case info
        self.case_info = CaseInfo(
            case_name=case_name,
            examiner=examiner,
            case_number=self.case_number_entry.get().strip(),
            description=self.description_text.get('1.0', tk.END).strip(),
            notes=self.notes_text.get('1.0', tk.END).strip()
        )
        
        self.result = True
        self.destroy()
    
    def on_cancel(self):
        """cancel dialog"""
        self.result = False
        self.destroy()
    
    def show_error(self, message):
        """show error message"""
        error = tk.Label(self, text=f"⚠ {message}",
                        font=get_font('label', bold=True),
                        bg='#252526', fg='#ff4500')
        error.pack()
        self.after(3000, error.destroy)
    
    def get_result(self):
        """return case info if dialog was successful"""
        self.wait_window()
        return self.case_info if self.result else None