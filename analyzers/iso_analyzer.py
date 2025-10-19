"""
iso_analyzer.py - analyzes ISO 9660 filesystem images
supports ISO files without needing to mount them

REFACTORED: Now uses error_handler, dependency_manager, and progress_manager
"""

import struct
from pathlib import Path
from datetime import datetime

# Import centralized management modules
from core.error_handler import (
    ISOImageError,
    DependencyError,
    FileSystemError,
    handle_filesystem_errors,
    log_error_report,
    logger
)
from core.dependency_manager import is_available, check_feature
from core.progress_manager import ProgressTracker


# Check for pycdlib availability using dependency manager
if is_available('pycdlib'):
    try:
        import pycdlib
        logger.info("✓ pycdlib library available - ISO support enabled")
    except ImportError as e:
        logger.warning(f"pycdlib import failed despite being marked available: {e}")
else:
    logger.info("✗ pycdlib library not available - ISO support disabled")
    logger.info("  Install with: pip install pycdlib")


class ISOAnalyzer:
    """Analyzes ISO 9660 image files"""
    
    def __init__(self, iso_path):
        """
        Initialize ISO analyzer
        
        Args:
            iso_path: Path to ISO file
        
        Raises:
            FileSystemError: If ISO file doesn't exist
        """
        self.iso_path = Path(iso_path)
        self.iso = None
        self.volume_id = None
        self.files = []
        self.total_size = 0
        
        # Validate ISO file exists
        if not self.iso_path.exists():
            raise FileSystemError(
                f"ISO file does not exist: {self.iso_path}",
                {'path': str(self.iso_path)}
            )
        
        logger.info(f"ISOAnalyzer initialized for: {self.iso_path}")
    
    def open_iso(self):
        """
        Open the ISO file
        
        Returns:
            bool: True if successful
        
        Raises:
            DependencyError: If pycdlib is not available
            ISOImageError: If ISO cannot be opened
        """
        # Check pycdlib availability
        if not is_available('pycdlib'):
            raise DependencyError(
                'pycdlib',
                'pip install pycdlib',
                "ISO image analysis requires pycdlib"
            )
        
        try:
            logger.info(f"Opening ISO file: {self.iso_path}")
            
            self.iso = pycdlib.PyCdlib()
            self.iso.open(str(self.iso_path))
            
            # Get volume identifier
            try:
                self.volume_id = self.iso.pvd.volume_identifier.decode('utf-8').strip()
                if not self.volume_id:
                    self.volume_id = "ISO_IMAGE"
            except Exception as e:
                logger.debug(f"Could not read volume identifier: {e}")
                self.volume_id = "ISO_IMAGE"
            
            logger.info(f"✓ ISO opened successfully")
            logger.info(f"✓ Volume ID: {self.volume_id}")
            
            return True
        
        except AttributeError as e:
            logger.error(f"Invalid ISO format: {e}")
            raise ISOImageError(
                "Invalid ISO format or corrupted file",
                {'path': str(self.iso_path), 'error': str(e)}
            )
        
        except Exception as e:
            logger.error(f"Error opening ISO: {e}")
            log_error_report(e, context={'iso_path': str(self.iso_path)})
            raise ISOImageError(
                f"Failed to open ISO file: {str(e)}",
                {'path': str(self.iso_path)}
            )
    
    @handle_filesystem_errors
    def scan_iso(self, progress_callback=None):
        """
        Scan all files in the ISO
        
        Args:
            progress_callback: Optional callback(value, message)
        
        Returns:
            list: List of file entry dictionaries
        
        Raises:
            ISOImageError: If ISO is not opened or scanning fails
        """
        if not self.iso:
            raise ISOImageError(
                "ISO must be opened before scanning",
                {'operation': 'scan_iso'}
            )
        
        # Initialize progress tracker
        tracker = ProgressTracker(progress_callback)
        tracker.start("Starting ISO scan...")
        
        logger.info("Scanning ISO filesystem...")
        
        try:
            self.files = []
            self.total_size = 0
            
            tracker.update(10, "Scanning ISO structure...")
            
            # Walk the ISO filesystem
            entry_count = 0
            
            for dirpath, dirnames, filenames in self.iso.walk(iso_path='/'):
                # Process directories
                for dirname in dirnames:
                    try:
                        full_path = f"{dirpath}/{dirname}".replace('//', '/')
                        
                        entry = {
                            'name': dirname,
                            'path': full_path,
                            'is_directory': True,
                            'size': 0,
                            'modified': None,
                            'is_deleted': False
                        }
                        self.files.append(entry)
                        entry_count += 1
                    
                    except Exception as e:
                        logger.debug(f"Error processing directory {dirname}: {e}")
                        continue
                
                # Process files
                for filename in filenames:
                    try:
                        full_path = f"{dirpath}/{filename}".replace('//', '/')
                        
                        # Get file info
                        file_entry = self.iso.get_entry(iso_path=full_path)
                        
                        # Extract metadata
                        size = file_entry.get_data_length()
                        self.total_size += size
                        
                        # Get date (ISO date format)
                        modified = None
                        try:
                            date_record = file_entry.date
                            modified = datetime(
                                date_record.years_since_1900 + 1900,
                                date_record.month,
                                date_record.day_of_month,
                                date_record.hour,
                                date_record.minute,
                                date_record.second
                            ).isoformat()
                        except Exception as e:
                            logger.debug(f"Could not parse date for {filename}: {e}")
                        
                        entry = {
                            'name': filename,
                            'path': full_path,
                            'is_directory': False,
                            'size': size,
                            'modified': modified,
                            'is_deleted': False,
                            'iso_entry': file_entry  # Store for later extraction
                        }
                        
                        self.files.append(entry)
                        entry_count += 1
                    
                    except Exception as e:
                        # File might have issues, add basic entry
                        logger.debug(f"Error processing file {filename}: {e}")
                        
                        entry = {
                            'name': filename,
                            'path': full_path,
                            'is_directory': False,
                            'size': 0,
                            'modified': None,
                            'is_deleted': False,
                            'error': str(e)
                        }
                        self.files.append(entry)
                        entry_count += 1
                
                # Update progress every 100 entries
                if entry_count % 100 == 0:
                    progress_value = min(90, 10 + int(entry_count / 10))
                    tracker.update(
                        progress_value,
                        f"Scanning... {entry_count} entries found"
                    )
            
            logger.info(f"✓ Found {len(self.files)} entries in ISO")
            logger.info(f"✓ Total data size: {self._format_size(self.total_size)}")
            
            tracker.complete(f"Scan complete! Found {len(self.files)} entries")
            
            return self.files
        
        except ISOImageError:
            raise
        
        except Exception as e:
            logger.error(f"ISO scan failed: {e}")
            log_error_report(e, context={
                'iso_path': str(self.iso_path),
                'entries_found': len(self.files)
            })
            raise ISOImageError(
                f"Failed to scan ISO: {str(e)}",
                {'iso_path': str(self.iso_path)}
            )
    
    def extract_file(self, iso_path, output_path):
        """
        Extract a single file from ISO
        
        Args:
            iso_path: Path within ISO
            output_path: Output file path
        
        Returns:
            bool: True if successful
        
        Raises:
            ISOImageError: If extraction fails
        """
        if not self.iso:
            raise ISOImageError(
                "ISO must be opened before extracting files",
                {'operation': 'extract_file'}
            )
        
        try:
            logger.info(f"Extracting {iso_path} to {output_path}")
            self.iso.get_file_from_iso(output_path, iso_path=iso_path)
            logger.info(f"✓ File extracted successfully")
            return True
        
        except Exception as e:
            logger.error(f"File extraction failed: {e}")
            raise ISOImageError(
                f"Failed to extract file: {str(e)}",
                {'iso_path': iso_path, 'output_path': output_path}
            )
    
    def get_file_content(self, iso_path, max_size=None):
        """
        Read file content from ISO without extracting
        
        Args:
            iso_path: Path within ISO
            max_size: Maximum bytes to read (None = all)
        
        Returns:
            bytes: File content or None on error
        
        Raises:
            ISOImageError: If reading fails
        """
        if not self.iso:
            raise ISOImageError(
                "ISO must be opened before reading files",
                {'operation': 'get_file_content'}
            )
        
        try:
            logger.debug(f"Reading content from {iso_path}")
            
            file_entry = self.iso.get_entry(iso_path=iso_path)
            size = file_entry.get_data_length()
            
            if max_size:
                size = min(size, max_size)
            
            # Read the file data
            data = b''
            with self.iso.open_file_from_iso(iso_path=iso_path) as f:
                data = f.read(size)
            
            logger.debug(f"✓ Read {len(data)} bytes")
            return data
        
        except Exception as e:
            logger.error(f"Failed to read file content: {e}")
            raise ISOImageError(
                f"Failed to read file content: {str(e)}",
                {'iso_path': iso_path}
            )
    
    def get_statistics(self):
        """
        Get ISO statistics
        
        Returns:
            dict: Statistics including file counts and sizes
        """
        file_count = sum(1 for f in self.files if not f['is_directory'])
        dir_count = sum(1 for f in self.files if f['is_directory'])
        
        stats = {
            'total_entries': len(self.files),
            'file_count': file_count,
            'directory_count': dir_count,
            'total_size': self.total_size,
            'volume_id': self.volume_id
        }
        
        logger.info(f"ISO Statistics: {stats}")
        return stats
    
    def _format_size(self, size):
        """
        Format size in human-readable format
        
        Args:
            size: Size in bytes
        
        Returns:
            str: Formatted size string
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"
    
    def close(self):
        """Close the ISO file and cleanup resources"""
        logger.info("Closing ISO file...")
        
        try:
            if self.iso:
                self.iso.close()
                self.iso = None
                logger.info("ISO file closed successfully")
        
        except Exception as e:
            logger.warning(f"Error closing ISO file: {e}")
    
    def export_to_json(self, output_path):
        """
        Export ISO analysis to JSON
        
        Args:
            output_path: Path to output JSON file
        
        Raises:
            ISOImageError: If export fails
        """
        import json
        
        try:
            logger.info(f"Exporting ISO analysis to {output_path}")
            
            # Remove iso_entry objects (not serializable)
            export_files = []
            for entry in self.files:
                export_entry = {k: v for k, v in entry.items() if k != 'iso_entry'}
                export_files.append(export_entry)
            
            export_data = {
                'iso_path': str(self.iso_path),
                'volume_id': self.volume_id,
                'files': export_files,
                'statistics': self.get_statistics()
            }
            
            with open(output_path, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            logger.info(f"✓ ISO analysis exported to {output_path}")
        
        except Exception as e:
            logger.error(f"Export failed: {e}")
            raise ISOImageError(
                f"Failed to export ISO analysis: {str(e)}",
                {'output_path': str(output_path)}
            )