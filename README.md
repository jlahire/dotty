# dotty v2

dotty turns filesystems, disk images, and web sessions into interactive graphs you can explore in a browser. built for forensic analysis and general poking around.

## what it does

- scan a local directory and see everything as a graph
- load a forensic disk image (DD, RAW, E01) and browse its contents
- parse memory dumps with Volatility3
- mount and explore ISO images
- scan a URL and map all its resources
- open a live browser session — watch requests, cookies, console logs, and JS errors come in real-time, pause/resume whenever, and inspect any loaded file
- analyze browser history (Chrome, Firefox, Edge), email archives (PST/OST), and Windows prefetch files
- chat with the scan data via a local Ollama model

## setup

```bash
git clone https://github.com/jlahire/dotty.git
cd dotty
pip install -r requirements.txt
python main.py
```

open `http://localhost:8000`

## optional extras

```bash
# live browser sessions (interactive mode)
playwright install chromium

# forensic disk images
pip install pytsk3 dissect.target

# memory dumps
pip install volatility3

# ISO images
pip install pycdlib

# email archives
pip install pypff  # or: bash install_pypff.sh
```

## structure

```
dotty/
├── server.py       FastAPI backend + all routes
├── graph.py        graph model
├── chat.py         Ollama chat
├── main.py         entry point
├── scan/           scan backends
├── analyze/        artifact analyzers
└── static/         web UI
```

## license

AGPL-3.0 — see LICENSE
