"""
scanner.py - walks through folders and finds files
imports: file_stuff.py for FileNode

REFACTORED: Now uses error_handler, dependency_manager, and progress_manager
"""

from pathlib import Path
from models.file_stuff import FileNode, DeletedFileNode
from analyzers.git_analyzer import GitAnalyzer

# Import centralized management modules
from core.error_handler import (
    FileSystemError,
    handle_filesystem_errors,
    safe_directory_scan,
    log_error_report,
    logger
)
from core.dependency_manager import is_available, check_feature
from core.progress_manager import ProgressTracker


@handle_filesystem_errors
def scan_folder(folder_path, progress_callback=None):
    """
    Scan a folder and return list of FileNode objects and git_analyzer
    
    Args:
        folder_path: Path to folder to scan
        progress_callback: Optional callback(value, message) for progress updates
    
    Returns:
        tuple: (list of FileNode objects, GitAnalyzer instance or None)
    
    Raises:
        FileSystemError: If folder doesn't exist or can't be accessed
    """
    # Initialize progress tracker
    tracker = ProgressTracker(progress_callback)
    tracker.start("Initializing scan...")
    
    folder = Path(folder_path)
    nodes = []
    git_analyzer = None
    
    # Validate folder exists
    if not folder.exists():
        error_msg = f"Folder does not exist: {folder_path}"
        logger.error(error_msg)
        raise FileSystemError(
            error_msg,
            {'path': str(folder_path), 'operation': 'scan_folder'}
        )
    
    if not folder.is_dir():
        error_msg = f"Path is not a directory: {folder_path}"
        logger.error(error_msg)
        raise FileSystemError(
            error_msg,
            {'path': str(folder_path), 'operation': 'scan_folder'}
        )
    
    try:
        # Check for git repository
        tracker.update(0, "Checking for git repository...")
        logger.info(f"Scanning folder: {folder_path}")
        
        git_analyzer = GitAnalyzer(folder_path)
        if git_analyzer.is_git_repo:
            logger.info("Git repository detected, analyzing...")
            tracker.update(5, "Analyzing git history...")
            
            try:
                git_analyzer.analyze()
                logger.info("Git analysis complete")
            except Exception as e:
                logger.warning(f"Git analysis failed: {e}")
                # Continue without git info rather than failing completely
                git_analyzer = None
        
        tracker.update(10, "Scanning files...")
        
        # Use safe directory scan with error handling
        try:
            all_items = safe_directory_scan(
                folder_path,
                recursive=True,
                follow_symlinks=False
            )
        except FileSystemError as e:
            logger.error(f"Directory scan failed: {e}")
            raise
        
        total_items = len(all_items)
        logger.info(f"Found {total_items} items to process")
        
        # Process each item
        processed = 0
        skipped_permission = 0
        skipped_other = 0
        
        for idx, item in enumerate(all_items):
            try:
                # Get git info for this file if available
                git_info = None
                if git_analyzer and git_analyzer.is_git_repo:
                    try:
                        relative_path = str(item.relative_to(folder))
                        git_info = git_analyzer.get_file_git_info(relative_path)
                    except Exception as e:
                        logger.debug(f"Could not get git info for {item}: {e}")
                
                # Create FileNode
                node = FileNode(item, git_info=git_info)
                nodes.append(node)
                processed += 1
                
                # Update progress (10-60% for scanning)
                if idx % 10 == 0:
                    progress = 10 + int((idx / total_items) * 50)
                    tracker.update(
                        progress,
                        f"Scanning... {processed}/{total_items} files"
                    )
            
            except PermissionError:
                skipped_permission += 1
                logger.debug(f"Permission denied: {item}")
                continue
            
            except Exception as e:
                skipped_other += 1
                logger.debug(f"Error processing {item}: {e}")
                continue
        
        tracker.update(60, "Processing deleted files...")
        
        # Add deleted files from git
        deleted_count = 0
        if git_analyzer and git_analyzer.is_git_repo:
            try:
                for file_path, git_info in git_analyzer.deleted_files.items():
                    try:
                        deleted_node = DeletedFileNode(git_info, folder_path)
                        nodes.append(deleted_node)
                        deleted_count += 1
                    except Exception as e:
                        logger.debug(f"Error creating deleted node for {file_path}: {e}")
                        continue
                
                logger.info(f"Added {deleted_count} deleted files from git history")
            
            except Exception as e:
                logger.warning(f"Error processing deleted files: {e}")
        
        # Log summary
        logger.info(f"Scan complete: {processed} files processed, "
                   f"{skipped_permission} permission denied, "
                   f"{skipped_other} other errors, "
                   f"{deleted_count} deleted files")
        
        if skipped_permission > 0:
            logger.warning(f"Skipped {skipped_permission} files due to permission errors")
        
        tracker.update(65, f"Found {len(nodes)} total items")
        
        # Complete the scan
        completion_msg = f"Scan complete! Found {len(nodes)} items"
        tracker.complete(completion_msg)
        logger.info(completion_msg)
        
        return nodes, git_analyzer
    
    except FileSystemError:
        # Re-raise FileSystemError as-is
        raise
    
    except Exception as e:
        # Log unexpected errors and wrap in FileSystemError
        error_context = {
            'operation': 'scan_folder',
            'path': str(folder_path),
            'items_processed': len(nodes)
        }
        log_error_report(e, context=error_context)
        
        raise FileSystemError(
            f"Unexpected error during folder scan: {str(e)}",
            error_context
        )