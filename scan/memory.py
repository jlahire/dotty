"""
dotty v2 — memory dump scanner
by jLaHire

volatility3 wrapper. pulls processes, files, network connections.
"""

from __future__ import annotations

import logging

from graph import Node, make_id

log = logging.getLogger(__name__)


def scan_memory_dump(dump_path: str) -> list[Node]:
    from volatility3.framework import contexts, automagic, plugins
    from volatility3 import framework

    ctx = contexts.Context()
    available = automagic.available(ctx)
    automagics = automagic.choose_automagic(available, ctx)
    ctx.config["automagic.LayerStacker.single_location"] = f"file://{dump_path}"

    nodes = []
    nodes.extend(_get_processes(ctx, automagics, framework, plugins))
    nodes.extend(_get_files(ctx, automagics, framework, plugins))
    return nodes


def _get_processes(ctx, automagics, framework, plugins) -> list[Node]:
    for plugin_name in ["windows.pslist.PsList", "linux.pslist.PsList"]:
        try:
            plugin_class = framework.import_class(f"volatility3.plugins.{plugin_name}")
            constructed = plugins.construct_plugin(ctx, automagics, plugin_class, "plugins", None, None)
            result = constructed.run()

            nodes = []
            for row in result:
                try:
                    pid = row[1]
                    name = str(row[2])
                    ppid = row[3]
                    threads = row[4]
                    handles = row[5]
                    create_time = str(row[7]) if len(row) > 7 else ""

                    nodes.append(Node(
                        id=make_id(f"proc:{pid}:{name}"),
                        name=name,
                        path=f"process/{pid}/{name}",
                        kind="process",
                        info={
                            "pid": pid, "ppid": ppid,
                            "threads": threads, "handles": handles,
                            "created": create_time,
                        },
                    ))
                except (IndexError, TypeError):
                    continue
            return nodes
        except Exception:
            continue
    return []


def _get_files(ctx, automagics, framework, plugins) -> list[Node]:
    try:
        plugin_class = framework.import_class("volatility3.plugins.windows.filescan.FileScan")
        constructed = plugins.construct_plugin(ctx, automagics, plugin_class, "plugins", None, None)
        result = constructed.run()

        nodes = []
        for row in result:
            if len(nodes) >= 5000:
                break
            try:
                offset = hex(row[0])
                name = str(row[1])
                size = row[2] if len(row) > 2 else 0

                nodes.append(Node(
                    id=make_id(f"memfile:{offset}:{name}"),
                    name=name.split("\\")[-1] if "\\" in name else name,
                    path=name,
                    kind="file",
                    info={
                        "offset": offset, "size": size,
                        "extension": name.split(".")[-1].lower() if "." in name else "",
                        "source": "memory_dump",
                    },
                ))
            except (IndexError, TypeError):
                continue
        return nodes
    except Exception:
        return []
