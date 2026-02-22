"""
dotty v2 — forensic filesystem visualization
by jLaHire
"""

import webbrowser
import threading
import uvicorn

HOST = "127.0.0.1"
PORT = 8000

if __name__ == "__main__":
    threading.Timer(1.5, lambda: webbrowser.open(f"http://{HOST}:{PORT}")).start()
    uvicorn.run("server:app", host=HOST, port=PORT, reload=False)
