"""
dotty v2 — graph engine
by jLaHire

one node type, one graph, O(n) linking, cytoscape export.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath


@dataclass
class Node:
    id: str
    name: str
    path: str
    kind: str
    info: dict = field(default_factory=dict)
    is_hidden: bool = False
    is_deleted: bool = False
    is_system: bool = False


def make_id(path: str) -> str:
    return hashlib.md5(path.encode()).hexdigest()[:12]


SYSTEM_PATH_PARTS = {
    "windows", "system32", "program files", "program files (x86)", "programdata",
    "usr", "var", "etc", "bin", "sbin", "lib", "sys", "proc", "boot", "dev", "tmp", "opt",
    "system", "private",
    ".git", ".svn", ".hg", "__pycache__", ".cache", "node_modules", ".tmp", "temp",
}

SYSTEM_OWNERS = {
    "system", "administrator", "nt authority", "trustedinstaller",
    "network service", "local service", "root", "daemon", "bin",
    "sys", "adm", "nobody", "_system", "_installer",
}


def is_system_file(path_str: str, owner: str = "") -> bool:
    parts = {p.lower() for p in PurePosixPath(path_str).parts}
    if parts & SYSTEM_PATH_PARTS:
        return True
    if owner.lower().split("\\")[-1] in SYSTEM_OWNERS:
        return True
    return False


def get_owner(stat_info) -> str:
    try:
        import pwd
        return pwd.getpwuid(stat_info.st_uid).pw_name
    except (ImportError, KeyError):
        pass
    try:
        import win32security
        sd = win32security.GetFileSecurity(
            str(stat_info), win32security.OWNER_SECURITY_INFORMATION
        )
        owner_sid = sd.GetSecurityDescriptorOwner()
        name, domain, _ = win32security.LookupAccountSid(None, owner_sid)
        return f"{domain}\\{name}"
    except Exception:
        pass
    try:
        return f"uid:{stat_info.st_uid}"
    except AttributeError:
        return "unknown"


class Graph:
    def __init__(self):
        self.nodes: dict[str, Node] = {}
        self.links: list[dict] = []
        self.adj: dict[str, list[str]] = defaultdict(list)
        self.root_path: str | None = None
        self.tags: dict[str, set[str]] = defaultdict(set)
        self.favorites: set[str] = set()
        self.web_content: str | None = None

    def add_node(self, node: Node):
        self.nodes[node.id] = node

    def add_link(self, source: str, target: str, link_type: str, label: str = ""):
        if source not in self.nodes or target not in self.nodes:
            return
        if source == target:
            return
        self.links.append({
            "source": source, "target": target,
            "type": link_type, "label": label,
        })
        self.adj[source].append(target)
        self.adj[target].append(source)

    def link_all(self):
        self._link_parent_folders()
        self._link_by_group("extension", "same_ext")
        self._link_by_group("folder", "same_folder")
        self._link_by_group("date", "same_date")
        self._link_web_findings()

    def _link_parent_folders(self):
        folders_by_path = {}
        for node in self.nodes.values():
            if node.kind == "folder":
                folders_by_path[node.path] = node.id

        for node in self.nodes.values():
            if node.kind == "folder":
                continue
            parent = str(Path(node.path).parent)
            if parent in folders_by_path:
                self.add_link(node.id, folders_by_path[parent], "parent_folder",
                              Path(parent).name)

    def _link_by_group(self, key: str, link_type: str):
        groups: dict[str, list[Node]] = defaultdict(list)
        for node in self.nodes.values():
            if node.kind == "folder":
                continue
            if key == "extension":
                val = node.info.get("extension", "")
            elif key == "folder":
                val = str(Path(node.path).parent)
            elif key == "date":
                val = node.info.get("modified", "")[:10]
            else:
                continue
            if val:
                groups[val].append(node)

        for val, members in groups.items():
            if len(members) < 2:
                continue
            label = Path(val).name if key == "folder" else val
            if len(members) <= 6:
                for i in range(len(members)):
                    for j in range(i + 1, len(members)):
                        self.add_link(members[i].id, members[j].id, link_type, label)
            else:
                members.sort(key=lambda n: n.info.get("modified", ""))
                for i in range(len(members) - 1):
                    self.add_link(members[i].id, members[i + 1].id, link_type, label)

    def _link_web_findings(self):
        page_node = None
        for node in self.nodes.values():
            if node.kind == "web_page":
                page_node = node
                break
        if not page_node:
            return

        page_id = page_node.id
        is_interactive = page_node.info.get("interactive", False)

        if is_interactive:
            self._link_interactive_web(page_id)
        else:
            for node in self.nodes.values():
                if node.kind in ("web_finding", "web_cookie", "web_request", "web_redirect", "web_console"):
                    self.add_link(node.id, page_id, "security", node.info.get("category", "security"))

    def _link_interactive_web(self, page_id: str):
        # build domain→request-node lookup
        domain_nodes = {}
        for node in self.nodes.values():
            if node.kind == "web_request":
                d = node.info.get("domain", "")
                if d:
                    domain_nodes[d] = node.id

        # first-party requests link to page, third-party link to page too but lighter
        for node in self.nodes.values():
            if node.kind == "web_request":
                if not node.info.get("third_party"):
                    self.add_link(node.id, page_id, "security", "first-party")
                else:
                    self.add_link(node.id, page_id, "web_third_party", "third-party")

        # redirects link between their domain nodes (or to page if no domain node)
        for node in self.nodes.values():
            if node.kind == "web_redirect":
                from_d = node.info.get("from_domain", "")
                to_d = node.info.get("to_domain", "")
                from_id = domain_nodes.get(from_d)
                to_id = domain_nodes.get(to_d)
                if from_id:
                    self.add_link(node.id, from_id, "redirect_chain", "redirect")
                if to_id and to_id != from_id:
                    self.add_link(node.id, to_id, "redirect_chain", "redirect")
                if not from_id and not to_id:
                    self.add_link(node.id, page_id, "security", "redirect")

        # cookies link to their domain's request node (or page)
        for node in self.nodes.values():
            if node.kind == "web_cookie":
                d = node.info.get("domain", "").lstrip(".")
                target = domain_nodes.get(d, page_id)
                self.add_link(node.id, target, "security", "cookie")

        # findings + console link to page
        for node in self.nodes.values():
            if node.kind in ("web_finding", "web_console"):
                self.add_link(node.id, page_id, "security", node.info.get("category", "security"))

    def add_context_link(self, source: str, target: str, context: str):
        """
        AI-driven contextual linking. the idea: ollama reads two nodes,
        decides they're related (shared secrets, similar content, same
        investigation thread) and drops a link. these plug straight into
        the MOC — context links get high affinity so they cluster near
        the focus node.

        TODO: hook this into chat.py so the AI can call it mid-conversation.
        for now it's manually callable and the frontend treats context
        links like first-class MOC connections.
        """
        self.add_link(source, target, "context", context)

    def to_cytoscape(self, focus_id: str | None = None, max_hops: int = 3) -> dict:
        if focus_id and focus_id in self.nodes:
            hops = self.bfs(focus_id, max_hops)
        else:
            hops = {nid: 0 for nid in self.nodes}

        elements = []
        visible = set(hops.keys())

        for nid, hop in hops.items():
            node = self.nodes[nid]
            elements.append({
                "group": "nodes",
                "data": {
                    "id": node.id,
                    "name": node.name,
                    "path": node.path,
                    "kind": node.kind,
                    "extension": node.info.get("extension", ""),
                    "is_hidden": node.is_hidden,
                    "is_deleted": node.is_deleted,
                    "is_system": node.is_system,
                    "modified": node.info.get("modified", ""),
                    "size": node.info.get("size", 0),
                    "severity": node.info.get("severity", ""),
                    "tags": list(self.tags.get(nid, [])),
                    "favorite": nid in self.favorites,
                    "_hop": hop,
                },
            })

        for link in self.links:
            if link["source"] in visible and link["target"] in visible:
                elements.append({
                    "group": "edges",
                    "data": {
                        "source": link["source"],
                        "target": link["target"],
                        "link_type": link["type"],
                        "label": link["label"],
                    },
                })

        return {"elements": elements}

    def search(self, query: str) -> list[dict]:
        q = query.lower()
        results = []
        for node in self.nodes.values():
            if q in node.name.lower() or q in node.path.lower():
                results.append({
                    "id": node.id, "name": node.name,
                    "path": node.path, "kind": node.kind,
                })
        return results[:50]

    def bfs(self, start_id: str, max_hops: int = 3) -> dict[str, int]:
        if start_id not in self.nodes:
            return {}
        visited = {start_id: 0}
        frontier = [start_id]
        for hop in range(1, max_hops + 1):
            next_frontier = []
            for nid in frontier:
                for neighbor in self.adj.get(nid, []):
                    if neighbor not in visited:
                        visited[neighbor] = hop
                        next_frontier.append(neighbor)
            frontier = next_frontier
        return visited

    def auto_focus(self) -> str | None:
        conn_counts = defaultdict(int)
        for link in self.links:
            conn_counts[link["source"]] += 1
            conn_counts[link["target"]] += 1

        user_nodes = [
            nid for nid, node in self.nodes.items()
            if node.kind != "folder" and not node.is_system
        ]
        if user_nodes:
            return max(user_nodes, key=lambda nid: conn_counts.get(nid, 0))
        if self.nodes:
            return max(self.nodes, key=lambda nid: conn_counts.get(nid, 0))
        return None

    def get_tree(self) -> list[dict]:
        is_web = self.root_path and self.root_path.startswith(("http://", "https://"))
        if is_web:
            return self._get_web_tree()
        return self._get_fs_tree()

    def _get_fs_tree(self) -> list[dict]:
        tree_map: dict[str, dict] = {}
        file_map: dict[str, list[dict]] = defaultdict(list)

        for node in self.nodes.values():
            if node.kind == "folder":
                tree_map[node.path] = {
                    "id": node.id, "name": node.name,
                    "path": node.path, "children": [], "files": [],
                }
            else:
                parent = str(Path(node.path).parent)
                file_map[parent].append({
                    "id": node.id, "name": node.name, "kind": node.kind,
                })

        for path, folder in tree_map.items():
            folder["files"] = sorted(file_map.get(path, []), key=lambda f: f["name"])

        roots = []
        for path, folder in sorted(tree_map.items()):
            parent_path = str(Path(path).parent)
            if parent_path in tree_map and parent_path != path:
                tree_map[parent_path]["children"].append(folder)
            else:
                roots.append(folder)

        return roots

    def _get_web_tree(self) -> list[dict]:
        categories = {
            "web_page": "Page",
            "web_headers": "Headers",
            "web_script": "Scripts",
            "web_style": "Stylesheets",
            "web_image": "Images",
            "web_link": "Links",
            "web_form": "Forms",
            "web_input": "Form Inputs",
            "web_iframe": "Iframes",
            "web_meta": "Meta Tags",
            "web_finding": "Security Findings",
            "web_cookie": "Cookies",
            "web_request": "Requests",
            "web_redirect": "Redirects",
            "web_console": "Console Messages",
        }

        groups: dict[str, list[dict]] = defaultdict(list)
        for node in self.nodes.values():
            label = categories.get(node.kind, "Other")
            url = node.info.get("url", node.path)
            groups[label].append({
                "id": node.id,
                "name": node.name,
                "kind": node.kind,
                "url": url,
                "third_party": node.info.get("third_party", False),
                "external": node.info.get("external", False),
                "domain": node.info.get("domain", ""),
            })

        tree = []
        for kind, label in categories.items():
            items = groups.get(label, [])
            if not items:
                continue
            tree.append({
                "id": f"_cat_{kind}",
                "name": f"{label} ({len(items)})",
                "children": [],
                "files": sorted(items, key=lambda f: f["name"]),
            })

        return tree

    def get_stats(self) -> dict:
        kind_counts = defaultdict(int)
        for node in self.nodes.values():
            kind_counts[node.kind] += 1
        link_type_counts = defaultdict(int)
        for link in self.links:
            link_type_counts[link["type"]] += 1
        return {
            "total_nodes": len(self.nodes),
            "total_links": len(self.links),
            "kinds": dict(kind_counts),
            "link_types": dict(link_type_counts),
            "root_path": self.root_path,
        }
