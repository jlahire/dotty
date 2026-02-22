"""
dotty v2 — live directory scanner
by jLaHire
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from graph import Node, make_id, is_system_file, get_owner

log = logging.getLogger(__name__)


def scan_directory(root: str, progress=None) -> list[Node]:
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise ValueError(f"Not a directory: {root}")

    nodes: list[Node] = []
    items = list(root_path.rglob("*"))
    total = len(items)

    for i, item in enumerate(items):
        try:
            node = _make_node(item, root_path)
            if node:
                nodes.append(node)
        except (PermissionError, OSError):
            pass

        if progress and total > 0 and i % 100 == 0:
            progress(i / total, f"Scanned {i}/{total}")

    if progress:
        progress(1.0, f"Done — {len(nodes)} nodes")

    return nodes


def _make_node(item: Path, root: Path) -> Node | None:
    try:
        stat = item.stat()
    except (PermissionError, OSError):
        return None

    kind = "folder" if item.is_dir() else "file"
    path_str = str(item)
    owner = get_owner(stat)

    return Node(
        id=make_id(path_str),
        name=item.name,
        path=path_str,
        kind=kind,
        info={
            "size": stat.st_size if not item.is_dir() else 0,
            "extension": item.suffix.lower() if not item.is_dir() else "",
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "accessed": datetime.fromtimestamp(stat.st_atime).isoformat(),
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "owner": owner,
            "relative": str(item.relative_to(root)),
        },
        is_hidden=item.name.startswith("."),
        is_system=is_system_file(path_str, owner),
    )
