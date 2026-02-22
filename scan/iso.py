"""
dotty v2 — ISO 9660 scanner
by jLaHire
"""

from __future__ import annotations

import logging
from datetime import datetime

from graph import Node, make_id

log = logging.getLogger(__name__)


def scan_iso_image(iso_path: str) -> list[Node]:
    import pycdlib

    iso = pycdlib.PyCdlib()
    iso.open(str(iso_path))

    nodes = []

    try:
        volume_id = iso.pvd.volume_identifier.decode("utf-8").strip()
    except Exception:
        volume_id = "ISO"

    for dirpath, dirnames, filenames in iso.walk(iso_path="/"):
        for dname in dirnames:
            full = f"{dirpath}/{dname}" if dirpath != "/" else f"/{dname}"
            nodes.append(Node(
                id=make_id(f"iso:{full}"),
                name=dname,
                path=full,
                kind="folder",
                info={"volume": volume_id, "relative": full},
            ))

        for fname in filenames:
            full = f"{dirpath}/{fname}" if dirpath != "/" else f"/{fname}"
            info = {"volume": volume_id, "relative": full}

            try:
                entry = iso.get_entry(iso_path=full)
                info["size"] = entry.get_data_length()
                info["extension"] = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
                d = entry.date
                info["modified"] = datetime(
                    d.years_since_1900 + 1900, d.month, d.day_of_month,
                    d.hour, d.minute, d.second,
                ).isoformat()
            except Exception:
                info["size"] = 0
                info["extension"] = ""

            nodes.append(Node(
                id=make_id(f"iso:{full}"),
                name=fname,
                path=full,
                kind="file",
                info=info,
            ))

    iso.close()
    return nodes
