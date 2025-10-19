"""
prefetch_analyzer.py - Windows Prefetch analyzer with MAM decompression
NOW INCLUDES: Complete MAM decompression support for Windows 10+ prefetch files

REFACTORED: Now uses error_handler, dependency_manager, and progress_manager
"""

import struct
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import hashlib

# Import centralized management modules
from core.error_handler import (
    PrefetchAnalysisError,
    FileSystemError,
    handle_filesystem_errors,
    safe_file_read,
    log_error_report,
    logger
)
from core.dependency_manager import is_available, check_feature
from core.progress_manager import ProgressTracker


class PrefetchAnalyzer:
    """Analyzes Windows Prefetch (.pf) files including compressed Windows 10+ files"""
    
    # Prefetch versions
    PREFETCH_VERSIONS = {
        17: 'Windows XP/2003',
        23: 'Windows Vista/7',
        26: 'Windows 8.1',
        30: 'Windows 10/11'
    }
    
    def __init__(self, prefetch_path=None):
        """
        Initialize prefetch analyzer
        
        Args:
            prefetch_path: Path to Prefetch folder (usually C:\Windows\Prefetch)
        
        Raises:
            FileSystemError: If prefetch path doesn't exist
        """
        if prefetch_path:
            self.prefetch_path = Path(prefetch_path)
        else:
            # Default Windows Prefetch location
            self.prefetch_path = Path('C:/Windows/Prefetch')
        
        self.prefetch_files = []
        self.execution_timeline = []
        self.programs = {}
        self.compressed_count = 0
        self.decompression_failed = []
        
        logger.info(f"PrefetchAnalyzer initialized for: {self.prefetch_path}")
    
    @handle_filesystem_errors
    def find_prefetch_files(self):
        """
        Find all .pf files in Prefetch directory
        
        Returns:
            list: List of prefetch file paths
        
        Raises:
            FileSystemError: If directory doesn't exist or can't be accessed
        """
        if not self.prefetch_path.exists():
            raise FileSystemError(
                f"Prefetch directory not found: {self.prefetch_path}",
                {'path': str(self.prefetch_path)}
            )
        
        try:
            pf_files = list(self.prefetch_path.glob('*.pf'))
            logger.info(f"Found {len(pf_files)} prefetch files")
            return pf_files
        
        except Exception as e:
            logger.error(f"Error finding prefetch files: {e}")
            raise FileSystemError(
                f"Failed to search for prefetch files: {str(e)}",
                {'path': str(self.prefetch_path)}
            )
    
    def analyze(self, progress_callback=None):
        """
        Analyze all prefetch files - main entry point
        
        Args:
            progress_callback: Optional callback(value, message)
        
        Returns:
            dict: Programs dictionary with execution information
        
        Raises:
            PrefetchAnalysisError: If analysis fails
        """
        # Initialize progress tracker
        tracker = ProgressTracker(progress_callback)
        tracker.start("Finding prefetch files...")
        
        try:
            pf_files = self.find_prefetch_files()
            
            if not pf_files:
                logger.warning("No prefetch files found")
                tracker.complete("No prefetch files found")
                return {}
            
            tracker.update(10, f"Analyzing {len(pf_files)} prefetch files...")
            
            # Process each prefetch file
            for idx, pf_file in enumerate(pf_files):
                try:
                    progress = 10 + int((idx / len(pf_files)) * 60)
                    tracker.update(progress, f"Analyzing: {pf_file.name}")
                    
                    pf_data = self._parse_prefetch_file(pf_file)
                    if pf_data:
                        self.prefetch_files.append(pf_data)
                        self._add_to_timeline(pf_data)
                        self._add_to_programs(pf_data)
                
                except Exception as e:
                    logger.warning(f"Error parsing {pf_file.name}: {e}")
                    continue
            
            tracker.update(70, "Building timeline...")
            
            # Sort timeline
            self.execution_timeline.sort(key=lambda x: x['timestamp'], reverse=True)
            
            # Log summary
            logger.info(f"✓ Prefetch analysis complete:")
            logger.info(f"  Total programs: {len(self.programs)}")
            logger.info(f"  Timeline entries: {len(self.execution_timeline)}")
            logger.info(f"  Compressed files: {self.compressed_count}")
            
            if self.decompression_failed:
                logger.warning(f"  Decompression failed: {len(self.decompression_failed)}")
                logger.debug(f"  Failed files: {self.decompression_failed}")
            
            tracker.complete(
                f"Analysis complete! {len(self.programs)} programs analyzed"
            )
            
            return self.programs
        
        except FileSystemError:
            raise
        
        except Exception as e:
            logger.error(f"Prefetch analysis failed: {e}")
            log_error_report(e, context={'prefetch_path': str(self.prefetch_path)})
            raise PrefetchAnalysisError(
                f"Failed to analyze prefetch files: {str(e)}",
                {'prefetch_path': str(self.prefetch_path)}
            )
    
    def _parse_prefetch_file(self, pf_path):
        """
        Parse a single prefetch file
        
        Args:
            pf_path: Path to prefetch file
        
        Returns:
            dict: Parsed prefetch data or None if parsing fails
        """
        try:
            # Read file content
            with open(pf_path, 'rb') as f:
                data = f.read()
            
            # Check if compressed (Windows 10+)
            if data[:4] == b'MAM\x04':
                logger.debug(f"Compressed file detected: {pf_path.name}")
                self.compressed_count += 1
                
                data = self._decompress_mam(data)
                if not data:
                    self.decompression_failed.append(pf_path.name)
                    logger.warning(f"✗ Failed to decompress {pf_path.name}")
                    return None
                
                logger.debug(f"✓ Decompressed successfully: {pf_path.name}")
            
            # Parse header to get version
            if len(data) < 4:
                logger.warning(f"File too small: {pf_path.name}")
                return None
            
            version = struct.unpack('<I', data[0:4])[0]
            
            if version not in self.PREFETCH_VERSIONS:
                logger.warning(f"Unknown prefetch version {version} in {pf_path.name}")
                return None
            
            # Parse based on version
            if version == 17:
                return self._parse_version_17(data, pf_path)
            elif version == 23:
                return self._parse_version_23(data, pf_path)
            elif version == 26:
                return self._parse_version_26(data, pf_path)
            elif version == 30:
                return self._parse_version_30(data, pf_path)
        
        except Exception as e:
            logger.debug(f"Error reading {pf_path.name}: {e}")
            return None
    
    def _decompress_mam(self, compressed_data):
        """
        Decompress MAM compressed prefetch (Windows 10+)
        
        MAM (Memory Allocation Manager) compression is a variant of LZNT1
        used by Windows 10+.
        
        Args:
            compressed_data: Compressed data bytes
        
        Returns:
            bytes: Decompressed data or None if decompression fails
        """
        try:
            # MAM header structure:
            # 0x00-0x03: Signature "MAM\x04"
            # 0x04-0x07: Uncompressed size (little-endian DWORD)
            
            if compressed_data[:4] != b'MAM\x04':
                return None
            
            # Get uncompressed size
            uncompressed_size = struct.unpack('<I', compressed_data[4:8])[0]
            
            # Compressed data starts at offset 8
            compressed_payload = compressed_data[8:]
            
            # Attempt LZNT1 decompression
            decompressed = self._lznt1_decompress(compressed_payload, uncompressed_size)
            
            if decompressed and len(decompressed) == uncompressed_size:
                return decompressed
            
            logger.warning(
                f"Decompression size mismatch: got {len(decompressed) if decompressed else 0}, "
                f"expected {uncompressed_size}"
            )
            return None
        
        except Exception as e:
            logger.debug(f"MAM decompression error: {e}")
            return None
    
    def _lznt1_decompress(self, compressed_data, uncompressed_size):
        """
        Decompress LZNT1 compressed data
        
        LZNT1 is a sliding window compression algorithm used by Windows.
        
        Args:
            compressed_data: Compressed data bytes
            uncompressed_size: Expected uncompressed size
        
        Returns:
            bytes: Decompressed data or None if decompression fails
        """
        try:
            output = []
            pos = 0
            
            while pos < len(compressed_data) and len(output) < uncompressed_size:
                # Read chunk header
                if pos + 2 > len(compressed_data):
                    break
                
                chunk_header = struct.unpack('<H', compressed_data[pos:pos+2])[0]
                pos += 2
                
                # Check if chunk is compressed
                if chunk_header == 0:
                    break
                
                chunk_size = (chunk_header & 0x0FFF) + 1
                is_compressed = (chunk_header & 0x8000) != 0
                
                chunk_end = pos + chunk_size
                
                if not is_compressed:
                    # Uncompressed chunk
                    output.extend(compressed_data[pos:chunk_end])
                    pos = chunk_end
                else:
                    # Compressed chunk - process flags and tokens
                    while pos < chunk_end and len(output) < uncompressed_size:
                        if pos >= len(compressed_data):
                            break
                        
                        # Read flag byte
                        flag_byte = compressed_data[pos]
                        pos += 1
                        
                        # Process 8 tokens
                        for bit in range(8):
                            if len(output) >= uncompressed_size:
                                break
                            
                            if pos >= chunk_end:
                                break
                            
                            if flag_byte & (1 << bit):
                                # Compressed token (2 bytes)
                                if pos + 2 > len(compressed_data):
                                    break
                                
                                token = struct.unpack('<H', compressed_data[pos:pos+2])[0]
                                pos += 2
                                
                                # Calculate match length and distance
                                output_size = len(output)
                                
                                if output_size < 0x10:
                                    max_bits = 4
                                elif output_size < 0x20:
                                    max_bits = 5
                                elif output_size < 0x1000:
                                    max_bits = 6
                                else:
                                    max_bits = 12
                                
                                length_bits = 16 - max_bits
                                length_mask = (1 << length_bits) - 1
                                
                                match_length = (token & length_mask) + 3
                                match_distance = (token >> length_bits) + 1
                                
                                # Copy from window
                                if match_distance > len(output):
                                    # Invalid distance, pad with zeros
                                    for _ in range(match_length):
                                        output.append(0)
                                else:
                                    start_pos = len(output) - match_distance
                                    for _ in range(match_length):
                                        if start_pos < len(output):
                                            output.append(output[start_pos])
                                            start_pos += 1
                                        else:
                                            output.append(0)
                            
                            else:
                                # Literal byte
                                if pos >= len(compressed_data):
                                    break
                                output.append(compressed_data[pos])
                                pos += 1
            
            return bytes(output[:uncompressed_size])
        
        except Exception as e:
            logger.debug(f"LZNT1 decompression error: {e}")
            return None
    
    def _parse_version_17(self, data, pf_path):
        """Parse Windows XP/2003 prefetch (version 17)"""
        try:
            # Offsets for version 17
            executable_name_offset = 0x10
            executable_name_length = 60
            
            # Extract executable name (Unicode)
            exec_name_raw = data[executable_name_offset:executable_name_offset + executable_name_length]
            exec_name = exec_name_raw.decode('utf-16-le', errors='ignore').rstrip('\x00')
            
            # Prefetch hash
            prefetch_hash = struct.unpack('<I', data[0x4C:0x50])[0]
            
            # Run count
            run_count = struct.unpack('<I', data[0x90:0x94])[0]
            
            # Last execution time (FILETIME)
            last_exec_time = struct.unpack('<Q', data[0x78:0x80])[0]
            last_exec_datetime = self._filetime_to_datetime(last_exec_time)
            
            return {
                'filename': pf_path.name,
                'version': 17,
                'version_name': self.PREFETCH_VERSIONS[17],
                'executable_name': exec_name,
                'prefetch_hash': f'{prefetch_hash:08X}',
                'run_count': run_count,
                'last_execution': last_exec_datetime,
                'execution_times': [last_exec_datetime] if last_exec_datetime else [],
                'file_path': str(pf_path)
            }
        except Exception as e:
            logger.debug(f"Version 17 parse error: {e}")
            return None
    
    def _parse_version_23(self, data, pf_path):
        """Parse Windows Vista/7 prefetch (version 23)"""
        try:
            # Similar to version 17 but with different offsets
            executable_name_offset = 0x10
            executable_name_length = 60
            
            exec_name_raw = data[executable_name_offset:executable_name_offset + executable_name_length]
            exec_name = exec_name_raw.decode('utf-16-le', errors='ignore').rstrip('\x00')
            
            prefetch_hash = struct.unpack('<I', data[0x4C:0x50])[0]
            run_count = struct.unpack('<I', data[0x98:0x9C])[0]
            
            # Last execution time
            last_exec_time = struct.unpack('<Q', data[0x80:0x88])[0]
            last_exec_datetime = self._filetime_to_datetime(last_exec_time)
            
            return {
                'filename': pf_path.name,
                'version': 23,
                'version_name': self.PREFETCH_VERSIONS[23],
                'executable_name': exec_name,
                'prefetch_hash': f'{prefetch_hash:08X}',
                'run_count': run_count,
                'last_execution': last_exec_datetime,
                'execution_times': [last_exec_datetime] if last_exec_datetime else [],
                'file_path': str(pf_path)
            }
        except Exception as e:
            logger.debug(f"Version 23 parse error: {e}")
            return None
    
    def _parse_version_26(self, data, pf_path):
        """Parse Windows 8.1 prefetch (version 26)"""
        try:
            # Version 26 stores last 8 execution times
            executable_name_offset = 0x10
            executable_name_length = 60
            
            exec_name_raw = data[executable_name_offset:executable_name_offset + executable_name_length]
            exec_name = exec_name_raw.decode('utf-16-le', errors='ignore').rstrip('\x00')
            
            prefetch_hash = struct.unpack('<I', data[0x4C:0x50])[0]
            run_count = struct.unpack('<I', data[0xD0:0xD4])[0]
            
            # Extract up to 8 execution times
            execution_times = []
            for i in range(8):
                offset = 0x80 + (i * 8)
                try:
                    exec_time = struct.unpack('<Q', data[offset:offset+8])[0]
                    exec_datetime = self._filetime_to_datetime(exec_time)
                    if exec_datetime:
                        execution_times.append(exec_datetime)
                except:
                    break
            
            last_exec = execution_times[0] if execution_times else None
            
            return {
                'filename': pf_path.name,
                'version': 26,
                'version_name': self.PREFETCH_VERSIONS[26],
                'executable_name': exec_name,
                'prefetch_hash': f'{prefetch_hash:08X}',
                'run_count': run_count,
                'last_execution': last_exec,
                'execution_times': execution_times,
                'file_path': str(pf_path)
            }
        except Exception as e:
            logger.debug(f"Version 26 parse error: {e}")
            return None
    
    def _parse_version_30(self, data, pf_path):
        """Parse Windows 10/11 prefetch (version 30)"""
        try:
            # Version 30 similar to 26
            executable_name_offset = 0x10
            executable_name_length = 60
            
            exec_name_raw = data[executable_name_offset:executable_name_offset + executable_name_length]
            exec_name = exec_name_raw.decode('utf-16-le', errors='ignore').rstrip('\x00')
            
            prefetch_hash = struct.unpack('<I', data[0x4C:0x50])[0]
            run_count = struct.unpack('<I', data[0xD0:0xD4])[0]
            
            # Extract up to 8 execution times
            execution_times = []
            for i in range(8):
                offset = 0x80 + (i * 8)
                try:
                    exec_time = struct.unpack('<Q', data[offset:offset+8])[0]
                    exec_datetime = self._filetime_to_datetime(exec_time)
                    if exec_datetime:
                        execution_times.append(exec_datetime)
                except:
                    break
            
            last_exec = execution_times[0] if execution_times else None
            
            return {
                'filename': pf_path.name,
                'version': 30,
                'version_name': self.PREFETCH_VERSIONS[30],
                'executable_name': exec_name,
                'prefetch_hash': f'{prefetch_hash:08X}',
                'run_count': run_count,
                'last_execution': last_exec,
                'execution_times': execution_times,
                'file_path': str(pf_path)
            }
        except Exception as e:
            logger.debug(f"Version 30 parse error: {e}")
            return None
    
    def _filetime_to_datetime(self, filetime):
        """Convert Windows FILETIME to Python datetime"""
        if not filetime or filetime == 0:
            return None
        
        try:
            # FILETIME is 100-nanosecond intervals since 1601-01-01
            epoch = datetime(1601, 1, 1)
            delta = timedelta(microseconds=filetime / 10)
            return epoch + delta
        except:
            return None
    
    def _add_to_timeline(self, pf_data):
        """Add prefetch data to execution timeline"""
        for exec_time in pf_data.get('execution_times', []):
            if exec_time:
                self.execution_timeline.append({
                    'timestamp': exec_time,
                    'executable': pf_data['executable_name'],
                    'prefetch_file': pf_data['filename'],
                    'type': 'execution'
                })
    
    def _add_to_programs(self, pf_data):
        """Add prefetch data to programs dictionary"""
        exec_name = pf_data['executable_name']
        
        if exec_name not in self.programs:
            self.programs[exec_name] = {
                'name': exec_name,
                'run_count': pf_data['run_count'],
                'last_execution': pf_data['last_execution'],
                'first_execution': None,
                'execution_times': pf_data['execution_times'].copy(),
                'prefetch_files': [pf_data['filename']],
                'version': pf_data['version']
            }
            
            # Set first execution (oldest)
            if pf_data['execution_times']:
                self.programs[exec_name]['first_execution'] = min(pf_data['execution_times'])
        else:
            # Update existing program info
            prog = self.programs[exec_name]
            prog['run_count'] = max(prog['run_count'], pf_data['run_count'])
            prog['prefetch_files'].append(pf_data['filename'])
            
            # Merge execution times
            for exec_time in pf_data['execution_times']:
                if exec_time not in prog['execution_times']:
                    prog['execution_times'].append(exec_time)
            
            # Update first/last execution
            if prog['execution_times']:
                prog['last_execution'] = max(prog['execution_times'])
                prog['first_execution'] = min(prog['execution_times'])
    
    def export_to_json(self, output_file):
        """
        Export analysis results to JSON
        
        Args:
            output_file: Path to output JSON file
        
        Raises:
            PrefetchAnalysisError: If export fails
        """
        import json
        
        try:
            logger.info(f"Exporting prefetch analysis to {output_file}")
            
            data = {
                'prefetch_path': str(self.prefetch_path),
                'total_programs': len(self.programs),
                'total_prefetch_files': len(self.prefetch_files),
                'compressed_files': self.compressed_count,
                'decompression_failures': len(self.decompression_failed),
                'programs': {},
                'timeline': []
            }
            
            # Export programs (convert datetime to string)
            for name, prog_data in self.programs.items():
                data['programs'][name] = {
                    'name': prog_data['name'],
                    'run_count': prog_data['run_count'],
                    'last_execution': str(prog_data['last_execution']) if prog_data['last_execution'] else None,
                    'first_execution': str(prog_data['first_execution']) if prog_data['first_execution'] else None,
                    'execution_times': [str(t) for t in prog_data['execution_times']],
                    'prefetch_files': prog_data['prefetch_files'],
                    'version': prog_data['version']
                }
            
            # Export timeline (last 1000 entries)
            for entry in self.execution_timeline[:1000]:
                data['timeline'].append({
                    'timestamp': str(entry['timestamp']),
                    'executable': entry['executable'],
                    'prefetch_file': entry['prefetch_file']
                })
            
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"✓ Prefetch analysis exported to {output_file}")
        
        except Exception as e:
            logger.error(f"Export failed: {e}")
            raise PrefetchAnalysisError(
                f"Failed to export prefetch analysis: {str(e)}",
                {'output_file': str(output_file)}
            )
    
    def get_statistics(self):
        """Get analysis statistics"""
        stats = {
            'total_programs': len(self.programs),
            'total_prefetch_files': len(self.prefetch_files),
            'compressed_files': self.compressed_count,
            'decompression_failures': len(self.decompression_failed),
            'timeline_entries': len(self.execution_timeline)
        }
        
        logger.info(f"Prefetch Statistics: {stats}")
        return stats