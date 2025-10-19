#!/usr/bin/env python3
"""
update_fonts_auto.py - Automatically update all Python files to use font_config
Run this script in your project directory to update all files at once
"""

import re
from pathlib import Path

# Font mapping rules
FONT_REPLACEMENTS = {
    r"font=\('Arial', 18, 'bold'\)": "font=get_font('title', bold=True)",
    r"font=\('Arial', 16, 'bold'\)": "font=get_font('title', bold=True)",
    r"font=\('Arial', 14, 'bold'\)": "font=get_font('subtitle', bold=True)",
    r"font=\('Arial', 14\)": "font=get_font('subtitle')",
    r"font=\('Arial', 12, 'bold'\)": "font=get_font('heading', bold=True)",
    r"font=\('Arial', 11, 'bold'\)": "font=get_font('heading', bold=True)",
    r"font=\('Arial', 10, 'bold'\)": "font=get_font('button', bold=True)",
    r"font=\('Arial', 10\)": "font=get_font('text')",
    r"font=\('Arial', 9, 'bold'\)": "font=get_font('label', bold=True)",
    r"font=\('Arial', 9, 'italic'\)": "font=get_font('small', italic=True)",
    r"font=\('Arial', 9\)": "font=get_font('small')",
    r"font=\('Arial', 8\)": "font=get_font('tiny')",
    r"font=\('Courier', 10\)": "font=get_code_font('code')",
    r"font=\('Courier', 9\)": "font=get_code_font('code')",
    r"font=\('Courier New', \d+\)": "font=get_code_font('code')",
}

# Files to update (UI files only)
UI_FILES = [
    'info_panel.py',
    'filter_panel.py', 
    'timeline_panel.py',
    'tree_view.py',
    'device_capture_dialog.py',
    'display.py'
]

def update_file(filepath):
    """Update a single file with font replacements"""
    print(f"Processing {filepath}...")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Check if already has import
        has_import = 'from ui.font_config import' in content
        
        # Apply replacements
        for pattern, replacement in FONT_REPLACEMENTS.items():
            content = re.sub(pattern, replacement, content)
        
        # Add import if needed and changes were made
        if not has_import and content != original_content:
            # Find the import section
            import_match = re.search(r'(import tkinter.*?\n)', content)
            if import_match:
                # Add after tkinter import
                import_line = import_match.group(0)
                new_import = import_line + "from ui.font_config import get_font, get_code_font, FONTS\n"
                content = content.replace(import_line, new_import, 1)
            else:
                # Add at the beginning after docstring
                lines = content.split('\n')
                insert_pos = 0
                for i, line in enumerate(lines):
                    if line.strip().startswith('"""') or line.strip().startswith("'''"):
                        # Find end of docstring
                        for j in range(i+1, len(lines)):
                            if '"""' in lines[j] or "'''" in lines[j]:
                                insert_pos = j + 1
                                break
                        break
                
                if insert_pos > 0:
                    lines.insert(insert_pos, "from ui.font_config import get_font, get_code_font, FONTS")
                    content = '\n'.join(lines)
        
        # Write back if changed
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  ✓ Updated {filepath}")
            return True
        else:
            print(f"  - No changes needed for {filepath}")
            return False
            
    except Exception as e:
        print(f"  ✗ Error updating {filepath}: {e}")
        return False

def main():
    """Main function to update all files"""
    print("=" * 60)
    print("Dotty Font Configuration Auto-Updater")
    print("=" * 60)
    print()
    
    current_dir = Path('.')
    updated_count = 0
    
    # Check if font_config.py exists
    if not (current_dir / 'font_config.py').exists():
        print("ERROR: font_config.py not found!")
        print("Please create font_config.py first.")
        return
    
    print("Found font_config.py ✓")
    print()
    
    # Update each UI file
    for filename in UI_FILES:
        filepath = current_dir / filename
        
        if filepath.exists():
            if update_file(filepath):
                updated_count += 1
        else:
            print(f"  ⚠ {filename} not found, skipping...")
    
    print()
    print("=" * 60)
    print(f"Complete! Updated {updated_count} file(s)")
    print("=" * 60)
    print()
    print("To adjust font sizes, edit FONT_SCALE in font_config.py")
    print()

if __name__ == '__main__':
    main()