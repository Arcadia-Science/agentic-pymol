"""Shared instances: the FastMCP application, the singleton PyMOLClient, and
the `surface_pymol_error` decorator that fattens `PyMOLError` so its stdout
and traceback survive FastMCP's `str(exception)` serialization to the agent."""

from __future__ import annotations
import os
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from agentic_pymol.client import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT_SECONDS,
    PyMOLClient,
)
from agentic_pymol.errors import PyMOLError

PORT_PATH = Path.home() / ".config" / "pymol-mcp" / "port"


def _resolve_port() -> int:
    """Precedence: `PYMOL_MCP_PORT` env > `~/.config/pymol-mcp/port` written
    by the plugin on `start()` > `DEFAULT_PORT`.

    The plugin writes the file once its listening socket has actually bound;
    a missing file means either the plugin isn't running yet (so falling back
    to the default is as good as anything) or it crashed without cleanup (in
    which case the connect will fail with the existing ConnectionError, which
    is the right user-facing signal).
    """
    env = os.environ.get("PYMOL_MCP_PORT", "").strip()
    if env:
        return int(env)
    if PORT_PATH.exists():
        text = PORT_PATH.read_text().strip()
        if text:
            return int(text)
    return DEFAULT_PORT


mcp = FastMCP("pymol")

client = PyMOLClient(
    host=os.environ.get("PYMOL_MCP_HOST", DEFAULT_HOST),
    port=_resolve_port(),
    timeout=float(os.environ.get("PYMOL_MCP_TIMEOUT", DEFAULT_TIMEOUT_SECONDS)),
)


def surface_pymol_error(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Re-raise `PyMOLError` as `ToolError` with the plugin's captured stdout
    and traceback folded into the message.

    FastMCP surfaces a tool's failure to the agent via `str(exception)` only,
    so the typed `traceback_text` and `stdout` attributes on `PyMOLError`
    would otherwise be dropped on the way out. The decorator's catch is the
    one place we can rewrite the message before that conversion happens.

    Decoration order matters: this decorator must sit INSIDE `@mcp.tool()`.
    Reversed, FastMCP registers the un-wrapped function and this layer
    silently does nothing.
    """

    @wraps(fn)
    def inner(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except PyMOLError as e:
            parts = [f"{e.error_type}: {e.message}"]
            if e.stdout.strip():
                parts.append(f"--- stdout ---\n{e.stdout.rstrip()}")
            if e.traceback_text.strip():
                parts.append(f"--- traceback ---\n{e.traceback_text.rstrip()}")
            raise ToolError("\n\n".join(parts)) from e

    return inner
