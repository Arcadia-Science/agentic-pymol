"""
Test fixtures.

The plugin imports `pymol` lazily inside handlers, so tests inject a fake
`pymol` module into `sys.modules` and exercise the plugin against it. The
plugin is loaded from its hyphenated directory via importlib.

Token auth is bypassed by setting `PYMOL_MCP_TOKEN` to a fixed test value so
no real `~/.config/pymol-mcp/token` is created.
"""

from __future__ import annotations
import json
import socket
import struct
import sys
import threading
import time
import types
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TEST_TOKEN = "test-token-1234567890abcdef"
LENGTH_HEADER = struct.Struct(">I")


class FakeCmd:
    """
    Minimal stand-in for `pymol.cmd` used by tests.

    Every method appends a `(name, args, kwargs)` tuple to `self.calls` so
    tests can assert on dispatch arguments. Return values default to realistic
    PyMOL shapes; individual tests override via attributes like
    `fake_cmd.align_return = (...)` before invoking.
    """

    def __init__(self) -> None:
        self.interrupted = threading.Event()
        self.interrupt_calls = 0
        self.echo_calls: list[Any] = []
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.iterate_rows: list[dict[str, Any]] = []
        self.align_return: tuple[Any, ...] = (1.5, 100, 5, 2.5, 120, 800.0, 95)
        self.super_return: tuple[Any, ...] = (0.8, 80, 5, 1.2, 90, 750.0, 88)
        self.cealign_return: dict[str, Any] = {
            "RMSD": 2.3,
            "alignment_length": 75,
            "rotation_matrix": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0],
        }
        self.rms_return: float = 1.1
        self.rms_cur_return: float = 0.9
        self.alter_return: int = 42
        self.get_model_return: dict[str, Any] = {
            "_kind": "model",
            "atoms": [{"name": "CA", "resi": "1"}],
            "n_atoms": 1,
        }
        self.get_fastastr_return: str = ">obj_A\nMKL\n"
        self.get_distance_return: float = 3.8
        self.get_extent_return: list[list[float]] = [[-1.0, -2.0, -3.0], [4.0, 5.0, 6.0]]
        self.get_object_list_return: list[str] = ["obj1", "obj2"]
        self.get_names_return: list[str] = ["sel1"]
        self.get_chains_return: list[str] = ["A", "B"]
        self.count_atoms_return: int = 500
        self.count_states_return: int = 10
        self.get_view_return: list[float] = [float(i) for i in range(18)]
        self.get_coords_return: list[list[float]] | None = [[0.0, 1.0, 2.0], [3.0, 4.0, 5.0]]
        self.get_frame_return: int = 7
        self.get_state_return: int = 3
        self.png_payload: bytes = b"\x89PNG\r\n\x1a\nfake-png-bytes"

    def _record(self, name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        self.calls.append((name, args, kwargs))

    def interrupt(self) -> None:
        self.interrupt_calls += 1
        self.interrupted.set()

    def echo(self, x: Any) -> Any:
        self.echo_calls.append(x)
        return x

    def slow(self, duration: float = 0.5) -> str:
        time.sleep(duration)
        return "done"

    def align(self, *args: Any, **kwargs: Any) -> tuple[Any, ...]:
        self._record("align", args, kwargs)
        return self.align_return

    def super(self, *args: Any, **kwargs: Any) -> tuple[Any, ...]:
        self._record("super", args, kwargs)
        return self.super_return

    def cealign(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self._record("cealign", args, kwargs)
        return self.cealign_return

    def rms(self, *args: Any, **kwargs: Any) -> float:
        self._record("rms", args, kwargs)
        return self.rms_return

    def rms_cur(self, *args: Any, **kwargs: Any) -> float:
        self._record("rms_cur", args, kwargs)
        return self.rms_cur_return

    def iterate(self, selection: str, expression: str, space: dict[str, Any]) -> int:
        self._record("iterate", (selection, expression), {})
        for row in self.iterate_rows:
            space["_acc"].append(dict(row))
        return len(self.iterate_rows)

    def iterate_state(
        self, state: int, selection: str, expression: str, space: dict[str, Any]
    ) -> int:
        self._record("iterate_state", (state, selection, expression), {})
        for row in self.iterate_rows:
            space["_acc"].append(dict(row))
        return len(self.iterate_rows)

    def alter(self, *args: Any, **kwargs: Any) -> int:
        self._record("alter", args, kwargs)
        return self.alter_return

    def get_model(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self._record("get_model", args, kwargs)
        return self.get_model_return

    def get_fastastr(self, *args: Any, **kwargs: Any) -> str:
        self._record("get_fastastr", args, kwargs)
        return self.get_fastastr_return

    def fetch(self, *args: Any, **kwargs: Any) -> None:
        self._record("fetch", args, kwargs)

    def load(self, *args: Any, **kwargs: Any) -> None:
        self._record("load", args, kwargs)

    def save(self, *args: Any, **kwargs: Any) -> None:
        self._record("save", args, kwargs)

    def png(self, filename: str, *args: Any, **kwargs: Any) -> None:
        self._record("png", (filename, *args), kwargs)
        Path(filename).write_bytes(self.png_payload)

    def get_distance(self, *args: Any, **kwargs: Any) -> float:
        self._record("get_distance", args, kwargs)
        return self.get_distance_return

    def get_extent(self, *args: Any, **kwargs: Any) -> list[list[float]]:
        self._record("get_extent", args, kwargs)
        return self.get_extent_return

    def get_object_list(self, *args: Any, **kwargs: Any) -> list[str]:
        self._record("get_object_list", args, kwargs)
        return self.get_object_list_return

    def get_names(self, *args: Any, **kwargs: Any) -> list[str]:
        self._record("get_names", args, kwargs)
        return self.get_names_return

    def get_chains(self, *args: Any, **kwargs: Any) -> list[str]:
        self._record("get_chains", args, kwargs)
        return self.get_chains_return

    def count_atoms(self, *args: Any, **kwargs: Any) -> int:
        self._record("count_atoms", args, kwargs)
        return self.count_atoms_return

    def count_states(self, *args: Any, **kwargs: Any) -> int:
        self._record("count_states", args, kwargs)
        return self.count_states_return

    def get_view(self, *args: Any, **kwargs: Any) -> list[float]:
        self._record("get_view", args, kwargs)
        return self.get_view_return

    def set_view(self, *args: Any, **kwargs: Any) -> None:
        self._record("set_view", args, kwargs)

    def get_coords(self, *args: Any, **kwargs: Any) -> list[list[float]] | None:
        self._record("get_coords", args, kwargs)
        return self.get_coords_return

    def get_frame(self, *args: Any, **kwargs: Any) -> int:
        self._record("get_frame", args, kwargs)
        return self.get_frame_return

    def get_state(self, *args: Any, **kwargs: Any) -> int:
        self._record("get_state", args, kwargs)
        return self.get_state_return

    def do(self, *args: Any, **kwargs: Any) -> None:
        self._record("do", args, kwargs)
        print(f"did: {args[0] if args else ''}")


@pytest.fixture(autouse=True)
def _set_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYMOL_MCP_TOKEN", TEST_TOKEN)


@pytest.fixture
def fake_cmd() -> FakeCmd:
    return FakeCmd()


@pytest.fixture
def fake_pymol(fake_cmd: FakeCmd) -> Iterator[FakeCmd]:
    pymol_mod = types.ModuleType("pymol")
    pymol_mod.cmd = fake_cmd  # type: ignore
    sys.modules["pymol"] = pymol_mod
    yield fake_cmd
    sys.modules.pop("pymol", None)


@pytest.fixture
def plugin_module() -> Iterator[Any]:
    import logging

    import pymol_plugin

    pymol_plugin._token = None
    pymol_plugin.socket_server = None
    pymol_plugin.listening = False
    logging.getLogger("pymol-mcp-plugin").setLevel(logging.CRITICAL)
    yield pymol_plugin
    if pymol_plugin.socket_server is not None and pymol_plugin.listening:
        pymol_plugin.socket_server.stop()
        pymol_plugin.socket_server = None
        pymol_plugin.listening = False


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_for_port(host: str, port: int, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        probe = socket.socket()
        probe.settimeout(0.1)
        result = probe.connect_ex((host, port))
        probe.close()
        if result == 0:
            return
        time.sleep(0.02)
    raise RuntimeError(f"port {port} did not open within {timeout}s")


@pytest.fixture
def running_plugin(plugin_module: Any, fake_pymol: FakeCmd) -> Iterator[tuple[str, int]]:
    host = "127.0.0.1"
    port = _free_port()
    server = plugin_module.SocketServer(host=host, port=port)
    server.start()
    _wait_for_port(host, port)
    yield host, port
    server.stop()


def send_recv_raw(
    host: str, port: int, request: dict[str, Any], timeout: float = 5.0
) -> dict[str, Any]:
    """Bypass PyMOLClient for tests that need to manipulate the request envelope directly."""
    body = json.dumps(request).encode("utf-8")
    sock = socket.create_connection((host, port), timeout=timeout)
    sock.settimeout(timeout)
    sock.sendall(LENGTH_HEADER.pack(len(body)) + body)
    header = _recv_exactly(sock, LENGTH_HEADER.size)
    (length,) = LENGTH_HEADER.unpack(header)
    payload = _recv_exactly(sock, length)
    sock.close()
    return json.loads(payload.decode("utf-8"))


def _recv_exactly(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("peer closed during recv")
        buf.extend(chunk)
    return bytes(buf)


@pytest.fixture
def server_module(plugin_module: Any) -> Any:
    """The agentic_pymol package — used by tests that exercise PyMOLClient/PyMOLError."""
    pytest.importorskip("mcp")
    import agentic_pymol

    return agentic_pymol
