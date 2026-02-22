"""
dotty v2 — browser artifact extraction
by jLaHire

chrome, firefox, edge, safari, brave, opera.
copies DBs to temp before reading to avoid lock issues.
"""

from __future__ import annotations

import logging
import platform
import shutil
import sqlite3
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from graph import Node, make_id

log = logging.getLogger(__name__)

CHROME_EPOCH = datetime(1601, 1, 1)
SAFARI_EPOCH = datetime(2001, 1, 1)

SEARCH_ENGINES = {
    "google.com": "q", "bing.com": "q", "yahoo.com": "p",
    "duckduckgo.com": "q", "yandex.com": "text", "baidu.com": "wd",
}

BROWSER_PATHS = {
    "chrome": {
        "linux": [".config/google-chrome/Default", ".config/google-chrome/Profile *"],
        "darwin": ["Library/Application Support/Google/Chrome/Default"],
        "win32": ["AppData/Local/Google/Chrome/User Data/Default"],
    },
    "firefox": {
        "linux": [".mozilla/firefox/*.default*"],
        "darwin": ["Library/Application Support/Firefox/Profiles/*.default*"],
        "win32": ["AppData/Roaming/Mozilla/Firefox/Profiles/*.default*"],
    },
    "edge": {
        "linux": [".config/microsoft-edge/Default"],
        "darwin": ["Library/Application Support/Microsoft Edge/Default"],
        "win32": ["AppData/Local/Microsoft/Edge/User Data/Default"],
    },
    "brave": {
        "linux": [".config/BraveSoftware/Brave-Browser/Default"],
        "darwin": ["Library/Application Support/BraveSoftware/Brave-Browser/Default"],
        "win32": ["AppData/Local/BraveSoftware/Brave-Browser/User Data/Default"],
    },
    "safari": {
        "darwin": ["Library/Safari"],
    },
    "opera": {
        "linux": [".config/opera/Default"],
        "win32": ["AppData/Roaming/Opera Software/Opera Stable"],
    },
}


def analyze_browser(root_path: str) -> list[Node]:
    nodes = []
    home = Path(root_path)

    sys = platform.system().lower()
    if sys == "linux":
        plat = "linux"
    elif sys == "darwin":
        plat = "darwin"
    else:
        plat = "win32"

    for browser, paths in BROWSER_PATHS.items():
        for pattern in paths.get(plat, []):
            for profile_dir in home.glob(pattern):
                if not profile_dir.is_dir():
                    continue
                try:
                    if browser == "safari":
                        nodes.extend(_safari(profile_dir, browser))
                    elif browser == "firefox":
                        nodes.extend(_firefox(profile_dir, browser))
                    else:
                        nodes.extend(_chromium(profile_dir, browser))
                except Exception as e:
                    log.debug(f"{browser}: {e}")

    return nodes


def _safe_query(db_path: Path, query: str) -> list:
    if not db_path.exists():
        return []

    tmp = Path(tempfile.mktemp(suffix=".db"))
    try:
        shutil.copy2(db_path, tmp)
        conn = sqlite3.connect(str(tmp))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query).fetchall()
        conn.close()
        return rows
    except Exception as e:
        log.debug(f"query failed on {db_path}: {e}")
        return []
    finally:
        tmp.unlink(missing_ok=True)


def _chrome_time(ts):
    if not ts or ts <= 0:
        return ""
    try:
        return (CHROME_EPOCH + timedelta(microseconds=ts)).isoformat()
    except (ValueError, OverflowError):
        return ""


def _extract_search(url: str) -> str:
    try:
        parsed = urlparse(url)
        for domain, param in SEARCH_ENGINES.items():
            if domain in parsed.netloc:
                q = parse_qs(parsed.query).get(param, [""])[0]
                return q
    except Exception:
        pass
    return ""


def _chromium(profile: Path, browser: str) -> list[Node]:
    nodes = []

    rows = _safe_query(profile / "History", """
        SELECT urls.url, urls.title, urls.visit_count, urls.last_visit_time,
               visits.visit_time
        FROM urls LEFT JOIN visits ON urls.id = visits.url
        ORDER BY visits.visit_time DESC
    """)
    for r in rows:
        url = r["url"]
        nodes.append(Node(
            id=make_id(f"bh:{browser}:{url}:{r['visit_time']}"),
            name=r["title"] or url[:60],
            path=url,
            kind="browser_history",
            info={
                "browser": browser, "url": url, "title": r["title"] or "",
                "visit_count": r["visit_count"],
                "visited": _chrome_time(r["visit_time"]),
                "search_query": _extract_search(url),
            },
        ))

    rows = _safe_query(profile / "History", """
        SELECT target_path, tab_url, start_time, total_bytes, received_bytes, state
        FROM downloads ORDER BY start_time DESC
    """)
    for r in rows:
        nodes.append(Node(
            id=make_id(f"bd:{browser}:{r['target_path']}"),
            name=Path(r["target_path"]).name if r["target_path"] else "download",
            path=r["target_path"] or "",
            kind="browser_download",
            info={
                "browser": browser, "url": r["tab_url"] or "",
                "size": r["total_bytes"], "received": r["received_bytes"],
                "started": _chrome_time(r["start_time"]),
                "state": r["state"],
            },
        ))

    bookmarks_file = profile / "Bookmarks"
    if bookmarks_file.exists():
        try:
            data = json.loads(bookmarks_file.read_text(errors="ignore"))
            _extract_bookmarks(data.get("roots", {}), browser, nodes)
        except Exception:
            pass

    return nodes


def _extract_bookmarks(obj, browser, nodes, folder=""):
    if isinstance(obj, dict):
        if obj.get("type") == "url":
            url = obj.get("url", "")
            nodes.append(Node(
                id=make_id(f"bb:{browser}:{url}"),
                name=obj.get("name", url[:60]),
                path=url,
                kind="browser_bookmark",
                info={
                    "browser": browser, "url": url,
                    "folder": folder, "added": obj.get("date_added", ""),
                },
            ))
        elif obj.get("type") == "folder":
            for child in obj.get("children", []):
                _extract_bookmarks(child, browser, nodes, obj.get("name", ""))
        else:
            for v in obj.values():
                _extract_bookmarks(v, browser, nodes, folder)


def _firefox(profile: Path, browser: str) -> list[Node]:
    nodes = []

    rows = _safe_query(profile / "places.sqlite", """
        SELECT moz_places.url, moz_places.title, moz_places.visit_count,
               moz_historyvisits.visit_date
        FROM moz_places
        LEFT JOIN moz_historyvisits ON moz_places.id = moz_historyvisits.place_id
        ORDER BY moz_historyvisits.visit_date DESC
    """)
    for r in rows:
        url = r["url"]
        ts = r["visit_date"]
        visited = datetime.fromtimestamp(ts / 1_000_000).isoformat() if ts else ""
        nodes.append(Node(
            id=make_id(f"bh:{browser}:{url}:{ts}"),
            name=r["title"] or url[:60],
            path=url,
            kind="browser_history",
            info={
                "browser": browser, "url": url, "title": r["title"] or "",
                "visit_count": r["visit_count"], "visited": visited,
                "search_query": _extract_search(url),
            },
        ))

    rows = _safe_query(profile / "places.sqlite", """
        SELECT moz_places.url, moz_bookmarks.title, moz_bookmarks.dateAdded
        FROM moz_bookmarks
        JOIN moz_places ON moz_bookmarks.fk = moz_places.id
        WHERE moz_bookmarks.type = 1
        ORDER BY moz_bookmarks.dateAdded DESC
    """)
    for r in rows:
        url = r["url"]
        nodes.append(Node(
            id=make_id(f"bb:{browser}:{url}"),
            name=r["title"] or url[:60],
            path=url,
            kind="browser_bookmark",
            info={"browser": browser, "url": url},
        ))

    return nodes


def _safari(profile: Path, browser: str) -> list[Node]:
    nodes = []

    rows = _safe_query(profile / "History.db", """
        SELECT history_items.url, history_items.visit_count,
               history_visits.visit_time, history_visits.title
        FROM history_items
        LEFT JOIN history_visits ON history_items.id = history_visits.history_item
        ORDER BY history_visits.visit_time DESC
    """)
    for r in rows:
        url = r["url"]
        ts = r["visit_time"]
        visited = (SAFARI_EPOCH + timedelta(seconds=ts)).isoformat() if ts else ""
        nodes.append(Node(
            id=make_id(f"bh:{browser}:{url}:{ts}"),
            name=r["title"] or url[:60],
            path=url,
            kind="browser_history",
            info={
                "browser": browser, "url": url, "title": r["title"] or "",
                "visit_count": r["visit_count"], "visited": visited,
                "search_query": _extract_search(url),
            },
        ))

    return nodes
