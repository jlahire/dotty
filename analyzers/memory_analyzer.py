"""
memory_analyzer.py - analyzes memory dumps for processes and files
uses volatility3 for memory forensics

REFACTORED: Now uses error_handler, dependency_manager, and progress_manager
"""

import subprocess
import json
import tempfile
from pathlib import Path
from datetime import datetime

# Import centralized management modules
from core.error_handler import (
    MemoryDumpError,
    DependencyError,
    handle_memory_errors,
    log_error_report,
    logger
)
from core.dependency_manager import is_available, check_feature
from core.progress_manager import ProgressTracker, MultiStepProgressTracker


# Check for volatility3 availability using dependency manager
if is_available('volatility3'):
    try:
        import volatility3
        from volatility3 import framework
        from volatility3.framework import contexts, automagic, plugins, exceptions
        from volatility3.cli import text_renderer
        logger.info("✓ volatility3 library available - memory dump support enabled")
    except ImportError as e:
        logger.warning(f"volatility3 import failed despite being marked available: {e}")
else:
    logger.info("✗ volatility3 library not available - memory dump support disabled")
    logger.info("  Install with: pip install volatility3")


class MemoryAnalyzer:
    """Analyzes memory dump files using Volatility3"""
    
    def __init__(self, dump_path):
        self.dump_path = Path(dump_path)
        self.profile = None
        self.processes = []
        self.files = []
        self.network_connections = []
        self.registry_keys = []
        
        logger.info(f"MemoryAnalyzer initialized for: {self.dump_path}")
        
        # Validate dump file exists
        if not self.dump_path.exists():
            raise MemoryDumpError(
                f"Memory dump file does not exist: {self.dump_path}",
                {'path': str(self.dump_path)}
            )
    
    @handle_memory_errors
    def detect_profile(self, progress_callback=None):
        """
        Detect OS profile from memory dump
        
        Args:
            progress_callback: Optional callback(value, message)
        
        Returns:
            bool: True if profile detected successfully
        
        Raises:
            DependencyError: If volatility3 is not available
            MemoryDumpError: If profile detection fails
        """
        # Check volatility3 availability
        if not is_available('volatility3'):
            raise DependencyError(
                'volatility3',
                'pip install volatility3',
                "Memory dump analysis requires Volatility3"
            )
        
        # Initialize progress tracker
        tracker = ProgressTracker(progress_callback)
        tracker.start("Detecting OS profile...")
        
        logger.info(f"Analyzing memory dump: {self.dump_path}")
        
        try:
            # Create volatility3 context
            ctx = self._create_context()
            
            tracker.update(30, "Attempting Windows detection...")
            
            # Try Windows detection first (most common)
            try:
                plugin = self._get_plugin(ctx, "windows.info.Info")
                if plugin:
                    self.profile = "Windows"
                    logger.info("✓ Detected OS: Windows")
                    tracker.complete("Profile detected: Windows")
                    return True
            except Exception as e:
                logger.debug(f"Windows detection failed: {e}")
            
            tracker.update(60, "Attempting Linux detection...")
            
            # Try Linux detection
            try:
                plugin = self._get_plugin(ctx, "linux.pslist.PsList")
                if plugin:
                    self.profile = "Linux"
                    logger.info("✓ Detected OS: Linux")
                    tracker.complete("Profile detected: Linux")
                    return True
            except Exception as e:
                logger.debug(f"Linux detection failed: {e}")
            
            # Default to Windows if uncertain
            self.profile = "Windows"
            logger.warning("⚠ Could not definitively detect OS, assuming Windows")
            tracker.complete("Profile assumed: Windows (uncertain)")
            return True
        
        except Exception as e:
            logger.error(f"Profile detection failed: {e}")
            log_error_report(e, context={'dump_path': str(self.dump_path)})
            raise MemoryDumpError(
                f"Failed to detect OS profile: {str(e)}",
                {'dump_path': str(self.dump_path)}
            )
    
    def _create_context(self):
        """
        Create volatility3 context for analysis
        
        Returns:
            volatility3 context object
        
        Raises:
            MemoryDumpError: If context creation fails
        """
        try:
            ctx = contexts.Context()
            
            # Set up the context with the memory dump
            automagic.choose_automagic(automagic.available(ctx), ctx)
            
            # Add the file to context
            ctx.config['automagic.LayerStacker.single_location'] = f"file://{self.dump_path}"
            
            logger.debug("Volatility3 context created successfully")
            return ctx
        
        except Exception as e:
            logger.error(f"Failed to create volatility3 context: {e}")
            raise MemoryDumpError(
                f"Failed to initialize memory analysis context: {str(e)}",
                {'dump_path': str(self.dump_path)}
            )
    
    def _get_plugin(self, ctx, plugin_name):
        """
        Get a volatility3 plugin instance
        
        Args:
            ctx: Volatility3 context
            plugin_name: Full plugin name (e.g., "windows.pslist.PsList")
        
        Returns:
            Plugin instance or None if not available
        """
        try:
            plugin_class = framework.import_class(f"volatility3.plugins.{plugin_name}")
            constructed = plugins.construct_plugin(
                ctx,
                automagic.choose_automagic(automagic.available(ctx), ctx),
                plugin_class,
                'plugins',
                None,
                None
            )
            logger.debug(f"Loaded plugin: {plugin_name}")
            return constructed
        
        except Exception as e:
            logger.debug(f"Failed to load plugin {plugin_name}: {e}")
            return None
    
    @handle_memory_errors
    def analyze_processes(self, progress_callback=None):
        """
        Extract process list from memory dump
        
        Args:
            progress_callback: Optional callback(value, message)
        
        Returns:
            list: List of process info dictionaries
        
        Raises:
            DependencyError: If volatility3 is not available
            MemoryDumpError: If process extraction fails
        """
        if not is_available('volatility3'):
            raise DependencyError(
                'volatility3',
                'pip install volatility3',
                "Volatility3 required for process analysis"
            )
        
        # Initialize progress tracker
        tracker = ProgressTracker(progress_callback)
        tracker.start("Extracting process list...")
        
        logger.info("Extracting process list from memory...")
        
        try:
            ctx = self._create_context()
            
            # Get appropriate plugin based on OS
            if self.profile == "Windows":
                plugin = self._get_plugin(ctx, "windows.pslist.PsList")
            elif self.profile == "Linux":
                plugin = self._get_plugin(ctx, "linux.pslist.PsList")
            else:
                plugin = self._get_plugin(ctx, "windows.pslist.PsList")
            
            if not plugin:
                raise MemoryDumpError(
                    "Could not load process list plugin",
                    {'profile': self.profile}
                )
            
            tracker.update(30, "Running process extraction...")
            
            # Run the plugin
            results = []
            count = 0
            
            for row in plugin.run():
                try:
                    process_info = {
                        'pid': row[1] if len(row) > 1 else 0,
                        'name': str(row[2]) if len(row) > 2 else "unknown",
                        'ppid': row[3] if len(row) > 3 else 0,
                        'threads': row[4] if len(row) > 4 else 0,
                        'handles': row[5] if len(row) > 5 else 0,
                        'create_time': str(row[7]) if len(row) > 7 else "unknown"
                    }
                    results.append(process_info)
                    count += 1
                    
                    # Update progress periodically
                    if count % 10 == 0:
                        tracker.update(
                            min(90, 30 + count),
                            f"Found {count} processes..."
                        )
                
                except Exception as e:
                    logger.debug(f"Error processing process entry: {e}")
                    continue
            
            self.processes = results
            logger.info(f"✓ Found {len(self.processes)} processes")
            tracker.complete(f"Extracted {len(self.processes)} processes")
            
            return results
        
        except MemoryDumpError:
            raise
        
        except Exception as e:
            logger.error(f"Process extraction failed: {e}")
            log_error_report(e, context={'profile': self.profile})
            raise MemoryDumpError(
                f"Failed to extract processes: {str(e)}",
                {'profile': self.profile}
            )
    
    @handle_memory_errors
    def analyze_files(self, progress_callback=None):
        """
        Extract file handles and cached files from memory
        
        Args:
            progress_callback: Optional callback(value, message)
        
        Returns:
            list: List of file info dictionaries
        
        Raises:
            DependencyError: If volatility3 is not available
            MemoryDumpError: If file extraction fails
        """
        if not is_available('volatility3'):
            raise DependencyError(
                'volatility3',
                'pip install volatility3',
                "Volatility3 required for file analysis"
            )
        
        # Initialize progress tracker
        tracker = ProgressTracker(progress_callback)
        tracker.start("Extracting file information...")
        
        logger.info("Extracting file information from memory...")
        
        try:
            ctx = self._create_context()
            
            # Get file scan plugin
            if self.profile == "Windows":
                plugin = self._get_plugin(ctx, "windows.filescan.FileScan")
            else:
                # Linux file extraction uses different methods
                logger.warning("Linux file extraction not fully implemented")
                plugin = None
            
            if not plugin:
                logger.warning("Could not load file scan plugin")
                tracker.complete("File scan plugin not available")
                return []
            
            tracker.update(30, "Running file scan...")
            
            # Run the plugin
            results = []
            count = 0
            
            for row in plugin.run():
                try:
                    file_info = {
                        'offset': hex(row[0]) if len(row) > 0 else "0x0",
                        'name': str(row[1]) if len(row) > 1 else "unknown",
                        'size': row[2] if len(row) > 2 else 0,
                        'access': str(row[3]) if len(row) > 3 else "unknown"
                    }
                    results.append(file_info)
                    count += 1
                    
                    # Update progress every 100 files
                    if count % 100 == 0:
                        progress_value = min(90, 30 + int(count / 100))
                        tracker.update(
                            progress_value,
                            f"Extracting files... {count}"
                        )
                    
                    # Limit to prevent excessive memory usage
                    if count >= 5000:
                        logger.warning("Reached file extraction limit (5000 files)")
                        break
                
                except Exception as e:
                    logger.debug(f"Error processing file entry: {e}")
                    continue
            
            self.files = results
            logger.info(f"✓ Found {len(self.files)} file references")
            tracker.complete(f"Extracted {len(self.files)} file references")
            
            return results
        
        except MemoryDumpError:
            raise
        
        except Exception as e:
            logger.error(f"File extraction failed: {e}")
            log_error_report(e, context={'profile': self.profile})
            raise MemoryDumpError(
                f"Failed to extract files: {str(e)}",
                {'profile': self.profile}
            )
    
    @handle_memory_errors
    def analyze_network(self, progress_callback=None):
        """
        Extract network connections from memory
        
        Args:
            progress_callback: Optional callback(value, message)
        
        Returns:
            list: List of network connection info dictionaries
        
        Raises:
            DependencyError: If volatility3 is not available
            MemoryDumpError: If network extraction fails
        """
        if not is_available('volatility3'):
            raise DependencyError(
                'volatility3',
                'pip install volatility3',
                "Volatility3 required for network analysis"
            )
        
        # Initialize progress tracker
        tracker = ProgressTracker(progress_callback)
        tracker.start("Extracting network connections...")
        
        logger.info("Extracting network connections from memory...")
        
        try:
            ctx = self._create_context()
            
            # Get network plugin
            if self.profile == "Windows":
                plugin = self._get_plugin(ctx, "windows.netscan.NetScan")
            elif self.profile == "Linux":
                plugin = self._get_plugin(ctx, "linux.netscan.NetScan")
            else:
                plugin = None
            
            if not plugin:
                logger.warning("Could not load network scan plugin")
                tracker.complete("Network scan plugin not available")
                return []
            
            tracker.update(30, "Running network scan...")
            
            # Run the plugin
            results = []
            count = 0
            
            for row in plugin.run():
                try:
                    conn_info = {
                        'offset': hex(row[0]) if len(row) > 0 else "0x0",
                        'protocol': str(row[1]) if len(row) > 1 else "unknown",
                        'local_addr': str(row[2]) if len(row) > 2 else "unknown",
                        'foreign_addr': str(row[3]) if len(row) > 3 else "unknown",
                        'state': str(row[4]) if len(row) > 4 else "unknown",
                        'pid': row[5] if len(row) > 5 else 0,
                        'owner': str(row[6]) if len(row) > 6 else "unknown"
                    }
                    results.append(conn_info)
                    count += 1
                    
                    # Update progress periodically
                    if count % 20 == 0:
                        tracker.update(
                            min(90, 30 + count * 3),
                            f"Found {count} connections..."
                        )
                
                except Exception as e:
                    logger.debug(f"Error processing network entry: {e}")
                    continue
            
            self.network_connections = results
            logger.info(f"✓ Found {len(self.network_connections)} network connections")
            tracker.complete(f"Extracted {len(self.network_connections)} connections")
            
            return results
        
        except MemoryDumpError:
            raise
        
        except Exception as e:
            logger.error(f"Network extraction failed: {e}")
            log_error_report(e, context={'profile': self.profile})
            raise MemoryDumpError(
                f"Failed to extract network connections: {str(e)}",
                {'profile': self.profile}
            )