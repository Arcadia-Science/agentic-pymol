# pyright: reportMissingImports=false
"""
Wire-level framing: 4-byte big-endian length + JSON body, capped at 4 MB.
Used in both directions between the plugin and the MCP server.
"""

from __future__ import annotations
import json
import socket
import struct
from typing import Any

MAX_MESSAGE_BYTES = 4 * 1024 * 1024
LENGTH_HEADER = struct.Struct(">I")


def recv_exactly(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("peer closed during recv")
        buf.extend(chunk)
    return bytes(buf)


def recv_message(sock: socket.socket) -> dict[str, Any]:
    header = recv_exactly(sock, LENGTH_HEADER.size)
    (length,) = LENGTH_HEADER.unpack(header)
    if length > MAX_MESSAGE_BYTES:
        raise ValueError(f"message length {length} exceeds {MAX_MESSAGE_BYTES} byte cap")
    body = recv_exactly(sock, length)
    return json.loads(body.decode("utf-8"))


def send_message(sock: socket.socket, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    if len(body) > MAX_MESSAGE_BYTES:
        body = json.dumps(
            {
                "ok": False,
                "error": {
                    "type": "ResponseTooLarge",
                    "message": f"response of {len(body)} bytes exceeds {MAX_MESSAGE_BYTES} cap",
                    "traceback": "",
                },
                "stdout": "",
            }
        ).encode("utf-8")
    sock.sendall(LENGTH_HEADER.pack(len(body)) + body)
