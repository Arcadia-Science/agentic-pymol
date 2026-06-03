"""
Tests for the cancellation path.

`test_op_interrupt_calls_cmd_interrupt` exercises the plugin's `op="interrupt"`
handler in isolation.

`test_timeout_triggers_side_channel_interrupt` is the integration test for the
real failure mode we care about: a long-running call that exceeds the
PyMOLClient timeout. It asserts that on `socket.timeout` the client opens a
*fresh* connection, fires `op="interrupt"`, and then surfaces a
`TransportTimeout` to the caller. The plugin records `cmd.interrupt()` having
been called by the side connection.
"""

from __future__ import annotations
import threading
import time
from typing import Any

import pytest

from .conftest import TEST_TOKEN, FakeCmd, send_recv_raw


def test_op_interrupt_calls_cmd_interrupt(
    running_plugin: tuple[str, int], fake_pymol: FakeCmd
) -> None:
    host, port = running_plugin
    response = send_recv_raw(host, port, {"op": "interrupt", "token": TEST_TOKEN})
    assert response["ok"] is True
    assert fake_pymol.interrupted.wait(timeout=1.0)
    assert fake_pymol.interrupt_calls == 1


def test_timeout_triggers_side_channel_interrupt(
    running_plugin: tuple[str, int],
    fake_pymol: FakeCmd,
    server_module: Any,
) -> None:
    host, port = running_plugin
    client = server_module.PyMOLClient(host=host, port=port, timeout=0.15)

    with pytest.raises(server_module.PyMOLError) as excinfo:
        client.call("slow", [], {"duration": 1.0}, "test_call")

    assert excinfo.value.error_type == "TransportTimeout"
    assert fake_pymol.interrupted.wait(timeout=2.0), (
        "expected the MCP server to fire op=interrupt on timeout"
    )
    assert fake_pymol.interrupt_calls >= 1


def test_no_interrupt_on_clean_transport_error(
    running_plugin: tuple[str, int],
    fake_pymol: FakeCmd,
    server_module: Any,
) -> None:
    """Plain transport errors (e.g., peer crash) should NOT trigger interrupt — only timeouts do."""
    host, port = running_plugin
    client = server_module.PyMOLClient(host=host, port=port, timeout=2.0)

    client.call("echo", ["warmup"], {}, "warmup")
    assert fake_pymol.interrupt_calls == 0

    client._sock.close()
    client._sock = None
    client._sock = client._ensure_connected()
    client._sock.shutdown(1)

    with pytest.raises(server_module.PyMOLError) as excinfo:
        client.call("echo", ["after-shutdown"], {}, "second_call")
    assert excinfo.value.error_type == "TransportError"
    time.sleep(0.2)
    assert fake_pymol.interrupt_calls == 0


def test_interrupt_works_concurrently_with_in_flight_call(
    running_plugin: tuple[str, int],
    fake_pymol: FakeCmd,
) -> None:
    """The plugin must accept a fresh connection for op=interrupt while another worker is busy."""
    host, port = running_plugin

    slow_done = threading.Event()
    slow_response: dict[str, Any] = {}

    def fire_slow() -> None:
        slow_response.update(
            send_recv_raw(
                host,
                port,
                {
                    "op": "call",
                    "fn": "slow",
                    "args": [],
                    "kwargs": {"duration": 0.3},
                    "token": TEST_TOKEN,
                },
                timeout=5.0,
            )
        )
        slow_done.set()

    t = threading.Thread(target=fire_slow, daemon=True)
    t.start()

    time.sleep(0.05)

    interrupt_response = send_recv_raw(host, port, {"op": "interrupt", "token": TEST_TOKEN})
    assert interrupt_response["ok"] is True
    assert fake_pymol.interrupt_calls == 1

    assert slow_done.wait(timeout=2.0)
    assert slow_response.get("ok") is True
    assert slow_response.get("value") == "done"
