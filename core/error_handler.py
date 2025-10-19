"""
error_handler.py - Comprehensive error handling for Dotty

This module provides custom exception classes and error handling utilities
to replace generic try/except blocks throughout the application.
"""

import traceback
import logging
import sys
import io
from pathlib import Path
from datetime import datetime


# Configure logging with UTF-8 support for Windows
def setup_logging(log_file=None):
    """Set up logging to file and console with UTF-8 encoding support"""
    
    # Calculate path to project root
    if log_file is None:
        project_root = Path(__file__).parent.parent
        log_file = project_root / 'dotty_errors.log'
    
    # Create a UTF-8 capable stream handler for console output
    if sys.platform == 'win32':
        # On Windows, ensure we use UTF-8 encoding for console
        console_handler = logging.StreamHandler(
            io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        )
    else:
        # On Unix-like systems, use default StreamHandler
        console_handler = logging.StreamHandler()
    
    # Set up basic logging configuration
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            console_handler
        ]
    )
    return logging.getLogger('dotty')


logger = setup_logging()


# ============================================================================
# Custom Exception Classes
# ============================================================================

class DottyError(Exception):
    """Base exception for all Dotty errors"""
    def __init__(self, message, details=None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)
    
    def get_user_message(self):
        """Get user-friendly error message"""
        return self.message
    
    def get_detailed_message(self):
        """Get detailed error message for logging"""
        msg = f"{self.message}"
        if self.details:
            msg += f"\n\nDetails: {self.details}"
        return msg


class FileSystemError(DottyError):
    """Errors related to filesystem operations"""
    pass


class ForensicImageError(DottyError):
    """Errors related to forensic image processing"""
    pass


class MemoryDumpError(DottyError):
    """Errors related to memory dump analysis"""
    pass


class ISOImageError(DottyError):
    """Errors related to ISO image processing"""
    pass


class BrowserAnalysisError(DottyError):
    """Errors related to browser data analysis"""
    pass


class EmailAnalysisError(DottyError):
    """Errors related to email analysis"""
    pass


class PrefetchAnalysisError(DottyError):
    """Errors related to prefetch analysis"""
    pass


class DeviceCaptureError(DottyError):
    """Errors related to device capture operations"""
    pass


class GraphError(DottyError):
    """Errors related to graph operations"""
    pass


class DependencyError(DottyError):
    """Errors related to missing dependencies"""
    def __init__(self, library, install_command, message=None):
        self.library = library
        self.install_command = install_command
        msg = message or f"Required library '{library}' is not installed"
        super().__init__(msg, {'library': library, 'install': install_command})
    
    def get_user_message(self):
        return (f"{self.message}\n\n"
                f"Install with:\n{self.install_command}\n\n"
                f"Then restart the application.")


# ============================================================================
# Error Reporting
# ============================================================================

def generate_error_report(error, context=None):
    """
    Generate detailed error report
    
    Args:
        error: Exception object
        context: Additional context dictionary
    
    Returns:
        Formatted error report string
    """
    report = []
    report.append("="*60)
    report.append("DOTTY ERROR REPORT")
    report.append("="*60)
    report.append(f"Time: {datetime.now().isoformat()}")
    report.append(f"Error Type: {type(error).__name__}")
    report.append(f"Error Message: {str(error)}")
    
    if isinstance(error, DottyError) and error.details:
        report.append("\nError Details:")
        for key, value in error.details.items():
            report.append(f"  {key}: {value}")
    
    if context:
        report.append("\nContext:")
        for key, value in context.items():
            report.append(f"  {key}: {value}")
    
    report.append("\nTraceback:")
    report.append(traceback.format_exc())
    report.append("="*60)
    
    return "\n".join(report)


def log_error_report(error, context=None, save_to_file=True):
    """
    Log and optionally save error report
    
    Args:
        error: Exception object
        context: Additional context
        save_to_file: Save report to file
    
    Returns:
        Path to error report file (if saved)
    """
    report = generate_error_report(error, context)
    
    logger.error(f"\n{report}")
    
    if save_to_file:
        try:
            project_root = Path(__file__).parent.parent
            error_dir = project_root / 'logs' / 'error_reports'
            error_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            error_file = error_dir / f"error_{timestamp}.txt"
            
            with open(error_file, 'w', encoding='utf-8') as f:
                f.write(report)
            
            return error_file
        except Exception as e:
            logger.error(f"Failed to save error report: {e}")
            return None
    
    return None


# ============================================================================
# User-Friendly Error Messages
# ============================================================================

ERROR_MESSAGES = {
    'permission_denied': (
        "Permission Denied",
        "You don't have permission to access this file or directory.\n\n"
        "Try running the application with administrator/root privileges."
    ),
    'file_not_found': (
        "File Not Found",
        "The specified file or directory could not be found.\n\n"
        "Please check the path and try again."
    ),
    'corrupted_image': (
        "Corrupted Image",
        "The forensic image appears to be corrupted or incomplete.\n\n"
        "Try using a different image or check the image integrity."
    ),
    'unsupported_format': (
        "Unsupported Format",
        "This file format is not supported.\n\n"
        "Please convert to a supported format and try again."
    ),
    'missing_dependency': (
        "Missing Dependency",
        "A required library is not installed.\n\n"
        "Please install the missing dependency and restart."
    ),
    'disk_full': (
        "Disk Full",
        "Not enough disk space to complete the operation.\n\n"
        "Free up some space and try again."
    ),
    'network_error': (
        "Network Error",
        "Unable to connect to the specified resource.\n\n"
        "Check your network connection and try again."
    ),
}


def get_user_friendly_message(error_type):
    """Get user-friendly error message for error type"""
    return ERROR_MESSAGES.get(error_type, (
        "Unexpected Error",
        "An unexpected error occurred.\n\n"
        "Please check the error log for details."
    ))


# ============================================================================
# Error Handler Decorators
# ============================================================================

def handle_filesystem_errors(func):
    """Decorator for filesystem operation error handling"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except PermissionError as e:
            logger.error(f"Permission denied: {e}")
            raise FileSystemError(
                "Permission denied accessing file or directory",
                {'path': str(e), 'error': 'PermissionError'}
            )
        except FileNotFoundError as e:
            logger.error(f"File not found: {e}")
            raise FileSystemError(
                "File or directory not found",
                {'path': str(e), 'error': 'FileNotFoundError'}
            )
        except OSError as e:
            logger.error(f"OS error: {e}")
            raise FileSystemError(
                f"System error: {str(e)}",
                {'error': 'OSError', 'errno': e.errno}
            )
        except Exception as e:
            logger.error(f"Unexpected filesystem error: {e}", exc_info=True)
            raise FileSystemError(
                f"Unexpected error: {str(e)}",
                {'error': type(e).__name__}
            )
    return wrapper


def handle_forensic_errors(func):
    """Decorator for forensic image processing error handling"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ImportError as e:
            logger.error(f"Missing forensic library: {e}")
            lib_name = str(e).split("'")[1] if "'" in str(e) else "unknown"
            if 'pytsk3' in str(e):
                raise DependencyError('pytsk3', 'pip install pytsk3')
            elif 'dissect' in str(e):
                raise DependencyError('dissect', 'pip install dissect.target dissect.evidence')
            else:
                raise ForensicImageError(
                    f"Required forensic library not found: {lib_name}",
                    {'library': lib_name}
                )
        except Exception as e:
            logger.error(f"Forensic processing error: {e}", exc_info=True)
            raise ForensicImageError(
                f"Failed to process forensic image: {str(e)}",
                {'error': type(e).__name__}
            )
    return wrapper


def handle_memory_errors(func):
    """Decorator for memory dump analysis error handling"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ImportError as e:
            logger.error(f"Missing memory analysis library: {e}")
            raise DependencyError('volatility3', 'pip install volatility3')
        except Exception as e:
            logger.error(f"Memory analysis error: {e}", exc_info=True)
            raise MemoryDumpError(
                f"Failed to analyze memory dump: {str(e)}",
                {'error': type(e).__name__}
            )
    return wrapper


# ============================================================================
# Safe File Operations
# ============================================================================

def safe_file_read(file_path, max_size=None, encoding='utf-8'):
    """
    Safely read a file with proper error handling
    
    Args:
        file_path: Path to file
        max_size: Maximum bytes to read (None = all)
        encoding: Text encoding (None = binary)
    
    Returns:
        File content or None on error
    
    Raises:
        FileSystemError: On access or read errors
    """
    try:
        path = Path(file_path)
        
        if not path.exists():
            raise FileSystemError(f"File does not exist: {file_path}")
        
        if not path.is_file():
            raise FileSystemError(f"Not a file: {file_path}")
        
        mode = 'r' if encoding else 'rb'
        kwargs = {'encoding': encoding, 'errors': 'ignore'} if encoding else {}
        
        with open(path, mode, **kwargs) as f:
            if max_size:
                return f.read(max_size)
            return f.read()
    
    except PermissionError:
        raise FileSystemError(f"Permission denied: {file_path}")
    except OSError as e:
        raise FileSystemError(f"Cannot read file: {e}")
    except Exception as e:
        logger.error(f"Unexpected error reading {file_path}: {e}")
        raise FileSystemError(f"Failed to read file: {e}")


def safe_directory_scan(directory_path, recursive=True, follow_symlinks=False):
    """
    Safely scan a directory with proper error handling
    
    Args:
        directory_path: Path to directory
        recursive: Scan subdirectories
        follow_symlinks: Follow symbolic links
    
    Returns:
        List of Path objects
    
    Raises:
        FileSystemError: On access errors
    """
    try:
        path = Path(directory_path)
        
        if not path.exists():
            raise FileSystemError(f"Directory does not exist: {directory_path}")
        
        if not path.is_dir():
            raise FileSystemError(f"Not a directory: {directory_path}")
        
        items = []
        
        if recursive:
            for item in path.rglob('*'):
                try:
                    if not follow_symlinks and item.is_symlink():
                        continue
                    items.append(item)
                except (PermissionError, OSError):
                    logger.warning(f"Skipping inaccessible item: {item}")
                    continue
        else:
            for item in path.iterdir():
                try:
                    if not follow_symlinks and item.is_symlink():
                        continue
                    items.append(item)
                except (PermissionError, OSError):
                    logger.warning(f"Skipping inaccessible item: {item}")
                    continue
        
        return items
    
    except PermissionError:
        raise FileSystemError(f"Permission denied: {directory_path}")
    except OSError as e:
        raise FileSystemError(f"Cannot access directory: {e}")
    except Exception as e:
        logger.error(f"Unexpected error scanning {directory_path}: {e}")
        raise FileSystemError(f"Failed to scan directory: {e}")


def safe_file_write(file_path, content, encoding='utf-8', mode='w'):
    """
    Safely write to a file with proper error handling
    
    Args:
        file_path: Path to file
        content: Content to write
        encoding: Text encoding (None = binary)
        mode: Write mode ('w' or 'a')
    
    Returns:
        True on success
    
    Raises:
        FileSystemError: On write errors
    """
    try:
        path = Path(file_path)
        
        # Create parent directories if they don't exist
        path.parent.mkdir(parents=True, exist_ok=True)
        
        write_mode = mode if encoding else mode + 'b'
        kwargs = {'encoding': encoding} if encoding else {}
        
        with open(path, write_mode, **kwargs) as f:
            f.write(content)
        
        return True
    
    except PermissionError:
        raise FileSystemError(f"Permission denied: {file_path}")
    except OSError as e:
        raise FileSystemError(f"Cannot write file: {e}")
    except Exception as e:
        logger.error(f"Unexpected error writing {file_path}: {e}")
        raise FileSystemError(f"Failed to write file: {e}")