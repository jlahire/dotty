"""
dotty v2 — windows prefetch analyzer
by jLaHire

MAM decompression, prefetch struct parsing across XP through Win11.
"""

from __future__ import annotations

import logging
import struct
from datetime import datetime, timedelta
from pathlib import Path

from graph import Node, make_id

log = logging.getLogger(__name__)

FILETIME_EPOCH = datetime(1601, 1, 1)

VERSION_OFFSETS = {
    17: {"run_count": 0x90, "last_exec": 0x78, "exec_size": 8, "exec_count": 1},
    23: {"run_count": 0x98, "last_exec": 0x80, "exec_size": 8, "exec_count": 1},
    26: {"run_count": 0xD0, "last_exec": 0x80, "exec_size": 8, "exec_count": 8},
    30: {"run_count": 0xD0, "last_exec": 0x80, "exec_size": 8, "exec_count": 8},
}


def analyze_prefetch(root_path: str) -> list[Node]:
    root = Path(root_path)
    nodes = []

    for pf in root.rglob("*.pf"):
        try:
            node = _parse_prefetch(pf)
            if node:
                nodes.append(node)
        except Exception as e:
            log.debug(f"prefetch {pf}: {e}")

    return nodes


def _parse_prefetch(pf_path: Path) -> Node | None:
    data = pf_path.read_bytes()

    if data[:4] == b"MAM\x04":
        data = _decompress_mam(data)

    if len(data) < 0x54:
        return None

    version = struct.unpack("<I", data[0:4])[0]
    offsets = VERSION_OFFSETS.get(version)
    if not offsets:
        return None

    exe_name = data[0x10:0x10 + 60].decode("utf-16-le", errors="ignore").rstrip("\x00")
    pf_hash = struct.unpack("<I", data[0x4C:0x50])[0]

    rc_off = offsets["run_count"]
    run_count = struct.unpack("<I", data[rc_off:rc_off + 4])[0] if len(data) > rc_off + 4 else 0

    exec_times = []
    le_off = offsets["last_exec"]
    for i in range(offsets["exec_count"]):
        off = le_off + i * offsets["exec_size"]
        if off + 8 > len(data):
            break
        ft = struct.unpack("<Q", data[off:off + 8])[0]
        if ft > 0:
            try:
                dt = FILETIME_EPOCH + timedelta(microseconds=ft // 10)
                exec_times.append(dt.isoformat())
            except (ValueError, OverflowError):
                pass

    return Node(
        id=make_id(f"pf:{pf_path}:{pf_hash}"),
        name=exe_name,
        path=str(pf_path),
        kind="prefetch",
        info={
            "exe_name": exe_name,
            "hash": f"0x{pf_hash:08X}",
            "run_count": run_count,
            "last_executed": exec_times[0] if exec_times else "",
            "execution_times": exec_times,
            "version": version,
            "extension": ".exe",
        },
    )


def _decompress_mam(compressed: bytes) -> bytes:
    if len(compressed) < 8:
        raise ValueError("MAM header too short")

    uncompressed_size = struct.unpack("<I", compressed[4:8])[0]
    payload = compressed[8:]
    return _lznt1_decompress(payload, uncompressed_size)


def _lznt1_decompress(data: bytes, expected_size: int) -> bytes:
    output = bytearray()
    pos = 0

    while pos < len(data) and len(output) < expected_size:
        if pos + 2 > len(data):
            break

        chunk_header = struct.unpack("<H", data[pos:pos + 2])[0]
        pos += 2

        if chunk_header == 0:
            break

        chunk_size = (chunk_header & 0x0FFF) + 1
        is_compressed = (chunk_header & 0x8000) != 0
        chunk_end = pos + chunk_size

        if chunk_end > len(data):
            chunk_end = len(data)

        if not is_compressed:
            output.extend(data[pos:chunk_end])
            pos = chunk_end
            continue

        while pos < chunk_end and len(output) < expected_size:
            if pos >= len(data):
                break
            flags = data[pos]
            pos += 1

            for bit in range(8):
                if pos >= chunk_end or len(output) >= expected_size:
                    break

                if not (flags & (1 << bit)):
                    output.append(data[pos])
                    pos += 1
                else:
                    if pos + 2 > len(data):
                        break
                    token = struct.unpack("<H", data[pos:pos + 2])[0]
                    pos += 2

                    out_len = len(output)
                    if out_len < 0x10:
                        length_bits = 12
                    elif out_len < 0x20:
                        length_bits = 11
                    elif out_len < 0x40:
                        length_bits = 10
                    elif out_len < 0x80:
                        length_bits = 9
                    elif out_len < 0x100:
                        length_bits = 8
                    elif out_len < 0x200:
                        length_bits = 7
                    elif out_len < 0x400:
                        length_bits = 6
                    elif out_len < 0x800:
                        length_bits = 5
                    elif out_len < 0x1000:
                        length_bits = 4
                    else:
                        length_bits = 4

                    length_mask = (1 << length_bits) - 1
                    match_length = (token & length_mask) + 3
                    position_bits = 16 - length_bits
                    match_distance = (token >> length_bits) + 1

                    for _ in range(match_length):
                        if len(output) >= expected_size:
                            break
                        src = len(output) - match_distance
                        if src < 0:
                            output.append(0)
                        else:
                            output.append(output[src])

    return bytes(output[:expected_size])
