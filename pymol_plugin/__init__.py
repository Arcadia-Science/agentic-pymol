# pyright: reportMissingImports=false
"""
PyMOL plugin entry point.

PyMOL's plugin manager loads this package by directory and calls
`__init_plugin__` to register a menu item. Clicking the menu item opens the
dialog defined in `plugin.ui`; clicking "Start Listening" spawns the
`SocketServer` from `pymol_plugin.server`.

Implementation is split across:
- `auth.py`: shared-secret token (load / generate / verify)
- `framing.py`: length-prefixed JSON wire protocol
- `serialize.py`: PyMOL return-value -> JSON shape
- `handlers.py`: `op="call" | "iterate" | "exec" | "interrupt"` dispatch
- `server.py`: TCP accept loop, worker thread per connection

See `server.py` (the MCP-side `agentic_pymol`) for the matching client.
"""

from __future__ import annotations
import os
from typing import Any

from pymol_plugin.server import SocketServer

dialog: Any = None
socket_server: SocketServer | None = None
listening: bool = False
current_port: int = SocketServer().port


def __init_plugin__(app: Any = None) -> None:  # noqa: ARG001 -- PyMOL passes the app arg
    from pymol.plugins import addmenuitemqt

    addmenuitemqt("agentic-pymol plugin", run_plugin_gui)


def run_plugin_gui() -> None:
    global dialog
    if dialog is None:
        dialog = make_dialog()
    dialog.show()


def make_dialog() -> Any:
    from pymol.Qt import QtWidgets
    from pymol.Qt.utils import loadUi

    dlg = QtWidgets.QDialog()
    uifile = os.path.join(os.path.dirname(__file__), "plugin.ui")
    form = loadUi(uifile, dlg)
    form.input_port.setValue(current_port)
    _set_status(form, "Not listening")

    def toggle_listening() -> None:
        global socket_server, listening, current_port
        if not listening:
            current_port = form.input_port.value()
            socket_server = SocketServer(port=current_port)
            if socket_server.start():
                listening = True
                form.button_toggle_listening.setText("Stop Listening")
                _set_status(form, f"Listening on port {current_port}")
        else:
            if socket_server:
                socket_server.stop()
            listening = False
            form.button_toggle_listening.setText("Start Listening")
            _set_status(form, "Not listening")

    def close_dialog() -> None:
        global socket_server, listening
        if socket_server and listening:
            socket_server.stop()
            listening = False
        dlg.close()

    form.button_toggle_listening.clicked.connect(toggle_listening)
    form.button_close.clicked.connect(close_dialog)
    return dlg


def _set_status(form: Any, text: str) -> None:
    form.label_status.setText(text)
    if "Not listening" in text:
        form.label_status.setStyleSheet("color: red;")
    elif "Listening" in text:
        form.label_status.setStyleSheet("color: green;")
    else:
        form.label_status.setStyleSheet("")
