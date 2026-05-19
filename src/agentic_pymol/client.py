from __future__ import annotations
import json
import logging
import socket
import struct
import time
from contextlib import suppress
from typing import Any

from agentic_pymol.auth import load_token
from agentic_pymol.errors import PyMOLError
from agentic_pymol.responses import OkResponse

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9876
LENGTH_HEADER = struct.Struct(">I")
MAX_MESSAGE_BYTES = 4 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 60.0

logger = logging.getLogger("pymol-mcp")


class PyMOLClient:
    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock: socket.socket | None = None
        self._token: str | None = None

    def _get_token(self) -> str:
        if self._token is None:
            self._token = load_token()
        return self._token

    def _ensure_connected(self) -> socket.socket:
        if self._sock is not None:
            return self._sock
        try:
            sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        except OSError as e:
            raise PyMOLError(
                "ConnectionError",
                f"could not connect to PyMOL plugin at {self.host}:{self.port} ({e}). "
                f"Is PyMOL running and the MCP plugin started?",
                "",
                "",
            ) from None
        sock.settimeout(self.timeout)
        self._sock = sock
        logger.info(f"connected to PyMOL plugin at {self.host}:{self.port}")
        return sock

    def _close(self) -> None:
        if self._sock is None:
            return
        try:
            self._sock.close()
        except OSError:
            pass
        self._sock = None

    def _best_effort_interrupt(self) -> None:
        if self._token is None:
            return
        body = json.dumps({"op": "interrupt", "token": self._token}).encode("utf-8")
        frame = LENGTH_HEADER.pack(len(body)) + body
        with suppress(OSError):
            with socket.create_connection((self.host, self.port), timeout=2.0) as side:
                side.sendall(frame)
                logger.info("sent interrupt to PyMOL plugin (best-effort)")

    def _send_recv(self, request: dict[str, Any], timeout: float) -> dict[str, Any]:
        sock = self._ensure_connected()
        sock.settimeout(timeout)
        request = {**request, "token": self._get_token()}
        body = json.dumps(request).encode("utf-8")
        if len(body) > MAX_MESSAGE_BYTES:
            raise PyMOLError(
                "RequestTooLarge",
                f"request size {len(body)} exceeds {MAX_MESSAGE_BYTES} cap",
                "",
                "",
            )
        try:
            sock.sendall(LENGTH_HEADER.pack(len(body)) + body)
            header = _recv_exactly(sock, LENGTH_HEADER.size)
            (length,) = LENGTH_HEADER.unpack(header)
            if length > MAX_MESSAGE_BYTES:
                self._close()
                raise PyMOLError(
                    "ResponseTooLarge",
                    f"response size {length} exceeds {MAX_MESSAGE_BYTES} cap",
                    "",
                    "",
                )
            response_bytes = _recv_exactly(sock, length)
        except TimeoutError:
            self._close()
            self._best_effort_interrupt()
            raise PyMOLError(
                "TransportTimeout",
                f"call exceeded {timeout}s; interrupt sent to PyMOL — long C-layer ops "
                f"(e.g. ray) will bail out, pure-Python loops may not",
                "",
                "",
            ) from None
        except (BrokenPipeError, ConnectionResetError, ConnectionError, OSError) as e:
            self._close()
            raise PyMOLError("TransportError", f"socket I/O failed: {e}", "", "") from None
        return json.loads(response_bytes.decode("utf-8"))

    def _do(
        self, request: dict[str, Any], tool_name: str, timeout: float | None = None
    ) -> OkResponse:
        effective_timeout = timeout if timeout is not None else self.timeout
        start = time.monotonic()
        raw = self._send_recv(request, effective_timeout)
        duration_ms = int((time.monotonic() - start) * 1000)
        envelope = OkResponse.from_envelope(raw)
        logger.info(f"{tool_name} ok=True duration_ms={duration_ms}")
        return envelope

    def call(
        self,
        fn: str,
        args: list[Any],
        kwargs: dict[str, Any],
        tool_name: str,
        timeout: float | None = None,
    ) -> OkResponse:
        return self._do(
            {"op": "call", "fn": fn, "args": args, "kwargs": kwargs}, tool_name, timeout=timeout
        )

    def iterate(
        self,
        selection: str,
        properties: list[str],
        state: int | None,
        tool_name: str,
        timeout: float | None = None,
    ) -> OkResponse:
        return self._do(
            {"op": "iterate", "selection": selection, "properties": properties, "state": state},
            tool_name,
            timeout=timeout,
        )

    def exec_code(
        self, code: str, return_expr: str | None, tool_name: str, timeout: float | None = None
    ) -> OkResponse:
        return self._do(
            {"op": "exec", "code": code, "return_expr": return_expr}, tool_name, timeout=timeout
        )


def _recv_exactly(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("peer closed during recv")
        buf.extend(chunk)
    return bytes(buf)
