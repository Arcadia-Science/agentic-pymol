"""
Tests for the port-discovery file written by the plugin and read by the
MCP server.

The plugin advertises its actually-bound port at `~/.config/pymol-mcp/port`
after the listening socket binds, and removes the file when the socket
closes. The MCP server's `_resolve_port()` reads that file when the
`PYMOL_MCP_PORT` env var is unset, so the two sides stay in sync even if
the user changes the port in the plugin's dialog.
"""

from __future__ import annotations
import socket
import time
from pathlib import Path
from typing import Any

import pytest

from .conftest import FakeCmd, _wait_for_port


class TestWritePortFile:
    def test_writes_port_atomically(self, plugin_module: Any) -> None:
        plugin_module._write_port_file(12345)
        assert plugin_module.PORT_PATH.read_text() == "12345"

    def test_remove_is_idempotent_when_absent(self, plugin_module: Any) -> None:
        assert not plugin_module.PORT_PATH.exists()
        plugin_module._remove_port_file()
        plugin_module._remove_port_file()

    def test_remove_deletes_when_present(self, plugin_module: Any) -> None:
        plugin_module._write_port_file(9999)
        assert plugin_module.PORT_PATH.exists()
        plugin_module._remove_port_file()
        assert not plugin_module.PORT_PATH.exists()


class TestServerLifecycle:
    def test_start_writes_actual_bound_port(
        self,
        plugin_module: Any,
        fake_pymol: FakeCmd,  # noqa: ARG002
    ) -> None:
        host = "127.0.0.1"
        probe = socket.socket()
        probe.bind((host, 0))
        free_port = probe.getsockname()[1]
        probe.close()

        server = plugin_module.SocketServer(host=host, port=free_port)
        server.start()
        try:
            _wait_for_port(host, free_port)
            assert plugin_module.PORT_PATH.read_text() == str(free_port)
        finally:
            server.stop()

    def test_stop_removes_port_file(
        self,
        plugin_module: Any,
        fake_pymol: FakeCmd,  # noqa: ARG002
    ) -> None:
        host = "127.0.0.1"
        probe = socket.socket()
        probe.bind((host, 0))
        free_port = probe.getsockname()[1]
        probe.close()

        server = plugin_module.SocketServer(host=host, port=free_port)
        server.start()
        _wait_for_port(host, free_port)
        assert plugin_module.PORT_PATH.exists()
        server.stop()
        assert not plugin_module.PORT_PATH.exists()

    def test_start_records_kernel_assigned_port_when_port_zero(
        self,
        plugin_module: Any,
        fake_pymol: FakeCmd,  # noqa: ARG002
    ) -> None:
        """`port=0` asks the kernel to assign; the file must reflect the
        actual port, not 0."""
        host = "127.0.0.1"
        server = plugin_module.SocketServer(host=host, port=0)
        server.start()
        try:
            deadline = time.monotonic() + 2.0
            while not plugin_module.PORT_PATH.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            recorded = int(plugin_module.PORT_PATH.read_text())
            assert recorded != 0
            assert 1024 <= recorded <= 65535
        finally:
            server.stop()


class TestResolvePort:
    def test_env_var_wins_over_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from agentic_pymol import app

        port_file = tmp_path / "port"
        port_file.write_text("11111")
        monkeypatch.setattr(app, "PORT_PATH", port_file)
        monkeypatch.setenv("PYMOL_MCP_PORT", "22222")
        assert app._resolve_port() == 22222

    def test_file_used_when_env_unset(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from agentic_pymol import app

        port_file = tmp_path / "port"
        port_file.write_text("33333")
        monkeypatch.setattr(app, "PORT_PATH", port_file)
        monkeypatch.delenv("PYMOL_MCP_PORT", raising=False)
        assert app._resolve_port() == 33333

    def test_default_when_neither_set(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from agentic_pymol import app
        from agentic_pymol.client import DEFAULT_PORT

        monkeypatch.setattr(app, "PORT_PATH", tmp_path / "port")
        monkeypatch.delenv("PYMOL_MCP_PORT", raising=False)
        assert app._resolve_port() == DEFAULT_PORT

    def test_empty_env_treated_as_unset(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from agentic_pymol import app

        port_file = tmp_path / "port"
        port_file.write_text("44444")
        monkeypatch.setattr(app, "PORT_PATH", port_file)
        monkeypatch.setenv("PYMOL_MCP_PORT", "   ")
        assert app._resolve_port() == 44444

    def test_empty_file_falls_back_to_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from agentic_pymol import app
        from agentic_pymol.client import DEFAULT_PORT

        port_file = tmp_path / "port"
        port_file.write_text("")
        monkeypatch.setattr(app, "PORT_PATH", port_file)
        monkeypatch.delenv("PYMOL_MCP_PORT", raising=False)
        assert app._resolve_port() == DEFAULT_PORT
