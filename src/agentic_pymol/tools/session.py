from __future__ import annotations

from agentic_pymol.app import client, mcp
from agentic_pymol.types import RunResult, Status


@mcp.tool()
def status() -> Status:
    """
    Return a snapshot of the PyMOL session.

    Useful as a connectivity probe: if this succeeds, the plugin is reachable.
    """
    objects = client.call("get_object_list", ["all"], {}, "status").value
    selections = client.call("get_names", ["selections"], {}, "status").value
    frame = client.call("get_frame", [], {}, "status").value
    state = client.call("get_state", [], {}, "status").value
    return Status(objects=objects, selections=selections, frame=frame, state=state)


@mcp.tool()
def do(command: str) -> str:
    """
    Run a PyMOL command-line string verbatim through `cmd.do(...)`.

    Use this for any PyMOL CLI command that doesn't have a dedicated tool, e.g.
    `show cartoon, chain A`, `color red, resi 50-60`, `bg_color white`.
    Returns whatever PyMOL printed to stdout. Note that `cmd.do` does NOT raise
    on PyMOL errors — failures appear as text in the returned string.
    """
    response = client.call("do", [command], {}, "do")
    return response.stdout


@mcp.tool()
def run(code: str, return_expr: str = "") -> RunResult:
    """
    Execute arbitrary Python in the PyMOL plugin's namespace.

    `cmd`, `pymol`, and (if available) `np` are pre-imported. If `return_expr`
    is non-empty, the plugin evaluates it after `exec` and returns its value
    serialized.

    Security: this is an unsandboxed Python `exec` inside the PyMOL process.
    Anything Python can do — open files, make network calls, import modules,
    shell out — is in scope. The only thing standing between this tool and
    full remote code execution on the host is the shared-secret auth token
    (`~/.config/pymol-mcp/token` or `PYMOL_MCP_TOKEN`). Treat that token like
    an SSH key: don't share it, don't commit it, and don't expose the plugin's
    TCP port beyond localhost.
    """
    return_expr_arg = return_expr if return_expr else None
    response = client.exec_code(code, return_expr_arg, "run")
    return RunResult(stdout=response.stdout, value=response.value)
