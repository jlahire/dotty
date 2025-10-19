# update_all_imports.py
"""
Master script to update all import statements after reorganization
"""
from pathlib import Path
import re

# Define import mappings
IMPORT_MAPPINGS = {
    # Core modules
    'from error_handler import': 'from core.error_handler import',
    'from dependency_manager import': 'from core.dependency_manager import',
    'from config_manager import': 'from core.config_manager import',
    'from progress_manager import': 'from core.progress_manager import',
    'import error_handler': 'import core.error_handler',
    'import dependency_manager': 'import core.dependency_manager',
    'import config_manager': 'import core.config_manager',
    'import progress_manager': 'import core.progress_manager',
    
    # Model modules
    'from file_stuff import': 'from models.file_stuff import',
    'from graph_stuff import': 'from models.graph_stuff import',
    'from case_manager import': 'from models.case_manager import',
    'import file_stuff': 'import models.file_stuff',
    'import graph_stuff': 'import models.graph_stuff',
    'import case_manager': 'import models.case_manager',
    
    # Scanning modules
    'from scanner import': 'from scanning.scanner import',
    'from forensic_scanner import': 'from scanning.forensic_scanner import',
    'from device_capture import': 'from scanning.device_capture import',
    'import scanner': 'import scanning.scanner',
    'import forensic_scanner': 'import scanning.forensic_scanner',
    'import device_capture': 'import scanning.device_capture',
    
    # Analyzer modules
    'from forensic_analyzer import': 'from analyzers.forensic_analyzer import',
    'from memory_analyzer import': 'from analyzers.memory_analyzer import',
    'from iso_analyzer import': 'from analyzers.iso_analyzer import',
    'from browser_analyzer import': 'from analyzers.browser_analyzer import',
    'from email_analyzer import': 'from analyzers.email_analyzer import',
    'from prefetch_analyzer import': 'from analyzers.prefetch_analyzer import',
    'from git_analyzer import': 'from analyzers.git_analyzer import',
    'import forensic_analyzer': 'import analyzers.forensic_analyzer',
    'import memory_analyzer': 'import analyzers.memory_analyzer',
    'import iso_analyzer': 'import analyzers.iso_analyzer',
    'import browser_analyzer': 'import analyzers.browser_analyzer',
    'import email_analyzer': 'import analyzers.email_analyzer',
    'import prefetch_analyzer': 'import analyzers.prefetch_analyzer',
    'import git_analyzer': 'import analyzers.git_analyzer',
    
    # UI modules
    'from display import': 'from ui.display import',
    'from info_panel import': 'from ui.info_panel import',
    'from tree_view import': 'from ui.tree_view import',
    'from filter_panel import': 'from ui.filter_panel import',
    'from timeline_panel import': 'from ui.timeline_panel import',
    'from heatmap_panel import': 'from ui.heatmap_panel import',
    'from font_config import': 'from ui.font_config import',
    'from splash_screen import': 'from ui.splash_screen import',
    'import display': 'import ui.display',
    'import info_panel': 'import ui.info_panel',
    'import tree_view': 'import ui.tree_view',
    'import filter_panel': 'import ui.filter_panel',
    'import timeline_panel': 'import ui.timeline_panel',
    'import heatmap_panel': 'import ui.heatmap_panel',
    'import font_config': 'import ui.font_config',
    'import splash_screen': 'import ui.splash_screen',
    
    # UI Dialog modules
    'from case_dialog import': 'from ui.dialogs.case_dialog import',
    'from filter_dialog import': 'from ui.dialogs.filter_dialog import',
    'from file_preview import': 'from ui.dialogs.file_preview import',
    'from device_capture_dialog import': 'from ui.dialogs.device_capture_dialog import',
    'import case_dialog': 'import ui.dialogs.case_dialog',
    'import filter_dialog': 'import ui.dialogs.filter_dialog',
    'import file_preview': 'import ui.dialogs.file_preview',
    'import device_capture_dialog': 'import ui.dialogs.device_capture_dialog',
    
    # Graph modules
    'from layout import': 'from graph.layout import',
    'from linker import': 'from graph.linker import',
    'import layout': 'import graph.layout',
    'import linker': 'import graph.linker',
}

def update_imports_in_file(filepath):
    """Update imports in a single file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Apply all mappings
        for old_import, new_import in IMPORT_MAPPINGS.items():
            content = content.replace(old_import, new_import)
        
        # Only write if changed
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
    
    except Exception as e:
        print(f"  ✗ Error updating {filepath}: {e}")
        return False

def update_all_imports():
    """Update imports in all Python files"""
    directories = ['core', 'models', 'scanning', 'analyzers', 'ui', 'graph', 'utils']
    
    updated_files = []
    
    # Update main.py separately
    print("Updating main.py...")
    if update_imports_in_file('main.py'):
        updated_files.append('main.py')
        print("  ✓ main.py updated")
    else:
        print("  - main.py (no changes)")
    
    # Update all files in new directories
    for directory in directories:
        dir_path = Path(directory)
        if not dir_path.exists():
            print(f"⚠ Directory not found: {directory}")
            continue
        
        print(f"\nUpdating files in {directory}/...")
        py_files = list(dir_path.rglob('*.py'))
        
        for py_file in py_files:
            if py_file.name == '__init__.py':
                continue
            
            if update_imports_in_file(py_file):
                updated_files.append(str(py_file))
                print(f"  ✓ {py_file.name}")
            else:
                print(f"  - {py_file.name} (no changes)")
    
    print(f"\n{'='*60}")
    print(f"Updated {len(updated_files)} files:")
    for f in updated_files:
        print(f"  • {f}")
    print(f"{'='*60}")

if __name__ == '__main__':
    print("Updating all import statements...")
    print("="*60)
    update_all_imports()
    print("\n✓ Import update complete!")