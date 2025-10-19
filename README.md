# Dotty - Filesystem Graph Visualization Tool

A forensic analysis tool that visualizes filesystem structures as interactive graphs.

## Features

- **Live Filesystem Analysis** - Scan and visualize any directory
- **Forensic Image Support** - Analyze DD, RAW, and E01 images
- **Memory Dump Analysis** - Parse memory dumps with Volatility3
- **Browser History** - Analyze browser data (Chrome, Firefox, Edge)
- **Email Analysis** - Parse PST/OST email archives
- **Git Integration** - Visualize repository structure and history
- **Zettelkasten Layout** - Focus-based graph visualization

## Installation

```bash
# Clone the repository
git clone https://github.com/jlahire/dotty.git
cd dotty

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

## Project Structure

dotty/
├── core/           # Core functionality (error handling, config, etc.)
├── models/         # Data models (FileNode, Graph, etc.)
├── scanning/       # File system scanning modules
├── analyzers/      # Forensic analyzers (memory, browser, etc.)
├── ui/             # User interface components
├── graph/          # Graph layout and linking algorithms
├── utils/          # Utility scripts
└── logs/           # Application logs and error reports

## Requirements

- Python 3.11+
- tkinter (usually bundled with Python)
- See `requirements.txt` for full list

## Optional Dependencies

For advanced features, install:

```bash
# Forensic image support
pip install pytsk3 dissect.target

# Memory analysis
pip install volatility3

# Email analysis
pip install pypff

# ISO support
pip install pycdlib
```

## Usage

1. Launch the application: `python main.py`
2. Choose analysis mode from the File menu
3. Select a folder, forensic image, or memory dump
4. Explore the graph visualization

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
