"""
font_config.py - centralized font configuration for the entire application
"""

# Font scale factor - increase this to make all fonts larger
FONT_SCALE = 1.3

# Base font sizes
BASE_FONTS = {
    'title': 16,
    'subtitle': 12,
    'heading': 11,
    'label': 10,
    'text': 10,
    'button': 10,
    'small': 9,
    'tiny': 8,
    'code': 9,
    'tree': 9,
    'splash_title': 72,
    'splash_subtitle': 14,
    'splash_button': 10,
    'splash_desc': 8
}

# Calculate scaled fonts
FONTS = {key: int(size * FONT_SCALE) for key, size in BASE_FONTS.items()}

# Font families
FONT_FAMILIES = {
    'default': 'Arial',
    'code': 'Courier',
    'mono': 'Courier New'
}

def get_font(font_type, bold=False, italic=False):
    """Get a font tuple for tkinter"""
    family = FONT_FAMILIES['default']
    if font_type == 'code':
        family = FONT_FAMILIES['code']
    
    size = FONTS.get(font_type, FONTS['text'])
    
    style = []
    if bold:
        style.append('bold')
    if italic:
        style.append('italic')
    
    if style:
        return (family, size, ' '.join(style))
    else:
        return (family, size)

def get_code_font(size_type='code'):
    """Get monospace font for code display"""
    return (FONT_FAMILIES['mono'], FONTS.get(size_type, FONTS['code']))