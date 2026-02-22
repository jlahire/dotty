"""
dotty v2 — forensic image scanner
by jLaHire

DD/RAW via pytsk3, E01 via dissect. walks filesystem entries,
extracts metadata, flags deleted files.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from graph import Node, make_id

log = logging.getLogger(__name__)


class DissectBridge:
    """wraps a dissect EWF stream so pytsk3 can read E01 images"""

    def __init__(self, ewf_path: str):
        from dissect.evidence.ewf import EWF
        self.stream = EWF(open(ewf_path, "rb"))

    def read(self, offset: int, size: int) -> bytes:
        self.stream.seek(offset)
        return self.stream.read(size)

    def get_size(self) -> int:
        return self.stream.size


def scan_forensic_image(image_path: str, progress=None) -> list[Node]:
    import pytsk3

    path = Path(image_path)
    ext = path.suffix.lower()

    if ext == ".e01":
        bridge = DissectBridge(str(path))
        img_info = pytsk3.Img_Info(url="", type=pytsk3.TSK_IMG_TYPE_EXTERNAL)
        img_info.read = bridge.read
        img_info.get_size = bridge.get_size
    else:
        img_info = pytsk3.Img_Info(str(path))

    fs_info = _detect_filesystem(pytsk3, img_info)
    if not fs_info:
        raise RuntimeError("No filesystem found in image")

    nodes = []
    _walk(pytsk3, fs_info, "/", nodes, depth=0, progress=progress)

    if progress:
        progress(1.0, f"Done — {len(nodes)} entries")

    return nodes


def _detect_filesystem(pytsk3, img_info):
    try:
        vol = pytsk3.Volume_Info(img_info)
        for part in vol:
            if part.flags == pytsk3.TSK_VS_PART_FLAG_ALLOC:
                try:
                    return pytsk3.FS_Info(img_info, offset=part.start * 512)
                except Exception:
                    continue
    except Exception:
        pass

    try:
        return pytsk3.FS_Info(img_info)
    except Exception:
        return None


def _walk(pytsk3, fs_info, path, nodes, depth=0, progress=None):
    if depth > 50:
        return

    try:
        directory = fs_info.open_dir(path=path)
    except Exception:
        return

    for entry in directory:
        try:
            name = entry.info.name.name.decode("utf-8", errors="replace")
        except Exception:
            continue

        if name in (".", ".."):
            continue

        full_path = f"{path}/{name}" if path != "/" else f"/{name}"
        is_dir = entry.info.meta and entry.info.meta.type == pytsk3.TSK_FS_META_TYPE_DIR
        is_deleted = bool(entry.info.name.flags & pytsk3.TSK_FS_NAME_FLAG_UNALLOC)

        info = {"relative": full_path}

        if entry.info.meta:
            meta = entry.info.meta
            info["inode"] = meta.addr
            info["size"] = meta.size if not is_dir else 0

            for field, attr in [("modified", "mtime"), ("accessed", "atime"),
                                ("created", "crtime"), ("changed", "ctime")]:
                ts = getattr(meta, attr, None)
                if ts and ts > 0:
                    try:
                        info[field] = datetime.fromtimestamp(ts).isoformat()
                    except (ValueError, OSError):
                        pass

        info["extension"] = Path(name).suffix.lower() if not is_dir else ""

        kind = "folder" if is_dir else "forensic"
        if is_deleted:
            kind = "deleted"

        nodes.append(Node(
            id=make_id(f"forensic:{full_path}"),
            name=name,
            path=full_path,
            kind=kind,
            info=info,
            is_deleted=is_deleted,
        ))

        if progress and len(nodes) % 200 == 0:
            progress(0.5, f"Found {len(nodes)} entries...")

        if is_dir and not is_deleted:
            try:
                _walk(pytsk3, fs_info, full_path, nodes, depth + 1, progress)
            except Exception:
                pass
