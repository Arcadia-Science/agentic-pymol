from __future__ import annotations
from typing import Any

from .conftest import TEST_TOKEN, FakeCmd, send_recv_raw


def _request(op: str, **fields: Any) -> dict[str, Any]:
    return {"op": op, "token": TEST_TOKEN, **fields}


def test_call_returns_serialized_value(
    running_plugin: tuple[str, int], fake_pymol: FakeCmd
) -> None:
    host, port = running_plugin
    response = send_recv_raw(
        host, port, _request("call", fn="echo", args=[{"a": 1, "b": [2, 3]}], kwargs={})
    )
    assert response["ok"] is True
    assert response["value"] == {"a": 1, "b": [2, 3]}


def test_call_unknown_attribute_returns_attribute_error(running_plugin: tuple[str, int]) -> None:
    host, port = running_plugin
    response = send_recv_raw(host, port, _request("call", fn="does_not_exist", args=[], kwargs={}))
    assert response["ok"] is False
    assert response["error"]["type"] == "AttributeError"


def test_call_invalid_identifier_rejected(running_plugin: tuple[str, int]) -> None:
    host, port = running_plugin
    response = send_recv_raw(host, port, _request("call", fn="echo; rm -rf /", args=[], kwargs={}))
    assert response["ok"] is False
    assert response["error"]["type"] == "BadRequest"


def test_call_empty_fn_rejected(running_plugin: tuple[str, int]) -> None:
    host, port = running_plugin
    response = send_recv_raw(host, port, _request("call", fn="", args=[], kwargs={}))
    assert response["ok"] is False
    assert response["error"]["type"] == "BadRequest"


def test_unknown_op_rejected(running_plugin: tuple[str, int]) -> None:
    host, port = running_plugin
    response = send_recv_raw(host, port, _request("nonsense"))
    assert response["ok"] is False
    assert response["error"]["type"] == "BadRequest"


def test_exec_runs_code_and_returns_expression(
    running_plugin: tuple[str, int], fake_pymol: FakeCmd
) -> None:
    host, port = running_plugin
    response = send_recv_raw(
        host,
        port,
        _request(
            "exec",
            code="result = cmd.echo(7) + cmd.echo(35)",
            return_expr="result",
        ),
    )
    assert response["ok"] is True
    assert response["value"] == 42
    assert fake_pymol.echo_calls == [7, 35]


def test_exec_without_return_expr_returns_none(
    running_plugin: tuple[str, int], fake_pymol: FakeCmd
) -> None:
    host, port = running_plugin
    response = send_recv_raw(host, port, _request("exec", code="cmd.echo(99)", return_expr=None))
    assert response["ok"] is True
    assert response["value"] is None
    assert fake_pymol.echo_calls == [99]


def test_exec_propagates_python_error(running_plugin: tuple[str, int]) -> None:
    host, port = running_plugin
    response = send_recv_raw(
        host, port, _request("exec", code="raise ValueError('boom')", return_expr=None)
    )
    assert response["ok"] is False
    assert response["error"]["type"] == "ValueError"
    assert "boom" in response["error"]["message"]


def test_iterate_invalid_property_rejected(running_plugin: tuple[str, int]) -> None:
    host, port = running_plugin
    response = send_recv_raw(
        host,
        port,
        _request(
            "iterate",
            selection="all",
            properties=["resi; rm -rf /"],
            state=None,
        ),
    )
    assert response["ok"] is False
    assert response["error"]["type"] == "BadRequest"


def test_iterate_empty_properties_rejected(running_plugin: tuple[str, int]) -> None:
    host, port = running_plugin
    response = send_recv_raw(
        host,
        port,
        _request(
            "iterate",
            selection="all",
            properties=[],
            state=None,
        ),
    )
    assert response["ok"] is False
    assert response["error"]["type"] == "BadRequest"
