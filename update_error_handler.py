# update_error_handler.py
from pathlib import Path

# Read the file
with open('core/error_handler.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Update paths
content = content.replace(
    "def setup_logging(log_file='dotty_errors.log'):",
    "def setup_logging(log_file=None):"
)

# Add path calculation at the top of setup_logging function
setup_function = """def setup_logging(log_file=None):
    \"\"\"Set up logging to file and console with UTF-8 encoding support\"\"\"
    
    # Calculate path to project root
    if log_file is None:
        project_root = Path(__file__).parent.parent
        log_file = project_root / 'dotty_errors.log'
    """

content = content.replace(
    '''def setup_logging(log_file=None):
    """Set up logging to file and console with UTF-8 encoding support"""
    ''',
    setup_function
)

# Update error_reports path
content = content.replace(
    "error_dir = Path('error_reports')",
    "project_root = Path(__file__).parent.parent\n            error_dir = project_root / 'logs' / 'error_reports'"
)

# Write back
with open('core/error_handler.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ Updated core/error_handler.py")