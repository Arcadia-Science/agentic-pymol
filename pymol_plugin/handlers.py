# pyright: reportMissingImports=false
"""
Op dispatch and per-op handlers.

Every request is gated on token validation in `dispatch`. Recognized ops are
`call`, `iterate`, `exec`, and `interrupt`. `cmd.interrupt()` is lock-free
and safe to call from a different thread than the one running PyMOL.
"""

from __future__ import annotations
import io
import logging
import re
import traceback
from contextlib import redirect_stdout
from typing import Any

from pymol_plugin.auth import token_ok
from pymol_plugin.serialize import serialize

ITERATE_ROW_LIMIT = 200_000
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*$")

logger = logging.getLogger("pymol-mcp-plugin")


def dispatch(request: dict[str, Any]) -> dict[str, Any]:
    if not token_ok(request.get("token")):
        return _error_response("Unauthorized", "missing or invalid auth token", "", "")
    op = request.get("op")
    if op == "call":
        return _handle_call(request)
    if op == "iterate":
        return _handle_iterate(request)
    if op == "exec":
        return _handle_exec(request)
    if op == "interrupt":
        return _handle_interrupt(request)
    return _error_response("BadRequest", f"unknown op: {op!r}", "", "")


def _handle_interrupt(request: dict[str, Any]) -> dict[str, Any]:
    from pymol import cmd

    logger.info("PyMOL MCP interrupt requested")
    cmd.interrupt()
    return {"ok": True, "value": None, "stdout": ""}


def _handle_call(request: dict[str, Any]) -> dict[str, Any]:
    fn_name = request.get("fn", "")
    args = request.get("args", []) or []
    kwargs = request.get("kwargs", {}) or {}
    if not isinstance(fn_name, str) or not fn_name:
        return _error_response("BadRequest", "fn must be a non-empty string", "", "")
    from pymol import cmd

    target: Any = cmd
    for part in fn_name.split("."):
        if not IDENTIFIER_RE.match(part):
            return _error_response("BadRequest", f"invalid attribute name: {part!r}", "", "")
        if not hasattr(target, part):
            return _error_response("AttributeError", f"cmd has no attribute {fn_name!r}", "", "")
        target = getattr(target, part)
    if not callable(target):
        return _error_response("TypeError", f"{fn_name!r} is not callable", "", "")
    logger.info(f"PyMOL MCP call: {fn_name}(args={args!r}, kwargs={kwargs!r})")
    return _run_capturing(lambda: target(*args, **kwargs))


def _handle_iterate(request: dict[str, Any]) -> dict[str, Any]:
    selection = request.get("selection", "")
    properties = request.get("properties", []) or []
    state = request.get("state")
    if not isinstance(selection, str):
        return _error_response("BadRequest", "selection must be a string", "", "")
    if not isinstance(properties, list) or not all(isinstance(p, str) for p in properties):
        return _error_response("BadRequest", "properties must be a list of strings", "", "")
    for p in properties:
        if not IDENTIFIER_RE.match(p):
            return _error_response("BadRequest", f"invalid property identifier: {p!r}", "", "")
    if not properties:
        return _error_response("BadRequest", "properties must not be empty", "", "")

    from pymol import cmd

    payload = "{" + ", ".join(f'"{p}": {p}' for p in properties) + "}"
    expression = (
        f"(_acc.append({payload}) if len(_acc) < {ITERATE_ROW_LIMIT} else _overflow.append(1))"
    )
    space: dict[str, Any] = {"_acc": [], "_overflow": []}

    def thunk():
        if state is None:
            return cmd.iterate(selection, expression, space=space)
        return cmd.iterate_state(int(state), selection, expression, space=space)

    logger.info(
        f"PyMOL MCP iterate: selection={selection!r}, properties={properties!r}, state={state!r}"
    )
    result = _run_capturing(thunk)
    if not result["ok"]:
        return result
    if space["_overflow"]:
        return _error_response(
            "IterateOverflow",
            f"iterate produced more than {ITERATE_ROW_LIMIT} rows; narrow the selection",
            "",
            result["stdout"],
        )
    return {
        "ok": True,
        "value": [serialize(row) for row in space["_acc"]],
        "stdout": result["stdout"],
    }


def _handle_exec(request: dict[str, Any]) -> dict[str, Any]:
    """
    Run arbitrary Python in the plugin's interpreter and (optionally) eval a
    return expression. Intentionally unsandboxed: callers can import anything,
    touch the filesystem, and make network calls. Gated only by the
    shared-secret token validated upstream in `dispatch`; the listening socket
    is bound to 127.0.0.1 so it is not reachable off-host without explicit
    forwarding.
    """
    code = request.get("code", "")
    return_expr = request.get("return_expr")
    if not isinstance(code, str):
        return _error_response("BadRequest", "code must be a string", "", "")
    if return_expr is not None and not isinstance(return_expr, str):
        return _error_response("BadRequest", "return_expr must be a string or null", "", "")
    import pymol
    from pymol import cmd

    from pymol_plugin.serialize import _maybe_numpy

    exec_globals: dict[str, Any] = {
        "cmd": cmd,
        "pymol": pymol,
        "__builtins__": __builtins__,
    }
    np = _maybe_numpy()
    if np is not None:
        exec_globals["np"] = np
    logger.info(f"PyMOL MCP exec ({len(code)} chars, return_expr={return_expr!r})")

    def thunk():
        exec(code, exec_globals)
        if return_expr is None:
            return None
        return eval(return_expr, exec_globals)

    return _run_capturing(thunk)


def _run_capturing(thunk) -> dict[str, Any]:
    buffer = io.StringIO()
    try:
        with redirect_stdout(buffer):
            value = thunk()
    except Exception as e:
        return _error_response(
            type(e).__name__,
            str(e),
            traceback.format_exc(),
            buffer.getvalue(),
        )
    return {
        "ok": True,
        "value": serialize(value),
        "stdout": buffer.getvalue(),
    }


def _error_response(error_type: str, message: str, tb: str, stdout: str) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {"type": error_type, "message": message, "traceback": tb},
        "stdout": stdout,
    }
