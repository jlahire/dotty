"""
forensic_scanner.py - scans forensic images for files and deleted files
uses pytsk3 for DD/RAW and dissect for E01 (pure Python!)

REFACTORED: Now uses error_handler, dependency_manager, and progress_manager
"""

import pytsk3
from pathlib import Path
from datetime import datetime

# Import centralized management modules
from core.error_handler import (
    ForensicImageError,
    DependencyError,
    handle_forensic_errors,
    log_error_report,
    logger
)
from core.dependency_manager import is_available, check_feature
from core.progress_manager import ProgressTracker


# Check for dissect availability using dependency manager
if is_available('dissect'):
    try:
        from dissect.target import Target
        from dissect.evidence import ewf
        logger.info("✓ dissect library available - E01 support enabled")
    except ImportError as e:
        logger.warning(f"dissect import failed despite being marked available: {e}")
        # Handle gracefully
else:
    logger.info("✗ dissect library not available - E01 support disabled")
    logger.info("  Install with: pip install dissect.target dissect.evidence")


class DissectImgInfo(pytsk3.Img_Info):
    """Wrapper for E01 images using dissect"""
    
    def __init__(self, ewf_stream):
        self._ewf_stream = ewf_stream
        self._size = ewf_stream.size
        super().__init__(url="", type=pytsk3.TSK_IMG_TYPE_EXTERNAL)
    
    def close(self):
        if self._ewf_stream:
            self._ewf_stream.close()
    
    def read(self, offset, size):
        self._ewf_stream.seek(offset)
        return self._ewf_stream.read(size)
    
    def get_size(self):
        return self._size


class ForensicScanner:
    """Scans forensic disk images for files"""
    
    def __init__(self, image_path):
        self.image_path = Path(image_path)
        self.img_info = None
        self.fs_info = None
        self.image_type = self.detect_image_type()
        self.filesystem_type = None
        self.ewf_stream = None
        
        logger.info(f"ForensicScanner initialized for: {self.image_path}")
        logger.info(f"Detected image type: {self.image_type}")
    
    def detect_image_type(self):
        """Detect forensic image format from file extension"""
        ext = self.image_path.suffix.lower()
        
        if ext in ['.e01', '.ex01']:
            return 'E01'
        elif ext in ['.dd', '.raw', '.img']:
            return 'DD'
        elif ext in ['.aff', '.afd']:
            return 'AFF'
        else:
            logger.warning(f"Unknown extension {ext}, assuming DD/RAW format")
            return 'DD'
    
    @handle_forensic_errors
    def open_image(self):
        """
        Open the forensic image
        
        Returns:
            bool: True if successful, False otherwise
        
        Raises:
            ForensicImageError: If image cannot be opened
            DependencyError: If required libraries are missing
        """
        logger.info(f"Opening forensic image: {self.image_path}")
        
        if not self.image_path.exists():
            raise ForensicImageError(
                f"Image file does not exist: {self.image_path}",
                {'path': str(self.image_path)}
            )
        
        try:
            if self.image_type == 'E01':
                # Check if dissect is available
                if not is_available('dissect'):
                    error_msg = (
                        "E01 format requires dissect library\n\n"
                        "Install with:\n"
                        "  pip install dissect.target dissect.evidence\n\n"
                        "Or convert E01 to DD format using FTK Imager"
                    )
                    logger.error("Dissect library not available for E01 processing")
                    raise DependencyError(
                        'dissect',
                        'pip install dissect.target dissect.evidence',
                        error_msg
                    )
                
                # Open E01 with dissect
                logger.info("Opening E01 file with dissect...")
                
                # dissect expects the base path (it will find segments automatically)
                base_path = str(self.image_path)
                
                # Open EWF stream
                self.ewf_stream = ewf.EWF(base_path)
                
                # Wrap in pytsk3 interface
                self.img_info = DissectImgInfo(self.ewf_stream)
                
                logger.info("✓ E01 image opened successfully")
            
            else:
                # DD/RAW - use pytsk3 directly
                logger.info("Opening DD/RAW image with pytsk3...")
                self.img_info = pytsk3.Img_Info(str(self.image_path))
                logger.info("✓ DD/RAW image opened successfully")
            
            image_size = self.img_info.get_size()
            logger.info(f"✓ Image size: {image_size:,} bytes ({image_size / (1024**3):.2f} GB)")
            
            return True
        
        except DependencyError:
            # Re-raise dependency errors as-is
            raise
        
        except AttributeError as e:
            logger.error(f"Image format error: {e}")
            raise ForensicImageError(
                "Invalid image format or corrupted file",
                {'path': str(self.image_path), 'error': str(e)}
            )
        
        except Exception as e:
            logger.error(f"Error opening image: {e}")
            log_error_report(e, context={'image_path': str(self.image_path)})
            raise ForensicImageError(
                f"Failed to open forensic image: {str(e)}",
                {'path': str(self.image_path), 'image_type': self.image_type}
            )
    
    @handle_forensic_errors
    def detect_filesystem(self):
        """
        Detect and open filesystem from the image
        
        Returns:
            bool: True if successful, False otherwise
        
        Raises:
            ForensicImageError: If filesystem detection fails
        """
        if not self.img_info:
            raise ForensicImageError(
                "Image must be opened before detecting filesystem",
                {'operation': 'detect_filesystem'}
            )
        
        logger.info("Detecting filesystem...")
        
        try:
            # Try to open volume system first (for partitioned images)
            try:
                volume = pytsk3.Volume_Info(self.img_info)
                
                logger.info(f"Found volume system with {len(volume)} partitions")
                
                # Find first filesystem partition
                for partition in volume:
                    if partition.flags == pytsk3.TSK_VS_PART_FLAG_ALLOC:
                        logger.info(
                            f"  Partition at offset {partition.start} "
                            f"(type: {partition.desc.decode('utf-8', errors='ignore')})"
                        )
                        
                        try:
                            # Try to open filesystem on this partition
                            self.fs_info = pytsk3.FS_Info(
                                self.img_info,
                                offset=partition.start * 512
                            )
                            self.filesystem_type = self._get_fs_type_name(self.fs_info.info.ftype)
                            logger.info(f"✓ Found filesystem: {self.filesystem_type}")
                            return True
                        
                        except Exception as e:
                            logger.debug(f"  Could not open filesystem on partition: {e}")
                            continue
                
                # No valid partition found
                logger.warning("No valid filesystem partition found in volume")
            
            except Exception as e:
                # No volume system or error reading it
                logger.debug(f"No volume system found or error: {e}")
            
            # Try to open filesystem directly (unpartitioned image)
            logger.info("Attempting to open filesystem directly...")
            self.fs_info = pytsk3.FS_Info(self.img_info)
            self.filesystem_type = self._get_fs_type_name(self.fs_info.info.ftype)
            logger.info(f"✓ Found filesystem: {self.filesystem_type}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error detecting filesystem: {e}")
            log_error_report(e, context={'image_path': str(self.image_path)})
            raise ForensicImageError(
                f"Failed to detect filesystem: {str(e)}",
                {'image_path': str(self.image_path)}
            )
    
    def _get_fs_type_name(self, fs_type):
        """Convert filesystem type constant to readable name"""
        fs_types = {
            pytsk3.TSK_FS_TYPE_NTFS: 'NTFS',
            pytsk3.TSK_FS_TYPE_FAT32: 'FAT32',
            pytsk3.TSK_FS_TYPE_EXFAT: 'exFAT',
            pytsk3.TSK_FS_TYPE_EXT2: 'EXT2',
            pytsk3.TSK_FS_TYPE_EXT3: 'EXT3',
            pytsk3.TSK_FS_TYPE_EXT4: 'EXT4',
            pytsk3.TSK_FS_TYPE_HFS: 'HFS',
            pytsk3.TSK_FS_TYPE_APFS: 'APFS',
        }
        return fs_types.get(fs_type, f'Unknown (type {fs_type})')
    
    @handle_forensic_errors
    def scan_filesystem(self, progress_callback=None):
        """
        Scan filesystem and return list of file entries
        
        Args:
            progress_callback: Optional callback(value, message) for progress
        
        Returns:
            list: List of file entry dictionaries
        
        Raises:
            ForensicImageError: If scanning fails
        """
        if not self.fs_info:
            raise ForensicImageError(
                "Filesystem must be detected before scanning",
                {'operation': 'scan_filesystem'}
            )
        
        logger.info("Scanning filesystem...")
        
        # Initialize progress tracker
        tracker = ProgressTracker(progress_callback)
        tracker.start("Starting filesystem scan...")
        
        entries = []
        
        try:
            root = self.fs_info.open_dir(path="/")
            entries = self._scan_directory_recursive(
                root, 
                "/", 
                tracker,
                depth=0
            )
            
            logger.info(f"✓ Found {len(entries)} entries")
            tracker.complete(f"Scan complete! Found {len(entries)} entries")
            
            return entries
        
        except Exception as e:
            logger.error(f"Error scanning filesystem: {e}")
            log_error_report(e, context={
                'filesystem_type': self.filesystem_type,
                'entries_found': len(entries)
            })
            raise ForensicImageError(
                f"Failed to scan filesystem: {str(e)}",
                {'filesystem_type': self.filesystem_type}
            )
    
    def _scan_directory_recursive(self, directory, path, tracker, depth=0):
        """
        Recursively scan directory
        
        Args:
            directory: pytsk3 directory object
            path: Current path string
            tracker: ProgressTracker instance
            depth: Current recursion depth
        
        Returns:
            list: List of file entries
        """
        entries = []
        
        # Prevent infinite recursion
        if depth > 50:
            logger.warning(f"Maximum recursion depth reached at path: {path}")
            return entries
        
        try:
            for entry in directory:
                # Skip . and ..
                if entry.info.name.name in [b'.', b'..']:
                    continue
                
                try:
                    # Decode filename
                    try:
                        file_name = entry.info.name.name.decode('utf-8', errors='ignore')
                    except:
                        file_name = str(entry.info.name.name)
                    
                    full_path = path + file_name
                    
                    # Get file metadata
                    file_entry = {
                        'name': file_name,
                        'path': full_path,
                        'inode': entry.info.meta.addr if entry.info.meta else 0,
                        'is_deleted': bool(entry.info.name.flags & pytsk3.TSK_FS_NAME_FLAG_UNALLOC),
                        'is_directory': entry.info.meta and entry.info.meta.type == pytsk3.TSK_FS_META_TYPE_DIR,
                        'size': entry.info.meta.size if entry.info.meta else 0,
                        'entry': entry  # Store reference for on-demand access
                    }
                    
                    # Get timestamps
                    if entry.info.meta:
                        file_entry['modified'] = self._convert_timestamp(entry.info.meta.mtime)
                        file_entry['accessed'] = self._convert_timestamp(entry.info.meta.atime)
                        file_entry['created'] = self._convert_timestamp(entry.info.meta.crtime)
                        file_entry['changed'] = self._convert_timestamp(entry.info.meta.ctime)
                    
                    entries.append(file_entry)
                    
                    # Update progress every 100 files
                    if len(entries) % 100 == 0:
                        progress_value = min(90, 10 + int(len(entries) / 10))
                        tracker.update(
                            progress_value,
                            f"Scanning... {len(entries)} entries found"
                        )
                    
                    # Recurse into directories (only non-deleted ones)
                    if file_entry['is_directory'] and not file_entry['is_deleted']:
                        try:
                            sub_dir = entry.as_directory()
                            sub_entries = self._scan_directory_recursive(
                                sub_dir,
                                full_path + "/",
                                tracker,
                                depth + 1
                            )
                            entries.extend(sub_entries)
                        
                        except Exception as e:
                            logger.debug(f"Error scanning subdirectory {full_path}: {e}")
                            continue
                
                except Exception as e:
                    logger.debug(f"Error processing entry at {path}: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error scanning directory {path}: {e}")
        
        return entries
    
    def _convert_timestamp(self, ts):
        """Convert filesystem timestamp to ISO format"""
        if ts and ts > 0:
            try:
                return datetime.fromtimestamp(ts).isoformat()
            except Exception as e:
                logger.debug(f"Error converting timestamp {ts}: {e}")
                return None
        return None
    
    @handle_forensic_errors
    def read_file_content(self, entry, max_size=None):
        """
        Read file content on-demand
        
        Args:
            entry: File entry with pytsk3 entry object
            max_size: Maximum bytes to read (None = all)
        
        Returns:
            bytes: File content or None on error
        
        Raises:
            ForensicImageError: If reading fails
        """
        try:
            if not entry.info.meta:
                logger.warning("Entry has no metadata, cannot read content")
                return None
            
            size = entry.info.meta.size
            if max_size:
                size = min(size, max_size)
            
            if size == 0:
                return b''
            
            offset = 0
            data = b''
            
            # Read in 1MB chunks
            while offset < size:
                chunk_size = min(1024 * 1024, size - offset)
                chunk = entry.read_random(offset, chunk_size)
                
                if not chunk:
                    break
                
                data += chunk
                offset += len(chunk)
            
            logger.debug(f"Read {len(data)} bytes from file")
            return data
        
        except Exception as e:
            logger.error(f"Error reading file content: {e}")
            raise ForensicImageError(
                f"Failed to read file content: {str(e)}",
                {'size': size if 'size' in locals() else 'unknown'}
            )
    
    def close(self):
        """Close the image and cleanup resources"""
        logger.info("Closing forensic image...")
        
        try:
            if self.ewf_stream:
                self.ewf_stream.close()
                self.ewf_stream = None
                logger.debug("EWF stream closed")
            
            if self.img_info:
                self.img_info.close()
                self.img_info = None
                logger.debug("Image info closed")
            
            self.fs_info = None
            logger.info("Forensic image closed successfully")
        
        except Exception as e:
            logger.warning(f"Error closing forensic image: {e}")