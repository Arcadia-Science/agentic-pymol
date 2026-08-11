"""
Tests for the module-level `start_listening` / `stop_listening` entry points, including
that the dialog's "Start Listening" button still goes through them.
"""

from __future__ import annotations
import socket
import sys
import time
import types
from typing import Any

import pytest

from .conftest import _free_port, _wait_for_port

# The dialog overwrites the port spin box with the module's `current_port` when it is built,
# so the value the fake form starts with is never the one the toggle test actually uses.
DEFAULT_FAKE_PORT = 9999


def _wait_for_port_closed(host: str, port: int, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        probe = socket.socket()
        probe.settimeout(0.1)
        result = probe.connect_ex((host, port))
        probe.close()
        if result != 0:
            return
        time.sleep(0.02)
    raise AssertionError(f"port {port} was still accepting connections after {timeout}s")


def test_entry_points_exist_at_module_scope(plugin_module: Any) -> None:
    assert callable(plugin_module.start_listening)
    assert callable(plugin_module.stop_listening)


def test_start_listening_opens_the_port(plugin_module: Any) -> None:
    port = _free_port()
    assert plugin_module.start_listening(port) is True
    assert plugin_module.listening is True
    assert plugin_module.current_port == port
    assert plugin_module.socket_server is not None

    _wait_for_port("127.0.0.1", port)
    connection = socket.create_connection(("127.0.0.1", port), timeout=2.0)
    connection.close()

    plugin_module.stop_listening()
    assert plugin_module.listening is False
    _wait_for_port_closed("127.0.0.1", port)
    assert plugin_module.socket_server.thread is None


def test_start_listening_is_idempotent(plugin_module: Any) -> None:
    port = _free_port()
    assert plugin_module.start_listening(port) is True
    server = plugin_module.socket_server

    assert plugin_module.start_listening(_free_port()) is True
    assert plugin_module.socket_server is server
    assert plugin_module.current_port == port

    plugin_module.stop_listening()


def test_stop_listening_is_safe_when_not_listening(plugin_module: Any) -> None:
    assert plugin_module.listening is False
    plugin_module.stop_listening()
    assert plugin_module.listening is False


class FakeSpinBox:
    def __init__(self, value: int) -> None:
        self._value = value

    def setValue(self, value: int) -> None:
        self._value = value

    def value(self) -> int:
        return self._value


class FakeSignal:
    def __init__(self) -> None:
        self.slot: Any = None

    def connect(self, slot: Any) -> None:
        self.slot = slot


class FakeButton:
    def __init__(self) -> None:
        self.text = ""
        self.clicked = FakeSignal()

    def setText(self, text: str) -> None:
        self.text = text


class FakeLabel:
    def __init__(self) -> None:
        self.text = ""

    def setText(self, text: str) -> None:
        self.text = text

    def setStyleSheet(self, style: str) -> None:
        pass


class FakeForm:
    def __init__(self, port: int) -> None:
        self.input_port = FakeSpinBox(port)
        self.button_toggle_listening = FakeButton()
        self.button_close = FakeButton()
        self.label_status = FakeLabel()

    def show(self) -> None:
        pass

    def close(self) -> None:
        pass


@pytest.fixture
def fake_qt(monkeypatch: pytest.MonkeyPatch) -> Any:
    """
    Install a fake `pymol.Qt` so `make_dialog` can be built without a running PyMOL,
    and return the form it loads.
    """
    form = FakeForm(port=DEFAULT_FAKE_PORT)

    qt_module = types.ModuleType("pymol.Qt")
    qt_module.QtWidgets = types.SimpleNamespace(QDialog=lambda: form)  # type: ignore
    utils_module = types.ModuleType("pymol.Qt.utils")
    utils_module.loadUi = lambda uifile, dlg: form  # type: ignore

    monkeypatch.setitem(sys.modules, "pymol", types.ModuleType("pymol"))
    monkeypatch.setitem(sys.modules, "pymol.Qt", qt_module)
    monkeypatch.setitem(sys.modules, "pymol.Qt.utils", utils_module)
    return form


def test_toggle_listening_routes_through_the_entry_points(
    plugin_module: Any, fake_qt: FakeForm
) -> None:
    """
    Tests that the dialog's button still starts and stops the listener, and still
    updates the button and status labels the same way.
    """
    plugin_module.make_dialog()
    toggle = fake_qt.button_toggle_listening.clicked.slot

    port = _free_port()
    fake_qt.input_port.setValue(port)

    toggle()
    assert plugin_module.listening is True
    assert plugin_module.current_port == port
    assert fake_qt.button_toggle_listening.text == "Stop Listening"
    assert fake_qt.label_status.text == f"Listening on port {port}"
    _wait_for_port("127.0.0.1", port)

    toggle()
    assert plugin_module.listening is False
    assert fake_qt.button_toggle_listening.text == "Start Listening"
    assert fake_qt.label_status.text == "Not listening"
    _wait_for_port_closed("127.0.0.1", port)


def test_dialog_opened_after_a_headless_start_shows_the_listener_as_running(
    plugin_module: Any, fake_qt: FakeForm
) -> None:
    """
    Tests that a dialog built while the listener is already running reflects that, so its
    button does not offer to start a listener that is up -- which would stop it instead.
    """
    port = _free_port()
    assert plugin_module.start_listening(port) is True
    _wait_for_port("127.0.0.1", port)

    plugin_module.make_dialog()
    assert fake_qt.button_toggle_listening.text == "Stop Listening"
    assert fake_qt.label_status.text == f"Listening on port {port}"

    fake_qt.button_toggle_listening.clicked.slot()
    assert plugin_module.listening is False
    _wait_for_port_closed("127.0.0.1", port)
