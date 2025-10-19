"""
file_preview.py - file content preview widget
supports text, code, images, PDFs, and binary files

REFACTORED: Now uses error_handler, dependency_manager, and progress_manager
"""

import tkinter as tk
from tkinter import scrolledtext
from pathlib import Path
from PIL import Image, ImageTk
import io
from ui.font_config import get_font, get_code_font

# Import centralized management modules
from core.error_handler import (
    FileSystemError,
    safe_file_read,
    logger
)
from core.dependency_manager import is_available


class FilePreview(tk.Frame):
    """Widget for previewing file contents"""
    
    # Supported text extensions
    TEXT_EXTENSIONS = {
        '.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.xml',
        '.yaml', '.yml', '.ini', '.cfg', '.conf', '.sh', '.bat', '.ps1',
        '.c', '.cpp', '.h', '.hpp', '.java', '.cs', '.go', '.rs', '.rb',
        '.php', '.swift', '.kt', '.sql', '.r', '.m', '.scala', '.pl',
        '.lua', '.vim', '.el', '.clj', '.erl', '.ex', '.exs', '.hs',
        '.log', '.csv', '.tsv', '.gitignore', '.dockerignore', '.env'
    }
    
    # Image extensions
    IMAGE_EXTENSIONS = {
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.webp', '.tiff', '.tif'
    }
    
    # Code syntax colors (simple highlighting)
    SYNTAX_COLORS = {
        'keyword': '#569cd6',    # Blue
        'string': '#ce9178',     # Orange
        'comment': '#6a9955',    # Green
        'number': '#b5cea8',     # Light green
        'function': '#dcdcaa',   # Yellow
    }
    
    def __init__(self, parent):
        super().__init__(parent, bg='#1e1e1e')
        
        self.current_node = None
        self.current_image = None  # Keep reference to prevent garbage collection
        
        self.setup_ui()
        
        logger.debug("FilePreview widget initialized")
    
    def setup_ui(self):
        """Create preview UI"""
        # Header with file type indicator
        header = tk.Frame(self, bg='#2d2d30', height=30)
        header.pack(side=tk.TOP, fill=tk.X)
        header.pack_propagate(False)
        
        tk.Label(header, text="File Preview", 
                font=get_font('small', bold=True),
                bg='#2d2d30', fg='#9cdcfe').pack(side=tk.LEFT, padx=10)
        
        self.type_label = tk.Label(header, text="", 
                                   font=get_font('tiny'),
                                   bg='#2d2d30', fg='#666666')
        self.type_label.pack(side=tk.RIGHT, padx=10)
        
        # Preview area (will contain different widgets based on file type)
        self.preview_area = tk.Frame(self, bg='#1e1e1e')
        self.preview_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Default message
        self.show_message("No file selected\n\nDouble-click a file to preview")
    
    def preview_file(self, node):
        """
        Preview a file node
        
        Args:
            node: FileNode object to preview
        """
        self.current_node = node
        
        # Clear previous preview
        for widget in self.preview_area.winfo_children():
            widget.destroy()
        
        if node.is_folder:
            self.show_message("📁 Folder\n\nCannot preview directories")
            self.type_label.config(text="Directory")
            return
        
        # Check if file is accessible
        if not hasattr(node, 'path') or not node.path.exists():
            # Forensic/deleted file
            if hasattr(node, 'is_deleted') and node.is_deleted:
                self.show_message("🗑️ Deleted File\n\nFile has been deleted\nRecovery may be possible")
                self.type_label.config(text="Deleted")
            else:
                self.show_message("⚠️ Inaccessible\n\nFile cannot be accessed")
                self.type_label.config(text="Inaccessible")
            return
        
        extension = node.info.get('extension', '').lower()
        file_size = node.info.get('size', 0)
        
        # Check file size (don't preview huge files)
        if file_size > 10 * 1024 * 1024:  # 10MB limit
            self.show_message(
                f"📄 Large File\n\n{self.format_size(file_size)}\n\n"
                "File too large to preview"
            )
            self.type_label.config(text=f"Large {extension}")
            logger.info(f"Skipped preview of large file: {node.path} ({file_size} bytes)")
            return
        
        # Determine preview type
        try:
            if extension in self.IMAGE_EXTENSIONS:
                self.preview_image(node)
            elif extension in self.TEXT_EXTENSIONS or extension == '':
                self.preview_text(node)
            elif extension == '.pdf':
                self.preview_pdf(node)
            else:
                self.preview_binary(node)
        
        except Exception as e:
            logger.error(f"Error previewing file {node.path}: {e}")
            self.show_message(f"⚠️ Preview Error\n\n{str(e)}")
            self.type_label.config(text="Error")
    
    def preview_text(self, node):
        """Preview text/code file"""
        try:
            logger.debug(f"Previewing text file: {node.path}")
            
            # Use safe_file_read with size limit
            content = safe_file_read(node.path, max_size=100000, encoding='utf-8')
            
            if content is None:
                raise FileSystemError("Failed to read file")
            
            # Create text widget with scrollbar
            text_frame = tk.Frame(self.preview_area, bg='#1e1e1e')
            text_frame.pack(fill=tk.BOTH, expand=True)
            
            text_widget = tk.Text(text_frame, 
                                 bg='#1e1e1e', fg='#d4d4d4',
                                 font=get_code_font('code'),
                                 wrap=tk.NONE,
                                 insertbackground='#d4d4d4')
            
            # Scrollbars
            v_scroll = tk.Scrollbar(text_frame, orient='vertical', command=text_widget.yview)
            h_scroll = tk.Scrollbar(text_frame, orient='horizontal', command=text_widget.xview)
            
            text_widget.config(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
            
            v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
            h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
            text_widget.pack(fill=tk.BOTH, expand=True)
            
            # Insert content
            text_widget.insert('1.0', content)
            
            # Apply simple syntax highlighting for code files
            extension = node.info.get('extension', '').lower()
            if extension in {'.py', '.js', '.java', '.c', '.cpp', '.cs', '.go', '.rs'}:
                self.apply_syntax_highlighting(text_widget, extension)
            
            text_widget.config(state=tk.DISABLED)
            
            # Update type label
            lines = content.count('\n') + 1
            size = len(content.encode('utf-8'))
            self.type_label.config(text=f"Text • {lines} lines • {self.format_size(size)}")
            
            logger.debug(f"Text preview loaded: {lines} lines")
        
        except FileSystemError as e:
            logger.error(f"Failed to read text file: {e}")
            self.show_message(f"⚠️ Read Error\n\n{e.get_user_message()}")
            self.type_label.config(text="Text Error")
        
        except Exception as e:
            logger.error(f"Text preview error: {e}")
            self.show_message(f"⚠️ Error\n\nCannot preview text:\n{str(e)}")
            self.type_label.config(text="Text Error")
    
    def preview_image(self, node):
        """Preview image file"""
        try:
            logger.debug(f"Previewing image: {node.path}")
            
            img = Image.open(node.path)
            
            # Get original dimensions
            orig_width, orig_height = img.size
            
            # Scale to fit
            max_width = 600
            max_height = 500
            
            ratio = min(max_width / img.width, max_height / img.height, 1.0)
            new_width = int(img.width * ratio)
            new_height = int(img.height * ratio)
            
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            photo = ImageTk.PhotoImage(img)
            self.current_image = photo  # Keep reference
            
            img_label = tk.Label(self.preview_area, image=photo, bg='#1e1e1e')
            img_label.pack(expand=True)
            
            extension = node.info.get('extension', 'image')
            self.type_label.config(text=f"Image • {orig_width}x{orig_height} • {extension}")
            
            logger.debug(f"Image preview loaded: {orig_width}x{orig_height}")
        
        except Exception as e:
            logger.error(f"Image preview error: {e}")
            self.show_message(f"🖼️ Image File\n\nCannot preview:\n{str(e)}")
            self.type_label.config(text="Image Error")
    
    def preview_pdf(self, node):
        """Preview PDF file"""
        try:
            logger.debug(f"Previewing PDF: {node.path}")
            
            # Check if pdf2image is available
            if not is_available('pdf2image'):
                self.show_message(
                    "📄 PDF File\n\n"
                    "PDF preview requires pdf2image\n\n"
                    "Install with:\n"
                    "pip install pdf2image"
                )
                self.type_label.config(text="PDF (no preview)")
                logger.info("PDF preview unavailable - pdf2image not installed")
                return
            
            # Import pdf2image
            from pdf2image import convert_from_path
            
            # Convert first page to image
            images = convert_from_path(str(node.path), first_page=1, last_page=1)
            
            if images:
                img = images[0]
                
                # Scale to fit
                max_width = 600
                max_height = 500
                
                ratio = min(max_width / img.width, max_height / img.height, 1.0)
                new_width = int(img.width * ratio)
                new_height = int(img.height * ratio)
                
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                photo = ImageTk.PhotoImage(img)
                self.current_image = photo
                
                img_label = tk.Label(self.preview_area, image=photo, bg='#1e1e1e')
                img_label.pack(expand=True)
                
                self.type_label.config(text="PDF • Page 1")
                logger.debug("PDF preview loaded (first page)")
            else:
                raise Exception("No pages in PDF")
        
        except ImportError:
            self.show_message(
                "📄 PDF File\n\n"
                "PDF preview requires pdf2image\n\n"
                "Install with:\n"
                "pip install pdf2image"
            )
            self.type_label.config(text="PDF (no preview)")
            logger.info("PDF preview unavailable - pdf2image import failed")
        
        except Exception as e:
            logger.error(f"PDF preview error: {e}")
            self.show_message(f"📄 PDF File\n\nCannot preview:\n{str(e)}")
            self.type_label.config(text="PDF Error")
    
    def preview_binary(self, node):
        """Preview binary file (hex dump)"""
        try:
            logger.debug(f"Previewing binary file: {node.path}")
            
            # Use safe_file_read for binary
            data = safe_file_read(node.path, max_size=4096, encoding=None)
            
            if data is None:
                raise FileSystemError("Failed to read file")
            
            # Create hex dump
            hex_lines = []
            for i in range(0, len(data), 16):
                chunk = data[i:i+16]
                
                # Hex representation
                hex_str = ' '.join(f'{b:02x}' for b in chunk)
                
                # ASCII representation
                ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
                
                hex_lines.append(f"{i:08x}  {hex_str:<48}  {ascii_str}")
            
            # Create text widget
            text_frame = tk.Frame(self.preview_area, bg='#1e1e1e')
            text_frame.pack(fill=tk.BOTH, expand=True)
            
            text_widget = tk.Text(text_frame, 
                                 bg='#1e1e1e', fg='#d4d4d4',
                                 font=get_code_font('code'),
                                 wrap=tk.NONE)
            
            v_scroll = tk.Scrollbar(text_frame, orient='vertical', command=text_widget.yview)
            text_widget.config(yscrollcommand=v_scroll.set)
            
            v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
            text_widget.pack(fill=tk.BOTH, expand=True)
            
            text_widget.insert('1.0', '\n'.join(hex_lines))
            text_widget.config(state=tk.DISABLED)
            
            extension = node.info.get('extension', 'unknown')
            self.type_label.config(text=f"Binary • {extension}")
            
            logger.debug(f"Binary preview loaded: {len(data)} bytes")
        
        except FileSystemError as e:
            logger.error(f"Failed to read binary file: {e}")
            self.show_message(f"⚠️ Read Error\n\n{e.get_user_message()}")
            self.type_label.config(text="Binary Error")
        
        except Exception as e:
            logger.error(f"Binary preview error: {e}")
            self.show_message(f"⚠️ Error\n\nCannot preview binary:\n{str(e)}")
            self.type_label.config(text="Binary Error")
    
    def apply_syntax_highlighting(self, text_widget, extension):
        """Apply simple syntax highlighting"""
        # Define keywords for different languages
        keywords = {
            '.py': ['def', 'class', 'import', 'from', 'if', 'else', 'elif', 'for', 'while', 
                   'return', 'try', 'except', 'finally', 'with', 'as', 'pass', 'break',
                   'continue', 'yield', 'lambda', 'True', 'False', 'None', 'and', 'or', 'not'],
            '.js': ['function', 'var', 'let', 'const', 'if', 'else', 'for', 'while', 'return',
                   'class', 'import', 'export', 'async', 'await', 'try', 'catch', 'finally'],
            '.java': ['public', 'private', 'protected', 'class', 'interface', 'extends',
                     'implements', 'if', 'else', 'for', 'while', 'return', 'try', 'catch'],
            '.c': ['int', 'char', 'float', 'double', 'void', 'if', 'else', 'for', 'while',
                  'return', 'struct', 'typedef', 'include', 'define'],
            '.cpp': ['int', 'char', 'float', 'double', 'void', 'if', 'else', 'for', 'while',
                    'return', 'class', 'public', 'private', 'protected', 'namespace'],
        }
        
        lang_keywords = keywords.get(extension, [])
        
        # Configure tags
        text_widget.tag_config('keyword', foreground=self.SYNTAX_COLORS['keyword'])
        text_widget.tag_config('string', foreground=self.SYNTAX_COLORS['string'])
        text_widget.tag_config('comment', foreground=self.SYNTAX_COLORS['comment'])
        
        # Highlight keywords
        for keyword in lang_keywords:
            start = '1.0'
            while True:
                pos = text_widget.search(r'\m' + keyword + r'\M', start, stopindex='end', regexp=True)
                if not pos:
                    break
                end = f"{pos}+{len(keyword)}c"
                text_widget.tag_add('keyword', pos, end)
                start = end
        
        # Highlight strings
        for quote in ['"', "'"]:
            start = '1.0'
            while True:
                pos = text_widget.search(quote, start, stopindex='end')
                if not pos:
                    break
                # Find closing quote
                end_pos = text_widget.search(quote, f"{pos}+1c", stopindex='end')
                if end_pos:
                    text_widget.tag_add('string', pos, f"{end_pos}+1c")
                    start = f"{end_pos}+1c"
                else:
                    break
        
        # Highlight comments
        if extension == '.py':
            comment_char = '#'
        elif extension in ['.js', '.java', '.c', '.cpp', '.cs', '.go', '.rs']:
            comment_char = '//'
        else:
            return
        
        start = '1.0'
        while True:
            pos = text_widget.search(comment_char, start, stopindex='end')
            if not pos:
                break
            line_end = text_widget.index(f"{pos} lineend")
            text_widget.tag_add('comment', pos, line_end)
            start = f"{pos}+1l"
    
    def show_message(self, message):
        """Show a message in preview area"""
        label = tk.Label(self.preview_area, 
                        text=message,
                        bg='#1e1e1e', fg='#666666',
                        font=get_font('text'),
                        justify=tk.CENTER)
        label.pack(expand=True)
    
    def format_size(self, bytes_size):
        """Format bytes to readable size"""
        if bytes_size == 0:
            return '0 B'
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        i = 0
        size = float(bytes_size)
        while size >= 1024 and i < len(units)-1:
            size /= 1024
            i += 1
        return f"{size:.2f} {units[i]}"