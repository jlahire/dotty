"""
case_manager.py - manages forensic case information
"""

import json
from datetime import datetime
from pathlib import Path


class CaseInfo:
    """stores forensic case information"""
    
    def __init__(self, case_name="", examiner="", case_number="", 
                 description="", notes=""):
        self.case_name = case_name
        self.examiner = examiner
        self.case_number = case_number
        self.description = description
        self.notes = notes
        self.created_date = datetime.now().isoformat()
        self.image_path = None
        self.image_type = None
        self.filesystem_type = None
        self.image_size = None
        self.analysis_stats = {}
    
    def to_dict(self):
        """convert to dictionary"""
        return {
            'case_name': self.case_name,
            'examiner': self.examiner,
            'case_number': self.case_number,
            'description': self.description,
            'notes': self.notes,
            'created_date': self.created_date,
            'image_path': str(self.image_path) if self.image_path else None,
            'image_type': self.image_type,
            'filesystem_type': self.filesystem_type,
            'image_size': self.image_size,
            'analysis_stats': self.analysis_stats
        }
    
    def from_dict(self, data):
        """load from dictionary"""
        self.case_name = data.get('case_name', '')
        self.examiner = data.get('examiner', '')
        self.case_number = data.get('case_number', '')
        self.description = data.get('description', '')
        self.notes = data.get('notes', '')
        self.created_date = data.get('created_date', '')
        self.image_path = data.get('image_path')
        self.image_type = data.get('image_type')
        self.filesystem_type = data.get('filesystem_type')
        self.image_size = data.get('image_size')
        self.analysis_stats = data.get('analysis_stats', {})
    
    def save_to_file(self, filepath):
        """save case info to JSON file"""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    def load_from_file(self, filepath):
        """load case info from JSON file"""
        with open(filepath, 'r') as f:
            data = json.load(f)
            self.from_dict(data)
    
    def get_summary(self):
        """get summary text for display"""
        lines = []
        lines.append(f"Case: {self.case_name}")
        if self.case_number:
            lines.append(f"Case #: {self.case_number}")
        lines.append(f"Examiner: {self.examiner}")
        lines.append(f"Date: {self.created_date[:10]}")
        
        if self.image_path:
            lines.append(f"\nImage: {Path(self.image_path).name}")
            if self.image_type:
                lines.append(f"Format: {self.image_type}")
            if self.filesystem_type:
                lines.append(f"Filesystem: {self.filesystem_type}")
            if self.image_size:
                lines.append(f"Size: {self._format_size(self.image_size)}")
        
        if self.analysis_stats:
            lines.append(f"\nAnalysis Results:")
            stats = self.analysis_stats
            lines.append(f"  Total Entries: {stats.get('total_entries', 0)}")
            lines.append(f"  Active Files: {stats.get('active_files', 0)}")
            lines.append(f"  Deleted Files: {stats.get('deleted_files', 0)}")
            lines.append(f"  Recoverable: {stats.get('recoverable', 0)}")
            lines.append(f"  Partial: {stats.get('partial', 0)}")
            lines.append(f"  Unrecoverable: {stats.get('unrecoverable', 0)}")
        
        return "\n".join(lines)
    
    def _format_size(self, bytes):
        """format bytes to readable size"""
        if bytes == 0:
            return '0 B'
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        i = 0
        while bytes >= 1024 and i < len(units)-1:
            bytes /= 1024
            i += 1
        return f"{bytes:.2f} {units[i]}"