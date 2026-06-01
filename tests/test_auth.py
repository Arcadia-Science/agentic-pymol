from __future__ import annotations
from pathlib import Path
from typing import Any

import pytest

from .conftest import TEST_TOKEN, FakeCmd, send_recv_raw


def test_correct_token_allows_call(running_plugin: tuple[str, int], fake_pymol: FakeCmd) -> None:
    host, port = running_plugin
    response = send_recv_raw(
        host,
        port,
        {
            "op": "call",
            "fn": "echo",
            "args": ["hello"],
            "kwargs": {},
            "token": TEST_TOKEN,
        },
    )
    assert response["ok"] is True
    assert response["value"] == "hello"
    assert fake_pymol.echo_calls == ["hello"]


@pytest.mark.parametrize("bad_token", ["", "wrong-token", "x" * 64])
def test_wrong_token_rejected(
    running_plugin: tuple[str, int], fake_pymol: FakeCmd, bad_token: str
) -> None:
    host, port = running_plugin
    response = send_recv_raw(
        host,
        port,
        {
            "op": "call",
            "fn": "echo",
            "args": ["hello"],
            "kwargs": {},
            "token": bad_token,
        },
    )
    assert response["ok"] is False
    assert response["error"]["type"] == "Unauthorized"
    assert fake_pymol.echo_calls == []


def test_missing_token_rejected(running_plugin: tuple[str, int], fake_pymol: FakeCmd) -> None:
    host, port = running_plugin
    response = send_recv_raw(
        host,
        port,
        {
            "op": "call",
            "fn": "echo",
            "args": ["hello"],
            "kwargs": {},
        },
    )
    assert response["ok"] is False
    assert response["error"]["type"] == "Unauthorized"
    assert fake_pymol.echo_calls == []


def test_non_string_token_rejected(running_plugin: tuple[str, int]) -> None:
    host, port = running_plugin
    request: dict[str, Any] = {"op": "call", "fn": "echo", "args": [], "kwargs": {}, "token": 12345}
    response = send_recv_raw(host, port, request)
    assert response["ok"] is False
    assert response["error"]["type"] == "Unauthorized"


def test_empty_token_source_does_not_authorize_empty_peer(
    plugin_module: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Tests that empty token file doesn't bypass auth"""
    monkeypatch.delenv("PYMOL_MCP_TOKEN", raising=False)
    (tmp_path / "token").write_text("")
    monkeypatch.setattr(plugin_module, "TOKEN_PATH", tmp_path / "token")
    assert not plugin_module.token_ok("")
