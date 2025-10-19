"""
file_stuff.py - represents files and folders
NOW INCLUDES: Browser, Email, and Prefetch node types
ENHANCED: User/owner metadata and system file detection
"""

import hashlib
import platform
from pathlib import Path
from datetime import datetime


class FileNode:
    """represents a single file or directory"""
    
    def __init__(self, path, git_info=None):
        self.path = Path(path)
        self.id = self.make_id()
        self.name = self.path.name or str(path)
        self.is_folder = self.path.is_dir()
        self.is_hidden = self.check_hidden()
        self.is_deleted = False  # set by git analyzer
        self.git_info = git_info  # git metadata
        self.info = self.get_info()
        
        # position for drawing
        self.x = 0
        self.y = 0
        
        # what this connects to
        self.connections = {}
    
    def make_id(self):
        """create unique id from path"""
        return hashlib.md5(str(self.path.absolute()).encode()).hexdigest()[:12]
    
    def check_hidden(self):
        """check if file is hidden"""
        # files starting with . are hidden (unix style)
        if self.name.startswith('.'):
            return True
        
        # on windows, check hidden attribute
        try:
            import stat
            if self.path.stat().st_file_attributes & stat.FILE_ATTRIBUTE_HIDDEN:
                return True
        except:
            pass
        
        return False
    
    def get_info(self):
        """get file metadata with owner information"""
        try:
            stat_info = self.path.stat()
            info = {
                'size': stat_info.st_size,
                'modified': datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                'accessed': datetime.fromtimestamp(stat_info.st_atime).isoformat(),
                'created': datetime.fromtimestamp(stat_info.st_ctime).isoformat(),
                'extension': self.path.suffix.lower(),
                'full_path': str(self.path.absolute()),
                'is_hidden': self.is_hidden
            }
            
            # Add owner information (platform-specific)
            owner_name = self._get_owner_name(stat_info)
            info['owner_name'] = owner_name
            info['owner_uid'] = getattr(stat_info, 'st_uid', None)
            info['owner_gid'] = getattr(stat_info, 'st_gid', None)
            
            # Detect system vs user files
            info['is_system_file'] = self._is_system_file(owner_name)
            
            # add git info if available
            if self.git_info:
                info['git'] = self.git_info
                # Git provides additional user context
                if 'author' in self.git_info:
                    info['git_author'] = self.git_info['author']
            
            return info
        except Exception as e:
            return {
                'error': 'cannot read', 
                'is_hidden': self.is_hidden,
                'owner_name': 'unknown',
                'is_system_file': False
            }
    
    def _get_owner_name(self, stat_info):
        """Get file owner name (cross-platform)"""
        try:
            if platform.system() == 'Windows':
                # Windows owner lookup
                try:
                    import win32security
                    sd = win32security.GetFileSecurity(
                        str(self.path), 
                        win32security.OWNER_SECURITY_INFORMATION
                    )
                    owner_sid = sd.GetSecurityDescriptorOwner()
                    name, domain, type_num = win32security.LookupAccountSid(None, owner_sid)
                    return f"{domain}\\{name}" if domain else name
                except ImportError:
                    # Fallback if win32security not available
                    return "unknown"
                except:
                    return "unknown"
            else:
                # Unix/Linux/Mac owner lookup
                try:
                    import pwd
                    owner_info = pwd.getpwuid(stat_info.st_uid)
                    return owner_info.pw_name
                except ImportError:
                    return f"uid:{stat_info.st_uid}"
                except:
                    return "unknown"
        except:
            return "unknown"
    
    def _is_system_file(self, owner_name):
        """Detect if file is system-created vs user-created"""
        path_str = str(self.path).lower()
        
        # System directories (cross-platform)
        system_paths = [
            # Windows
            'windows', 'system32', 'program files', 'programdata',
            'appdata\\local\\temp', 'appdata\\roaming\\microsoft',
            # Unix/Linux
            '/usr/', '/var/', '/etc/', '/bin/', '/sbin/', '/lib/', '/sys/', '/proc/',
            '/boot/', '/dev/', '/tmp/', '/opt/',
            # Mac
            '/system/', '/library/application support/', '/private/',
            # Version control and temp
            '.git/', '.svn/', '.hg/', '__pycache__/', '.cache/', 
            'node_modules/', '.tmp/', 'temp/'
        ]
        
        for sys_path in system_paths:
            if sys_path in path_str:
                return True
        
        # System users/owners
        if owner_name and owner_name != 'unknown':
            owner_lower = owner_name.lower()
            system_users = [
                # Windows
                'system', 'administrator', 'nt authority', 'trustedinstaller',
                'network service', 'local service',
                # Unix/Linux
                'root', 'daemon', 'bin', 'sys', 'adm', 'nobody',
                # Mac
                '_system', '_installer'
            ]
            
            for sys_user in system_users:
                if sys_user in owner_lower:
                    return True
        
        return False


class DeletedFileNode:
    """represents a deleted file from git history"""
    
    def __init__(self, git_info, repo_path):
        self.path = Path(repo_path) / git_info['path']
        self.id = self.make_id()
        self.name = git_info['name']
        self.is_folder = False  # assume file for now
        self.is_hidden = False
        self.is_deleted = True
        self.git_info = git_info
        self.info = self.get_info()
        
        # position for drawing
        self.x = 0
        self.y = 0
        
        # connections
        self.connections = []
    
    def make_id(self):
        """create unique id"""
        return hashlib.md5(str(self.path.absolute()).encode()).hexdigest()[:12]
    
    def get_info(self):
        """get metadata for deleted file"""
        return {
            'size': 0,  # unknown
            'modified': self.git_info.get('deleted_date', 'unknown'),
            'extension': self.path.suffix.lower(),
            'full_path': str(self.path.absolute()),
            'is_hidden': False,
            'is_deleted': True,
            'deleted_by': self.git_info.get('deleted_by', 'unknown'),
            'deleted_commit': self.git_info.get('deleted_commit', 'unknown'),
            'commit_message': self.git_info.get('commit_message', 'unknown'),
            'git': self.git_info,
            'owner_name': self.git_info.get('deleted_by', 'unknown'),
            'is_system_file': False
        }


class ForensicFileNode:
    """represents a file or directory from a forensic image"""
    
    def __init__(self, entry_data, forensic_info, base_path=""):
        """
        entry_data: dict with file entry info from forensic scanner
        forensic_info: dict with recovery status from forensic analyzer
        base_path: base path for the image
        """
        self.entry_data = entry_data
        self.forensic_info = forensic_info
        
        # basic attributes
        self.name = entry_data.get('name', 'unknown')
        self.path = Path(base_path) / entry_data.get('path', self.name)
        self.id = self.make_id()
        self.is_folder = entry_data.get('is_directory', False)
        self.is_hidden = self.name.startswith('.')
        self.is_deleted = entry_data.get('is_deleted', False)
        
        # forensic-specific attributes
        self.recovery_status = forensic_info.get('recovery_status', 'unknown')
        self.recovery_level = forensic_info.get('recovery_level', 0)
        
        # build info dict
        self.info = self.get_info()
        
        # git info (not applicable for forensic)
        self.git_info = None
        
        # position for drawing
        self.x = 0
        self.y = 0
        
        # connections
        self.connections = []
    
    def make_id(self):
        """create unique id from path and inode"""
        inode = self.entry_data.get('inode', 0)
        unique_str = f"{self.path}_{inode}"
        return hashlib.md5(unique_str.encode()).hexdigest()[:12]
    
    def get_info(self):
        """get file metadata"""
        info = {
            'size': self.entry_data.get('size', 0),
            'modified': self.entry_data.get('modified', 'unknown'),
            'accessed': self.entry_data.get('accessed', 'unknown'),
            'created': self.entry_data.get('created', 'unknown'),
            'changed': self.entry_data.get('changed', 'unknown'),
            'extension': Path(self.name).suffix.lower(),
            'full_path': str(self.path),
            'is_hidden': self.is_hidden,
            'is_deleted': self.is_deleted,
            'inode': self.entry_data.get('inode', 0),
            'owner_name': 'forensic',
            'is_system_file': False
        }
        
        # add forensic-specific info
        if self.is_deleted:
            info['recovery_status'] = self.recovery_status
            info['recovery_level'] = self.recovery_level
            info['recovery_notes'] = self.forensic_info.get('notes', 'N/A')
            info['data_size'] = self.forensic_info.get('data_size', 0)
            info['link_count'] = self.forensic_info.get('link_count', 0)
        
        return info


class MemoryFileNode:
    """represents a file reference from memory dump"""
    
    def __init__(self, file_data, process_info=None, base_path="memory"):
        """
        file_data: dict with file info from memory analyzer
        process_info: dict with process that owns this file handle
        base_path: base identifier for memory analysis
        """
        self.file_data = file_data
        self.process_info = process_info
        
        # basic attributes
        file_name = file_data.get('name', 'unknown')
        self.name = Path(file_name).name if file_name != 'unknown' else 'unknown'
        self.path = Path(base_path) / file_name
        self.id = self.make_id()
        self.is_folder = self._detect_folder(file_name)
        self.is_hidden = self.name.startswith('.')
        self.is_deleted = False
        
        # memory-specific attributes
        self.memory_offset = file_data.get('offset', '0x0')
        self.access_mode = file_data.get('access', 'unknown')
        
        # build info dict
        self.info = self.get_info()
        
        # git info (not applicable)
        self.git_info = None
        
        # position for drawing
        self.x = 0
        self.y = 0
        
        # connections
        self.connections = []
    
    def make_id(self):
        """create unique id from offset and name"""
        unique_str = f"{self.memory_offset}_{self.file_data.get('name', 'unknown')}"
        return hashlib.md5(unique_str.encode()).hexdigest()[:12]
    
    def _detect_folder(self, file_name):
        """detect if this is a directory reference"""
        if file_name == 'unknown':
            return False
        # Common directory indicators
        if '\\Windows\\' in file_name or '\\Program Files\\' in file_name:
            if not Path(file_name).suffix:
                return True
        return False
    
    def get_info(self):
        """get file metadata"""
        info = {
            'size': self.file_data.get('size', 0),
            'modified': 'unknown',  # not available from memory
            'extension': Path(self.name).suffix.lower() if self.name != 'unknown' else '',
            'full_path': str(self.path),
            'is_hidden': self.is_hidden,
            'is_deleted': False,
            'source': 'memory_dump',
            'owner_name': 'memory',
            'is_system_file': True
        }
        
        # add memory-specific info
        info['memory_offset'] = self.memory_offset
        info['access_mode'] = self.access_mode
        
        # add process info if available
        if self.process_info:
            info['process_name'] = self.process_info.get('name', 'unknown')
            info['process_pid'] = self.process_info.get('pid', 0)
        
        return info


class MemoryProcessNode:
    """represents a process from memory dump"""
    
    def __init__(self, process_data, base_path="memory/processes"):
        """
        process_data: dict with process info from memory analyzer
        base_path: base identifier
        """
        self.process_data = process_data
        
        # basic attributes
        self.pid = process_data.get('pid', 0)
        self.ppid = process_data.get('ppid', 0)
        self.name = process_data.get('name', f'process_{self.pid}')
        self.path = Path(base_path) / self.name
        self.id = self.make_id()
        self.is_folder = False
        self.is_hidden = False
        self.is_deleted = False
        
        # process-specific attributes
        self.threads = process_data.get('threads', 0)
        self.handles = process_data.get('handles', 0)
        
        # build info dict
        self.info = self.get_info()
        
        # git info (not applicable)
        self.git_info = None
        
        # position for drawing
        self.x = 0
        self.y = 0
        
        # connections
        self.connections = []
    
    def make_id(self):
        """create unique id from pid and name"""
        unique_str = f"proc_{self.pid}_{self.name}"
        return hashlib.md5(unique_str.encode()).hexdigest()[:12]
    
    def get_info(self):
        """get process metadata"""
        info = {
            'size': 0,  # not applicable
            'modified': self.process_data.get('create_time', 'unknown'),
            'extension': '.exe',  # treat as executable
            'full_path': str(self.path),
            'is_hidden': False,
            'is_deleted': False,
            'source': 'memory_dump',
            'type': 'process',
            'owner_name': 'process',
            'is_system_file': True
        }
        
        # add process-specific info
        info['pid'] = self.pid
        info['ppid'] = self.ppid
        info['threads'] = self.threads
        info['handles'] = self.handles
        info['create_time'] = self.process_data.get('create_time', 'unknown')
        
        return info


class ISOFileNode:
    """represents a file or directory from an ISO image"""
    
    def __init__(self, entry_data, base_path="iso"):
        """
        entry_data: dict with file entry info from ISO analyzer
        base_path: base identifier for ISO
        """
        self.entry_data = entry_data
        
        # basic attributes
        self.name = entry_data.get('name', 'unknown')
        self.path = Path(base_path) / entry_data.get('path', self.name).lstrip('/')
        self.id = self.make_id()
        self.is_folder = entry_data.get('is_directory', False)
        self.is_hidden = self.name.startswith('.')
        self.is_deleted = False
        
        # build info dict
        self.info = self.get_info()
        
        # git info (not applicable)
        self.git_info = None
        
        # position for drawing
        self.x = 0
        self.y = 0
        
        # connections
        self.connections = []
    
    def make_id(self):
        """create unique id from path"""
        unique_str = f"iso_{self.entry_data.get('path', self.name)}"
        return hashlib.md5(unique_str.encode()).hexdigest()[:12]
    
    def get_info(self):
        """get file metadata"""
        info = {
            'size': self.entry_data.get('size', 0),
            'modified': self.entry_data.get('modified', 'unknown'),
            'extension': Path(self.name).suffix.lower() if not self.is_folder else '',
            'full_path': str(self.path),
            'is_hidden': self.is_hidden,
            'is_deleted': False,
            'source': 'iso_image',
            'owner_name': 'iso',
            'is_system_file': False
        }
        
        # add any error info
        if 'error' in self.entry_data:
            info['error'] = self.entry_data['error']
        
        return info


# ============================================================================
# Browser, Email, and Prefetch Node Types
# ============================================================================

class BrowserHistoryNode:
    """represents browser history entry"""
    
    def __init__(self, entry_data, base_path="browser"):
        self.entry_data = entry_data
        self.name = entry_data.get('title', 'Untitled')[:50]
        self.path = Path(base_path) / entry_data.get('browser', 'unknown') / 'history' / self.name
        self.id = hashlib.md5(
            f"{entry_data.get('url', '')}_{entry_data.get('visit_time', '')}".encode()
        ).hexdigest()[:12]
        self.is_folder = False
        self.is_hidden = False
        self.is_deleted = False
        self.info = self.get_info()
        self.git_info = None
        self.x = 0
        self.y = 0
        self.connections = []
    
    def get_info(self):
        return {
            'size': 0,
            'modified': str(self.entry_data.get('visit_time', 'unknown')),
            'extension': '.url',
            'full_path': str(self.path),
            'is_hidden': False,
            'is_deleted': False,
            'source': 'browser_history',
            'url': self.entry_data.get('url', ''),
            'visit_count': self.entry_data.get('visit_count', 0),
            'browser': self.entry_data.get('browser', 'unknown'),
            'owner_name': 'browser',
            'is_system_file': False
        }


class BrowserBookmarkNode:
    """represents browser bookmark"""
    
    def __init__(self, entry_data, base_path="browser"):
        self.entry_data = entry_data
        self.name = entry_data.get('title', 'Untitled')[:50]
        self.path = Path(base_path) / entry_data.get('browser', 'unknown') / 'bookmarks' / self.name
        self.id = hashlib.md5(
            f"{entry_data.get('url', '')}_{entry_data.get('date_added', '')}".encode()
        ).hexdigest()[:12]
        self.is_folder = False
        self.is_hidden = False
        self.is_deleted = False
        self.info = self.get_info()
        self.git_info = None
        self.x = 0
        self.y = 0
        self.connections = []
    
    def get_info(self):
        return {
            'size': 0,
            'modified': str(self.entry_data.get('date_added', 'unknown')),
            'extension': '.bookmark',
            'full_path': str(self.path),
            'is_hidden': False,
            'is_deleted': False,
            'source': 'browser_bookmarks',
            'url': self.entry_data.get('url', ''),
            'browser': self.entry_data.get('browser', 'unknown'),
            'owner_name': 'browser',
            'is_system_file': False
        }


class BrowserDownloadNode:
    """represents browser download"""
    
    def __init__(self, entry_data, base_path="browser"):
        self.entry_data = entry_data
        self.name = entry_data.get('target_path', 'unknown')
        if '\\' in self.name or '/' in self.name:
            self.name = Path(self.name).name
        self.path = Path(base_path) / entry_data.get('browser', 'unknown') / 'downloads' / self.name
        self.id = hashlib.md5(
            f"{entry_data.get('url', '')}_{entry_data.get('start_time', '')}".encode()
        ).hexdigest()[:12]
        self.is_folder = False
        self.is_hidden = False
        self.is_deleted = False
        self.info = self.get_info()
        self.git_info = None
        self.x = 0
        self.y = 0
        self.connections = []
    
    def get_info(self):
        return {
            'size': self.entry_data.get('total_bytes', 0),
            'modified': str(self.entry_data.get('start_time', 'unknown')),
            'extension': Path(self.name).suffix.lower(),
            'full_path': str(self.path),
            'is_hidden': False,
            'is_deleted': False,
            'source': 'browser_downloads',
            'url': self.entry_data.get('url', ''),
            'browser': self.entry_data.get('browser', 'unknown'),
            'owner_name': 'browser',
            'is_system_file': False
        }


class EmailMessageNode:
    """represents email message"""
    
    def __init__(self, entry_data, base_path="email"):
        self.entry_data = entry_data
        self.name = entry_data.get('subject', 'No Subject')[:50]
        self.path = Path(base_path) / entry_data.get('folder', 'inbox') / self.name
        self.id = hashlib.md5(
            f"{entry_data.get('message_id', '')}_{entry_data.get('date', '')}".encode()
        ).hexdigest()[:12]
        self.is_folder = False
        self.is_hidden = False
        self.is_deleted = False
        self.info = self.get_info()
        self.git_info = None
        self.x = 0
        self.y = 0
        self.connections = []
    
    def get_info(self):
        return {
            'size': self.entry_data.get('size', 0),
            'modified': str(self.entry_data.get('date', 'unknown')),
            'extension': '.eml',
            'full_path': str(self.path),
            'is_hidden': False,
            'is_deleted': False,
            'source': 'email',
            'from': self.entry_data.get('from', 'unknown'),
            'to': self.entry_data.get('to', 'unknown'),
            'has_attachments': self.entry_data.get('has_attachments', False),
            'owner_name': self.entry_data.get('from', 'unknown'),
            'is_system_file': False
        }


class EmailAttachmentNode:
    """represents email attachment"""
    
    def __init__(self, entry_data, base_path="email/attachments"):
        self.entry_data = entry_data
        self.name = entry_data.get('filename', 'attachment')
        self.path = Path(base_path) / self.name
        self.id = hashlib.md5(
            f"{entry_data.get('message_id', '')}_{self.name}".encode()
        ).hexdigest()[:12]
        self.is_folder = False
        self.is_hidden = False
        self.is_deleted = False
        self.info = self.get_info()
        self.git_info = None
        self.x = 0
        self.y = 0
        self.connections = []
    
    def get_info(self):
        return {
            'size': self.entry_data.get('size', 0),
            'modified': str(self.entry_data.get('date', 'unknown')),
            'extension': Path(self.name).suffix.lower(),
            'full_path': str(self.path),
            'is_hidden': False,
            'is_deleted': False,
            'source': 'email_attachment',
            'message_subject': self.entry_data.get('message_subject', 'unknown'),
            'owner_name': 'email',
            'is_system_file': False
        }


class PrefetchProgramNode:
    """represents program from prefetch analysis"""
    
    def __init__(self, entry_data, base_path="prefetch"):
        self.entry_data = entry_data
        self.name = entry_data.get('executable', 'unknown')
        self.path = Path(base_path) / self.name
        self.id = hashlib.md5(
            f"{self.name}_{entry_data.get('hash', '')}".encode()
        ).hexdigest()[:12]
        self.is_folder = False
        self.is_hidden = False
        self.is_deleted = False
        self.info = self.get_info()
        self.git_info = None
        self.x = 0
        self.y = 0
        self.connections = []
    
    def get_info(self):
        return {
            'size': 0,
            'modified': str(self.entry_data.get('last_run', 'unknown')),
            'extension': '.exe',
            'full_path': str(self.path),
            'is_hidden': False,
            'is_deleted': False,
            'source': 'prefetch',
            'run_count': self.entry_data.get('run_count', 0),
            'last_run': self.entry_data.get('last_run', 'unknown'),
            'owner_name': 'prefetch',
            'is_system_file': True
        }