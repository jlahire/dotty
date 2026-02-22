"""
dotty v2 — web page forensic scanner
by jLaHire

fetches a url and rips it apart: html structure, scripts, stylesheets,
images, links, forms, meta tags, cookies, headers. builds nodes for
everything so you can see the full anatomy of a page in the MOC.
"""

from __future__ import annotations

import hashlib
import logging
import ssl
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime
from html.parser import HTMLParser

from graph import Node, make_id

log = logging.getLogger(__name__)


class PageParser(HTMLParser):
    def __init__(self, base_url):
        super().__init__()
        self.base = base_url
        self.scripts = []
        self.stylesheets = []
        self.images = []
        self.links = []
        self.forms = []
        self.metas = []
        self.iframes = []
        self.inputs = []
        self.inline_scripts = []
        self.title = ""
        self._in_title = False
        self._title_buf = []
        self._in_a = False
        self._a_buf = []
        self._current_form_idx = -1
        self._in_script = False
        self._script_buf = []

    def _abs(self, url):
        if not url:
            return ""
        return urllib.parse.urljoin(self.base, url)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)

        if tag == "script":
            src = a.get("src")
            if src:
                self.scripts.append({
                    "url": self._abs(src),
                    "type": a.get("type", ""),
                    "async": "async" in a,
                    "defer": "defer" in a,
                    "integrity": a.get("integrity", ""),
                    "crossorigin": a.get("crossorigin", ""),
                })
            else:
                self._in_script = True
                self._script_buf = []

        elif tag == "link" and a.get("rel", "").lower() == "stylesheet":
            href = a.get("href")
            if href:
                self.stylesheets.append({
                    "url": self._abs(href),
                    "media": a.get("media", ""),
                    "integrity": a.get("integrity", ""),
                })

        elif tag == "img":
            src = a.get("src") or a.get("data-src")
            if src:
                self.images.append({
                    "url": self._abs(src),
                    "alt": a.get("alt", ""),
                    "width": a.get("width", ""),
                    "height": a.get("height", ""),
                    "loading": a.get("loading", ""),
                })

        elif tag == "a":
            href = a.get("href")
            if href and not href.startswith(("#", "javascript:", "mailto:")):
                self._in_a = True
                self._a_buf = []
                self.links.append({
                    "url": self._abs(href),
                    "text": "",
                    "rel": a.get("rel", ""),
                    "target": a.get("target", ""),
                })

        elif tag == "form":
            self.forms.append({
                "action": self._abs(a.get("action", "")),
                "method": a.get("method", "GET").upper(),
                "enctype": a.get("enctype", ""),
                "id": a.get("id", ""),
                "name": a.get("name", ""),
            })
            self._current_form_idx = len(self.forms) - 1

        elif tag in ("input", "textarea", "select", "button"):
            self.inputs.append({
                "tag": tag,
                "type": a.get("type", ""),
                "name": a.get("name", ""),
                "value": a.get("value", "")[:100],
                "hidden": a.get("type", "").lower() == "hidden",
                "form_index": self._current_form_idx,
            })

        elif tag == "iframe":
            src = a.get("src")
            if src:
                self.iframes.append({
                    "url": self._abs(src),
                    "sandbox": a.get("sandbox", ""),
                    "allow": a.get("allow", ""),
                })

        elif tag == "meta":
            name = a.get("name", a.get("property", ""))
            content = a.get("content", "")
            if name and content:
                self.metas.append({"name": name, "content": content})

        elif tag == "title":
            self._in_title = True

    def handle_data(self, data):
        if self._in_title:
            self._title_buf.append(data)
        if self._in_a:
            self._a_buf.append(data)
        if self._in_script:
            self._script_buf.append(data)

    def handle_endtag(self, tag):
        if tag == "title" and self._in_title:
            self._in_title = False
            self.title = "".join(self._title_buf).strip()
        if tag == "a" and self._in_a:
            self._in_a = False
            text = "".join(self._a_buf).strip()
            if text and self.links:
                self.links[-1]["text"] = text[:120]
        if tag == "script" and self._in_script:
            self._in_script = False
            content = "".join(self._script_buf).strip()[:2000]
            if content:
                self.inline_scripts.append(content)
        if tag == "form":
            self._current_form_idx = -1


def scan_webpage(url: str, progress=None) -> list[Node]:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc
    now = datetime.now().isoformat()

    if progress:
        progress(0.1, f"Fetching {domain}...")

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (dotty forensic scanner)",
        "Accept": "text/html,application/xhtml+xml",
    })

    try:
        resp = urllib.request.urlopen(req, timeout=15, context=ctx)
        html = resp.read().decode("utf-8", errors="ignore")
        headers = dict(resp.getheaders())
        status = resp.status
        final_url = resp.url
    except urllib.error.HTTPError as e:
        html = ""
        headers = dict(e.headers) if e.headers else {}
        status = e.code
        final_url = url
    except Exception as e:
        raise RuntimeError(f"Failed to fetch {url}: {e}")

    if progress:
        progress(0.4, "Parsing page structure...")

    parser = PageParser(final_url)
    try:
        parser.feed(html)
    except Exception:
        pass

    nodes = []

    page_node = Node(
        id=make_id(f"web:{final_url}"),
        name=parser.title or domain,
        path=final_url,
        kind="web_page",
        info={
            "url": final_url,
            "domain": domain,
            "status": status,
            "title": parser.title,
            "size": len(html),
            "modified": now,
            "server": headers.get("Server", ""),
            "content_type": headers.get("Content-Type", ""),
            "x_powered_by": headers.get("X-Powered-By", ""),
            "x_frame_options": headers.get("X-Frame-Options", ""),
            "content_security_policy": headers.get("Content-Security-Policy", ""),
            "strict_transport_security": headers.get("Strict-Transport-Security", ""),
            "set_cookie": headers.get("Set-Cookie", ""),
            "x_content_type_options": headers.get("X-Content-Type-Options", ""),
            "referrer_policy": headers.get("Referrer-Policy", ""),
            "permissions_policy": headers.get("Permissions-Policy", ""),
            "access_control_allow_origin": headers.get("Access-Control-Allow-Origin", ""),
            "access_control_allow_credentials": headers.get("Access-Control-Allow-Credentials", ""),
            "scheme": parsed.scheme,
            "is_https": parsed.scheme == "https",
            "scripts_count": len(parser.scripts),
            "links_count": len(parser.links),
            "images_count": len(parser.images),
            "forms_count": len(parser.forms),
        },
    )
    nodes.append(page_node)

    header_node = Node(
        id=make_id(f"webheaders:{final_url}"),
        name=f"Headers ({domain})",
        path=f"{final_url}#headers",
        kind="web_headers",
        info={k: v for k, v in headers.items()},
    )
    nodes.append(header_node)

    if progress:
        progress(0.6, f"Found {len(parser.scripts)} scripts, {len(parser.links)} links...")

    for i, s in enumerate(parser.scripts):
        fname = _url_filename(s["url"]) or f"script_{i}.js"
        nodes.append(Node(
            id=make_id(f"webscript:{s['url']}"),
            name=fname,
            path=s["url"],
            kind="web_script",
            info={
                "url": s["url"],
                "type": s["type"],
                "async": s["async"],
                "defer": s["defer"],
                "integrity": s["integrity"],
                "crossorigin": s["crossorigin"],
                "domain": urllib.parse.urlparse(s["url"]).netloc,
                "third_party": urllib.parse.urlparse(s["url"]).netloc != domain,
                "extension": ".js",
                "modified": now,
            },
        ))

    for i, s in enumerate(parser.stylesheets):
        fname = _url_filename(s["url"]) or f"style_{i}.css"
        nodes.append(Node(
            id=make_id(f"webcss:{s['url']}"),
            name=fname,
            path=s["url"],
            kind="web_style",
            info={
                "url": s["url"],
                "media": s["media"],
                "integrity": s["integrity"],
                "domain": urllib.parse.urlparse(s["url"]).netloc,
                "third_party": urllib.parse.urlparse(s["url"]).netloc != domain,
                "extension": ".css",
                "modified": now,
            },
        ))

    for i, img in enumerate(parser.images):
        fname = _url_filename(img["url"]) or f"image_{i}"
        ext = ""
        for e in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".bmp"):
            if e in img["url"].lower():
                ext = e
                break
        nodes.append(Node(
            id=make_id(f"webimg:{img['url']}"),
            name=fname,
            path=img["url"],
            kind="web_image",
            info={
                "url": img["url"],
                "alt": img["alt"],
                "width": img["width"],
                "height": img["height"],
                "domain": urllib.parse.urlparse(img["url"]).netloc,
                "third_party": urllib.parse.urlparse(img["url"]).netloc != domain,
                "extension": ext,
                "modified": now,
            },
        ))

    seen_domains = set()
    for i, link in enumerate(parser.links):
        link_domain = urllib.parse.urlparse(link["url"]).netloc
        nodes.append(Node(
            id=make_id(f"weblink:{link['url']}:{i}"),
            name=link["text"] or _url_filename(link["url"]) or link["url"][:60],
            path=link["url"],
            kind="web_link",
            info={
                "url": link["url"],
                "rel": link["rel"],
                "target": link["target"],
                "domain": link_domain,
                "external": link_domain != domain,
                "modified": now,
            },
        ))
        seen_domains.add(link_domain)

    for i, form in enumerate(parser.forms):
        nodes.append(Node(
            id=make_id(f"webform:{form['action']}:{i}"),
            name=form["name"] or form["id"] or f"form_{i}",
            path=form["action"],
            kind="web_form",
            info={
                "action": form["action"],
                "method": form["method"],
                "enctype": form["enctype"],
                "modified": now,
            },
        ))

    for i, iframe in enumerate(parser.iframes):
        nodes.append(Node(
            id=make_id(f"webiframe:{iframe['url']}"),
            name=_url_filename(iframe["url"]) or f"iframe_{i}",
            path=iframe["url"],
            kind="web_iframe",
            info={
                "url": iframe["url"],
                "sandbox": iframe["sandbox"],
                "allow": iframe["allow"],
                "domain": urllib.parse.urlparse(iframe["url"]).netloc,
                "third_party": urllib.parse.urlparse(iframe["url"]).netloc != domain,
                "modified": now,
            },
        ))

    for meta in parser.metas:
        nodes.append(Node(
            id=make_id(f"webmeta:{meta['name']}:{meta['content'][:30]}"),
            name=meta["name"],
            path=f"{final_url}#meta:{meta['name']}",
            kind="web_meta",
            info={
                "name": meta["name"],
                "content": meta["content"],
                "modified": now,
            },
        ))

    if parser.inline_scripts:
        all_inline = "\n".join(parser.inline_scripts)
        nodes.append(Node(
            id=make_id(f"webinline:{final_url}"),
            name=f"inline scripts ({len(parser.inline_scripts)})",
            path=f"{final_url}#inline-scripts",
            kind="web_script",
            info={
                "count": len(parser.inline_scripts),
                "inline": True,
                "has_eval": "eval(" in all_inline,
                "has_document_write": "document.write(" in all_inline,
                "has_innerhtml": "innerHTML" in all_inline,
                "has_localstorage": "localStorage" in all_inline,
                "has_sessionstorage": "sessionStorage" in all_inline,
                "has_indexeddb": "indexedDB" in all_inline,
                "modified": now,
            },
        ))

    for i, inp in enumerate(parser.inputs):
        form_label = ""
        if inp["form_index"] >= 0 and inp["form_index"] < len(parser.forms):
            f = parser.forms[inp["form_index"]]
            form_label = f["name"] or f["id"] or f"form_{inp['form_index']}"
        nodes.append(Node(
            id=make_id(f"webinput:{final_url}:{i}:{inp['name']}"),
            name=inp["name"] or f"{inp['tag']}_{i}",
            path=f"{final_url}#input:{inp['name'] or i}",
            kind="web_input",
            info={
                "tag": inp["tag"],
                "type": inp["type"],
                "name": inp["name"],
                "value": inp["value"],
                "hidden": inp["hidden"],
                "form_index": inp["form_index"],
                "form_name": form_label,
                "modified": now,
            },
        ))

    if progress:
        progress(1.0, f"Done — {len(nodes)} elements from {domain}")

    return nodes


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.pieces = []
        self._skip = False
        self._skip_tags = {"script", "style", "noscript"}

    def handle_starttag(self, tag, attrs):
        if tag in self._skip_tags:
            self._skip = True
        if tag in ("br", "p", "div", "h1", "h2", "h3", "h4", "li", "tr"):
            self.pieces.append("\n")

    def handle_endtag(self, tag):
        if tag in self._skip_tags:
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            self.pieces.append(data)

    def get_text(self):
        raw = "".join(self.pieces)
        lines = [l.strip() for l in raw.splitlines()]
        return "\n".join(l for l in lines if l)[:8000]


def fetch_page_text(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (dotty forensic scanner)",
        "Accept": "text/html,application/xhtml+xml",
    })

    try:
        resp = urllib.request.urlopen(req, timeout=15, context=ctx)
        html = resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return ""

    extractor = TextExtractor()
    try:
        extractor.feed(html)
    except Exception:
        pass
    return extractor.get_text()


def _url_filename(url: str) -> str:
    try:
        path = urllib.parse.urlparse(url).path
        name = path.rstrip("/").split("/")[-1]
        if name and "." in name:
            return urllib.parse.unquote(name)
        return urllib.parse.unquote(name) if name else ""
    except Exception:
        return ""
