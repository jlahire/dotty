"""
forensic_analyzer.py - analyzes deleted files and recovery status
determines recoverability based on filesystem metadata
"""

import pytsk3


class ForensicAnalyzer:
    """analyzes forensic entries for recovery status"""
    
    def __init__(self, filesystem_type):
        self.filesystem_type = filesystem_type
    
    def analyze_entry(self, entry_data):
        """analyze a file entry and determine recovery status"""
        if not entry_data.get('is_deleted'):
            return {
                'is_deleted': False,
                'recovery_status': 'active',
                'recovery_level': 100,
                'notes': 'File is active'
            }
        
        # deleted file analysis
        entry = entry_data.get('entry')
        if not entry or not entry.info.meta:
            return {
                'is_deleted': True,
                'recovery_status': 'unrecoverable',
                'recovery_level': 0,
                'notes': 'No metadata available'
            }
        
        meta = entry.info.meta
        
        # check if file data is allocated
        has_data = self._check_data_availability(entry)
        
        # determine recovery status
        if has_data:
            if meta.size > 0:
                recovery_status = 'recoverable'
                recovery_level = 90
                notes = 'File data appears intact'
            else:
                recovery_status = 'partial'
                recovery_level = 50
                notes = 'Zero-length file or metadata only'
        else:
            recovery_status = 'unrecoverable'
            recovery_level = 10
            notes = 'File data overwritten or unavailable'
        
        # NTFS-specific analysis
        if self.filesystem_type == 'NTFS':
            ntfs_info = self._analyze_ntfs_entry(entry, meta)
            if ntfs_info:
                notes += f" | {ntfs_info}"
        
        return {
            'is_deleted': True,
            'recovery_status': recovery_status,
            'recovery_level': recovery_level,
            'notes': notes,
            'inode': meta.addr,
            'link_count': meta.nlink if hasattr(meta, 'nlink') else 0,
            'data_size': meta.size
        }
    
    def _check_data_availability(self, entry):
        """check if file data is still available"""
        try:
            if not entry.info.meta:
                return False
            
            # try to read first block
            test_data = entry.read_random(0, 512)
            if test_data and len(test_data) > 0:
                # check if it's all zeros (overwritten)
                if test_data == b'\x00' * len(test_data):
                    return False
                return True
            
        except:
            pass
        
        return False
    
    def _analyze_ntfs_entry(self, entry, meta):
        """NTFS-specific analysis"""
        notes = []
        
        # check MFT flags
        if hasattr(meta, 'flags'):
            if meta.flags & pytsk3.TSK_FS_META_FLAG_ALLOC:
                notes.append("MFT entry allocated")
            else:
                notes.append("MFT entry deallocated")
        
        # check for resident vs non-resident data
        try:
            # if file is small, it might be resident in MFT
            if meta.size < 1024:
                notes.append("Possibly resident in MFT")
        except:
            pass
        
        return " | ".join(notes) if notes else None
    
    def calculate_overall_recovery(self, entries):
        """calculate overall recovery statistics"""
        total = len(entries)
        deleted = sum(1 for e in entries if e.get('is_deleted'))
        recoverable = sum(1 for e in entries 
                         if e.get('is_deleted') and 
                         e.get('recovery_status') == 'recoverable')
        partial = sum(1 for e in entries 
                     if e.get('is_deleted') and 
                     e.get('recovery_status') == 'partial')
        unrecoverable = sum(1 for e in entries 
                           if e.get('is_deleted') and 
                           e.get('recovery_status') == 'unrecoverable')
        
        return {
            'total_entries': total,
            'active_files': total - deleted,
            'deleted_files': deleted,
            'recoverable': recoverable,
            'partial': partial,
            'unrecoverable': unrecoverable
        }