# update_config_manager.py
from pathlib import Path

with open('core/config_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and update config file path (assuming it's referenced)
# Add after imports or in __init__:
if "dotty_config.json" in content and "Path(__file__)" not in content:
    # Add path calculation to __init__ or wherever config file is loaded
    content = content.replace(
        "'dotty_config.json'",
        "Path(__file__).parent.parent / 'dotty_config.json'"
    )
    
    # Make sure Path is imported
    if "from pathlib import Path" not in content:
        content = "from pathlib import Path\n" + content

with open('core/config_manager.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ Updated core/config_manager.py")