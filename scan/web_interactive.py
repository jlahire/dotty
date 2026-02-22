"""
dotty v2 — interactive web session
by jLaHire

launches a visible chromium window via playwright, captures all network
events (requests, responses, redirects, cookies, console messages) and
streams them through on_event callback. when done, converts captured
data into graph nodes following the list[Node] pattern.
"""

from __future__ import annotations

import logging
import socket
import threading
import urllib.parse
from datetime import datetime

# module-level DNS cache shared across sessions
_dns_cache: dict[str, str] = {}


def _resolve_ip(hostname: str) -> str:
    """Resolve hostname → IP with cache; falls back to hostname on failure."""
    hostname = hostname.strip("[]")  # strip IPv6 brackets
    if not hostname:
        return ""
    if hostname in _dns_cache:
        return _dns_cache[hostname]
    try:
        ip = socket.gethostbyname(hostname)
    except Exception:
        ip = hostname
    _dns_cache[hostname] = ip
    return ip

from graph import Node, make_id

log = logging.getLogger(__name__)


class SessionData:
    def __init__(self):
        self.requests: list[dict] = []
        self.responses: list[dict] = []
        self.redirects: list[dict] = []
        self.cookies: dict[str, dict] = {}
        self.cookie_events: list[dict] = []
        self.console_messages: list[dict] = []
        self.js_errors: list[dict] = []
        self.pages_visited: list[dict] = []
        self._cookie_snapshot: dict[str, dict] = {}


class InteractiveSession:
    def __init__(self, url: str, on_event=None):
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        self.url = url
        self.on_event = on_event or (lambda e: None)
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()  # set = paused, clear = running
        self.data = SessionData()
        self._started = datetime.now()
        self._seen_ips: set[str] = set()  # tracks first-connection SYN per IP

    def start(self):
        """Blocking — run in executor thread. Launches browser and waits."""
        from playwright.sync_api import sync_playwright

        self._emit({"event": "session_started", "url": self.url,
                     "time": self._started.isoformat()})

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=False)
            context = browser.new_context(ignore_https_errors=True)

            context.on("page", lambda page: self._attach_page(page, context))

            page = context.new_page()
            self._attach_page(page, context)

            try:
                page.goto(self.url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                self._emit({"event": "navigation_error", "error": str(e),
                            "time": datetime.now().isoformat()})

            self._diff_cookies(context)

            while not self._stop_event.is_set():
                if not browser.is_connected():
                    break
                try:
                    self._stop_event.wait(0.5)
                    if not self._stop_event.is_set() and browser.is_connected():
                        self._diff_cookies(context)
                except Exception:
                    break

            try:
                browser.close()
            except Exception:
                pass

        self._emit({"event": "session_ended",
                     "time": datetime.now().isoformat(),
                     "stats": {
                         "requests": len(self.data.requests),
                         "responses": len(self.data.responses),
                         "redirects": len(self.data.redirects),
                         "cookies": len(self.data.cookies),
                         "console": len(self.data.console_messages),
                         "errors": len(self.data.js_errors),
                         "pages": len(self.data.pages_visited),
                     }})

    def stop(self):
        """Thread-safe — can be called from any thread."""
        self._stop_event.set()
        self._pause_event.clear()  # unblock any paused wait

    def pause(self):
        """Pause event capture (browser stays open)."""
        self._pause_event.set()
        self._emit({"event": "session_paused", "time": datetime.now().isoformat()})

    def resume(self):
        """Resume event capture after pause."""
        self._pause_event.clear()
        self._emit({"event": "session_resumed", "time": datetime.now().isoformat()})

    def _attach_page(self, page, context):
        page.on("request", lambda req: self._on_request(req))
        page.on("response", lambda resp: self._on_response(resp))
        page.on("console", lambda msg: self._on_console(msg))
        page.on("pageerror", lambda err: self._on_page_error(err))
        page.on("framenavigated", lambda frame: self._on_frame_navigated(frame))

    def _on_request(self, request):
        now = datetime.now().isoformat()

        # traffic log — emitted first so frontend IP cache is populated before request event
        parsed_u = urllib.parse.urlparse(request.url)
        hostname = parsed_u.netloc.split(":")[0].strip("[]")
        ip = _resolve_ip(hostname)
        path = parsed_u.path or "/"
        if len(path) > 38:
            path = path[:18] + "..." + path[-14:]
        if ip and ip not in self._seen_ips:
            self._seen_ips.add(ip)
            self._emit_traffic("outgoing", ip, "SYN", request.url, now)
        self._emit_traffic("outgoing", ip, f"{request.method} {path}", request.url, now)

        redirect_from = None
        rr = request.redirected_from
        if rr:
            redirect_from = rr.url
            rd = {
                "from_url": rr.url,
                "to_url": request.url,
                "status": None,
                "time": now,
            }
            self.data.redirects.append(rd)
            self._emit({"event": "redirect", "from": rr.url,
                         "to": request.url, "time": now})

        entry = {
            "method": request.method,
            "url": request.url,
            "resource_type": request.resource_type,
            "time": now,
            "redirect_from": redirect_from,
        }
        self.data.requests.append(entry)
        self._emit({"event": "request", "method": request.method,
                     "url": request.url, "resource_type": request.resource_type,
                     "time": now})

    def _on_response(self, response):
        now = datetime.now().isoformat()
        status = response.status
        url = response.url
        content_type = ""
        try:
            headers = response.headers
            content_type = headers.get("content-type", "")
        except Exception:
            pass

        entry = {
            "status": status,
            "url": url,
            "content_type": content_type,
            "time": now,
        }
        self.data.responses.append(entry)

        # update redirect status if we have a matching redirect
        if status in (301, 302, 307, 308):
            for rd in reversed(self.data.redirects):
                if rd["from_url"] == url and rd["status"] is None:
                    rd["status"] = status
                    break

        # traffic log — incoming response (emitted first so frontend IP cache is populated)
        parsed_u = urllib.parse.urlparse(url)
        hostname = parsed_u.netloc.split(":")[0].strip("[]")
        ip = _resolve_ip(hostname)
        ct_short = content_type.split(";")[0].split("/")[-1][:12] if content_type else ""
        status_cls = "OK" if status < 300 else ("REDIR" if status < 400 else "ERR")
        msg = f"HTTP {status} {status_cls}" + (f" ({ct_short})" if ct_short else "")
        self._emit_traffic("incoming", ip, msg, url, now)

        self._emit({"event": "response", "status": status, "url": url,
                     "content_type": content_type, "time": now})

    def _on_console(self, msg):
        now = datetime.now().isoformat()
        text = msg.text[:500] if msg.text else ""
        level = msg.type
        entry = {"type": level, "text": text, "time": now}
        self.data.console_messages.append(entry)
        self._emit({"event": "console", "level": level, "text": text,
                     "time": now})

    def _on_page_error(self, error):
        now = datetime.now().isoformat()
        text = str(error)[:500]
        entry = {"text": text, "time": now}
        self.data.js_errors.append(entry)
        self._emit({"event": "js_error", "text": text, "time": now})

    def _on_frame_navigated(self, frame):
        if frame.parent_frame is not None:
            return
        now = datetime.now().isoformat()
        url = frame.url
        entry = {"url": url, "time": now}
        self.data.pages_visited.append(entry)
        self._emit({"event": "navigation", "url": url, "time": now})

    def _diff_cookies(self, context):
        try:
            current = {c["name"]: c for c in context.cookies()}
        except Exception:
            return

        now = datetime.now().isoformat()
        old = self.data._cookie_snapshot

        for name, cookie in current.items():
            if name not in old:
                self.data.cookies[name] = {**cookie, "first_seen": now, "last_seen": now, "event": "set"}
                self.data.cookie_events.append({"event": "cookie_set", "name": name, "cookie": cookie, "time": now})
                self._emit({"event": "cookie_set", "name": name,
                             "domain": cookie.get("domain", ""),
                             "secure": cookie.get("secure", False),
                             "httpOnly": cookie.get("httpOnly", False),
                             "sameSite": cookie.get("sameSite", ""),
                             "time": now})
            elif cookie.get("value") != old[name].get("value"):
                if name in self.data.cookies:
                    self.data.cookies[name]["last_seen"] = now
                    self.data.cookies[name]["event"] = "modified"
                self.data.cookie_events.append({"event": "cookie_modified", "name": name, "cookie": cookie, "time": now})
                self._emit({"event": "cookie_modified", "name": name,
                             "domain": cookie.get("domain", ""),
                             "time": now})

        for name in old:
            if name not in current:
                self.data.cookie_events.append({"event": "cookie_deleted", "name": name, "time": now})
                self._emit({"event": "cookie_deleted", "name": name, "time": now})
                if name in self.data.cookies:
                    self.data.cookies[name]["event"] = "deleted"

        self.data._cookie_snapshot = current

    def _emit_traffic(self, category: str, ip: str, msg: str, url: str, time: str):
        self._emit({
            "event": "traffic",
            "category": category,
            "ip": ip,
            "msg": msg,
            "url": url,
            "time": time,
        })

    def _emit(self, event):
        # always pass through lifecycle events; drop others while paused
        lifecycle = {"session_started", "session_ended", "session_paused", "session_resumed"}
        if self._pause_event.is_set() and event.get("event") not in lifecycle:
            return
        try:
            self.on_event({"type": "session_event", **event})
        except Exception as e:
            log.debug(f"Event emit failed: {e}")

    def to_nodes(self) -> list[Node]:
        nodes = []
        now = datetime.now().isoformat()
        parsed = urllib.parse.urlparse(self.url)
        domain = parsed.netloc

        # web_page node
        page_node = Node(
            id=make_id(f"web:interactive:{self.url}"),
            name=f"Interactive: {domain}",
            path=self.url,
            kind="web_page",
            info={
                "url": self.url,
                "domain": domain,
                "interactive": True,
                "pages_visited": len(self.data.pages_visited),
                "total_requests": len(self.data.requests),
                "total_cookies": len(self.data.cookies),
                "total_redirects": len(self.data.redirects),
                "total_console": len(self.data.console_messages),
                "total_errors": len(self.data.js_errors),
                "scheme": parsed.scheme,
                "is_https": parsed.scheme == "https",
                "modified": self._started.isoformat(),
            },
        )
        nodes.append(page_node)

        # web_request nodes — grouped by domain
        domain_reqs: dict[str, list[dict]] = {}
        for req in self.data.requests:
            req_domain = urllib.parse.urlparse(req["url"]).netloc
            domain_reqs.setdefault(req_domain, []).append(req)

        for req_domain, reqs in domain_reqs.items():
            resource_types = {}
            for r in reqs:
                rt = r.get("resource_type", "other")
                resource_types[rt] = resource_types.get(rt, 0) + 1
            is_tp = req_domain != domain
            label = req_domain or "unknown"
            nodes.append(Node(
                id=make_id(f"webreq:domain:{req_domain}"),
                name=f"{label} ({len(reqs)})",
                path=f"https://{req_domain}" if req_domain else "#requests",
                kind="web_request",
                info={
                    "domain": req_domain,
                    "count": len(reqs),
                    "resource_types": resource_types,
                    "third_party": is_tp,
                    "time": reqs[0]["time"],
                    "modified": reqs[0]["time"],
                },
            ))

        # web_redirect nodes — deduplicated by from→to pair
        seen_redirects = set()
        for rd in self.data.redirects:
            key = f"{rd['from_url']}>{rd['to_url']}"
            if key in seen_redirects:
                continue
            seen_redirects.add(key)
            nodes.append(Node(
                id=make_id(f"webredir:{key}"),
                name=f"{rd.get('status', '3xx')} {_short_url(rd['from_url'])}",
                path=rd["from_url"],
                kind="web_redirect",
                info={
                    "from_url": rd["from_url"],
                    "to_url": rd["to_url"],
                    "status": rd.get("status"),
                    "from_domain": urllib.parse.urlparse(rd["from_url"]).netloc,
                    "to_domain": urllib.parse.urlparse(rd["to_url"]).netloc,
                    "time": rd["time"],
                    "modified": rd["time"],
                },
            ))

        # web_cookie nodes
        for name, cookie in self.data.cookies.items():
            nodes.append(Node(
                id=make_id(f"webcookie:session:{name}"),
                name=name,
                path=f"#cookie:session:{name}",
                kind="web_cookie",
                info={
                    "name": name,
                    "value": str(cookie.get("value", ""))[:20] + "..." if len(str(cookie.get("value", ""))) > 20 else str(cookie.get("value", "")),
                    "domain": cookie.get("domain", ""),
                    "path": cookie.get("path", ""),
                    "secure": cookie.get("secure", False),
                    "httponly": cookie.get("httpOnly", False),
                    "samesite": cookie.get("sameSite", ""),
                    "expires": str(cookie.get("expires", "")),
                    "first_seen": cookie.get("first_seen", ""),
                    "last_seen": cookie.get("last_seen", ""),
                    "event_type": cookie.get("event", "set"),
                    "interactive": True,
                    "modified": cookie.get("first_seen", now),
                },
            ))

        # web_console nodes — grouped by level
        errors = [m for m in self.data.console_messages if m["type"] in ("error",)]
        errors += [{"type": "error", "text": e["text"], "time": e["time"]} for e in self.data.js_errors]
        warnings = [m for m in self.data.console_messages if m["type"] == "warning"]

        if errors:
            nodes.append(Node(
                id=make_id(f"webconsole:errors:{self.url}"),
                name=f"Console Errors ({len(errors)})",
                path=f"{self.url}#console:errors",
                kind="web_console",
                info={
                    "level": "error",
                    "count": len(errors),
                    "messages": [e["text"][:200] for e in errors[:50]],
                    "modified": errors[0]["time"] if errors else now,
                },
            ))

        if warnings:
            nodes.append(Node(
                id=make_id(f"webconsole:warnings:{self.url}"),
                name=f"Console Warnings ({len(warnings)})",
                path=f"{self.url}#console:warnings",
                kind="web_console",
                info={
                    "level": "warning",
                    "count": len(warnings),
                    "messages": [w["text"][:200] for w in warnings[:50]],
                    "modified": warnings[0]["time"] if warnings else now,
                },
            ))

        # Individual resource file nodes (deduped by URL, key resource types only)
        _RTYPE_MAP = {
            "document": ("web_page", ".html"),
            "script": ("web_script", ".js"),
            "stylesheet": ("web_style", ".css"),
            "image": ("web_image", ""),
            "font": ("web_style", ""),
            "media": ("web_image", ""),
        }
        seen_file_urls: set[str] = set()
        for req in self.data.requests:
            url = req["url"]
            rtype = req.get("resource_type", "other")
            if rtype not in _RTYPE_MAP or url in seen_file_urls:
                continue
            seen_file_urls.add(url)
            kind, default_ext = _RTYPE_MAP[rtype]
            fname = _file_name(url) or _short_url(url)
            ext = default_ext
            clean = url.lower().split("?")[0].split("#")[0]
            for e in (".js", ".mjs", ".css", ".html", ".htm", ".png", ".jpg",
                      ".jpeg", ".gif", ".svg", ".webp", ".ico", ".woff2",
                      ".woff", ".ttf", ".eot", ".json"):
                if clean.endswith(e):
                    ext = e
                    break
            req_domain = urllib.parse.urlparse(url).netloc
            nodes.append(Node(
                id=make_id(f"webfile:interactive:{url}"),
                name=fname,
                path=url,
                kind=kind,
                info={
                    "url": url,
                    "resource_type": rtype,
                    "domain": req_domain,
                    "third_party": req_domain != domain,
                    "extension": ext,
                    "interactive": True,
                    "modified": req["time"],
                },
            ))

        return nodes


def _file_name(url: str) -> str:
    try:
        path = urllib.parse.urlparse(url).path
        name = path.rstrip("/").split("/")[-1]
        return urllib.parse.unquote(name) if name else ""
    except Exception:
        return ""


def _short_url(url: str) -> str:
    try:
        p = urllib.parse.urlparse(url)
        path = p.path
        if len(path) > 40:
            path = path[:20] + "..." + path[-15:]
        return p.netloc + path
    except Exception:
        return url[:60]
