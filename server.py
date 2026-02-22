"""
dotty v2 — server
by jLaHire

fastapi app, all routes, websocket, static files.
"""

from __future__ import annotations

import asyncio
import logging
import mimetypes
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from graph import Graph
from scan.filesystem import scan_directory
from chat import OllamaChat

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Dotty v2")

graph = Graph()
ws_clients: list[WebSocket] = []
chat = OllamaChat()
active_session = None


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_clients.append(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_clients.remove(ws)


async def broadcast(msg: dict):
    for ws in ws_clients[:]:
        try:
            await ws.send_json(msg)
        except Exception:
            ws_clients.remove(ws)


# --- scans ---

@app.post("/api/scan/live")
async def scan_live(body: dict):
    path = body.get("path", "")
    if not path or not Path(path).is_dir():
        return JSONResponse({"error": "Invalid directory path"}, 400)

    async def run():
        global graph
        graph = Graph()
        graph.root_path = str(Path(path).resolve())

        loop = asyncio.get_event_loop()

        def progress(pct, msg):
            asyncio.run_coroutine_threadsafe(
                broadcast({"type": "progress", "percent": pct, "message": msg}), loop)

        nodes = await loop.run_in_executor(None, lambda: scan_directory(path, progress))
        for node in nodes:
            graph.add_node(node)

        try:
            from analyze.git import analyze_git, is_git_repo
            if is_git_repo(graph.root_path):
                for node in analyze_git(graph.root_path):
                    graph.add_node(node)
        except Exception:
            pass

        graph.link_all()
        focus = graph.auto_focus()
        await broadcast({"type": "scan_complete", "stats": graph.get_stats(), "focus": focus})

    asyncio.ensure_future(run())
    return {"status": "scanning"}


@app.post("/api/scan/forensic")
async def scan_forensic(body: dict):
    path = body.get("path", "")
    if not path or not Path(path).is_file():
        return JSONResponse({"error": "Invalid image path"}, 400)

    async def run():
        global graph
        graph = Graph()
        graph.root_path = path

        loop = asyncio.get_event_loop()

        def progress(pct, msg):
            asyncio.run_coroutine_threadsafe(
                broadcast({"type": "progress", "percent": pct, "message": msg}), loop)

        try:
            from scan.forensic import scan_forensic_image
            nodes = await loop.run_in_executor(None, lambda: scan_forensic_image(path, progress))
            for node in nodes:
                graph.add_node(node)
        except ImportError:
            await broadcast({"type": "scan_complete", "error": "pytsk3/dissect not installed"})
            return
        except Exception as e:
            await broadcast({"type": "scan_complete", "error": str(e)})
            return

        graph.link_all()
        focus = graph.auto_focus()
        await broadcast({"type": "scan_complete", "stats": graph.get_stats(), "focus": focus})

    asyncio.ensure_future(run())
    return {"status": "scanning"}


@app.post("/api/scan/memory")
async def scan_memory(body: dict):
    path = body.get("path", "")
    if not path or not Path(path).is_file():
        return JSONResponse({"error": "Invalid dump path"}, 400)

    async def run():
        global graph
        graph = Graph()
        graph.root_path = path

        loop = asyncio.get_event_loop()

        try:
            from scan.memory import scan_memory_dump
            nodes = await loop.run_in_executor(None, lambda: scan_memory_dump(path))
            for node in nodes:
                graph.add_node(node)
        except ImportError:
            await broadcast({"type": "scan_complete", "error": "volatility3 not installed"})
            return
        except Exception as e:
            await broadcast({"type": "scan_complete", "error": str(e)})
            return

        graph.link_all()
        focus = graph.auto_focus()
        await broadcast({"type": "scan_complete", "stats": graph.get_stats(), "focus": focus})

    asyncio.ensure_future(run())
    return {"status": "scanning"}


@app.post("/api/scan/web")
async def scan_web(body: dict):
    url = body.get("path", "")
    if not url:
        return JSONResponse({"error": "No URL provided"}, 400)

    async def run():
        global graph
        graph = Graph()
        if not url.startswith(("http://", "https://")):
            graph.root_path = "https://" + url
        else:
            graph.root_path = url

        loop = asyncio.get_event_loop()

        def progress(pct, msg):
            asyncio.run_coroutine_threadsafe(
                broadcast({"type": "progress", "percent": pct, "message": msg}), loop)

        try:
            from scan.web import scan_webpage, fetch_page_text
            nodes = await loop.run_in_executor(None, lambda: scan_webpage(url, progress))
            for node in nodes:
                graph.add_node(node)
            graph.web_content = await loop.run_in_executor(None, lambda: fetch_page_text(url))
        except Exception as e:
            await broadcast({"type": "scan_complete", "error": str(e)})
            return

        try:
            from analyze.web_security import analyze_web_security
            sec_nodes = analyze_web_security(graph)
            for node in sec_nodes:
                graph.add_node(node)
        except Exception as e:
            log.warning(f"Security analysis failed: {e}")

        graph.link_all()
        focus = graph.auto_focus()
        await broadcast({"type": "scan_complete", "stats": graph.get_stats(), "focus": focus})

    asyncio.ensure_future(run())
    return {"status": "scanning"}


@app.post("/api/scan/web-interactive")
async def scan_web_interactive(body: dict):
    global active_session
    url = body.get("path", "")
    if not url:
        return JSONResponse({"error": "No URL provided"}, 400)
    if active_session is not None:
        return JSONResponse({"error": "Interactive session already active"}, 409)

    async def run():
        global graph, active_session
        graph = Graph()
        if not url.startswith(("http://", "https://")):
            graph.root_path = "https://" + url
        else:
            graph.root_path = url

        loop = asyncio.get_event_loop()

        def on_event(evt):
            asyncio.run_coroutine_threadsafe(broadcast(evt), loop)

        try:
            from scan.web_interactive import InteractiveSession
            session = InteractiveSession(url, on_event=on_event)
            active_session = session
            await loop.run_in_executor(None, session.start)

            nodes = session.to_nodes()
            for node in nodes:
                graph.add_node(node)

            try:
                from analyze.web_security import analyze_web_security
                sec_nodes = analyze_web_security(graph)
                for node in sec_nodes:
                    graph.add_node(node)
            except Exception as e:
                log.warning(f"Security analysis failed: {e}")

            graph.link_all()
            focus = graph.auto_focus()
            await broadcast({"type": "scan_complete", "stats": graph.get_stats(), "focus": focus})
        except ImportError:
            await broadcast({"type": "scan_complete",
                             "error": "playwright not installed. Run: pip install playwright && playwright install chromium"})
        except Exception as e:
            await broadcast({"type": "scan_complete", "error": str(e)})
        finally:
            active_session = None

    asyncio.ensure_future(run())
    return {"status": "scanning"}


@app.post("/api/scan/web-interactive/stop")
async def stop_web_interactive():
    global active_session
    if active_session is None:
        return JSONResponse({"error": "No active session"}, 404)
    active_session.stop()
    return {"status": "stopping"}


@app.post("/api/scan/web-interactive/pause")
async def pause_web_interactive():
    global active_session
    if active_session is None:
        return JSONResponse({"error": "No active session"}, 404)
    active_session.pause()
    return {"status": "paused"}


@app.post("/api/scan/web-interactive/resume")
async def resume_web_interactive():
    global active_session
    if active_session is None:
        return JSONResponse({"error": "No active session"}, 404)
    active_session.resume()
    return {"status": "resumed"}


@app.post("/api/scan/iso")
async def scan_iso(body: dict):
    path = body.get("path", "")
    if not path or not Path(path).is_file():
        return JSONResponse({"error": "Invalid ISO path"}, 400)

    async def run():
        global graph
        graph = Graph()
        graph.root_path = path

        loop = asyncio.get_event_loop()

        try:
            from scan.iso import scan_iso_image
            nodes = await loop.run_in_executor(None, lambda: scan_iso_image(path))
            for node in nodes:
                graph.add_node(node)
        except ImportError:
            await broadcast({"type": "scan_complete", "error": "pycdlib not installed"})
            return
        except Exception as e:
            await broadcast({"type": "scan_complete", "error": str(e)})
            return

        graph.link_all()
        focus = graph.auto_focus()
        await broadcast({"type": "scan_complete", "stats": graph.get_stats(), "focus": focus})

    asyncio.ensure_future(run())
    return {"status": "scanning"}


# --- analysis ---

@app.post("/api/analyze/browser")
async def analyze_browser_route(body: dict):
    path = body.get("path", "")
    if not path or not Path(path).is_dir():
        return JSONResponse({"error": "Invalid path"}, 400)

    try:
        from analyze.browser import analyze_browser
        loop = asyncio.get_event_loop()
        nodes = await loop.run_in_executor(None, lambda: analyze_browser(path))
        for node in nodes:
            graph.add_node(node)
        graph.link_all()
        return {"status": "ok", "added": len(nodes)}
    except ImportError:
        return JSONResponse({"error": "Browser analysis dependencies missing"}, 500)


@app.post("/api/analyze/email")
async def analyze_email_route(body: dict):
    path = body.get("path", "")
    if not path or not Path(path).is_dir():
        return JSONResponse({"error": "Invalid path"}, 400)

    try:
        from analyze.email import analyze_email
        loop = asyncio.get_event_loop()
        nodes = await loop.run_in_executor(None, lambda: analyze_email(path))
        for node in nodes:
            graph.add_node(node)
        graph.link_all()
        return {"status": "ok", "added": len(nodes)}
    except ImportError:
        return JSONResponse({"error": "Email analysis dependencies missing"}, 500)


@app.post("/api/analyze/prefetch")
async def analyze_prefetch_route(body: dict):
    path = body.get("path", "")
    if not path or not Path(path).is_dir():
        return JSONResponse({"error": "Invalid path"}, 400)

    try:
        from analyze.prefetch import analyze_prefetch
        loop = asyncio.get_event_loop()
        nodes = await loop.run_in_executor(None, lambda: analyze_prefetch(path))
        for node in nodes:
            graph.add_node(node)
        graph.link_all()
        return {"status": "ok", "added": len(nodes)}
    except ImportError:
        return JSONResponse({"error": "Prefetch analysis dependencies missing"}, 500)


# --- graph ---

@app.get("/api/graph")
async def get_graph(focus: str | None = None, hops: int = 3):
    f = focus or graph.auto_focus()
    return graph.to_cytoscape(f, hops)


@app.get("/api/graph/node/{node_id}")
async def get_node(node_id: str):
    node = graph.nodes.get(node_id)
    if not node:
        return JSONResponse({"error": "Not found"}, 404)
    return {
        "id": node.id, "name": node.name, "path": node.path,
        "kind": node.kind, "info": node.info,
        "is_hidden": node.is_hidden, "is_deleted": node.is_deleted,
        "is_system": node.is_system,
        "connections": len(graph.adj.get(node.id, [])),
    }


@app.get("/api/graph/node/{node_id}/preview")
async def preview_node(node_id: str):
    node = graph.nodes.get(node_id)
    if not node:
        return JSONResponse({"error": "Not found"}, 404)

    # URL-based web nodes (from web/interactive scans) — preview via iframe
    if node.path.startswith(("http://", "https://")):
        mime = mimetypes.guess_type(node.name)[0] or "text/html"
        return {"type": "web", "mime": mime, "name": node.name, "url": node.path}

    p = Path(node.path)
    if not p.is_file():
        return JSONResponse({"error": "Not a readable file", "path": node.path}, 400)

    mime = mimetypes.guess_type(node.path)[0] or "application/octet-stream"
    is_text = mime.startswith("text/") or node.info.get("extension", "") in (
        ".py", ".js", ".json", ".css", ".html", ".md", ".txt", ".csv",
        ".xml", ".yaml", ".yml", ".ini", ".cfg", ".conf", ".sh", ".bat",
        ".c", ".cpp", ".h", ".java", ".go", ".rs", ".rb", ".php", ".ts",
        ".log", ".env", ".toml", ".sql", ".jsx", ".tsx", ".vue", ".svelte",
    )
    is_image = mime.startswith("image/")
    is_web_renderable = node.info.get("extension", "") in (".html", ".htm", ".svg")

    if is_web_renderable:
        return {"type": "web", "mime": mime, "name": node.name,
                "url": f"/api/graph/node/{node_id}/download",
                "size": p.stat().st_size}

    if is_image:
        return {"type": "image", "mime": mime, "name": node.name,
                "url": f"/api/graph/node/{node_id}/download"}

    if is_text:
        try:
            size = p.stat().st_size
            if size > 500_000:
                content = p.read_text(errors="ignore")[:500_000] + "\n\n[truncated]"
            else:
                content = p.read_text(errors="ignore")
            return {"type": "text", "mime": mime, "name": node.name,
                    "content": content, "size": size}
        except Exception as e:
            return JSONResponse({"error": str(e)}, 500)

    return {"type": "binary", "mime": mime, "name": node.name,
            "size": p.stat().st_size,
            "url": f"/api/graph/node/{node_id}/download"}


@app.get("/api/graph/node/{node_id}/download")
async def download_node(node_id: str):
    node = graph.nodes.get(node_id)
    if not node:
        return JSONResponse({"error": "Not found"}, 404)

    p = Path(node.path)
    if not p.is_file():
        return JSONResponse({"error": "Not a downloadable file"}, 400)

    return FileResponse(str(p), filename=node.name)


@app.get("/api/graph/security")
async def get_security():
    findings = []
    cookies = []
    summary = None
    for node in graph.nodes.values():
        if node.kind == "web_finding":
            entry = {"id": node.id, "name": node.name, **node.info}
            if node.info.get("category") == "summary":
                summary = entry
            else:
                findings.append(entry)
        elif node.kind == "web_cookie":
            cookies.append({"id": node.id, "name": node.name, **node.info})

    by_severity = {"critical": [], "warning": [], "info": [], "pass": []}
    for f in findings:
        sev = f.get("severity", "info")
        by_severity.setdefault(sev, []).append(f)

    return {"summary": summary, "by_severity": by_severity, "cookies": cookies}


@app.get("/api/graph/web-files")
async def get_web_files():
    file_kinds = {"web_page", "web_script", "web_style", "web_image"}
    results = []
    for node in graph.nodes.values():
        if node.kind not in file_kinds:
            continue
        if not node.path.startswith(("http://", "https://")):
            continue
        results.append({
            "id": node.id,
            "name": node.name,
            "kind": node.kind,
            "path": node.path,
            "info": node.info,
        })
    results.sort(key=lambda x: (x["kind"], x["name"].lower()))
    return results


@app.get("/api/graph/search")
async def search_graph(q: str = ""):
    if not q:
        return []
    return graph.search(q)


@app.get("/api/graph/tree")
async def get_tree():
    return graph.get_tree()


@app.get("/api/graph/stats")
async def get_stats():
    return graph.get_stats()


@app.get("/api/graph/export")
async def export_graph():
    nodes = []
    for n in graph.nodes.values():
        nodes.append({
            "id": n.id, "name": n.name, "path": n.path,
            "kind": n.kind, "info": n.info,
            "is_hidden": n.is_hidden, "is_deleted": n.is_deleted,
            "is_system": n.is_system,
        })
    return {"nodes": nodes, "links": graph.links, "stats": graph.get_stats()}


# --- tags / favorites ---

@app.post("/api/graph/node/{node_id}/tag")
async def tag_node(node_id: str, body: dict):
    if node_id not in graph.nodes:
        return JSONResponse({"error": "Not found"}, 404)
    tag = body.get("tag", "").strip()
    if not tag:
        return JSONResponse({"error": "Empty tag"}, 400)
    graph.tags[node_id].add(tag)
    return {"tags": list(graph.tags[node_id])}


@app.delete("/api/graph/node/{node_id}/tag")
async def untag_node(node_id: str, body: dict):
    if node_id not in graph.nodes:
        return JSONResponse({"error": "Not found"}, 404)
    tag = body.get("tag", "").strip()
    graph.tags[node_id].discard(tag)
    return {"tags": list(graph.tags[node_id])}


@app.post("/api/graph/node/{node_id}/favorite")
async def favorite_node(node_id: str):
    if node_id not in graph.nodes:
        return JSONResponse({"error": "Not found"}, 404)
    if node_id in graph.favorites:
        graph.favorites.discard(node_id)
        return {"favorite": False}
    graph.favorites.add(node_id)
    return {"favorite": True}


@app.get("/api/graph/favorites")
async def get_favorites():
    results = []
    for nid in graph.favorites:
        node = graph.nodes.get(nid)
        if node:
            results.append({
                "id": node.id, "name": node.name, "path": node.path,
                "kind": node.kind, "tags": list(graph.tags.get(nid, [])),
            })
    return results


@app.get("/api/graph/tagged")
async def get_tagged(tag: str = ""):
    results = []
    for nid, tags in graph.tags.items():
        if tag and tag not in tags:
            continue
        if not tags:
            continue
        node = graph.nodes.get(nid)
        if node:
            results.append({
                "id": node.id, "name": node.name, "path": node.path,
                "kind": node.kind, "tags": list(tags),
            })
    return results


@app.get("/api/graph/tags")
async def get_all_tags():
    all_tags = set()
    for tags in graph.tags.values():
        all_tags.update(tags)
    return sorted(all_tags)


# --- chat ---

@app.get("/api/chat/status")
async def chat_status():
    return {"available": await chat.check_available()}


@app.post("/api/chat")
async def chat_message(body: dict):
    message = body.get("message", "").strip()
    if not message:
        return JSONResponse({"error": "Empty message"}, 400)

    if not await chat.check_available():
        return JSONResponse({"error": "Ollama not running. Install from ollama.com."}, 503)

    async def generate():
        try:
            async for token in chat.stream_response(message, graph):
                yield f"data: {token}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: Error: {e}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.delete("/api/chat/history")
async def clear_chat():
    chat.clear_history()
    return {"status": "cleared"}


# --- static (must be last) ---
app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
